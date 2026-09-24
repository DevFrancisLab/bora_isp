from apps.incidents.models import Incident
from apps.incidents.services import ACTIVE_INCIDENT_STATUSES
from apps.subscribers.phones import find_subscriber_by_phone
from apps.support.models import SupportCase
from apps.support.services import record_inbound_report

UNKNOWN = "END We could not find your ISP account. Please contact support."
MENU = (
    "CON Welcome to ISPBora\n"
    "1. Report Internet Problem\n"
    "2. Check Outage\n"
    "3. Talk to Support"
)
PROBLEM_MENU = (
    "CON Report Internet Problem\n"
    "1. Internet Down\n"
    "2. Slow Internet\n"
    "3. Other Problem"
)
REPORTED = "END Your internet problem has been reported. ISPBora will keep you updated."
SLOW_REPORTED = "END Your slow internet problem has been reported. ISPBora will keep you updated."
KNOWN_OUTAGE = "END There is a known service issue in your area. ISPBora is working on it. You will receive updates by SMS."
NO_OUTAGE = "END No known outage is currently reported in your area."
SUPPORT = "END Your support request has been received. The ISP team will assist you shortly."


def _active_incident(subscriber):
    return (
        Incident.objects.filter(service_area=subscriber.service_area, status__in=ACTIVE_INCIDENT_STATUSES)
        .order_by("-started_at")
        .first()
    )


def handle_ussd(*, text, phone_number):
    choice = (text or "").strip()
    if choice == "":
        return MENU
    if choice == "1":
        return PROBLEM_MENU
    if choice == "1*1":
        case = record_inbound_report(
            phone_number=phone_number,
            category=SupportCase.Category.INTERNET_DOWN,
            subject="Internet Down",
            description="Customer reported that internet service is down via USSD.",
            priority=SupportCase.Priority.HIGH,
            source=SupportCase.Source.USSD,
        )
        if case is None:
            return UNKNOWN
        return REPORTED
    if choice == "1*2":
        case = record_inbound_report(
            phone_number=phone_number,
            category=SupportCase.Category.SLOW_INTERNET,
            subject="Slow Internet",
            description="Customer reported slow internet via USSD.",
            priority=SupportCase.Priority.MEDIUM,
            source=SupportCase.Source.USSD,
        )
        if case is None:
            return UNKNOWN
        return SLOW_REPORTED
    if choice == "1*3":
        return "END Please contact ISPBora support for assistance."
    if choice == "3":
        return SUPPORT
    if choice == "2":
        subscriber = find_subscriber_by_phone(phone_number)
        if subscriber is None:
            return UNKNOWN
        if _active_incident(subscriber) is None:
            return NO_OUTAGE
        return KNOWN_OUTAGE
    return "END Invalid choice. Please try again."
