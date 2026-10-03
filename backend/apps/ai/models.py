from django.db import models


class AgentRun(models.Model):
    channel = models.CharField(max_length=20)
    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agent_runs",
    )
    message = models.TextField()
    facts = models.JSONField(default=list, blank=True)
    decisions = models.JSONField(default=list, blank=True)
    decision = models.CharField(max_length=64, blank=True)
    reasoning_engine = models.CharField(max_length=32, blank=True)
    provider = models.CharField(max_length=32, blank=True)
    reply = models.TextField(blank=True)
    actions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel} {self.decision or 'unresolved'}"
