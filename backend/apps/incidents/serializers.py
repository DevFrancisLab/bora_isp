from django.utils import timezone
from rest_framework import serializers

from apps.incidents.models import Incident, IncidentReport


class IncidentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentReport
        fields = ["id", "incident", "support_case", "subscriber", "service_area", "created_at"]
        read_only_fields = ["created_at"]


class IncidentSerializer(serializers.ModelSerializer):
    service_area_name = serializers.CharField(source="service_area.name", read_only=True)
    assigned_technician_name = serializers.CharField(source="assigned_technician.name", read_only=True)
    reports = IncidentReportSerializer(many=True, read_only=True)
    started_at = serializers.DateTimeField(required=False)
    affected_subscriber_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Incident
        fields = [
            "id",
            "incident_number",
            "title",
            "description",
            "incident_type",
            "status",
            "severity",
            "service_area",
            "service_area_name",
            "affected_subscribers",
            "report_count",
            "assigned_technician",
            "assigned_technician_name",
            "started_at",
            "acknowledged_at",
            "resolved_at",
            "created_at",
            "updated_at",
            "reports",
            "affected_subscriber_ids",
        ]
        read_only_fields = [
            "incident_number",
            "affected_subscribers",
            "report_count",
            "acknowledged_at",
            "resolved_at",
            "created_at",
            "updated_at",
            "assigned_technician",
        ]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("started_at"):
            attrs["started_at"] = timezone.now()
        return attrs
