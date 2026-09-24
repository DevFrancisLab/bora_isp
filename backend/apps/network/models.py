from django.db import models


class ServiceArea(models.Model):
    class Status(models.TextChoices):
        OPERATIONAL = "OPERATIONAL", "Operational"
        DEGRADED = "DEGRADED", "Degraded"
        INVESTIGATING = "INVESTIGATING", "Investigating"
        OUTAGE = "OUTAGE", "Outage"

    name = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPERATIONAL)
    description = models.TextField(blank=True)
    subscriber_count = models.PositiveIntegerField(default=0)
    geometry = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def refresh_subscriber_count(self):
        self.subscriber_count = self.subscribers.count()
        self.save(update_fields=["subscriber_count", "updated_at"])


class NetworkSite(models.Model):
    class SiteType(models.TextChoices):
        POP = "POP", "POP"
        TOWER = "TOWER", "Tower"
        NODE = "NODE", "Node"
        CORE = "CORE", "Core"

    class Status(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        DEGRADED = "DEGRADED", "Degraded"
        OFFLINE = "OFFLINE", "Offline"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    name = models.CharField(max_length=120)
    site_type = models.CharField(max_length=20, choices=SiteType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ONLINE)
    service_area = models.ForeignKey(ServiceArea, on_delete=models.PROTECT, related_name="sites")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
