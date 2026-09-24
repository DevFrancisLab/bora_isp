from django.contrib import admin

from apps.network.models import NetworkSite, ServiceArea


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "subscriber_count", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "description")


@admin.register(NetworkSite)
class NetworkSiteAdmin(admin.ModelAdmin):
    list_display = ("name", "site_type", "status", "service_area", "latitude", "longitude")
    list_filter = ("site_type", "status", "service_area")
    search_fields = ("name", "description")
    autocomplete_fields = ("service_area",)
