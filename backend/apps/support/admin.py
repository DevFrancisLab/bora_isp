from django.contrib import admin

from apps.support.models import SupportCase


@admin.register(SupportCase)
class SupportCaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_number",
        "subject",
        "subscriber",
        "service_area",
        "category",
        "status",
        "priority",
        "source",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "priority", "category", "source", "service_area")
    search_fields = ("case_number", "subject", "description", "subscriber__full_name", "subscriber__account_number")
    autocomplete_fields = ("subscriber", "service_area")
