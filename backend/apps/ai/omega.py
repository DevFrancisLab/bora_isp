from apps.ai.models import AgentRun


class OmegaSession:
    """Remember customer turns in ISPBora.

    singnet/Omega is a separate MeTTa agent runtime (PeTTa, NAL, and PLN).
    That process is not started here. This session is the persistence boundary
    the customer workflow uses for the same receive, reason, act, and remember loop.
    """

    runtime = "ispbora-adapter"
    embedded_runtime = False

    def recall(self, subscriber, limit=3):
        if subscriber is None:
            return []
        runs = AgentRun.objects.filter(subscriber=subscriber).order_by("-created_at")[:limit]
        return [
            {
                "decision": run.decision,
                "reply": run.reply,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ]

    def remember(self, **fields):
        return AgentRun.objects.create(**fields)

    def describe(self, run):
        return {
            "mode": self.runtime,
            "embedded_runtime": self.embedded_runtime,
            "run_id": run.id if run is not None else None,
        }
