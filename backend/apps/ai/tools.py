import re
from contextvars import ContextVar

from django.db import transaction
from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError

from apps.common.models import Technician
from apps.incidents.models import Incident
from apps.network.models import ServiceArea
from apps.incidents.services import ACTIVE_INCIDENT_STATUSES, _send_sms_notices, assign_technician, outage_sms_body
from apps.messaging.africastalking_sms import _configured_credentials
from apps.subscribers.models import Subscriber
from apps.subscribers.phones import find_subscriber_by_phone, normalize_kenyan_phone
from apps.support.models import SupportCase
from apps.support.services import create_support_case as create_case_record

assistant_channel: ContextVar[str] = ContextVar("assistant_channel", default="dashboard")
assistant_message: ContextVar[str] = ContextVar("assistant_message", default="")

CLOSED_CASE_STATUSES = {SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED}
SEVERITY_RANK = {
    Incident.Severity.MINOR: 1,
    Incident.Severity.MAJOR: 2,
    Incident.Severity.CRITICAL: 3,
}
SUBSCRIBER_SAMPLE_LIMIT = 8
CHANNEL_SOURCES = {
    "dashboard": SupportCase.Source.DASHBOARD,
    "whatsapp": SupportCase.Source.WHATSAPP,
    "sms": SupportCase.Source.SMS,
    "ussd": SupportCase.Source.USSD,
    "voice": SupportCase.Source.VOICE,
}


def _action(action_type, label, status):
    return {"type": action_type, "label": label, "status": status}


def _subscriber_payload(subscriber):
    return {
        "id": subscriber.id,
        "account_number": subscriber.account_number,
        "name": subscriber.full_name,
        "phone": subscriber.phone_number,
        "plan": subscriber.plan,
        "status": subscriber.status,
        "connection_status": subscriber.connection_status,
        "service_area": subscriber.service_area.name,
        "service_area_status": subscriber.service_area.status,
    }


def _incident_payload(incident):
    return {
        "incident_number": incident.incident_number,
        "title": incident.title,
        "description": incident.description,
        "status": incident.status,
        "severity": incident.severity,
        "service_area": incident.service_area.name,
        "affected_subscriber_count": incident.affected_subscribers,
    }


def _case_payload(case):
    return {
        "case_number": case.case_number,
        "category": case.category,
        "subject": case.subject,
        "status": case.status,
        "priority": case.priority,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
    }


def _load_subscriber(subscriber_id):
    try:
        subscriber_id = int(subscriber_id)
    except (TypeError, ValueError):
        return None
    return Subscriber.objects.select_related("service_area").filter(pk=subscriber_id).first()


def find_subscriber(query):
    text = (query or "").strip()
    if not text:
        return {
            "status": "failed",
            "error": "A phone number, account number, or name is required.",
            "matches": [],
            "actions": [_action("subscriber_lookup", "Subscriber lookup needs a name, phone, or account", "failed")],
        }
    if normalize_kenyan_phone(text):
        found = find_subscriber_by_phone(text)
        matches = [found] if found else []
    else:
        account_matches = Subscriber.objects.select_related("service_area").filter(account_number__iexact=text)
        if account_matches.exists():
            matches = list(account_matches[:6])
        else:
            matches = list(Subscriber.objects.select_related("service_area").filter(full_name__icontains=text)[:6])
    if not matches:
        return {
            "status": "failed",
            "error": "No subscriber matched that phone number, account, or name.",
            "matches": [],
            "actions": [_action("subscriber_lookup", "Subscriber not found", "failed")],
        }
    if len(matches) > 1:
        return {
            "status": "success",
            "ambiguous": True,
            "matches": [_subscriber_payload(item) for item in matches],
            "actions": [_action("subscriber_lookup", "Several subscribers match", "success")],
        }
    return {
        "status": "success",
        "ambiguous": False,
        "subscriber": _subscriber_payload(matches[0]),
        "actions": [_action("subscriber_lookup", "Subscriber found", "success")],
    }


def _active_incidents_for(subscriber):
    return list(
        Incident.objects.select_related("service_area")
        .filter(service_area=subscriber.service_area, status__in=ACTIVE_INCIDENT_STATUSES)
        .order_by("-started_at")[:10]
    )


def _open_cases_for(subscriber):
    return list(
        SupportCase.objects.filter(subscriber=subscriber)
        .exclude(status__in=CLOSED_CASE_STATUSES)
        .order_by("-created_at")[:10]
    )


def get_subscriber_context(subscriber_id):
    subscriber = _load_subscriber(subscriber_id)
    if subscriber is None:
        return {
            "status": "failed",
            "error": "Subscriber not found.",
            "actions": [_action("subscriber_lookup", "Subscriber not found", "failed")],
        }
    incidents = _active_incidents_for(subscriber)
    cases = _open_cases_for(subscriber)
    return {
        "status": "success",
        "subscriber": _subscriber_payload(subscriber),
        "service_area": {"name": subscriber.service_area.name, "status": subscriber.service_area.status},
        "active_incidents": [_incident_payload(item) for item in incidents],
        "open_support_cases": [_case_payload(item) for item in cases],
        "actions": [
            _action("subscriber_lookup", "Subscriber found", "success"),
            _action("service_area_lookup", "Checked service area", "success"),
            _action("incident_lookup", "Checked active incidents", "success"),
            _action("support_case_lookup", "Checked open support cases", "success"),
        ],
    }


def check_active_incidents(subscriber_id=None):
    if subscriber_id in (None, "", 0, "0"):
        incidents = list(
            Incident.objects.select_related("service_area")
            .filter(status__in=ACTIVE_INCIDENT_STATUSES)
            .order_by("-started_at")[:10]
        )
        return {
            "status": "success",
            "active_incidents": [_incident_payload(item) for item in incidents],
            "actions": [_action("incident_lookup", "Checked active incidents", "success")],
        }
    subscriber = _load_subscriber(subscriber_id)
    if subscriber is None:
        return {
            "status": "failed",
            "error": "Subscriber not found.",
            "actions": [_action("incident_lookup", "Subscriber not found", "failed")],
        }
    incidents = _active_incidents_for(subscriber)
    return {
        "status": "success",
        "subscriber_id": subscriber.id,
        "service_area": subscriber.service_area.name,
        "active_incidents": [_incident_payload(item) for item in incidents],
        "actions": [_action("incident_lookup", "Checked active incidents", "success")],
    }


def get_open_support_cases(subscriber_id):
    subscriber = _load_subscriber(subscriber_id)
    if subscriber is None:
        return {
            "status": "failed",
            "error": "Subscriber not found.",
            "actions": [_action("support_case_lookup", "Subscriber not found", "failed")],
        }
    cases = _open_cases_for(subscriber)
    return {
        "status": "success",
        "subscriber_id": subscriber.id,
        "open_support_cases": [_case_payload(item) for item in cases],
        "actions": [_action("support_case_lookup", "Checked open support cases", "success")],
    }


def create_support_case(subscriber_id, category, subject, description, priority=""):
    subscriber = _load_subscriber(subscriber_id)
    if subscriber is None:
        return {
            "status": "failed",
            "error": "Subscriber not found.",
            "actions": [_action("support_case_created", "Subscriber not found", "failed")],
        }
    category = (category or "").strip().upper()
    if category not in SupportCase.Category.values:
        return {
            "status": "failed",
            "error": "Unsupported support case category.",
            "actions": [_action("support_case_created", "Support case was not created", "failed")],
        }
    subject = re.sub(r"\s+", " ", (subject or "").strip())[:160]
    description = (description or "").strip()[:2000]
    if not subject:
        return {
            "status": "failed",
            "error": "A subject is required.",
            "actions": [_action("support_case_created", "Support case was not created", "failed")],
        }
    priority = (priority or "").strip().upper()
    if not priority:
        priority = SupportCase.Priority.HIGH if category == SupportCase.Category.INTERNET_DOWN else SupportCase.Priority.MEDIUM
    if priority not in SupportCase.Priority.values:
        return {
            "status": "failed",
            "error": "Unsupported priority.",
            "actions": [_action("support_case_created", "Support case was not created", "failed")],
        }
    existing = (
        SupportCase.objects.filter(subscriber=subscriber, category=category)
        .exclude(status__in=CLOSED_CASE_STATUSES)
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return {
            "status": "success",
            "duplicate": True,
            "case_number": existing.case_number,
            "case_status": existing.status,
            "actions": [_action("support_case_lookup", f"Open case {existing.case_number} already exists", "success")],
        }
    source = CHANNEL_SOURCES.get(assistant_channel.get(), SupportCase.Source.DASHBOARD)
    case = create_case_record(
        {
            "subscriber": subscriber,
            "service_area": subscriber.service_area,
            "category": category,
            "subject": subject,
            "description": description,
            "priority": priority,
            "source": source,
        }
    )
    return {
        "status": "success",
        "duplicate": False,
        "case_number": case.case_number,
        "case_status": case.status,
        "category": case.category,
        "actions": [_action("support_case_created", f"Support case {case.case_number} created", "success")],
    }


def _mask_phone(phone):
    digits = "".join(character for character in (phone or "") if character.isdigit())
    if len(digits) < 4:
        return "the subscriber"
    return f"{digits[:4]}{'•' * max(len(digits) - 4, 4)}"


def notify_customer(subscriber_id):
    subscriber = _load_subscriber(subscriber_id)
    if subscriber is None:
        return {
            "status": "failed",
            "error": "Subscriber not found.",
            "actions": [_action("customer_notification", "Subscriber not found", "failed")],
        }
    incident = (
        Incident.objects.filter(service_area=subscriber.service_area, status__in=ACTIVE_INCIDENT_STATUSES)
        .order_by("-started_at")
        .first()
    )
    if incident is None:
        return {
            "status": "unavailable",
            "delivery": "no_outage",
            "error": "No active incident is recorded for this service area.",
            "actions": [_action("customer_notification", "No active outage to notify about", "unavailable")],
        }
    title = f"{incident.incident_number} service update"
    try:
        counts = _send_sms_notices(incident, [subscriber], title, outage_sms_body(incident), "OUTAGE")
    except Exception:
        return {
            "status": "failed",
            "delivery": "failed",
            "error": "The notification could not be sent.",
            "actions": [_action("customer_notification", "SMS notification failed", "failed")],
        }
    masked = _mask_phone(subscriber.phone_number)
    if counts["sent"]:
        return {
            "status": "success",
            "delivery": "sent",
            "incident_number": incident.incident_number,
            "actions": [_action("customer_notification", f"SMS sent to {masked}", "success")],
        }
    if counts["skipped"] and not counts["failed"]:
        return {
            "status": "success",
            "delivery": "already_sent",
            "incident_number": incident.incident_number,
            "actions": [_action("customer_notification", f"SMS already sent to {masked}", "success")],
        }
    if _configured_credentials() is None:
        return {
            "status": "unavailable",
            "delivery": "not_configured",
            "incident_number": incident.incident_number,
            "error": "SMS delivery is not currently configured.",
            "actions": [_action("customer_notification", "SMS delivery is not configured", "unavailable")],
        }
    return {
        "status": "failed",
        "delivery": "failed",
        "incident_number": incident.incident_number,
        "error": "SMS notification failed.",
        "actions": [_action("customer_notification", "SMS notification failed", "failed")],
    }


def _active_incident_queryset():
    return (
        Incident.objects.select_related("service_area", "assigned_technician")
        .filter(status__in=ACTIVE_INCIDENT_STATUSES)
        .annotate(live_affected_count=Count("affected", distinct=True))
    )


def _summary_payload(incident):
    technician = incident.assigned_technician
    count = getattr(incident, "live_affected_count", None)
    if count is None:
        count = incident.affected.count()
    return {
        "incident_number": incident.incident_number,
        "title": incident.title,
        "description": incident.description,
        "status": incident.status,
        "severity": incident.severity,
        "service_area": incident.service_area.name,
        "affected_subscriber_count": count,
        "started_at": incident.started_at.isoformat(),
        "assigned_technician": technician.name if technician else None,
    }


def _highest_severity(incidents):
    if not incidents:
        return None, []
    top = max(SEVERITY_RANK.get(item.severity, 0) for item in incidents)
    names = [name for name, rank in SEVERITY_RANK.items() if rank == top]
    return (names[0] if names else None), [
        item for item in incidents if SEVERITY_RANK.get(item.severity, 0) == top
    ]


def get_active_incident_summary():
    incidents = list(_active_incident_queryset().order_by("-started_at"))
    highest, top_incidents = _highest_severity(incidents)
    actions = [_action("incident_summary", "Checked active incidents", "success")]
    if top_incidents:
        actions.append(_action("incident_summary", "Found highest-severity incident", "success"))
    return {
        "status": "success",
        "active_incident_count": len(incidents),
        "highest_severity": highest,
        "highest_severity_incidents": [_summary_payload(item) for item in top_incidents],
        "incidents": [_summary_payload(item) for item in incidents],
        "actions": actions,
    }


def get_area_incidents(service_area):
    name = (service_area or "").strip()
    area = None
    if name:
        from apps.network.models import ServiceArea

        area = ServiceArea.objects.filter(name__iexact=name).first()
    if area is None:
        return {
            "status": "failed",
            "service_area": name,
            "active_incident_count": 0,
            "incidents": [],
            "error": "Service area not found.",
            "actions": [_action("area_incidents", "Service area not found", "failed")],
        }
    incidents = list(_active_incident_queryset().filter(service_area=area).order_by("-started_at"))
    return {
        "status": "success",
        "service_area": area.name,
        "active_incident_count": len(incidents),
        "incidents": [_summary_payload(item) for item in incidents],
        "actions": [_action("area_incidents", f"Checked {area.name} incidents", "success")],
    }


def _load_incident(incident_number):
    text = (incident_number or "").strip()
    if not text:
        return None
    return (
        _active_incident_queryset().filter(incident_number__iexact=text).first()
        or Incident.objects.select_related("service_area", "assigned_technician")
        .annotate(live_affected_count=Count("affected", distinct=True))
        .filter(incident_number__iexact=text)
        .first()
    )


def get_affected_subscribers(incident_number):
    incident = _load_incident(incident_number)
    if incident is None:
        return {
            "status": "failed",
            "error": "Incident not found.",
            "subscribers": [],
            "affected_subscriber_count": 0,
            "actions": [_action("affected_subscribers", "Incident not found", "failed")],
        }
    subscribers = list(incident.affected.select_related("service_area").order_by("full_name"))
    sample = subscribers[:SUBSCRIBER_SAMPLE_LIMIT]
    count = len(subscribers)
    return {
        "status": "success",
        "incident_number": incident.incident_number,
        "severity": incident.severity,
        "service_area": incident.service_area.name,
        "affected_subscriber_count": count,
        "sample_limited": count > len(sample),
        "subscribers": [
            {
                "id": item.id,
                "account_number": item.account_number,
                "name": item.full_name,
                "phone": item.phone_number,
                "connection_status": item.connection_status,
                "service_area": item.service_area.name,
            }
            for item in sample
        ],
        "actions": [_action("affected_subscribers", f"Found {count} affected subscribers", "success")],
    }


def get_support_case_summary():
    open_cases = SupportCase.objects.exclude(status__in=CLOSED_CASE_STATUSES)
    by_priority = {value: open_cases.filter(priority=value).count() for value, _label in SupportCase.Priority.choices}
    by_category = {value: open_cases.filter(category=value).count() for value, _label in SupportCase.Category.choices}
    highlighted = list(
        open_cases.filter(priority__in=[SupportCase.Priority.CRITICAL, SupportCase.Priority.HIGH]).order_by("-created_at")[:5]
    )
    return {
        "status": "success",
        "total_open_cases": open_cases.count(),
        "by_priority": by_priority,
        "by_category": by_category,
        "high_priority_cases": [_case_payload(item) for item in highlighted],
        "actions": [_action("support_summary", "Checked open support cases", "success")],
    }


def get_incident_impact_summary():
    incidents = list(_active_incident_queryset())
    if not incidents:
        return {
            "status": "success",
            "highest_impact_count": 0,
            "highest_impact_incident": None,
            "highest_impact_incidents": [],
            "actions": [_action("incident_impact", "Checked which incident affects the most subscribers", "success")],
        }
    top = max(item.live_affected_count for item in incidents)
    leaders = [item for item in incidents if item.live_affected_count == top]
    payloads = [_summary_payload(item) for item in leaders]
    return {
        "status": "success",
        "highest_impact_count": top,
        "highest_impact_incident": payloads[0] if len(payloads) == 1 else None,
        "highest_impact_incidents": payloads,
        "actions": [_action("incident_impact", "Checked which incident affects the most subscribers", "success")],
    }


def _technician_queryset():
    return Technician.objects.select_related("service_area").annotate(
        active_incident_count=Count(
            "incidents",
            filter=Q(incidents__status__in=ACTIVE_INCIDENT_STATUSES),
            distinct=True,
        )
    )


def _technician_payload(technician, incident_area_id=None):
    return {
        "id": technician.id,
        "name": technician.name,
        "phone": technician.phone_number,
        "email": technician.email,
        "status": technician.status,
        "service_area": technician.service_area.name,
        "active_incident_count": technician.active_incident_count,
        "matches_incident_area": incident_area_id is not None and technician.service_area_id == incident_area_id,
    }


def _status_counts(queryset):
    counts = {value: 0 for value, _label in Technician.Status.choices}
    for status in queryset.values_list("status", flat=True):
        counts[status] = counts.get(status, 0) + 1
    return counts


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _reassignment_requested(reassign):
    text = assistant_message.get()
    if text:
        return bool(re.search(r"\bre-?assign", text, re.IGNORECASE))
    return _as_bool(reassign)


def find_available_technicians(service_area="", incident_number="", name=""):
    area = None
    area_name = (service_area or "").strip()
    if area_name:
        area = ServiceArea.objects.filter(name__iexact=area_name).first()
        if area is None:
            return {
                "status": "failed",
                "available": False,
                "technicians": [],
                "reason": "Service area not found.",
                "actions": [_action("technician_lookup", "Service area not found", "failed")],
            }
    number = (incident_number or "").strip()
    incident = _load_incident(number) if number else None
    if number and incident is None:
        return {
            "status": "failed",
            "available": False,
            "technicians": [],
            "reason": "Incident not found.",
            "actions": [_action("technician_lookup", "Incident not found", "failed")],
        }
    incident_area_id = incident.service_area_id if incident else None
    queryset = _technician_queryset()
    if area is not None:
        queryset = queryset.filter(service_area=area)
    counts = _status_counts(queryset)
    name_text = (name or "").strip()
    people = queryset.order_by("name")
    matches = list(people.filter(name__icontains=name_text)) if name_text else None
    available = [item for item in (matches if matches is not None else people) if item.status == Technician.Status.AVAILABLE]
    available.sort(key=lambda item: (0 if incident_area_id and item.service_area_id == incident_area_id else 1, item.name))
    actions = [_action("technician_lookup", "Checked technician availability", "success")]
    if available:
        noun = "technician" if len(available) == 1 else "technicians"
        actions.append(_action("technician_found", f"Found {len(available)} available {noun}", "success"))
    else:
        actions.append(_action("technician_lookup", "No technicians currently available", "unavailable"))
    result = {
        "status": "success",
        "available": bool(available),
        "technicians": [_technician_payload(item, incident_area_id) for item in available],
        "status_counts": counts,
        "reason": None if available else "No technicians are currently available.",
        "actions": actions,
    }
    if matches is not None:
        result["matches"] = [_technician_payload(item, incident_area_id) for item in matches]
    return result


def get_incident_assignment_context(incident_number):
    incident = _load_incident(incident_number)
    if incident is None:
        return {
            "status": "failed",
            "error": "Incident not found.",
            "actions": [_action("incident_assignment", "Incident not found", "failed")],
        }
    technician = incident.assigned_technician
    payload = _summary_payload(incident)
    payload["assigned_technician"] = None if technician is None else {"id": technician.id, "name": technician.name, "status": technician.status}
    return {
        "status": "success",
        "incident": payload,
        "actions": [_action("incident_assignment", f"Checked incident {incident.incident_number}", "success")],
    }


@transaction.atomic
def assign_incident_to_technician(incident_number, technician_id, reassign=False):
    reassign = _reassignment_requested(reassign)
    incident = Incident.objects.select_for_update().select_related("service_area", "assigned_technician").filter(incident_number__iexact=(incident_number or "").strip()).first()
    if incident is None:
        return {
            "success": False,
            "status": "failed",
            "reason": "Incident not found.",
            "actions": [_action("incident_assignment", "Incident not found", "failed")],
        }
    try:
        technician_id = int(technician_id)
    except (TypeError, ValueError):
        technician_id = None
    technician = Technician.objects.select_for_update().filter(pk=technician_id).first() if technician_id else None
    if technician is None:
        return {
            "success": False,
            "status": "failed",
            "reason": "Technician not found.",
            "actions": [_action("incident_assignment", "Technician not found", "failed")],
        }
    current = incident.assigned_technician
    if current is not None and current.id == technician.id:
        return {
            "success": False,
            "changed": False,
            "status": "success",
            "reason": f"{incident.incident_number} is already assigned to {current.name}.",
            "actions": [_action("incident_assignment", f"{incident.incident_number} is already assigned to {current.name}", "success")],
        }
    if current is not None and not reassign:
        return {
            "success": False,
            "changed": False,
            "status": "success",
            "reason": f"{incident.incident_number} is already assigned to {current.name}. The assignment was not changed.",
            "actions": [_action("incident_assignment", f"{incident.incident_number} is already assigned to {current.name}", "success")],
        }
    if technician.status != Technician.Status.AVAILABLE:
        return {
            "success": False,
            "changed": False,
            "status": "failed",
            "reason": "Technician is no longer available.",
            "actions": [_action("incident_assignment", "Incident assignment failed", "failed")],
        }
    previous_id = current.id if current else None
    try:
        assign_technician(incident, technician.id)
    except ValidationError:
        return {
            "success": False,
            "changed": False,
            "status": "failed",
            "reason": "This incident cannot be assigned.",
            "actions": [_action("incident_assignment", "Incident assignment failed", "failed")],
        }
    if previous_id and previous_id != technician.id:
        still_assigned = Incident.objects.filter(assigned_technician_id=previous_id, status__in=ACTIVE_INCIDENT_STATUSES).exists()
        if not still_assigned:
            Technician.objects.filter(pk=previous_id).update(status=Technician.Status.AVAILABLE)
    incident.refresh_from_db()
    return {
        "success": True,
        "changed": True,
        "status": "success",
        "incident_number": incident.incident_number,
        "technician_id": technician.id,
        "technician_name": technician.name,
        "actions": [_action("incident_assignment", f"{incident.incident_number} assigned to {technician.name}", "success")],
    }
