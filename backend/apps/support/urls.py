from rest_framework.routers import DefaultRouter

from apps.support.views import SupportCaseViewSet

router = DefaultRouter()
router.register("support/cases", SupportCaseViewSet, basename="support-case")
urlpatterns = router.urls
