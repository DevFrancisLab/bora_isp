# Generated for the customer workflow audit log.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("subscribers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(max_length=20)),
                ("message", models.TextField()),
                ("facts", models.JSONField(blank=True, default=list)),
                ("decisions", models.JSONField(blank=True, default=list)),
                ("decision", models.CharField(blank=True, max_length=64)),
                ("reasoning_engine", models.CharField(blank=True, max_length=32)),
                ("provider", models.CharField(blank=True, max_length=32)),
                ("reply", models.TextField(blank=True)),
                ("actions", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "subscriber",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agent_runs",
                        to="subscribers.subscriber",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
