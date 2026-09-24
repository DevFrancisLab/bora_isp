from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.incidents.demo import simulate_demo_outage
from apps.incidents.models import Incident
from apps.incidents.serializers import IncidentSerializer
from apps.incidents.services import acknowledge_incident, assign_technician, notify_customers, open_incident, resolve_incident


class IncidentViewSet(viewsets.ModelViewSet):
    serializer_class = IncidentSerializer
    queryset = Incident.objects.select_related("service_area", "assigned_technician").prefetch_related("reports", "affected")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for field in ("status", "severity", "incident_type"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        if params.get("service_area"):
            queryset = queryset.filter(service_area_id=params["service_area"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        incident = open_incident(
            service_area=data["service_area"],
            title=data["title"],
            description=data.get("description", ""),
            incident_type=data.get("incident_type", Incident.IncidentType.CONNECTIVITY),
            severity=data.get("severity", Incident.Severity.MAJOR),
            affected_subscriber_ids=data.get("affected_subscriber_ids"),
            started_at=data.get("started_at") or timezone.now(),
            status=data.get("status"),
        )
        return Response(self.get_serializer(incident).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="simulate")
    def simulate(self, request):
        result = simulate_demo_outage()
        incident = result["incident"]
        payload = {
            "created": result["created"],
            "detail": result["detail"],
            "incident": self.get_serializer(incident).data if incident is not None else None,
        }
        code = status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK
        return Response(payload, status=code)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        incident = acknowledge_incident(self.get_object())
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        incident = assign_technician(self.get_object(), request.data.get("technician_id"))
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def notify(self, request, pk=None):
        result = notify_customers(self.get_object(), request.data.get("channel"))
        return Response({**result, "incident": self.get_serializer(self.get_object()).data})

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        incident = resolve_incident(self.get_object())
        return Response(self.get_serializer(incident).data)
