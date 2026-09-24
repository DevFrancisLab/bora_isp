from django.contrib import admin

from apps.messaging.models import Message, Notification


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "channel", "direction", "message_type", "status", "subscriber")
    list_filter = ("channel", "direction", "status", "message_type")
    search_fields = ("body", "subscriber__full_name", "subscriber__account_number")
    autocomplete_fields = ("subscriber",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "title", "channel", "status", "subscriber", "incident", "sent_at")
    list_filter = ("channel", "status")
    search_fields = ("title", "body", "subscriber__full_name", "incident__incident_number")
    autocomplete_fields = ("subscriber", "incident")
