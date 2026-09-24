from rest_framework.routers import DefaultRouter

from apps.subscribers.views import SubscriberViewSet

router = DefaultRouter()
router.register("subscribers", SubscriberViewSet, basename="subscriber")
urlpatterns = router.urls
