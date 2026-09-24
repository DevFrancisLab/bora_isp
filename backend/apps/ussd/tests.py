from datetime import date

from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status

from apps.incidents.models import Incident
from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber
from apps.subscribers.phones import normalize_kenyan_phone
from apps.support.models import SupportCase


class UssdCallbackTests(TestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani", status=ServiceArea.Status.OPERATIONAL)
        self.quiet = ServiceArea.objects.create(name="Lavington", status=ServiceArea.Status.OPERATIONAL)
        self.subscriber = Subscriber.objects.create(
            account_number="SUB-00124",
            full_name="Mary Wanjiku",
            phone_number="+254712438221",
            address="Kilimani, Nairobi",
            service_area=self.area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 3, 12),
        )
        self.quiet_subscriber = Subscriber.objects.create(
            account_number="SUB-00512",
            full_name="Samuel Kariuki",
            phone_number="+254707274525",
            address="Lavington, Nairobi",
            service_area=self.quiet,
            plan="Business 50 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 4, 2),
        )
        self.incident = Incident.objects.create(
            incident_number="INC-104",
            title="Kilimani Service Disruption",
            incident_type=Incident.IncidentType.CONNECTIVITY,
            status=Incident.Status.INVESTIGATING,
            severity=Incident.Severity.CRITICAL,
            service_area=self.area,
            affected_subscribers=1,
            report_count=0,
            started_at="2026-09-24T08:42:00Z",
        )
        self.incident.affected.add(self.subscriber)

    def post_ussd(self, text, phone="+254712438221"):
        return self.client.post(
            reverse("ussd-callback"),
            {
                "sessionId": "12345",
                "serviceCode": "*384#",
                "phoneNumber": phone,
                "text": text,
            },
        )

    def test_get_is_rejected_and_post_is_csrf_exempt(self):
        self.assertEqual(self.client.get("/ussd").status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        client = Client(enforce_csrf_checks=True)
        response = client.post("/ussd", {"sessionId": "12345", "serviceCode": "*384#", "phoneNumber": "+254712438221", "text": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))

    def test_empty_text_and_problem_menu(self):
        empty = self.post_ussd("")
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertTrue(empty.content.decode().startswith("CON Welcome to ISPBora"))
        problem = self.post_ussd("1")
        self.assertTrue(problem.content.decode().startswith("CON Report Internet Problem"))

    def test_internet_down_links_known_subscriber_and_keeps_counts(self):
        before = Subscriber.objects.count()
        response = self.post_ussd("1*1", "0712438221")
        self.assertEqual(response.content.decode(), "END Your internet problem has been reported. ISPBora will keep you updated.")
        self.assertEqual(Subscriber.objects.count(), before)
        case = SupportCase.objects.get()
        self.assertEqual(case.category, SupportCase.Category.INTERNET_DOWN)
        self.assertEqual(case.source, SupportCase.Source.USSD)
        self.assertEqual(case.subscriber, self.subscriber)
        self.incident.refresh_from_db()
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(self.incident.report_count, self.incident.reports.count())
        self.assertEqual(self.incident.affected_subscribers, self.incident.affected.count())
        self.assertEqual(self.incident.report_count, 1)

    def test_internet_down_without_incident_and_unknown_phone(self):
        response = self.post_ussd("1*1", "+254707274525")
        self.assertEqual(response.content.decode(), "END Your internet problem has been reported. ISPBora will keep you updated.")
        self.assertEqual(Incident.objects.filter(service_area=self.quiet).count(), 0)
        unknown = self.post_ussd("1*1", "+254700000000")
        self.assertEqual(unknown.content.decode(), "END We could not find your ISP account. Please contact support.")
        self.assertEqual(Subscriber.objects.count(), 2)
        self.assertEqual(SupportCase.objects.filter(subscriber=self.quiet_subscriber).count(), 1)

    def test_check_outage_does_not_create_a_case(self):
        active = self.post_ussd("2", "254712438221")
        quiet = self.post_ussd("2", "0707274525")
        self.assertEqual(active.content.decode(), "END There is a known service issue in your area. ISPBora is working on it. You will receive updates by SMS.")
        self.assertEqual(quiet.content.decode(), "END No known outage is currently reported in your area.")
        self.assertEqual(SupportCase.objects.count(), 0)
        self.assertEqual(Incident.objects.count(), 1)

    def test_support_and_invalid_choices(self):
        self.assertEqual(self.post_ussd("3").content.decode(), "END Your support request has been received. The ISP team will assist you shortly.")
        self.assertTrue(self.post_ussd("1*3").content.decode().startswith("END Please contact ISPBora support"))
        self.assertEqual(self.post_ussd("9").content.decode(), "END Invalid choice. Please try again.")
        self.assertEqual(SupportCase.objects.count(), 0)
        self.assertEqual(Incident.objects.count(), 1)

    def test_kenyan_phone_formats(self):
        self.assertEqual(normalize_kenyan_phone("0712438221"), "+254712438221")
        self.assertEqual(normalize_kenyan_phone("0112438221"), "+254112438221")
        self.assertEqual(normalize_kenyan_phone("254712438221"), "+254712438221")
        self.assertEqual(normalize_kenyan_phone("+254712438221"), "+254712438221")
        for phone in ("0712438221", "254712438221", "+254712438221"):
            response = self.post_ussd("1*2", phone)
            self.assertEqual(response.content.decode(), "END Your slow internet problem has been reported. ISPBora will keep you updated.")
        self.assertEqual(SupportCase.objects.filter(category=SupportCase.Category.SLOW_INTERNET, subscriber=self.subscriber).count(), 3)
        self.assertFalse(SupportCase.objects.filter(category=SupportCase.Category.SLOW_INTERNET, incident_reports__isnull=False).exists())

    def test_samuel_phone_formats_resolve_and_report(self):
        for phone in ("+254707274525", "0707274525", "254707274525"):
            found = Subscriber.objects.get(phone_number="+254707274525")
            self.assertEqual(found.account_number, "SUB-00512")
            self.assertEqual(found.full_name, "Samuel Kariuki")
            down = self.post_ussd("1*1", phone)
            self.assertEqual(down.content.decode(), "END Your internet problem has been reported. ISPBora will keep you updated.")
        self.assertEqual(
            SupportCase.objects.filter(
                subscriber=self.quiet_subscriber,
                category=SupportCase.Category.INTERNET_DOWN,
                source=SupportCase.Source.USSD,
            ).count(),
            3,
        )
        slow = self.post_ussd("1*2", "0707274525")
        self.assertEqual(slow.content.decode(), "END Your slow internet problem has been reported. ISPBora will keep you updated.")
        self.assertTrue(
            SupportCase.objects.filter(
                subscriber=self.quiet_subscriber,
                category=SupportCase.Category.SLOW_INTERNET,
                source=SupportCase.Source.USSD,
            ).exists()
        )
        outage = self.post_ussd("2", "254707274525")
        self.assertEqual(outage.content.decode(), "END No known outage is currently reported in your area.")
        unknown = self.post_ussd("1*1", "+254700000001")
        self.assertEqual(unknown.content.decode(), "END We could not find your ISP account. Please contact support.")
