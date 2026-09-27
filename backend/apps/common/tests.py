from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.models import Technician
from apps.incidents.models import Incident
from apps.network.models import ServiceArea


class TechnicianApiTests(APITestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Lavington")
        self.other = ServiceArea.objects.create(name="Kilimani")
        self.technician = Technician.objects.create(
            name="Peter Otieno",
            phone_number="+254701992145",
            email="peter@example.com",
            service_area=self.area,
            status=Technician.Status.AVAILABLE,
        )

    def test_list_returns_saved_technicians(self):
        response = self.client.get(reverse("technicians"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["name"], "Peter Otieno")
        self.assertEqual(response.data[0]["service_area_name"], "Lavington")

    def test_create_technician(self):
        response = self.client.post(
            reverse("technicians"),
            {
                "name": "Brian Kamau",
                "phone_number": "0711640228",
                "email": "brian@example.com",
                "service_area": self.other.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["phone_number"], "+254711640228")
        self.assertEqual(response.data["status"], Technician.Status.AVAILABLE)
        self.assertTrue(Technician.objects.filter(name="Brian Kamau").exists())

    def test_create_rejects_invalid_phone_and_missing_area(self):
        invalid = self.client.post(
            reverse("technicians"),
            {"name": "Brian Kamau", "phone_number": "123", "service_area": self.area.id},
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post(
            reverse("technicians"),
            {"name": "Brian Kamau", "phone_number": "0711640228", "service_area": 99999},
            format="json",
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_technician(self):
        response = self.client.delete(reverse("technician-detail", args=[self.technician.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Technician.objects.filter(pk=self.technician.id).exists())

    def test_delete_is_blocked_while_assigned_to_an_open_incident(self):
        Incident.objects.create(
            incident_number="INC-102",
            title="South link",
            status=Incident.Status.INVESTIGATING,
            severity=Incident.Severity.MAJOR,
            service_area=self.area,
            assigned_technician=self.technician,
            started_at=timezone.now(),
        )
        response = self.client.delete(reverse("technician-detail", args=[self.technician.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Technician.objects.filter(pk=self.technician.id).exists())

    def test_delete_missing_technician(self):
        response = self.client.delete(reverse("technician-detail", args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_phone_is_rejected(self):
        response = self.client.post(
            reverse("technicians"),
            {"name": "Peter Two", "phone_number": "0701992145", "service_area": self.area.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
