from django.urls import path

from apps.ai.views import assistant_view, customer_workflow_view

urlpatterns = [
    path("ai/assistant/", assistant_view, name="ai-assistant"),
    path("ai/customer/", customer_workflow_view, name="ai-customer-workflow"),
]
