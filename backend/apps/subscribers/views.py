from django.db.models import Q
from rest_framework import viewsets

from apps.subscribers.models import Subscriber
from apps.subscribers.serializers import SubscriberSerializer


class SubscriberViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriberSerializer
    queryset = Subscriber.objects.select_related("service_area")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        search = params.get("search")
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(account_number__icontains=search)
            )
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("service_area"):
            queryset = queryset.filter(service_area_id=params["service_area"])
        if params.get("connection_status"):
            queryset = queryset.filter(connection_status=params["connection_status"])
        return queryset

    def perform_create(self, serializer):
        subscriber = serializer.save()
        subscriber.service_area.refresh_subscriber_count()

    def perform_update(self, serializer):
        previous_area = serializer.instance.service_area
        subscriber = serializer.save()
        subscriber.service_area.refresh_subscriber_count()
        if previous_area.pk != subscriber.service_area_id:
            previous_area.refresh_subscriber_count()

    def perform_destroy(self, instance):
        area = instance.service_area
        instance.delete()
        area.refresh_subscriber_count()
