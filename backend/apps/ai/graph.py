import inspect
import json
import logging
import re
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition
from typing_extensions import Annotated, TypedDict

from apps.ai.prompts import BILLING_REPLY, SYSTEM_PROMPT
from apps.ai import tools as isp_tools

logger = logging.getLogger("apps.ai")


def operator_add(left, right):
    return list(left or []) + list(right or [])


BILLING_QUESTION = re.compile(
    r"\b(owe|owes|owing|balance|invoice|invoices|m-?pesa|how much|package price|expir(?:y|es|ed)|payment status)\b",
    re.IGNORECASE,
)
DISCONNECTED_QUESTION = re.compile(
    r"\b(?:disconnected|whose internet is (?:down|offline|disconnected))\b",
    re.IGNORECASE,
)


class AssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    actions: Annotated[list, operator_add]


class AssistantError(Exception):
    def __init__(self, message, category):
        super().__init__(message)
        self.message = message
        self.category = category


@tool
def find_subscriber(query: str) -> str:
    """Find a subscriber by Kenyan phone number, account number, or name. Use this before answering about a specific customer."""
    return json.dumps(isp_tools.find_subscriber(query))


@tool
def get_subscriber_context(subscriber_id: int) -> str:
    """Load one subscriber's area, connection status, active incidents, and open support cases."""
    return json.dumps(isp_tools.get_subscriber_context(subscriber_id))


@tool
def check_active_incidents(subscriber_id: int = 0) -> str:
    """Check active incidents. Pass a subscriber id to limit the check to that customer's service area. Pass 0 to list active incidents."""
    return json.dumps(isp_tools.check_active_incidents(subscriber_id or None))


@tool
def get_open_support_cases(subscriber_id: int) -> str:
    """List open support cases for one subscriber."""
    return json.dumps(isp_tools.get_open_support_cases(subscriber_id))


@tool
def create_support_case(subscriber_id: int, category: str, subject: str, description: str, priority: str = "") -> str:
    """Create a support case after checking for an open case in the same category. Category is INTERNET_DOWN, SLOW_INTERNET, ACCOUNT, BILLING, TECHNICAL, or OTHER."""
    return json.dumps(isp_tools.create_support_case(subscriber_id, category, subject, description, priority))


@tool
def notify_customer(subscriber_id: int) -> str:
    """Notify one subscriber about an active outage in their service area using the existing SMS path. Do not call this unless the operator asked to notify the customer."""
    return json.dumps(isp_tools.notify_customer(subscriber_id))


@tool
def get_active_incident_summary() -> str:
    """Summarize all active incidents and identify the highest severity. Severity is CRITICAL, then MAJOR, then MINOR. Use this for the most serious outage, not the outage with the most customers."""
    return json.dumps(isp_tools.get_active_incident_summary())


@tool
def get_area_incidents(service_area: str) -> str:
    """List active incidents for one service area name, such as Lavington or Kilimani."""
    return json.dumps(isp_tools.get_area_incidents(service_area))


@tool
def get_affected_subscribers(incident_number: str) -> str:
    """List subscribers linked to an incident number such as INC-104. Returns a count and a short sample."""
    return json.dumps(isp_tools.get_affected_subscribers(incident_number))


@tool
def get_support_case_summary() -> str:
    """Count open support cases by priority and category. Use this for organization-wide case questions."""
    return json.dumps(isp_tools.get_support_case_summary())


@tool
def get_incident_impact_summary() -> str:
    """Find the active incident affecting the most subscribers. This is impact, not severity."""
    return json.dumps(isp_tools.get_incident_impact_summary())


@tool
def find_available_technicians(service_area: str = "", incident_number: str = "", name: str = "") -> str:
    """Find technicians whose status is AVAILABLE. Optionally filter by service area, incident number, or name. Does not rank by proximity or skill."""
    return json.dumps(isp_tools.find_available_technicians(service_area, incident_number, name))


@tool
def get_incident_assignment_context(incident_number: str) -> str:
    """Read one incident before assignment, including its current technician if any."""
    return json.dumps(isp_tools.get_incident_assignment_context(incident_number))


@tool
def run_recorded_diagnostics(subscriber_id: int) -> str:
    """Read the stored connection, service area, and active incidents for one subscriber. This does not run a live network probe or restore service."""
    return json.dumps(isp_tools.run_recorded_diagnostics(subscriber_id))


@tool
def list_disconnected_subscribers(limit: int = 8) -> str:
    """List subscribers whose stored connection status is OFFLINE. Returns a count and a short sample."""
    return json.dumps(isp_tools.list_disconnected_subscribers(limit))


@tool
def explain_subscriber_decision(subscriber_id: int) -> str:
    """Read stored facts and return the MeTTa troubleshooting decision for one subscriber. Does not create a case or assign a technician."""
    from apps.ai.workflow import assess_subscriber

    return json.dumps(assess_subscriber(subscriber_id))


@tool
def assign_incident_to_technician(incident_number: str, technician_id: int, reassign: bool = False) -> str:
    """Assign an open incident to an available technician. Call this when the operator names the technician, and when exactly one available technician shares the incident service area. Set reassign true only when the operator explicitly asks to replace the current technician."""
    return json.dumps(isp_tools.assign_incident_to_technician(incident_number, technician_id, reassign))


def _explain_subscriber_decision(subscriber_id):
    from apps.ai.workflow import assess_subscriber

    return assess_subscriber(subscriber_id)


TOOL_FUNCTIONS = {
    "find_subscriber": isp_tools.find_subscriber,
    "get_subscriber_context": isp_tools.get_subscriber_context,
    "check_active_incidents": lambda subscriber_id=0: isp_tools.check_active_incidents(subscriber_id or None),
    "get_open_support_cases": isp_tools.get_open_support_cases,
    "create_support_case": isp_tools.create_support_case,
    "notify_customer": isp_tools.notify_customer,
    "get_active_incident_summary": isp_tools.get_active_incident_summary,
    "get_area_incidents": isp_tools.get_area_incidents,
    "get_affected_subscribers": isp_tools.get_affected_subscribers,
    "get_support_case_summary": isp_tools.get_support_case_summary,
    "get_incident_impact_summary": isp_tools.get_incident_impact_summary,
    "find_available_technicians": lambda service_area="", incident_number="", name="": isp_tools.find_available_technicians(service_area, incident_number, name),
    "get_incident_assignment_context": isp_tools.get_incident_assignment_context,
    "run_recorded_diagnostics": isp_tools.run_recorded_diagnostics,
    "list_disconnected_subscribers": isp_tools.list_disconnected_subscribers,
    "explain_subscriber_decision": _explain_subscriber_decision,
    "assign_incident_to_technician": lambda incident_number, technician_id, reassign=False: isp_tools.assign_incident_to_technician(incident_number, technician_id, reassign),
}
MODEL_TOOLS = [
    find_subscriber,
    get_subscriber_context,
    check_active_incidents,
    get_open_support_cases,
    create_support_case,
    notify_customer,
    get_active_incident_summary,
    get_area_incidents,
    get_affected_subscribers,
    get_support_case_summary,
    get_incident_impact_summary,
    find_available_technicians,
    get_incident_assignment_context,
    run_recorded_diagnostics,
    list_disconnected_subscribers,
    explain_subscriber_decision,
    assign_incident_to_technician,
]


def _public_result(result):
    if not isinstance(result, dict):
        return {"status": "failed", "error": "The tool returned an unexpected result."}
    return {key: value for key, value in result.items() if key != "actions"}


def _execute_tool(name, arguments):
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {
            "status": "failed",
            "error": "That action is not available.",
            "actions": [{"type": "tool", "label": "Requested action is not available", "status": "unavailable"}],
        }
    try:
        signature = inspect.signature(function)
        accepted = {
            name
            for name, param in signature.parameters.items()
            if param.kind in {param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY}
        }
        result = function(**{key: value for key, value in (arguments or {}).items() if key in accepted})
    except TypeError:
        return {
            "status": "failed",
            "error": "The tool arguments were invalid.",
            "actions": [{"type": name, "label": "The request could not be completed", "status": "failed"}],
        }
    except Exception:
        logger.warning("ai.tool name=%s status=failed", name)
        return {
            "status": "failed",
            "error": "The tool failed.",
            "actions": [{"type": name, "label": "The request could not be completed", "status": "failed"}],
        }
    if not isinstance(result, dict):
        result = {"status": "failed", "error": "The tool returned an unexpected result."}
    logger.info("ai.tool name=%s status=%s", name, result.get("status", "failed"))
    return result


def _tool_node(state):
    message = state["messages"][-1]
    outputs = []
    actions = []
    for call in getattr(message, "tool_calls", []) or []:
        result = _execute_tool(call.get("name"), call.get("args") or {})
        actions.extend(result.get("actions") or [])
        outputs.append(
            ToolMessage(
                content=json.dumps(_public_result(result)),
                tool_call_id=call.get("id") or call.get("name"),
                name=call.get("name") or "tool",
            )
        )
    return {"messages": outputs, "actions": actions}


def _agent_node(state, model):
    response = model.invoke(state["messages"])
    return {"messages": [response]}


def build_graph(model):
    bound = model.bind_tools(MODEL_TOOLS)

    def agent(state):
        return _agent_node(state, bound)

    graph = StateGraph(AssistantState)
    graph.add_node("agent", agent)
    graph.add_node("tools", _tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", "__end__": "__end__"})
    graph.add_edge("tools", "agent")
    return graph.compile()


def _plain_text(value):
    text = value.replace("**", "").replace("`", "")
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^(?:#{1,6}\s+|[-*]\s+|\d+\.\s+)", "", line).strip()
        line = re.sub(r"^(Severity|Service area|Status|Affected subscribers)\s*:\s*", "", line, flags=re.IGNORECASE)
        if line:
            lines.append(line)
    return " ".join(lines)


def _reply_text(message):
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return _plain_text(content)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(item["text"])
        return _plain_text("\n".join(parts))
    return ""


def _context_message(context):
    if not context:
        return ""
    subscriber_id = context.get("subscriber_id")
    if subscriber_id in (None, ""):
        return ""
    subscriber = isp_tools._load_subscriber(subscriber_id)
    if subscriber is None:
        return "The subscriber id supplied with this request does not exist. Do not treat it as a customer."
    return (
        f"The operator is currently viewing subscriber id {subscriber.id}, "
        f"account {subscriber.account_number}, name {subscriber.full_name}. "
        "Use this subscriber when they say this customer, unless they name someone else."
    )


def build_model():
    from apps.ai.providers import ProviderNotConfigured, build_chat_model

    try:
        return build_chat_model()
    except ProviderNotConfigured:
        raise AssistantError("The AI assistant is not configured.", "not_configured") from None


HISTORY_LIMIT = 8


def _history_messages(history):
    messages = []
    if not history:
        return messages
    for item in list(history)[-HISTORY_LIMIT:]:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), str) else ""
        content = " ".join(content.split())[:600]
        if not content:
            continue
        role = str(item.get("role") or "").lower()
        if role in {"operator", "user", "human"}:
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def run_assistant(*, message, context=None, channel="dashboard", history=None, model=None):
    if BILLING_QUESTION.search(message or ""):
        logger.info("ai.assistant channel=%s tools= billing_unavailable duration_ms=0", channel)
        return {"reply": BILLING_REPLY, "actions": []}
    if DISCONNECTED_QUESTION.search(message or ""):
        found = isp_tools.list_disconnected_subscribers()
        count = found["disconnected_count"]
        noun = "subscriber" if count == 1 else "subscribers"
        verb = "is" if count == 1 else "are"
        names = ", ".join(item["name"] for item in found["subscribers"]) or "none"
        sample = " The names are a sample." if found["sample_limited"] else ""
        reply = f"{count} {noun} {verb} recorded as offline. Sample: {names}.{sample}"
        return {"reply": reply, "actions": found["actions"], "provider": "records"}
    started = time.perf_counter()
    token = isp_tools.assistant_channel.set(channel or "dashboard")
    message_token = isp_tools.assistant_message.set(message or "")
    try:
        if model is None:
            model = build_model()
        graph = build_graph(model)
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        context_text = _context_message(context)
        if context_text:
            messages.append(SystemMessage(content=context_text))
        messages.extend(_history_messages(history))
        messages.append(HumanMessage(content=message))
        result = graph.invoke({"messages": messages, "actions": []}, config={"recursion_limit": 10})
        final = next((item for item in reversed(result["messages"]) if isinstance(item, AIMessage) and not item.tool_calls), None)
        reply = _reply_text(final) if final else ""
        if not reply:
            reply = "I could not complete that request from the available ISP data."
        actions = result.get("actions") or []
        payload = {"reply": reply, "actions": actions}
        provider = getattr(model, "last_provider", "")
        if provider:
            payload["provider"] = provider
            if getattr(model, "used_fallback", False):
                payload["provider"] = "groq"
        logger.info(
            "ai.assistant channel=%s tools=%s duration_ms=%s",
            channel,
            ",".join(item.get("type", "") for item in actions),
            int((time.perf_counter() - started) * 1000),
        )
        return payload
    except AssistantError:
        raise
    except Exception:
        logger.warning("ai.assistant error_category=provider_failure")
        raise AssistantError("The AI assistant is temporarily unavailable.", "unavailable") from None
    finally:
        isp_tools.assistant_message.reset(message_token)
        isp_tools.assistant_channel.reset(token)
