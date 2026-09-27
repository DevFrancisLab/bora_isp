from django.urls import path

from apps.common.views import dashboard_summary, technician_detail, technician_list

urlpatterns = [
    path("dashboard/summary/", dashboard_summary, name="dashboard-summary"),
    path("technicians/", technician_list, name="technicians"),
    path("technicians/<int:pk>/", technician_detail, name="technician-detail"),
]
