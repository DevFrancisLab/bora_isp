from django.db import models


class Incident(models.Model):
    class Status(models.TextChoices):
        INVESTIGATING = "INVESTIGATING", "Investigating"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        MONITORING = "MONITORING", "Monitoring"
        RESOLVED = "RESOLVED", "Resolved"

    class Severity(models.TextChoices):
        MINOR = "MINOR", "Minor"
        MAJOR = "MAJOR", "Major"
        CRITICAL = "CRITICAL", "Critical"

    class IncidentType(models.TextChoices):
        CONNECTIVITY = "CONNECTIVITY", "Connectivity"
        POWER = "POWER", "Power"
        EQUIPMENT = "EQUIPMENT", "Equipment"
        FIBER = "FIBER", "Fiber"
        UNKNOWN = "UNKNOWN", "Unknown"

    incident_number = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    incident_type = models.CharField(max_length=20, choices=IncidentType.choices, default=IncidentType.CONNECTIVITY)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVESTIGATING)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MAJOR)
    service_area = models.ForeignKey(
        "network.ServiceArea",
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    affected = models.ManyToManyField(
        "subscribers.Subscriber",
        related_name="affecting_incidents",
        blank=True,
    )
    affected_subscribers = models.PositiveIntegerField(default=0)
    report_count = models.PositiveIntegerField(default=0)
    assigned_technician = models.ForeignKey(
        "common.Technician",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incidents",
    )
    started_at = models.DateTimeField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.incident_number} {self.title}"


class IncidentReport(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="reports")
    support_case = models.ForeignKey(
        "support.SupportCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incident_reports",
    )
    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        on_delete=models.PROTECT,
        related_name="incident_reports",
    )
    service_area = models.ForeignKey(
        "network.ServiceArea",
        on_delete=models.PROTECT,
        related_name="incident_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "support_case"],
                condition=models.Q(support_case__isnull=False),
                name="unique_incident_support_case",
            )
        ]

    def __str__(self):
        return f"{self.incident.incident_number} / {self.subscriber.account_number}"
