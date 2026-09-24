from django.contrib import admin
from django.urls import include, path

from apps.ussd.views import ussd_callback

urlpatterns = [
    path("ussd", ussd_callback, name="ussd-callback"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.common.urls")),
    path("api/", include("apps.network.urls")),
    path("api/", include("apps.subscribers.urls")),
    path("api/", include("apps.support.urls")),
    path("api/", include("apps.incidents.urls")),
    path("api/", include("apps.messaging.urls")),
]
