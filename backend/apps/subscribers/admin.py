from django.contrib import admin

from apps.subscribers.models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = (
        "account_number",
        "full_name",
        "phone_number",
        "service_area",
        "plan",
        "status",
        "connection_status",
    )
    list_filter = ("status", "connection_status", "service_area", "plan")
    search_fields = ("account_number", "full_name", "phone_number", "email", "address")
    autocomplete_fields = ("service_area",)
