from django.contrib import admin

from apps.common.models import Activity, Technician


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "email", "status", "service_area", "created_at")
    list_filter = ("status", "service_area")
    search_fields = ("name", "phone_number", "email")
    autocomplete_fields = ("service_area",)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("text", "created_at")
    search_fields = ("text",)
