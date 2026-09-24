from rest_framework import serializers

from apps.support.models import SupportCase


class SupportCaseSerializer(serializers.ModelSerializer):
    subscriber_name = serializers.CharField(source="subscriber.full_name", read_only=True)
    service_area_name = serializers.CharField(source="service_area.name", read_only=True)
    possible_outage = serializers.SerializerMethodField()

    class Meta:
        model = SupportCase
        fields = [
            "id",
            "case_number",
            "subscriber",
            "subscriber_name",
            "category",
            "subject",
            "description",
            "status",
            "priority",
            "source",
            "assigned_to",
            "service_area",
            "service_area_name",
            "possible_outage",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = ["case_number", "created_at", "updated_at", "resolved_at"]

    def get_possible_outage(self, case):
        from apps.incidents.models import Incident
        from apps.incidents.services import ACTIVE_INCIDENT_STATUSES, CONNECTIVITY_CATEGORIES

        if case.category not in CONNECTIVITY_CATEGORIES:
            return False
        has_incident = Incident.objects.filter(
            service_area=case.service_area,
            status__in=ACTIVE_INCIDENT_STATUSES,
        ).exists()
        if has_incident:
            return False
        clustered = SupportCase.objects.filter(
            service_area=case.service_area,
            category__in=CONNECTIVITY_CATEGORIES,
        ).exclude(status__in=[SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED]).count()
        return clustered >= 3

    def validate(self, attrs):
        subscriber = attrs.get("subscriber") or getattr(self.instance, "subscriber", None)
        service_area = attrs.get("service_area") or getattr(self.instance, "service_area", None)
        if subscriber and service_area and subscriber.service_area_id != service_area.id:
            raise serializers.ValidationError({"service_area": "Service area must match the subscriber."})
        return attrs
