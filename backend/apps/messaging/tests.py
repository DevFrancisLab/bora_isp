import os
from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.incidents.models import Incident
from apps.messaging.africastalking_sms import SmsResult, send_sms
from apps.messaging.models import Notification
from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber


class SmsServiceTests(TestCase):
    def test_invalid_number_does_not_call_provider(self):
        with patch("apps.messaging.africastalking_sms._provider_send") as provider:
            result = send_sms("12345", "ISPBora test")
        provider.assert_not_called()
        self.assertFalse(result.ok)
        self.assertNotIn("api_key", result.error.lower())

    def test_normalizes_kenyan_number_before_send(self):
        with patch.dict(os.environ, {"AFRICASTALKING_USERNAME": "sandbox", "AFRICASTALKING_API_KEY": "secret-value", "AFRICASTALKING_ENV": "sandbox"}):
            with patch("apps.messaging.africastalking_sms._provider_send", return_value={"SMSMessageData": {"Recipients": [{"status": "Success"}]}}) as provider:
                result = send_sms("0712438221", "ISPBora test")
        provider.assert_called_once()
        self.assertEqual(provider.call_args.args[2], "+254712438221")
        self.assertTrue(result.ok)
        self.assertNotIn("secret-value", result.error)

    def test_provider_failure_and_missing_credentials(self):
        with patch.dict(os.environ, {"AFRICASTALKING_USERNAME": "sandbox", "AFRICASTALKING_API_KEY": "secret-value", "AFRICASTALKING_ENV": "sandbox"}):
            with patch("apps.messaging.africastalking_sms._provider_send", side_effect=RuntimeError("secret-value leaked")):
                failed = send_sms("+254712438221", "ISPBora test")
        self.assertFalse(failed.ok)
        self.assertNotIn("secret-value", failed.error)
        with patch.dict(os.environ, {"AFRICASTALKING_USERNAME": "", "AFRICASTALKING_API_KEY": "", "AFRICASTALKING_ENV": "sandbox"}, clear=False):
            missing = send_sms("+254712438221", "ISPBora test")
        self.assertFalse(missing.ok)
        self.assertEqual(missing.error, "Africa's Talking SMS is not configured.")


@override_settings(DEBUG=True)
class IncidentSmsTests(APITestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani")
        self.first = self._subscriber("SUB-00001", "Mary Wanjiku", "+254712438221")
        self.second = self._subscriber("SUB-00002", "James Ochieng", "0722615904")
        self.incident = Incident.objects.create(
            incident_number="INC-201",
            title="Kilimani Service Disruption",
            status=Incident.Status.INVESTIGATING,
            severity=Incident.Severity.MAJOR,
            service_area=self.area,
            started_at="2026-09-24T08:00:00Z",
        )
        self.incident.affected.add(self.first, self.second)

    def _subscriber(self, account, name, phone):
        return Subscriber.objects.create(
            account_number=account,
            full_name=name,
            phone_number=phone,
            address="Kilimani, Nairobi",
            service_area=self.area,
            plan="Home 10 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.OFFLINE,
            installation_date=date(2024, 3, 12),
        )

    def test_notify_sms_reaches_provider_without_name_error(self):
        with patch.dict(os.environ, {"AFRICASTALKING_USERNAME": "sandbox", "AFRICASTALKING_API_KEY": "test-key", "AFRICASTALKING_ENV": "sandbox"}):
            with patch("apps.messaging.africastalking_sms._provider_send", return_value={"SMSMessageData": {"Recipients": [{"status": "Success"}]}}) as provider:
                response = self.client.post(reverse("incident-notify", args=[self.incident.id]), {"channel": "SMS"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["sent"], 2)
        self.assertEqual(response.data["failed"], 0)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(Notification.objects.filter(incident=self.incident, status=Notification.Status.SENT).count(), 2)

    def test_notify_sms_records_success_failure_and_skips_duplicates(self):
        results = [SmsResult(ok=True, phone_number="+254712438221"), SmsResult(ok=False, phone_number="+254722615904", error="nope")]
        with patch("apps.incidents.services.send_sms", side_effect=results) as send:
            response = self.client.post(reverse("incident-notify", args=[self.incident.id]), {"channel": "SMS"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["sent"], 1)
        self.assertEqual(response.data["failed"], 1)
        self.assertEqual(send.call_count, 2)
        notices = Notification.objects.filter(incident=self.incident, channel=Notification.Channel.SMS)
        self.assertEqual(notices.filter(status=Notification.Status.SENT).count(), 1)
        self.assertEqual(notices.filter(status=Notification.Status.FAILED).count(), 1)
        self.assertIn("Kilimani", notices.first().body)
        self.assertNotIn("INC-201", notices.first().body)
        with patch("apps.incidents.services.send_sms", return_value=SmsResult(ok=True)) as repeat:
            again = self.client.post(reverse("incident-notify", args=[self.incident.id]), {"channel": "SMS"}, format="json")
        self.assertEqual(again.data["skipped"], 1)
        self.assertEqual(again.data["sent"], 1)
        self.assertEqual(repeat.call_count, 1)
        self.assertEqual(notices.filter(status=Notification.Status.SENT).count(), 2)

    def test_resolve_sends_restoration_sms_and_survives_provider_failure(self):
        with patch("apps.incidents.services.send_sms", side_effect=RuntimeError("down")):
            response = self.client.post(reverse("incident-resolve", args=[self.incident.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], Incident.Status.RESOLVED)
        notices = Notification.objects.filter(incident=self.incident, title__contains="service restored")
        self.assertEqual(notices.count(), 2)
        self.assertTrue(all(item.status == Notification.Status.FAILED for item in notices))
        self.assertNotIn("INC-201", notices.first().body)
