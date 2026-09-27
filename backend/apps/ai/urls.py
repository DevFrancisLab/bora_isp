from django.urls import path

from apps.ai.views import assistant_view

urlpatterns = [
    path("ai/assistant/", assistant_view, name="ai-assistant"),
]
