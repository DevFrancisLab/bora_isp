from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.models import Activity, Technician
from apps.incidents.models import Incident, IncidentReport
from apps.messaging.models import Notification
from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase


class OutageWorkflowTests(APITestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani", status=ServiceArea.Status.OPERATIONAL)
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
        self.technician = Technician.objects.create(
            name="Brian Kamau",
            phone_number="+254711640228",
            email="brian.kamau@kijaninetworks.co.ke",
            service_area=self.area,
        )

    def _create_incident(self):
        response = self.client.post(
            reverse("incident-list"),
            {
                "title": "Kilimani Service Disruption",
                "description": "Loss of service at Kilimani POP.",
                "incident_type": Incident.IncidentType.CONNECTIVITY,
                "severity": Incident.Severity.CRITICAL,
                "service_area": self.area.id,
                "affected_subscriber_ids": [self.subscriber.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def test_support_case_creation(self):
        response = self.client.post(
            reverse("support-case-list"),
            {
                "subscriber": self.subscriber.id,
                "category": SupportCase.Category.INTERNET_DOWN,
                "subject": "Internet Down",
                "description": "No connection since morning.",
                "priority": SupportCase.Priority.HIGH,
                "source": SupportCase.Source.WHATSAPP,
                "service_area": self.area.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data["case_number"].startswith("CASE-"))
        self.assertEqual(SupportCase.objects.count(), 1)
        self.assertEqual(Incident.objects.count(), 0)

    def test_internet_down_links_to_matching_incident_only(self):
        incident = self._create_incident()
        linked = self.client.post(
            reverse("support-case-list"),
            {
                "subscriber": self.subscriber.id,
                "category": SupportCase.Category.INTERNET_DOWN,
                "subject": "Internet Down",
                "description": "No connection since morning.",
                "priority": SupportCase.Priority.HIGH,
                "source": SupportCase.Source.DASHBOARD,
                "service_area": self.area.id,
            },
            format="json",
        )
        self.assertEqual(linked.status_code, status.HTTP_201_CREATED, linked.data)
        self.assertEqual(Incident.objects.count(), 1)
        incident_row = Incident.objects.get(pk=incident["id"])
        self.assertEqual(incident_row.report_count, 1)
        self.assertEqual(incident_row.reports.count(), 1)
        self.assertEqual(incident_row.affected.count(), 1)

        other = ServiceArea.objects.create(name="Lavington")
        other_subscriber = Subscriber.objects.create(
            account_number="SUB-00512",
            full_name="Samuel Kariuki",
            phone_number="+254722100483",
            address="Lavington, Nairobi",
            service_area=other,
            plan="Business 50 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 4, 2),
        )
        unlinked = self.client.post(
            reverse("support-case-list"),
            {
                "subscriber": other_subscriber.id,
                "category": SupportCase.Category.INTERNET_DOWN,
                "subject": "Internet Down",
                "description": "Office link is down.",
                "priority": SupportCase.Priority.HIGH,
                "source": SupportCase.Source.DASHBOARD,
                "service_area": other.id,
            },
            format="json",
        )
        self.assertEqual(unlinked.status_code, status.HTTP_201_CREATED, unlinked.data)
        self.assertEqual(Incident.objects.count(), 1)
        self.assertFalse(Incident.objects.filter(service_area=other).exists())

    def test_incident_creation_sets_area_outage(self):
        payload = self._create_incident()
        self.area.refresh_from_db()
        self.subscriber.refresh_from_db()
        self.assertEqual(payload["affected_subscribers"], 1)
        self.assertEqual(self.area.status, ServiceArea.Status.OUTAGE)
        self.assertEqual(self.subscriber.connection_status, Subscriber.ConnectionStatus.OFFLINE)

    def test_acknowledge_assign_notify_and_resolve(self):
        incident_id = self._create_incident()["id"]
        acknowledge = self.client.post(reverse("incident-acknowledge", args=[incident_id]))
        self.assertEqual(acknowledge.status_code, status.HTTP_200_OK, acknowledge.data)
        self.assertEqual(acknowledge.data["status"], Incident.Status.ACKNOWLEDGED)
        self.assertIsNotNone(acknowledge.data["acknowledged_at"])

        assign = self.client.post(
            reverse("incident-assign", args=[incident_id]),
            {"technician_id": self.technician.id},
            format="json",
        )
        self.assertEqual(assign.status_code, status.HTTP_200_OK, assign.data)
        self.assertEqual(assign.data["assigned_technician"], self.technician.id)
        self.technician.refresh_from_db()
        self.assertEqual(self.technician.status, Technician.Status.BUSY)

        notify = self.client.post(
            reverse("incident-notify", args=[incident_id]),
            {"channel": Notification.Channel.WHATSAPP},
            format="json",
        )
        self.assertEqual(notify.status_code, status.HTTP_200_OK, notify.data)
        self.assertEqual(notify.data["queued"], 1)
        self.assertEqual(Notification.objects.filter(incident_id=incident_id, title__contains="service update").count(), 1)

        resolve = self.client.post(reverse("incident-resolve", args=[incident_id]))
        self.assertEqual(resolve.status_code, status.HTTP_200_OK, resolve.data)
        self.assertEqual(resolve.data["status"], Incident.Status.RESOLVED)
        self.assertIsNotNone(resolve.data["resolved_at"])
        self.area.refresh_from_db()
        self.subscriber.refresh_from_db()
        self.assertEqual(self.area.status, ServiceArea.Status.OPERATIONAL)
        self.assertEqual(self.subscriber.connection_status, Subscriber.ConnectionStatus.ONLINE)
        self.assertTrue(
            Notification.objects.filter(incident_id=incident_id, title__contains="service restored").exists()
        )

    def test_dashboard_summary_uses_database_counts(self):
        self._create_incident()
        self.client.post(
            reverse("support-case-list"),
            {
                "subscriber": self.subscriber.id,
                "category": SupportCase.Category.INTERNET_DOWN,
                "subject": "Internet Down",
                "description": "Still offline.",
                "priority": SupportCase.Priority.HIGH,
                "source": SupportCase.Source.WHATSAPP,
                "service_area": self.area.id,
            },
            format="json",
        )
        summary = self.client.get(reverse("dashboard-summary"))
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data["active_subscribers"], 1)
        self.assertEqual(summary.data["online_subscribers"], 0)
        self.assertEqual(summary.data["open_issues"], 1)
        self.assertEqual(summary.data["active_outages"], 1)
        self.assertEqual(len(summary.data["active_incidents"]), 1)
        self.assertEqual(summary.data["network_status"][0]["status"], ServiceArea.Status.OUTAGE)
        self.assertTrue(summary.data["recent_activity"])


class SimulateOutageTests(APITestCase):
    def setUp(self):
        self.busy = ServiceArea.objects.create(name="Kilimani", status=ServiceArea.Status.OPERATIONAL)
        self.area = ServiceArea.objects.create(name="Lavington", status=ServiceArea.Status.OPERATIONAL)
        self.south = ServiceArea.objects.create(name="South B", status=ServiceArea.Status.OPERATIONAL)
        self.subscriber = Subscriber.objects.create(
            account_number="SUB-00512",
            full_name="Samuel Kariuki",
            phone_number="+254722100483",
            address="Lavington, Nairobi",
            service_area=self.area,
            plan="Business 50 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 4, 2),
        )
        self.second = Subscriber.objects.create(
            account_number="SUB-00540",
            full_name="Ann Wairimu",
            phone_number="+254733221760",
            address="Lavington, Nairobi",
            service_area=self.area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 5, 2),
        )
        Subscriber.objects.create(
            account_number="SUB-00415",
            full_name="David Kipchoge",
            phone_number="+254720667331",
            address="South B, Nairobi",
            service_area=self.south,
            plan="Home 10 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 2, 2),
        )
        Incident.objects.create(
            incident_number="INC-104",
            title="Kilimani Service Disruption",
            incident_type=Incident.IncidentType.CONNECTIVITY,
            status=Incident.Status.INVESTIGATING,
            severity=Incident.Severity.CRITICAL,
            service_area=self.busy,
            started_at="2026-09-24T08:42:00Z",
        )
        self.technician = Technician.objects.create(
            name="Brian Kamau",
            phone_number="+254711640228",
            email="brian.kamau@kijaninetworks.co.ke",
            service_area=self.area,
        )

    def test_simulation_creates_area_reports_counts_and_activity(self):
        response = self.client.post(reverse("incident-simulate"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data["created"])
        incident = Incident.objects.get(pk=response.data["incident"]["id"])
        self.assertEqual(incident.service_area, self.south)
        self.assertEqual(incident.title, "South B Connectivity Outage")
        self.assertEqual(incident.incident_type, Incident.IncidentType.CONNECTIVITY)
        self.assertEqual(incident.status, Incident.Status.INVESTIGATING)
        self.assertEqual(incident.severity, Incident.Severity.MAJOR)
        self.assertEqual(incident.reports.count(), 1)
        self.assertEqual(incident.report_count, incident.reports.count())
        self.assertEqual(incident.affected_subscribers, incident.affected.count())
        self.assertEqual(incident.affected.count(), 1)
        report = incident.reports.get()
        self.assertEqual(report.support_case.source, SupportCase.Source.WHATSAPP)
        self.assertEqual(report.support_case.category, SupportCase.Category.INTERNET_DOWN)
        self.assertTrue(Activity.objects.filter(text="Simulated outage created in South B").exists())
        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.connection_status, Subscriber.ConnectionStatus.ONLINE)

    def test_simulation_does_not_duplicate_an_active_incident(self):
        first = self.client.post(reverse("incident-simulate"))
        second = self.client.post(reverse("incident-simulate"))
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        self.assertNotEqual(second.data["incident"]["id"], first.data["incident"]["id"])
        third = self.client.post(reverse("incident-simulate"))
        self.assertEqual(third.status_code, status.HTTP_200_OK, third.data)
        self.assertFalse(third.data["created"])
        self.assertEqual(
            Incident.objects.filter(status__in=[
                Incident.Status.INVESTIGATING,
                Incident.Status.ACKNOWLEDGED,
                Incident.Status.MONITORING,
            ]).count(),
            3,
        )
        incident = Incident.objects.get(pk=first.data["incident"]["id"])
        self.assertEqual(IncidentReport.objects.filter(incident=incident).count(), incident.report_count)

    def test_simulated_incident_uses_existing_workflow(self):
        created = self.client.post(reverse("incident-simulate"))
        incident_id = created.data["incident"]["id"]
        acknowledge = self.client.post(reverse("incident-acknowledge", args=[incident_id]))
        self.assertEqual(acknowledge.data["status"], Incident.Status.ACKNOWLEDGED)
        assign = self.client.post(
            reverse("incident-assign", args=[incident_id]),
            {"technician_id": self.technician.id},
            format="json",
        )
        self.assertEqual(assign.data["assigned_technician"], self.technician.id)
        notify = self.client.post(
            reverse("incident-notify", args=[incident_id]),
            {"channel": "WHATSAPP"},
            format="json",
        )
        self.assertEqual(notify.status_code, status.HTTP_200_OK, notify.data)
        self.assertGreater(notify.data["queued"], 0)
        resolve = self.client.post(reverse("incident-resolve", args=[incident_id]))
        self.assertEqual(resolve.data["status"], Incident.Status.RESOLVED)
