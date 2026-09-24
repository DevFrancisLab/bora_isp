from rest_framework import serializers

from apps.subscribers.models import Subscriber


class SubscriberSerializer(serializers.ModelSerializer):
    service_area_name = serializers.CharField(source="service_area.name", read_only=True)

    class Meta:
        model = Subscriber
        fields = [
            "id",
            "account_number",
            "full_name",
            "phone_number",
            "email",
            "address",
            "service_area",
            "service_area_name",
            "plan",
            "status",
            "connection_status",
            "installation_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
