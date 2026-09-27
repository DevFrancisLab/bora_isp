import os
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from langchain_core.messages import AIMessage
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai.graph import AssistantError, run_assistant
from apps.ai.tools import (
    assign_incident_to_technician,
    check_active_incidents,
    create_support_case,
    find_available_technicians,
    find_subscriber,
    get_active_incident_summary,
    get_affected_subscribers,
    get_area_incidents,
    get_incident_assignment_context,
    get_incident_impact_summary,
    get_open_support_cases,
    get_subscriber_context,
    get_support_case_summary,
    notify_customer,
)
from apps.common.models import Technician
from apps.incidents.models import Incident
from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase


class ScriptedModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.transcripts = []

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        self.seen = list(messages)
        self.transcripts.append(self.seen)
        self.calls += 1
        if not self.replies:
            raise RuntimeError("model exhausted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def tool_call(name, args, call_id="call-1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


class ToolTests(TestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani", status=ServiceArea.Status.OUTAGE)
        self.quiet = ServiceArea.objects.create(name="Lavington", status=ServiceArea.Status.OPERATIONAL)
        self.mary = self._subscriber(self.area, "SUB-00124", "Mary Wanjiku", "+254712438221")
        self.other_mary = self._subscriber(self.quiet, "SUB-00125", "Mary Achieng", "+254700000111")
        self.incident = Incident.objects.create(
            incident_number="INC-104",
            title="Kilimani Service Disruption",
            description="Fiber cut",
            status=Incident.Status.INVESTIGATING,
            severity=Incident.Severity.CRITICAL,
            service_area=self.area,
            affected_subscribers=1,
            started_at=timezone.now(),
        )

    def _subscriber(self, area, account, name, phone):
        return Subscriber.objects.create(
            account_number=account,
            full_name=name,
            phone_number=phone,
            address=f"{area.name}, Nairobi",
            service_area=area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.OFFLINE,
            installation_date=date(2024, 3, 12),
        )

    def test_lookup_by_kenyan_phone(self):
        result = find_subscriber("0712438221")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["subscriber"]["account_number"], "SUB-00124")
        self.assertEqual(result["actions"][0]["type"], "subscriber_lookup")

    def test_subscriber_not_found(self):
        result = find_subscriber("0700000000")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["actions"][0]["label"], "Subscriber not found")

    def test_ambiguous_subscriber(self):
        result = find_subscriber("Mary")
        self.assertTrue(result["ambiguous"])
        self.assertEqual(len(result["matches"]), 2)

    def test_subscriber_context_includes_incident_and_case(self):
        SupportCase.objects.create(
            case_number="CASE-1001",
            subscriber=self.mary,
            service_area=self.area,
            category=SupportCase.Category.INTERNET_DOWN,
            subject="Internet Down",
            status=SupportCase.Status.OPEN,
            priority=SupportCase.Priority.HIGH,
        )
        result = get_subscriber_context(self.mary.id)
        self.assertEqual(result["subscriber"]["service_area"], "Kilimani")
        self.assertEqual(result["active_incidents"][0]["incident_number"], "INC-104")
        self.assertEqual(result["open_support_cases"][0]["case_number"], "CASE-1001")
        self.assertEqual(
            [item["type"] for item in result["actions"]],
            ["subscriber_lookup", "service_area_lookup", "incident_lookup", "support_case_lookup"],
        )

    def test_active_incident_found_and_absent(self):
        found = check_active_incidents(self.mary.id)
        self.assertEqual(found["active_incidents"][0]["incident_number"], "INC-104")
        quiet = check_active_incidents(self.other_mary.id)
        self.assertEqual(quiet["active_incidents"], [])

    def test_open_support_cases(self):
        self.assertEqual(get_open_support_cases(self.mary.id)["open_support_cases"], [])

    def test_support_case_creation_and_duplicate_protection(self):
        created = create_support_case(self.mary.id, "INTERNET_DOWN", "Internet Down", "Still down")
        self.assertEqual(created["status"], "success")
        self.assertFalse(created["duplicate"])
        self.assertTrue(SupportCase.objects.filter(case_number=created["case_number"], subscriber=self.mary).exists())
        duplicate = create_support_case(self.mary.id, "INTERNET_DOWN", "Internet Down", "Still down")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["case_number"], created["case_number"])
        self.assertEqual(SupportCase.objects.filter(subscriber=self.mary).count(), 1)

    @patch("apps.incidents.services.send_sms")
    @patch("apps.ai.tools._configured_credentials", return_value=None)
    def test_notification_reports_unconfigured_sms(self, _credentials, send_sms):
        from apps.messaging.africastalking_sms import SmsResult

        send_sms.return_value = SmsResult(ok=False, error="Africa's Talking SMS is not configured.")
        result = notify_customer(self.mary.id)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["delivery"], "not_configured")
        self.assertNotIn("SMS sent", result["actions"][0]["label"])
        quiet = notify_customer(self.other_mary.id)
        self.assertEqual(quiet["delivery"], "no_outage")
        self.assertEqual(send_sms.call_count, 1)


class GraphTests(TestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani")
        self.subscriber = Subscriber.objects.create(
            account_number="SUB-00124",
            full_name="Mary Wanjiku",
            phone_number="+254712438221",
            address="Kilimani, Nairobi",
            service_area=self.area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.ONLINE,
            installation_date=date(2024, 3, 12),
        )

    def test_simple_informational_request(self):
        model = ScriptedModel([AIMessage(content="There are no customer-specific facts in this answer.")])
        result = run_assistant(message="What can you help with?", model=model)
        self.assertEqual(result["actions"], [])
        self.assertIn("no customer-specific", result["reply"])
        self.assertEqual(model.calls, 1)

    def test_subscriber_lookup_tool_call(self):
        model = ScriptedModel(
            [
                tool_call("find_subscriber", {"query": "0712438221"}),
                AIMessage(content="Mary Wanjiku is the matching subscriber."),
            ]
        )
        result = run_assistant(message="Look up 0712438221", model=model)
        self.assertEqual(result["actions"][0]["type"], "subscriber_lookup")
        self.assertEqual(result["actions"][0]["status"], "success")
        self.assertIn("Mary Wanjiku", result["reply"])

    def test_multi_tool_workflow(self):
        model = ScriptedModel(
            [
                tool_call("find_subscriber", {"query": "SUB-00124"}, "call-1"),
                tool_call("check_active_incidents", {"subscriber_id": self.subscriber.id}, "call-2"),
                AIMessage(content="No active incident is recorded for this subscriber's area."),
            ]
        )
        result = run_assistant(message="Is this customer affected by an outage?", model=model)
        self.assertEqual([item["type"] for item in result["actions"]], ["subscriber_lookup", "incident_lookup"])
        self.assertIn("No active incident", result["reply"])

    def test_support_case_creation_workflow(self):
        model = ScriptedModel(
            [
                tool_call(
                    "create_support_case",
                    {
                        "subscriber_id": self.subscriber.id,
                        "category": "INTERNET_DOWN",
                        "subject": "Internet Down",
                        "description": "Still down",
                    },
                ),
                AIMessage(content="The support case was created."),
            ]
        )
        result = run_assistant(message="Create a support case because the internet is still down.", model=model)
        self.assertEqual(result["actions"][0]["type"], "support_case_created")
        self.assertEqual(SupportCase.objects.filter(subscriber=self.subscriber).count(), 1)

    def test_tool_failure_and_subscriber_not_found(self):
        model = ScriptedModel(
            [
                tool_call("find_subscriber", {"query": "0700000000"}),
                AIMessage(content="No subscriber matched that number."),
            ]
        )
        result = run_assistant(message="What's happening with 0700000000?", model=model)
        self.assertEqual(result["actions"][0]["status"], "failed")
        self.assertIn("No subscriber", result["reply"])

    def test_provider_failure(self):
        model = ScriptedModel([RuntimeError("provider down")])
        with self.assertRaises(AssistantError) as caught:
            run_assistant(message="Hello", model=model)
        self.assertEqual(caught.exception.category, "unavailable")
        self.assertNotIn("provider down", caught.exception.message)

    def test_billing_question_does_not_call_the_model(self):
        model = ScriptedModel([AIMessage(content="The customer owes KSh 5000.")])
        result = run_assistant(message="How much does this customer owe?", model=model)
        self.assertEqual(model.calls, 0)
        self.assertIn("not currently available", result["reply"])
        self.assertNotIn("5000", result["reply"])
        self.assertEqual(result["actions"], [])


class AssistantApiTests(APITestCase):
    def test_valid_request(self):
        with patch("apps.ai.views.run_assistant", return_value={"reply": "Mary is online.", "actions": [{"type": "subscriber_lookup", "label": "Subscriber found", "status": "success"}]}) as run:
            response = self.client.post(reverse("ai-assistant"), {"message": "What's happening with customer 0712438221?"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reply"], "Mary is online.")
        self.assertEqual(response.data["actions"][0]["status"], "success")
        run.assert_called_once()

    def test_empty_request(self):
        response = self.client.post(reverse("ai-assistant"), {"message": "  "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_provider_failure_hides_internals(self):
        with patch("apps.ai.views.run_assistant", side_effect=AssistantError("The AI assistant is temporarily unavailable.", "unavailable")):
            response = self.client.post(reverse("ai-assistant"), {"message": "Hello"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertNotIn("traceback", str(response.data).lower())
        self.assertNotIn("groq", str(response.data).lower())

    def test_tool_failure_is_returned_as_action_status(self):
        with patch("apps.ai.views.run_assistant", return_value={"reply": "No subscriber matched.", "actions": [{"type": "subscriber_lookup", "label": "Subscriber not found", "status": "failed"}]}):
            response = self.client.post(reverse("ai-assistant"), {"message": "Find 0700000000"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["actions"][0]["status"], "failed")

    def test_billing_question(self):
        response = self.client.post(reverse("ai-assistant"), {"message": "How much does customer 0712438221 owe?"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("not currently available", response.data["reply"])
        self.assertEqual(response.data["actions"], [])

    def test_history_is_forwarded(self):
        history = [{"role": "assistant", "content": "The most severe active incident is INC-104."}]
        with patch("apps.ai.views.run_assistant", return_value={"reply": "Using INC-104.", "actions": []}) as run:
            response = self.client.post(reverse("ai-assistant"), {"message": "assign this to a technician", "history": history}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(run.call_args.kwargs["history"], history)

    def test_history_must_be_a_list(self):
        response = self.client.post(reverse("ai-assistant"), {"message": "assign this", "history": "INC-104"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_provider_configuration(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "GROQ_MODEL": ""}):
            response = self.client.post(reverse("ai-assistant"), {"message": "Any active outages?"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("not configured", response.data["detail"])


class OperationalToolTests(TestCase):
    def setUp(self):
        self.kilimani = ServiceArea.objects.create(name="Kilimani")
        self.lavington = ServiceArea.objects.create(name="Lavington")
        self.mary = self._subscriber(self.kilimani, "SUB-00124", "Mary Wanjiku", "+254712438221")
        self.samuel = self._subscriber(self.lavington, "SUB-00512", "Samuel Kariuki", "+254707274525")
        self.ann = self._subscriber(self.lavington, "SUB-00540", "Ann Wairimu", "+254733221760")
        self.critical = self._incident("INC-104", "Kilimani Service Disruption", Incident.Severity.CRITICAL, self.kilimani, [self.mary])
        self.major = self._incident("INC-102", "South link degraded", Incident.Severity.MAJOR, self.lavington, [self.samuel, self.ann])
        SupportCase.objects.create(
            case_number="CASE-1001",
            subscriber=self.mary,
            service_area=self.kilimani,
            category=SupportCase.Category.INTERNET_DOWN,
            subject="Internet Down",
            priority=SupportCase.Priority.HIGH,
            status=SupportCase.Status.OPEN,
        )
        SupportCase.objects.create(
            case_number="CASE-1002",
            subscriber=self.samuel,
            service_area=self.lavington,
            category=SupportCase.Category.TECHNICAL,
            subject="Unstable",
            priority=SupportCase.Priority.LOW,
            status=SupportCase.Status.RESOLVED,
            resolved_at=timezone.now(),
        )

    def _subscriber(self, area, account, name, phone):
        return Subscriber.objects.create(
            account_number=account,
            full_name=name,
            phone_number=phone,
            address=f"{area.name}, Nairobi",
            service_area=area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.OFFLINE,
            installation_date=date(2024, 3, 12),
        )

    def _incident(self, number, title, severity, area, people):
        incident = Incident.objects.create(
            incident_number=number,
            title=title,
            description=title,
            status=Incident.Status.INVESTIGATING,
            severity=severity,
            service_area=area,
            affected_subscribers=len(people),
            started_at=timezone.now(),
        )
        incident.affected.set(people)
        return incident

    def test_active_incident_summary_picks_critical_over_larger_major(self):
        result = get_active_incident_summary()
        self.assertEqual(result["active_incident_count"], 2)
        self.assertEqual(result["highest_severity"], Incident.Severity.CRITICAL)
        self.assertEqual([item["incident_number"] for item in result["highest_severity_incidents"]], ["INC-104"])

    def test_tied_highest_severity_returns_every_match(self):
        self._incident("INC-109", "Second critical", Incident.Severity.CRITICAL, self.lavington, [])
        result = get_active_incident_summary()
        self.assertEqual(
            sorted(item["incident_number"] for item in result["highest_severity_incidents"]),
            ["INC-104", "INC-109"],
        )

    def test_no_active_incidents(self):
        Incident.objects.update(status=Incident.Status.RESOLVED)
        result = get_active_incident_summary()
        self.assertEqual(result["active_incident_count"], 0)
        self.assertIsNone(result["highest_severity"])
        self.assertEqual(result["highest_severity_incidents"], [])
        self.assertEqual(result["incidents"], [])

    def test_area_incidents(self):
        found = get_area_incidents("lavington")
        self.assertEqual(found["active_incident_count"], 1)
        self.assertEqual(found["incidents"][0]["incident_number"], "INC-102")
        empty = get_area_incidents("CBD")
        quiet = ServiceArea.objects.create(name="CBD")
        self.assertEqual(get_area_incidents(quiet.name)["incidents"], [])
        self.assertEqual(empty["status"], "failed")
        self.assertEqual(get_area_incidents("Missing Area")["status"], "failed")

    def test_affected_subscribers(self):
        found = get_affected_subscribers("INC-102")
        self.assertEqual(found["affected_subscriber_count"], 2)
        self.assertEqual({item["name"] for item in found["subscribers"]}, {"Samuel Kariuki", "Ann Wairimu"})
        none = self._incident("INC-110", "Empty", Incident.Severity.MINOR, self.kilimani, [])
        empty = get_affected_subscribers(none.incident_number)
        self.assertEqual(empty["affected_subscriber_count"], 0)
        self.assertEqual(empty["subscribers"], [])
        missing = get_affected_subscribers("INC-999")
        self.assertEqual(missing["status"], "failed")

    def test_support_case_summary_uses_real_categories(self):
        result = get_support_case_summary()
        self.assertEqual(result["total_open_cases"], 1)
        self.assertEqual(result["by_priority"][SupportCase.Priority.HIGH], 1)
        self.assertEqual(result["by_priority"][SupportCase.Priority.LOW], 0)
        self.assertEqual(result["by_category"][SupportCase.Category.INTERNET_DOWN], 1)
        self.assertEqual(result["by_category"][SupportCase.Category.BILLING], 0)
        SupportCase.objects.update(status=SupportCase.Status.CLOSED)
        self.assertEqual(get_support_case_summary()["total_open_cases"], 0)

    def test_impact_summary_uses_subscriber_count_not_severity(self):
        result = get_incident_impact_summary()
        self.assertEqual(result["highest_impact_incident"]["incident_number"], "INC-102")
        self.assertEqual(result["highest_impact_count"], 2)
        Incident.objects.update(status=Incident.Status.RESOLVED)
        clear = get_incident_impact_summary()
        self.assertIsNone(clear["highest_impact_incident"])
        self.assertEqual(clear["highest_impact_incidents"], [])


class OperationalGraphTests(TestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Kilimani")
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

    def test_most_severe_issue_uses_summary_and_affected_subscribers(self):
        model = ScriptedModel(
            [
                tool_call("get_active_incident_summary", {}, "call-1"),
                tool_call("get_affected_subscribers", {"incident_number": "INC-104"}, "call-2"),
                AIMessage(content="The most severe active incident is INC-104."),
            ]
        )
        result = run_assistant(message="Who has the most severe issue?", model=model)
        self.assertEqual([item["type"] for item in result["actions"]], ["incident_summary", "incident_summary", "affected_subscribers"])
        self.assertIn("INC-104", result["reply"])

    def test_most_customers_uses_impact_summary(self):
        model = ScriptedModel(
            [
                tool_call("get_incident_impact_summary", {}, "call-1"),
                AIMessage(content="INC-104 affects the most subscribers."),
            ]
        )
        result = run_assistant(message="Which issue affects the most customers?", model=model)
        self.assertEqual(result["actions"][0]["type"], "incident_impact")

    def test_open_case_count_uses_support_summary(self):
        model = ScriptedModel(
            [
                tool_call("get_support_case_summary", {}, "call-1"),
                AIMessage(content="There are 0 open support cases."),
            ]
        )
        result = run_assistant(message="How many open support cases do we have?", model=model)
        self.assertEqual(result["actions"][0]["type"], "support_summary")
        self.assertEqual(result["actions"][0]["status"], "success")


class TechnicianToolTests(TestCase):
    def setUp(self):
        self.lavington = ServiceArea.objects.create(name="Lavington")
        self.kilimani = ServiceArea.objects.create(name="Kilimani")
        self.brian = self._technician("Brian Mwangi", self.lavington, Technician.Status.AVAILABLE)
        self.john = self._technician("John Kamau", self.kilimani, Technician.Status.AVAILABLE)
        self.peter = self._technician("Peter Otieno", self.kilimani, Technician.Status.BUSY)
        self.offline = self._technician("Amina Hassan", self.lavington, Technician.Status.OFFLINE)
        self.incident = self._incident("INC-102", self.lavington)

    def _technician(self, name, area, status):
        return Technician.objects.create(
            name=name,
            phone_number=f"+2547{Technician.objects.count():08d}",
            email=f"{name.split()[0].lower()}@example.com",
            status=status,
            service_area=area,
        )

    def _incident(self, number, area, status=Incident.Status.INVESTIGATING):
        return Incident.objects.create(
            incident_number=number,
            title="Core Network Failure",
            description="Fiber issue",
            status=status,
            severity=Incident.Severity.CRITICAL,
            service_area=area,
            affected_subscribers=0,
            started_at=timezone.now(),
        )

    def test_available_technician_exists(self):
        result = find_available_technicians()
        self.assertTrue(result["available"])
        self.assertEqual({item["name"] for item in result["technicians"]}, {"Brian Mwangi", "John Kamau"})
        self.assertEqual(result["status_counts"][Technician.Status.BUSY], 1)
        self.assertEqual(result["status_counts"][Technician.Status.OFFLINE], 1)

    def test_multiple_technicians_available(self):
        extra = self._incident("INC-103", self.kilimani)
        extra.assigned_technician = self.john
        extra.save(update_fields=["assigned_technician"])
        result = find_available_technicians()
        self.assertEqual(len(result["technicians"]), 2)
        john = next(item for item in result["technicians"] if item["name"] == "John Kamau")
        self.assertEqual(john["active_incident_count"], 1)
        self.assertEqual(result["actions"][1]["label"], "Found 2 available technicians")

    def test_no_technicians_available(self):
        Technician.objects.update(status=Technician.Status.OFFLINE)
        result = find_available_technicians()
        self.assertFalse(result["available"])
        self.assertEqual(result["technicians"], [])
        self.assertEqual(result["reason"], "No technicians are currently available.")
        self.assertEqual(result["status_counts"][Technician.Status.AVAILABLE], 0)
        self.assertEqual(result["actions"][-1]["status"], "unavailable")

    def test_all_technicians_busy(self):
        Technician.objects.update(status=Technician.Status.BUSY)
        result = find_available_technicians()
        self.assertFalse(result["available"])
        self.assertEqual(result["status_counts"][Technician.Status.BUSY], 4)
        self.assertEqual(result["status_counts"][Technician.Status.AVAILABLE], 0)

    def test_status_filtering_excludes_busy_and_offline(self):
        names = {item["name"] for item in find_available_technicians()["technicians"]}
        self.assertNotIn("Peter Otieno", names)
        self.assertNotIn("Amina Hassan", names)

    def test_area_aware_lookup_prefers_incident_area(self):
        result = find_available_technicians(incident_number="INC-102")
        self.assertEqual(result["technicians"][0]["name"], "Brian Mwangi")
        self.assertTrue(result["technicians"][0]["matches_incident_area"])
        self.assertFalse(result["technicians"][1]["matches_incident_area"])
        lavington = find_available_technicians(service_area="Lavington")
        self.assertEqual([item["name"] for item in lavington["technicians"]], ["Brian Mwangi"])
        self.assertEqual(find_available_technicians(service_area="Nowhere")["status"], "failed")

    def test_assignment_context(self):
        result = get_incident_assignment_context("INC-102")
        self.assertEqual(result["incident"]["incident_number"], "INC-102")
        self.assertEqual(result["incident"]["service_area"], "Lavington")
        self.assertIsNone(result["incident"]["assigned_technician"])
        self.assertEqual(get_incident_assignment_context("INC-999")["status"], "failed")

    def test_assign_available_technician_persists(self):
        result = assign_incident_to_technician("INC-102", self.brian.id)
        self.assertTrue(result["success"])
        self.assertTrue(result["changed"])
        self.incident.refresh_from_db()
        self.brian.refresh_from_db()
        self.assertEqual(self.incident.assigned_technician_id, self.brian.id)
        self.assertEqual(self.brian.status, Technician.Status.BUSY)

    def test_technician_does_not_exist(self):
        result = assign_incident_to_technician("INC-102", 99999)
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Technician not found.")
        self.incident.refresh_from_db()
        self.assertIsNone(self.incident.assigned_technician_id)

    def test_incident_does_not_exist(self):
        result = assign_incident_to_technician("INC-999", self.brian.id)
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Incident not found.")

    def test_technician_unavailable(self):
        result = assign_incident_to_technician("INC-102", self.peter.id)
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Technician is no longer available.")
        self.incident.refresh_from_db()
        self.assertIsNone(self.incident.assigned_technician_id)

    def test_incident_already_assigned_is_not_overwritten(self):
        self.incident.assigned_technician = self.john
        self.incident.save(update_fields=["assigned_technician"])
        result = assign_incident_to_technician("INC-102", self.brian.id)
        self.assertFalse(result["changed"])
        self.assertIn("already assigned to John Kamau", result["reason"])
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.assigned_technician_id, self.john.id)

    def test_explicit_reassignment(self):
        self.incident.assigned_technician = self.john
        self.incident.save(update_fields=["assigned_technician"])
        self.john.status = Technician.Status.BUSY
        self.john.save(update_fields=["status"])
        result = assign_incident_to_technician("INC-102", self.brian.id, reassign=True)
        self.assertTrue(result["changed"])
        self.incident.refresh_from_db()
        self.john.refresh_from_db()
        self.brian.refresh_from_db()
        self.assertEqual(self.incident.assigned_technician_id, self.brian.id)
        self.assertEqual(self.brian.status, Technician.Status.BUSY)
        self.assertEqual(self.john.status, Technician.Status.AVAILABLE)

    def test_availability_change_between_lookup_and_assignment(self):
        found = find_available_technicians(name="Brian")
        self.assertEqual(found["technicians"][0]["id"], self.brian.id)
        self.brian.status = Technician.Status.OFFLINE
        self.brian.save(update_fields=["status"])
        result = assign_incident_to_technician("INC-102", self.brian.id)
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Technician is no longer available.")
        self.incident.refresh_from_db()
        self.assertIsNone(self.incident.assigned_technician_id)

    def test_resolved_incident_cannot_be_assigned(self):
        self.incident.status = Incident.Status.RESOLVED
        self.incident.save(update_fields=["status"])
        result = assign_incident_to_technician("INC-102", self.brian.id)
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "This incident cannot be assigned.")


class TechnicianGraphTests(TestCase):
    def setUp(self):
        self.area = ServiceArea.objects.create(name="Lavington")
        self.other = ServiceArea.objects.create(name="Kilimani")
        self.brian = Technician.objects.create(
            name="Brian Mwangi",
            phone_number="+254711000001",
            status=Technician.Status.AVAILABLE,
            service_area=self.area,
        )
        self.incident = Incident.objects.create(
            incident_number="INC-102",
            title="Core Network Failure",
            status=Incident.Status.INVESTIGATING,
            severity=Incident.Severity.CRITICAL,
            service_area=self.area,
            affected_subscribers=0,
            started_at=timezone.now(),
        )
        self.subscriber = Subscriber.objects.create(
            account_number="SUB-00124",
            full_name="Mary Wanjiku",
            phone_number="+254712438221",
            address="Lavington, Nairobi",
            service_area=self.area,
            plan="Home 20 Mbps",
            status=Subscriber.Status.ACTIVE,
            connection_status=Subscriber.ConnectionStatus.OFFLINE,
            installation_date=date(2024, 3, 12),
        )

    def test_find_an_available_technician(self):
        model = ScriptedModel(
            [
                tool_call("find_available_technicians", {}, "call-1"),
                AIMessage(content="Brian Mwangi is currently available."),
            ]
        )
        result = run_assistant(message="Find an available technician.", model=model)
        self.assertEqual(result["actions"][0]["type"], "technician_lookup")
        self.assertEqual(result["actions"][1]["type"], "technician_found")
        self.assertIn("Brian Mwangi", result["reply"])

    def test_are_any_technicians_available(self):
        model = ScriptedModel(
            [
                tool_call("find_available_technicians", {}, "call-1"),
                AIMessage(content="Yes. Brian Mwangi is currently available."),
            ]
        )
        result = run_assistant(message="Are any technicians available?", model=model)
        self.assertTrue(result["actions"][0]["status"] == "success")

    def test_assign_named_technician(self):
        model = ScriptedModel(
            [
                tool_call("get_incident_assignment_context", {"incident_number": "INC-102"}, "call-1"),
                tool_call("find_available_technicians", {"name": "Brian"}, "call-2"),
                tool_call("assign_incident_to_technician", {"incident_number": "INC-102", "technician_id": self.brian.id}, "call-3"),
                AIMessage(content="INC-102 has been assigned to Brian Mwangi."),
            ]
        )
        result = run_assistant(message="Assign INC-102 to Brian.", model=model)
        self.assertEqual(result["actions"][-1]["label"], "INC-102 assigned to Brian Mwangi")
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.assigned_technician_id, self.brian.id)

    def test_assign_to_someone_available(self):
        model = ScriptedModel(
            [
                tool_call("get_incident_assignment_context", {"incident_number": "INC-102"}, "call-1"),
                tool_call("find_available_technicians", {"incident_number": "INC-102"}, "call-2"),
                tool_call("assign_incident_to_technician", {"incident_number": "INC-102", "technician_id": self.brian.id}, "call-3"),
                AIMessage(content="INC-102 has been assigned to Brian Mwangi."),
            ]
        )
        result = run_assistant(message="Assign this issue to someone available.", model=model)
        self.assertIn("assigned to Brian Mwangi", result["actions"][-1]["label"])

    def test_no_technicians_available_workflow(self):
        self.brian.status = Technician.Status.BUSY
        self.brian.save(update_fields=["status"])
        model = ScriptedModel(
            [
                tool_call("find_available_technicians", {}, "call-1"),
                AIMessage(content="There are currently no available technicians."),
            ]
        )
        result = run_assistant(message="Are there any technicians available?", model=model)
        self.assertEqual(result["actions"][-1]["status"], "unavailable")
        self.assertIn("no available technicians", result["reply"])

    def test_assign_does_not_overwrite_when_model_sets_reassign(self):
        other = Technician.objects.create(
            name="John Kamau",
            phone_number="+254711000002",
            status=Technician.Status.BUSY,
            service_area=self.other,
        )
        self.incident.assigned_technician = other
        self.incident.save(update_fields=["assigned_technician"])
        model = ScriptedModel(
            [
                tool_call(
                    "assign_incident_to_technician",
                    {"incident_number": "INC-102", "technician_id": self.brian.id, "reassign": True},
                    "call-1",
                ),
                AIMessage(content="INC-102 is already assigned to John Kamau."),
            ]
        )
        result = run_assistant(message="Assign INC-102 to Brian.", model=model)
        self.assertFalse(result["actions"][-1]["label"].endswith("assigned to Brian Mwangi"))
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.assigned_technician_id, other.id)

    def test_explicit_reassign_message_replaces_technician(self):
        other = Technician.objects.create(
            name="John Kamau",
            phone_number="+254711000003",
            status=Technician.Status.BUSY,
            service_area=self.other,
        )
        self.incident.assigned_technician = other
        self.incident.save(update_fields=["assigned_technician"])
        model = ScriptedModel(
            [
                tool_call(
                    "assign_incident_to_technician",
                    {"incident_number": "INC-102", "technician_id": self.brian.id, "reassign": False},
                    "call-1",
                ),
                AIMessage(content="INC-102 has been reassigned to Brian Mwangi."),
            ]
        )
        result = run_assistant(message="Reassign INC-102 to Brian.", model=model)
        self.assertEqual(result["actions"][-1]["label"], "INC-102 assigned to Brian Mwangi")
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.assigned_technician_id, self.brian.id)

    def test_follow_up_keeps_the_previous_incident(self):
        model = ScriptedModel(
            [
                tool_call("get_incident_assignment_context", {"incident_number": "INC-102"}, "call-1"),
                AIMessage(content="INC-102 can be assigned."),
            ]
        )
        result = run_assistant(
            message="assign this to a technician",
            history=[
                {"role": "operator", "content": "what is the most severe active issue?"},
                {"role": "assistant", "content": "The most severe active incident is INC-102."},
            ],
            model=model,
        )
        contents = [item.content for item in model.transcripts[0]]
        self.assertIn("The most severe active incident is INC-102.", contents)
        self.assertEqual(contents[-1], "assign this to a technician")
        self.assertEqual(result["actions"][0]["label"], "Checked incident INC-102")

    def test_existing_subscriber_workflow_still_works(self):
        model = ScriptedModel(
            [
                tool_call("find_subscriber", {"query": "Mary Wanjiku"}, "call-1"),
                AIMessage(content="Mary Wanjiku is in Lavington."),
            ]
        )
        result = run_assistant(message="Find Mary Wanjiku.", model=model)
        self.assertEqual(result["actions"][0]["type"], "subscriber_lookup")
        self.assertIn("Mary Wanjiku", result["reply"])
