from rest_framework.routers import DefaultRouter

from apps.incidents.views import IncidentViewSet

router = DefaultRouter()
router.register("incidents", IncidentViewSet, basename="incident")
urlpatterns = router.urls
