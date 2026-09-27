from rest_framework import serializers

from apps.common.models import Technician
from apps.subscribers.phones import normalize_kenyan_phone


class TechnicianSerializer(serializers.ModelSerializer):
    service_area_name = serializers.CharField(source="service_area.name", read_only=True)

    class Meta:
        model = Technician
        fields = [
            "id",
            "name",
            "phone_number",
            "email",
            "status",
            "service_area",
            "service_area_name",
        ]
        read_only_fields = ["id", "service_area_name"]

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Enter the technician's name.")
        return name

    def validate_phone_number(self, value):
        phone = normalize_kenyan_phone(value)
        if not phone:
            raise serializers.ValidationError("Enter a valid Kenyan phone number.")
        queryset = Technician.objects.filter(phone_number=phone)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A technician with this phone number already exists.")
        return phone
