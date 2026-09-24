from django.urls import path

from apps.common.views import dashboard_summary, technician_list

urlpatterns = [
    path("dashboard/summary/", dashboard_summary, name="dashboard-summary"),
    path("technicians/", technician_list, name="technicians"),
]
