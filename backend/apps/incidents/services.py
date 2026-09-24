from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common.models import Activity, Technician
from apps.incidents.models import Incident
from apps.messaging.africastalking_sms import send_sms
from apps.messaging.models import Message, Notification
from apps.network.models import ServiceArea
from apps.network.services import apply_area_status, restore_area_if_clear
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase

CONNECTIVITY_CATEGORIES = {
    SupportCase.Category.INTERNET_DOWN,
    SupportCase.Category.SLOW_INTERNET,
    SupportCase.Category.TECHNICAL,
}
ACTIVE_INCIDENT_STATUSES = [
    Incident.Status.INVESTIGATING,
    Incident.Status.ACKNOWLEDGED,
    Incident.Status.MONITORING,
]


def next_incident_number():
    latest = Incident.objects.order_by("-id").first()
    number = 100 + (latest.id if latest else 0) + 1
    while Incident.objects.filter(incident_number=f"INC-{number}").exists():
        number += 1
    return f"INC-{number}"


def sync_incident_metrics(incident):
    incident.affected_subscribers = incident.affected.count()
    incident.report_count = incident.reports.count()
    incident.save(update_fields=["affected_subscribers", "report_count", "updated_at"])
    return incident


def area_status_for_incident(incident):
    if incident.severity == Incident.Severity.CRITICAL:
        return ServiceArea.Status.OUTAGE
    if incident.status == Incident.Status.INVESTIGATING:
        return ServiceArea.Status.INVESTIGATING
    return ServiceArea.Status.DEGRADED


@transaction.atomic
def open_incident(*, service_area, title, description, incident_type, severity, affected_subscriber_ids=None, incident_number=None, started_at=None, status=None):
    incident = Incident.objects.create(
        incident_number=incident_number or next_incident_number(),
        title=title,
        description=description or "",
        incident_type=incident_type,
        severity=severity,
        status=status or Incident.Status.INVESTIGATING,
        service_area=service_area,
        started_at=started_at or timezone.now(),
    )
    if affected_subscriber_ids:
        subscribers = Subscriber.objects.filter(id__in=affected_subscriber_ids, service_area=service_area)
        incident.affected.set(subscribers)
        subscribers.filter(status=Subscriber.Status.ACTIVE).update(connection_status=Subscriber.ConnectionStatus.OFFLINE)
    sync_incident_metrics(incident)
    apply_area_status(service_area, area_status_for_incident(incident))
    Activity.objects.create(text=f"{incident.incident_number} opened in {service_area.name}")
    return incident


def _require_open(incident, action):
    if incident.status == Incident.Status.RESOLVED:
        raise ValidationError({"status": f"Resolved incidents cannot be {action}."})


@transaction.atomic
def acknowledge_incident(incident):
    _require_open(incident, "acknowledged")
    incident.status = Incident.Status.ACKNOWLEDGED
    incident.acknowledged_at = timezone.now()
    incident.save(update_fields=["status", "acknowledged_at", "updated_at"])
    Activity.objects.create(text=f"{incident.incident_number} acknowledged")
    return incident


@transaction.atomic
def assign_technician(incident, technician_id):
    _require_open(incident, "assigned")
    try:
        technician = Technician.objects.get(pk=technician_id)
    except Technician.DoesNotExist as exc:
        raise ValidationError({"technician_id": "Technician not found."}) from exc
    incident.assigned_technician = technician
    incident.save(update_fields=["assigned_technician", "updated_at"])
    technician.status = Technician.Status.BUSY
    technician.save(update_fields=["status"])
    Activity.objects.create(text=f"{incident.incident_number} assigned to {technician.name}")
    return incident


def outage_sms_body(incident):
    return (
        f"ISPBora: We are investigating an internet service issue affecting {incident.service_area.name}. "
        "Our team is working to restore service. We will update you when service is restored."
    )


def restoration_sms_body():
    return (
        "ISPBora: Your internet service issue has been resolved. "
        "Please reconnect and check your connection. If you are still offline, contact support."
    )


def _queue_notice(incident, subscriber, channel, title, body, message_type):
    Notification.objects.create(
        subscriber=subscriber,
        incident=incident,
        channel=channel,
        title=title,
        body=body,
        status=Notification.Status.PENDING,
    )
    Message.objects.create(
        subscriber=subscriber,
        channel=channel,
        direction=Message.Direction.OUTBOUND,
        message_type=message_type,
        body=body,
        status=Message.Status.PENDING,
    )


def _send_sms_notices(incident, subscribers, title, body, message_type):
    sent = failed = skipped = 0
    now = timezone.now()
    for subscriber in subscribers:
        already_sent = Notification.objects.filter(
            incident=incident,
            subscriber=subscriber,
            channel=Notification.Channel.SMS,
            title=title,
            status=Notification.Status.SENT,
        ).exists()
        if already_sent:
            skipped += 1
            continue
        notice = Notification.objects.create(
            subscriber=subscriber,
            incident=incident,
            channel=Notification.Channel.SMS,
            title=title,
            body=body,
            status=Notification.Status.PENDING,
        )
        message = Message.objects.create(
            subscriber=subscriber,
            channel=Notification.Channel.SMS,
            direction=Message.Direction.OUTBOUND,
            message_type=message_type,
            body=body,
            status=Message.Status.PENDING,
        )
        try:
            result = send_sms(subscriber.phone_number, body)
        except Exception:
            result = None
        if result is not None and result.ok:
            notice.status = Notification.Status.SENT
            notice.sent_at = now
            message.status = Message.Status.SENT
            sent += 1
        else:
            notice.status = Notification.Status.FAILED
            message.status = Message.Status.FAILED
            failed += 1
        notice.save(update_fields=["status", "sent_at"])
        message.save(update_fields=["status"])
    return {"queued": sent + failed, "sent": sent, "failed": failed, "skipped": skipped}


@transaction.atomic
def notify_customers(incident, channel):
    _require_open(incident, "notified")
    valid = {choice for choice, _label in Notification.Channel.choices}
    if channel not in valid:
        raise ValidationError({"channel": "Unsupported channel."})
    subscribers = list(incident.affected.all())
    title = f"{incident.incident_number} service update"
    if channel == Notification.Channel.SMS:
        counts = _send_sms_notices(incident, subscribers, title, outage_sms_body(incident), "OUTAGE")
        Activity.objects.create(
            text=(
                f"{incident.incident_number} SMS update sent={counts['sent']} "
                f"failed={counts['failed']} skipped={counts['skipped']}"
            )
        )
        return counts
    body = (
        f"Kijani Networks: {incident.title} is affecting {incident.service_area.name}. "
        "Our team is working on it."
    )
    for subscriber in subscribers:
        _queue_notice(incident, subscriber, channel, title, body, "OUTAGE")
    Activity.objects.create(
        text=f"{incident.incident_number} notice queued for {len(subscribers)} subscribers on {channel}"
    )
    return {"queued": len(subscribers), "sent": 0, "failed": 0, "skipped": 0}


@transaction.atomic
def resolve_incident(incident):
    _require_open(incident, "resolved")
    now = timezone.now()
    incident.status = Incident.Status.RESOLVED
    incident.resolved_at = now
    incident.save(update_fields=["status", "resolved_at", "updated_at"])
    if incident.assigned_technician_id:
        Technician.objects.filter(pk=incident.assigned_technician_id).update(status=Technician.Status.AVAILABLE)
    affected = list(incident.affected.all())
    Subscriber.objects.filter(pk__in=[item.pk for item in affected], status=Subscriber.Status.ACTIVE).update(
        connection_status=Subscriber.ConnectionStatus.ONLINE
    )
    linked_cases = SupportCase.objects.filter(incident_reports__incident=incident).exclude(
        status__in=[SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED]
    )
    linked_cases.update(status=SupportCase.Status.RESOLVED, resolved_at=now)
    title = f"{incident.incident_number} service restored"
    counts = _send_sms_notices(incident, affected, title, restoration_sms_body(), "RESTORATION")
    restore_area_if_clear(incident.service_area)
    Activity.objects.create(
        text=(
            f"{incident.incident_number} resolved. Restoration SMS sent={counts['sent']} "
            f"failed={counts['failed']} skipped={counts['skipped']}."
        )
    )
    return incident


def link_case_to_open_incident(case):
    if case.category != SupportCase.Category.INTERNET_DOWN:
        return None
    incident = (
        Incident.objects.filter(service_area=case.service_area, status__in=ACTIVE_INCIDENT_STATUSES)
        .order_by("-started_at")
        .first()
    )
    if incident is None:
        return None
    from apps.incidents.models import IncidentReport

    report, created = IncidentReport.objects.get_or_create(
        incident=incident,
        support_case=case,
        defaults={
            "subscriber": case.subscriber,
            "service_area": case.service_area,
        },
    )
    if created:
        incident.affected.add(case.subscriber)
        sync_incident_metrics(incident)
        Activity.objects.create(text=f"{case.case_number} linked to {incident.incident_number}")
    return report
