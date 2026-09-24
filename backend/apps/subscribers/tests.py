from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber


class SubscriberApiTests(APITestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani", geometry=[])
        self.payload = {
            "account_number": "SUB-00124",
            "full_name": "Mary Wanjiku",
            "phone_number": "+254712438221",
            "email": "mary.wanjiku@example.com",
            "address": "Kilimani, Nairobi",
            "service_area": self.area.id,
            "plan": "Home 20 Mbps",
            "status": Subscriber.Status.ACTIVE,
            "connection_status": Subscriber.ConnectionStatus.OFFLINE,
            "installation_date": date(2024, 3, 12).isoformat(),
        }

    def test_create_and_retrieve_subscriber(self):
        created = self.client.post(reverse("subscriber-list"), self.payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        subscriber_id = created.data["id"]
        detail = self.client.get(reverse("subscriber-detail", args=[subscriber_id]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["full_name"], "Mary Wanjiku")
        self.assertEqual(detail.data["account_number"], "SUB-00124")
        self.area.refresh_from_db()
        self.assertEqual(self.area.subscriber_count, 1)

    def test_search_by_name_phone_and_account(self):
        self.client.post(reverse("subscriber-list"), self.payload, format="json")
        other = dict(self.payload, account_number="SUB-00999", full_name="James Ochieng", phone_number="+254722615904")
        self.client.post(reverse("subscriber-list"), other, format="json")

        by_name = self.client.get(reverse("subscriber-list"), {"search": "Wanjiku"})
        by_phone = self.client.get(reverse("subscriber-list"), {"search": "722615904"})
        by_account = self.client.get(reverse("subscriber-list"), {"search": "SUB-00124"})

        self.assertEqual([item["full_name"] for item in by_name.data["results"]], ["Mary Wanjiku"])
        self.assertEqual([item["full_name"] for item in by_phone.data["results"]], ["James Ochieng"])
        self.assertEqual([item["account_number"] for item in by_account.data["results"]], ["SUB-00124"])
