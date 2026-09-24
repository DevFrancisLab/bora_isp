from rest_framework.generics import ListAPIView

from apps.messaging.models import Message, Notification
from apps.messaging.serializers import MessageSerializer, NotificationSerializer


class MessageListView(ListAPIView):
    serializer_class = MessageSerializer
    queryset = Message.objects.select_related("subscriber")


class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer
    queryset = Notification.objects.select_related("subscriber", "incident")
