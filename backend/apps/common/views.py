from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.common.models import Activity, Technician
from apps.common.serializers import TechnicianSerializer
from apps.incidents.models import Incident
from apps.incidents.serializers import IncidentSerializer
from apps.network.models import ServiceArea
from apps.network.serializers import ServiceAreaSerializer
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase
from apps.support.serializers import SupportCaseSerializer


@api_view(["GET", "POST"])
def technician_list(request):
    if request.method == "POST":
        serializer = TechnicianSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        technician = serializer.save()
        Activity.objects.create(text=f"Technician added · {technician.name}")
        return Response(TechnicianSerializer(technician).data, status=status.HTTP_201_CREATED)
    technicians = Technician.objects.select_related("service_area")
    return Response(TechnicianSerializer(technicians, many=True).data)


@api_view(["DELETE"])
def technician_detail(request, pk):
    technician = Technician.objects.filter(pk=pk).first()
    if technician is None:
        return Response({"detail": "Technician not found."}, status=status.HTTP_404_NOT_FOUND)
    open_incident = technician.incidents.exclude(status=Incident.Status.RESOLVED).exists()
    if open_incident:
        return Response(
            {"detail": "This technician is assigned to an open incident. Reassign that incident before deleting them."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    name = technician.name
    technician.delete()
    Activity.objects.create(text=f"Technician removed · {name}")
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def dashboard_summary(request):
    open_cases = SupportCase.objects.exclude(status__in=[SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED])
    active_incidents = Incident.objects.exclude(status=Incident.Status.RESOLVED).select_related(
        "service_area", "assigned_technician"
    )
    recent_cases = SupportCase.objects.select_related("subscriber", "service_area")[:8]
    return Response(
        {
            "active_subscribers": Subscriber.objects.filter(status=Subscriber.Status.ACTIVE).count(),
            "online_subscribers": Subscriber.objects.filter(
                status=Subscriber.Status.ACTIVE,
                connection_status=Subscriber.ConnectionStatus.ONLINE,
            ).count(),
            "open_issues": open_cases.count(),
            "active_outages": ServiceArea.objects.filter(status=ServiceArea.Status.OUTAGE).count(),
            "active_incidents": IncidentSerializer(active_incidents, many=True).data,
            "recent_support_cases": SupportCaseSerializer(recent_cases, many=True).data,
            "network_status": ServiceAreaSerializer(ServiceArea.objects.all(), many=True).data,
            "recent_activity": [
                {"id": item.id, "text": item.text, "created_at": item.created_at}
                for item in Activity.objects.all()[:12]
            ],
        }
    )
