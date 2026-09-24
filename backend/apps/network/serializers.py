from rest_framework import serializers

from apps.network.models import NetworkSite, ServiceArea


class ServiceAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceArea
        fields = [
            "id",
            "name",
            "status",
            "description",
            "subscriber_count",
            "geometry",
            "created_at",
            "updated_at",
        ]


class NetworkSiteSerializer(serializers.ModelSerializer):
    service_area_name = serializers.CharField(source="service_area.name", read_only=True)

    class Meta:
        model = NetworkSite
        fields = [
            "id",
            "name",
            "site_type",
            "status",
            "service_area",
            "service_area_name",
            "latitude",
            "longitude",
            "description",
            "created_at",
            "updated_at",
        ]
