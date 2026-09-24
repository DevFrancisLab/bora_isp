from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.common.models import Activity, Technician
from apps.incidents.models import Incident
from apps.incidents.serializers import IncidentSerializer
from apps.network.models import ServiceArea
from apps.network.serializers import ServiceAreaSerializer
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase
from apps.support.serializers import SupportCaseSerializer


@api_view(["GET"])
def technician_list(request):
    technicians = Technician.objects.select_related("service_area")
    return Response(
        [
            {
                "id": item.id,
                "name": item.name,
                "phone_number": item.phone_number,
                "email": item.email,
                "status": item.status,
                "service_area": item.service_area_id,
                "service_area_name": item.service_area.name,
            }
            for item in technicians
        ]
    )
from apps.incidents.serializers import IncidentSerializer
from apps.network.models import ServiceArea
from apps.network.serializers import ServiceAreaSerializer
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase
from apps.support.serializers import SupportCaseSerializer


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
