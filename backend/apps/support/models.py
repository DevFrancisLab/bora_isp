from django.db import models


class SupportCase(models.Model):
    class Category(models.TextChoices):
        INTERNET_DOWN = "INTERNET_DOWN", "Internet down"
        SLOW_INTERNET = "SLOW_INTERNET", "Slow internet"
        ACCOUNT = "ACCOUNT", "Account"
        BILLING = "BILLING", "Billing"
        TECHNICAL = "TECHNICAL", "Technical"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        INVESTIGATING = "INVESTIGATING", "Investigating"
        ESCALATED = "ESCALATED", "Escalated"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Source(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        VOICE = "VOICE", "Voice"
        USSD = "USSD", "USSD"
        SMS = "SMS", "SMS"
        DASHBOARD = "DASHBOARD", "Dashboard"
        PHONE = "PHONE", "Phone"

    case_number = models.CharField(max_length=32, unique=True)
    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        on_delete=models.PROTECT,
        related_name="support_cases",
    )
    category = models.CharField(max_length=32, choices=Category.choices)
    subject = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.DASHBOARD)
    assigned_to = models.CharField(max_length=120, blank=True)
    service_area = models.ForeignKey(
        "network.ServiceArea",
        on_delete=models.PROTECT,
        related_name="support_cases",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.case_number} {self.subject}"
