from django.contrib import admin

from apps.ai.models import AgentRun


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "decision", "provider", "reasoning_engine", "created_at")
    readonly_fields = ("created_at",)
