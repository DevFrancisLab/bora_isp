from rest_framework import viewsets

from apps.support.models import SupportCase
from apps.support.serializers import SupportCaseSerializer
from apps.support.services import close_case_timestamp, create_support_case


class SupportCaseViewSet(viewsets.ModelViewSet):
    serializer_class = SupportCaseSerializer
    queryset = SupportCase.objects.select_related("subscriber", "service_area")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for field in ("status", "priority", "category", "source"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        if params.get("service_area"):
            queryset = queryset.filter(service_area_id=params["service_area"])
        if params.get("subscriber"):
            queryset = queryset.filter(subscriber_id=params["subscriber"])
        return queryset

    def perform_create(self, serializer):
        serializer.instance = create_support_case(serializer.validated_data)

    def perform_update(self, serializer):
        previous = serializer.instance.status
        case = serializer.save()
        close_case_timestamp(case, previous)
