from django.urls import path

from apps.network.views import area_list, network_status, site_list

urlpatterns = [
    path("network/areas/", area_list, name="network-areas"),
    path("network/sites/", site_list, name="network-sites"),
    path("network/status/", network_status, name="network-status"),
]
