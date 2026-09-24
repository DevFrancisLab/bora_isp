from django.contrib import admin

from apps.incidents.models import Incident, IncidentReport


class IncidentReportInline(admin.TabularInline):
    model = IncidentReport
    extra = 0
    autocomplete_fields = ("support_case", "subscriber", "service_area")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "incident_number",
        "title",
        "service_area",
        "status",
        "severity",
        "affected_subscribers",
        "report_count",
        "assigned_technician",
        "started_at",
    )
    list_filter = ("status", "severity", "incident_type", "service_area")
    search_fields = ("incident_number", "title", "description")
    autocomplete_fields = ("service_area", "assigned_technician")
    filter_horizontal = ("affected",)
    inlines = [IncidentReportInline]


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ("incident", "support_case", "subscriber", "service_area", "created_at")
    list_filter = ("service_area",)
    search_fields = ("incident__incident_number", "subscriber__full_name", "support_case__case_number")
    autocomplete_fields = ("incident", "support_case", "subscriber", "service_area")
