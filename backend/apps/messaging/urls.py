from django.urls import path

from apps.messaging.views import MessageListView, NotificationListView

urlpatterns = [
    path("messages/", MessageListView.as_view(), name="messages"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
]
