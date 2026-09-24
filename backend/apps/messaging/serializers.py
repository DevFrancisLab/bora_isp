from rest_framework import serializers

from apps.messaging.models import Message, Notification


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "subscriber",
            "channel",
            "direction",
            "message_type",
            "body",
            "status",
            "created_at",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "subscriber",
            "incident",
            "channel",
            "title",
            "body",
            "status",
            "created_at",
            "sent_at",
        ]
