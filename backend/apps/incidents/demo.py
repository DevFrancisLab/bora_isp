"""Hackathon Demo Mode only. Not a production outage API."""

from django.db import transaction

from apps.common.models import Activity
from apps.incidents.models import Incident
from apps.incidents.services import ACTIVE_INCIDENT_STATUSES, open_incident
from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase
from apps.support.services import create_support_case

PREFERRED_AREA_NAME = "South B"
DEMO_REPORT_LIMIT = 6


def _active_subscribers(area):
    return Subscriber.objects.filter(service_area=area, status=Subscriber.Status.ACTIVE).order_by("full_name")


def _active_incident(area):
    return (
        Incident.objects.filter(service_area=area, status__in=ACTIVE_INCIDENT_STATUSES)
        .order_by("-started_at")
        .first()
    )


def choose_demo_area():
    areas = list(ServiceArea.objects.order_by("name"))
    free = [area for area in areas if _active_incident(area) is None]
    if not free:
        return None
    preferred = next((area for area in free if area.name == PREFERRED_AREA_NAME and _active_subscribers(area).exists()), None)
    if preferred is not None:
        return preferred
    ranked = sorted(free, key=lambda area: (-_active_subscribers(area).count(), area.name))
    for area in ranked:
        if _active_subscribers(area).exists():
            return area
    return None


@transaction.atomic
def simulate_demo_outage():
    area = choose_demo_area()
    if area is None:
        existing = (
            Incident.objects.filter(status__in=ACTIVE_INCIDENT_STATUSES)
            .select_related("service_area", "assigned_technician")
            .order_by("-started_at")
            .first()
        )
        return {
            "created": False,
            "incident": existing,
            "detail": "Every service area already has an active incident.",
        }

    subscribers = list(_active_subscribers(area)[:DEMO_REPORT_LIMIT])
    incident = open_incident(
        service_area=area,
        title=f"{area.name} Connectivity Outage",
        description=(
            f"Demo mode opened a connectivity outage for {area.name}. "
            "Customers in the service area reported that internet service is down."
        ),
        incident_type=Incident.IncidentType.CONNECTIVITY,
        severity=Incident.Severity.MAJOR,
        status=Incident.Status.INVESTIGATING,
        affected_subscriber_ids=[item.id for item in subscribers],
    )
    for subscriber in subscribers:
        create_support_case(
            {
                "subscriber": subscriber,
                "service_area": area,
                "category": SupportCase.Category.INTERNET_DOWN,
                "subject": "Internet Down",
                "description": f"{subscriber.full_name} reported that internet service is down in {area.name}.",
                "priority": SupportCase.Priority.HIGH,
                "source": SupportCase.Source.WHATSAPP,
            }
        )
    Activity.objects.create(text=f"Simulated outage created in {area.name}")
    incident.refresh_from_db()
    return {
        "created": True,
        "incident": incident,
        "detail": f"Simulated outage created in {area.name}",
    }
