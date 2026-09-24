from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.incidents.models import Incident
from apps.network.models import NetworkSite, ServiceArea
from apps.network.serializers import NetworkSiteSerializer, ServiceAreaSerializer


@api_view(["GET"])
def area_list(request):
    areas = ServiceArea.objects.all()
    return Response(ServiceAreaSerializer(areas, many=True).data)


@api_view(["GET"])
def site_list(request):
    sites = NetworkSite.objects.select_related("service_area")
    return Response(NetworkSiteSerializer(sites, many=True).data)


@api_view(["GET"])
def network_status(request):
    areas = ServiceArea.objects.all()
    sites = NetworkSite.objects.select_related("service_area")
    return Response(
        {
            "areas": ServiceAreaSerializer(areas, many=True).data,
            "sites": NetworkSiteSerializer(sites, many=True).data,
            "active_incidents": Incident.objects.exclude(status=Incident.Status.RESOLVED).count(),
        }
    )
