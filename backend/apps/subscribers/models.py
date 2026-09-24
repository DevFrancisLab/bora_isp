from django.db import models


class Subscriber(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        INACTIVE = "INACTIVE", "Inactive"

    class ConnectionStatus(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        OFFLINE = "OFFLINE", "Offline"
        DEGRADED = "DEGRADED", "Degraded"
        UNKNOWN = "UNKNOWN", "Unknown"

    account_number = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=160)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255)
    service_area = models.ForeignKey(
        "network.ServiceArea",
        on_delete=models.PROTECT,
        related_name="subscribers",
    )
    plan = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    connection_status = models.CharField(
        max_length=20,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.UNKNOWN,
    )
    installation_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.account_number} {self.full_name}"
