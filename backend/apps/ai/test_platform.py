import json
import os
from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from langchain_core.messages import AIMessage
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai.models import AgentRun
from apps.ai.providers import (
    BasixChatModel,
    FallbackChatModel,
    ProviderError,
    ProviderNotConfigured,
    build_chat_model,
    embed_text,
)
from apps.ai.reasoning import decide
from apps.ai.graph import run_assistant
from apps.ai.workflow import run_customer_workflow
from apps.common.models import Technician
from apps.incidents.models import Incident
from apps.messaging.models import Message
from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase


class StubModel:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ProviderTests(SimpleTestCase):
    def test_missing_basix_and_groq_keys(self):
        with patch.dict(os.environ, {"BASIX_API_KEY": "", "GROQ_API_KEY": "", "GROQ_MODEL": ""}, clear=False):
            with self.assertRaises(ProviderNotConfigured):
                build_chat_model()

    def test_basix_http_failure_falls_back_to_groq(self):
        primary = StubModel(ProviderError("BASIX HTTP 429"))
        fallback = StubModel(AIMessage(content="Groq reply"))
        model = FallbackChatModel(primary=primary, fallback=fallback)
        bound = model.bind_tools([])
        reply = bound.invoke([AIMessage(content="ping")])
        self.assertEqual(reply.content, "Groq reply")
        self.assertEqual(model.last_provider, "groq")
        self.assertTrue(model.used_fallback)
        self.assertEqual(fallback.calls, 1)

    def test_basix_success_does_not_call_groq(self):
        primary = StubModel(AIMessage(content="BASIX reply"))
        fallback = StubModel(AIMessage(content="Groq reply"))
        model = FallbackChatModel(primary=primary, fallback=fallback)
        reply = model.invoke([])
        self.assertEqual(reply.content, "BASIX reply")
        self.assertEqual(model.last_provider, "basix")
        self.assertFalse(model.used_fallback)
        self.assertEqual(fallback.calls, 0)

    def test_both_providers_fail(self):
        model = FallbackChatModel(primary=StubModel(RuntimeError("basix down")), fallback=StubModel(RuntimeError("groq down")))
        with self.assertRaises(ProviderError):
            model.invoke([])

    def test_basix_chat_parses_tool_call_without_logging_the_key(self):
        captured = {}

        def fake_post(url, payload, api_key, timeout):
            captured["url"] = url
            captured["key"] = api_key
            captured["model"] = payload["model"]
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "find_subscriber", "arguments": json.dumps({"query": "Mary"})},
                                }
                            ],
                        }
                    }
                ]
            }

        model = BasixChatModel("qwen/qwen3.8-27b", "secret-key", "https://llm.c.singularitynet.io/v1", 5)
        with patch("apps.ai.providers._post_json", side_effect=fake_post):
            message = model.invoke([])
        self.assertEqual(captured["url"], "https://llm.c.singularitynet.io/v1/chat/completions")
        self.assertEqual(captured["model"], "qwen/qwen3.8-27b")
        self.assertEqual(message.tool_calls[0]["name"], "find_subscriber")
        self.assertEqual(message.tool_calls[0]["args"]["query"], "Mary")
        self.assertNotIn("secret-key", repr(model))

    def test_embedding_request_uses_configured_model(self):
        def fake_post(url, payload, api_key, timeout):
            self.assertTrue(url.endswith("/embeddings"))
            self.assertEqual(payload["model"], "BAAI/bge-base-en-v1.5")
            return {"data": [{"embedding": [0.1, 0.2]}]}

        with patch.dict(os.environ, {"BASIX_API_KEY": "secret-key", "BASIX_EMBEDDING_MODEL": "BAAI/bge-base-en-v1.5"}, clear=False):
            with patch("apps.ai.providers._post_json", side_effect=fake_post):
                vector = embed_text("internet down")
        self.assertEqual(vector, [0.1, 0.2])

    def test_env_example_has_no_live_key(self):
        example = open(os.path.join(os.path.dirname(__file__), "..", "..", ".env.example"), encoding="utf-8").read()
        self.assertIn("BASIX_API_KEY=", example)
        self.assertNotIn("sk-", example)


class MettaRuleTests(SimpleTestCase):
    def test_offline_before_diagnostics_requests_troubleshooting(self):
        result = decide(["customer-active", "service-active", "connection-offline", "diagnostics-not-run"])
        self.assertEqual(result["decision"], "troubleshooting-required")
        self.assertNotIn("technician-required", result["decisions"])
        self.assertIn(result["engine"], {"hyperon", "metta-file"})

    def test_failed_diagnostics_require_a_technician(self):
        result = decide(["customer-active", "service-active", "connection-offline", "diagnostics-failed"])
        self.assertEqual(result["decision"], "technician-required")

    def test_outage_and_offline_require_a_technician(self):
        result = decide(["customer-active", "service-outage", "connection-offline", "diagnostics-failed"])
        self.assertEqual(result["decision"], "technician-required")
        self.assertIn("troubleshooting-required", result["decisions"])

    def test_inactive_customer_is_human_escalation(self):
        result = decide(["customer-inactive", "connection-offline", "diagnostics-failed", "service-active"])
        self.assertEqual(result["decision"], "human-escalation-required")
        self.assertIn("technician-required", result["decisions"])

    def test_balance_due_is_a_billing_decision_only_when_asserted(self):
        result = decide(["balance-due", "customer-active", "connection-online", "diagnostics-success"])
        self.assertEqual(result["decision"], "billing-action-required")

    def test_online_service_needs_no_field_action(self):
        result = decide(["customer-active", "service-active", "connection-online", "diagnostics-success"])
        self.assertEqual(result["decision"], "service-appears-online")

    def test_hyperon_matches_the_rule_file_when_installed(self):
        try:
            import hyperon  # noqa: F401
        except ImportError:
            self.skipTest("hyperon is not installed")
        facts = ["customer-active", "service-active", "connection-offline", "diagnostics-failed"]
        with patch("apps.ai.reasoning._hyperon_available", return_value=False):
            interpreted = decide(facts)
        live = decide(facts)
        self.assertEqual(live["engine"], "hyperon")
        self.assertEqual(live["decision"], interpreted["decision"])
        self.assertEqual(set(live["decisions"]), set(interpreted["decisions"]))


class CustomerWorkflowTests(TestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani", status=ServiceArea.Status.OPERATIONAL)
        self.subscriber = Subscriber.objects.create(
            account_number="SUB-00124",
            full_name="Mary Wanjiku",
            phone_number="+254712438221",
            address="Kilimani, Nairobi",
            service_area=self.area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.OFFLINE,
            installation_date=date(2024, 3, 12),
        )
        self.incident = Incident.objects.create(
            incident_number="INC-104",
            title="Kilimani Service Disruption",
            status=Incident.Status.INVESTIGATING,
            severity=Incident.Severity.CRITICAL,
            service_area=self.area,
            affected_subscribers=1,
            started_at=timezone.now(),
        )
        self.incident.affected.add(self.subscriber)
        self.technician = Technician.objects.create(
            name="Brian Kamau",
            phone_number="+254711640228",
            status=Technician.Status.AVAILABLE,
            service_area=self.area,
        )

    def test_swahili_outage_creates_case_and_assigns_one_technician(self):
        result = run_customer_workflow(
            message="Internet yangu imekuwa down tangu asubuhi.",
            phone="0712438221",
            channel="whatsapp",
            model=False,
        )
        self.assertEqual(result["decision"], "technician-required")
        self.assertIn("customer-active", result["facts"])
        self.assertIn("connection-offline", result["facts"])
        self.assertIn("diagnostics-failed", result["facts"])
        self.assertNotIn("balance-due", result["facts"])
        self.assertEqual(result["provider"], "template")
        self.assertFalse(result["omega"]["embedded_runtime"])
        self.assertIn("Brian Kamau", result["reply"])
        self.assertNotIn("delivered", result["reply"].lower())
        labels = [item["label"] for item in result["actions"]]
        self.assertTrue(any(label.startswith("Customer identified") for label in labels))
        self.assertTrue(any(label.startswith("MeTTa:") for label in labels))
        self.assertIn("WhatsApp reply queued", labels)
        self.incident.refresh_from_db()
        self.technician.refresh_from_db()
        self.assertEqual(self.incident.assigned_technician_id, self.technician.id)
        self.assertEqual(self.technician.status, Technician.Status.BUSY)
        self.assertEqual(SupportCase.objects.filter(subscriber=self.subscriber).count(), 1)
        outbound = Message.objects.get(subscriber=self.subscriber, direction=Message.Direction.OUTBOUND)
        self.assertEqual(outbound.status, Message.Status.PENDING)
        self.assertEqual(outbound.channel, Message.Channel.WHATSAPP)
        self.assertTrue(AgentRun.objects.filter(subscriber=self.subscriber, decision="technician-required").exists())

    def test_failed_case_write_is_not_described_as_created(self):
        with patch("apps.ai.workflow.create_support_case", return_value={"status": "failed", "error": "nope", "actions": [{"type": "support_case_created", "label": "Support case was not created", "status": "failed"}]}):
            result = run_customer_workflow(message="Internet yangu imekuwa down tangu asubuhi.", phone="0712438221", model=False)
        self.assertIn("hatukuweza", result["reply"].lower())
        self.assertEqual(SupportCase.objects.count(), 0)
        self.incident.refresh_from_db()
        self.assertIsNone(self.incident.assigned_technician_id)

    def test_unsafe_model_claim_is_discarded(self):
        model = StubModel(AIMessage(content="The case was created and the SMS was delivered."))
        result = run_customer_workflow(message="Internet is down", phone="0712438221", model=model)
        self.assertNotIn("delivered", result["reply"].lower())
        self.assertEqual(result["provider"], "template")
        self.assertEqual(model.calls, 1)

    def test_online_customer_does_not_open_a_case(self):
        self.subscriber.connection_status = Subscriber.ConnectionStatus.ONLINE
        self.subscriber.save(update_fields=["connection_status"])
        self.incident.status = Incident.Status.RESOLVED
        self.incident.save(update_fields=["status"])
        result = run_customer_workflow(message="Internet yangu imekuwa down tangu asubuhi.", phone="0712438221", model=False)
        self.assertEqual(result["decision"], "service-appears-online")
        self.assertEqual(SupportCase.objects.count(), 0)
        self.assertIn("online", result["reply"].lower())

    def test_suspended_customer_is_not_assigned_a_technician(self):
        self.subscriber.status = Subscriber.Status.SUSPENDED
        self.subscriber.save(update_fields=["status"])
        result = run_customer_workflow(message="Internet yangu imekuwa down tangu asubuhi.", phone="0712438221", model=False)
        self.assertEqual(result["decision"], "human-escalation-required")
        case = SupportCase.objects.get(subscriber=self.subscriber)
        self.assertEqual(case.category, SupportCase.Category.ACCOUNT)
        self.incident.refresh_from_db()
        self.assertIsNone(self.incident.assigned_technician_id)

    def test_two_technicians_are_not_auto_assigned(self):
        Technician.objects.create(
            name="John Kamau",
            phone_number="+254711000099",
            status=Technician.Status.AVAILABLE,
            service_area=self.area,
        )
        result = run_customer_workflow(message="Internet yangu imekuwa down tangu asubuhi.", phone="0712438221", model=False)
        self.assertEqual(result["decision"], "technician-required")
        self.incident.refresh_from_db()
        self.assertIsNone(self.incident.assigned_technician_id)
        self.assertTrue(any(item["label"].startswith("Several area technicians") for item in result["actions"]))

    def test_unknown_phone_does_not_invent_a_customer(self):
        result = run_customer_workflow(message="Internet yangu imekuwa down tangu asubuhi.", phone="0700000000", model=False)
        self.assertEqual(result["actions"][0]["status"], "failed")
        self.assertEqual(SupportCase.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)

    def test_disconnected_question_answers_from_records(self):
        result = run_assistant(message="Show me customers whose internet is disconnected.", model=StubModel(AIMessage(content="invented")))
        self.assertEqual(result["provider"], "records")
        self.assertIn("1 subscriber is recorded as offline", result["reply"])
        self.assertIn("Mary Wanjiku", result["reply"])
        self.assertNotIn("invented", result["reply"])


class CustomerApiTests(APITestCase):
    def test_customer_workflow_endpoint(self):
        area = ServiceArea.objects.create(name="Kilimani")
        Subscriber.objects.create(
            account_number="SUB-00124",
            full_name="Mary Wanjiku",
            phone_number="+254712438221",
            address="Kilimani, Nairobi",
            service_area=area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 3, 12),
        )
        with patch("apps.ai.workflow.build_chat_model", side_effect=ProviderNotConfigured("missing")):
            response = self.client.post(
                reverse("ai-customer-workflow"),
                {"message": "Internet yangu imekuwa down tangu asubuhi.", "phone": "0712438221", "channel": "whatsapp"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["decision"], "service-appears-online")
        self.assertNotIn("sk-", json.dumps(response.data))

    def test_empty_customer_message(self):
        response = self.client.post(reverse("ai-customer-workflow"), {"message": " "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
