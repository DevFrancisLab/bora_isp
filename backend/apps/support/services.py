from django.db import transaction
from django.utils import timezone

from apps.common.models import Activity
from apps.support.models import SupportCase


def next_case_number():
    latest = SupportCase.objects.order_by("-id").first()
    number = 1000 + (latest.id if latest else 0) + 1
    while SupportCase.objects.filter(case_number=f"CASE-{number}").exists():
        number += 1
    return f"CASE-{number}"


@transaction.atomic
def create_support_case(validated_data):
    data = dict(validated_data)
    subscriber = data["subscriber"]
    data["service_area"] = data.get("service_area") or subscriber.service_area
    case = SupportCase.objects.create(case_number=next_case_number(), **data)
    Activity.objects.create(text=f"New support case created: {subscriber.full_name} reported {case.category}")
    from apps.incidents.services import link_case_to_open_incident

    link_case_to_open_incident(case)
    return case


def record_inbound_report(*, phone_number, category, subject, description, priority, source):
    from apps.subscribers.phones import find_subscriber_by_phone

    subscriber = find_subscriber_by_phone(phone_number)
    if subscriber is None:
        return None
    return create_support_case(
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


def close_case_timestamp(case, previous_status):
    if case.status in {SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED} and case.resolved_at is None:
        case.resolved_at = timezone.now()
        case.save(update_fields=["resolved_at", "updated_at"])
    elif previous_status in {SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED} and case.status not in {
        SupportCase.Status.RESOLVED,
        SupportCase.Status.CLOSED,
    }:
        case.resolved_at = None
        case.save(update_fields=["resolved_at", "updated_at"])
    return case
