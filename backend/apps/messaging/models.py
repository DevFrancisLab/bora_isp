from django.db import models


class Message(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        SMS = "SMS", "SMS"
        VOICE = "VOICE", "Voice"
        USSD = "USSD", "USSD"

    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "Inbound"
        OUTBOUND = "OUTBOUND", "Outbound"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"

    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    direction = models.CharField(max_length=20, choices=Direction.choices)
    message_type = models.CharField(max_length=40)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel} {self.direction} {self.created_at:%Y-%m-%d %H:%M}"


class Notification(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        SMS = "SMS", "SMS"
        VOICE = "VOICE", "Voice"
        USSD = "USSD", "USSD"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"

    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    incident = models.ForeignKey(
        "incidents.Incident",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    title = models.CharField(max_length=160)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
