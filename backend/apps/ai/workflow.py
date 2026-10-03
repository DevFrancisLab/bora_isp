import re

from langchain_core.messages import HumanMessage, SystemMessage

from apps.ai.omega import OmegaSession
from apps.ai.prompts import BILLING_REPLY
from apps.ai.providers import ProviderError, ProviderNotConfigured, build_chat_model
from apps.ai.reasoning import decide
from apps.ai.tools import (
    _action,
    _active_incidents_for,
    _load_subscriber,
    assign_incident_to_technician,
    assistant_channel,
    assistant_message,
    check_active_incidents,
    create_support_case,
    find_available_technicians,
    find_subscriber,
    get_incident_assignment_context,
    run_recorded_diagnostics,
)
from apps.messaging.models import Message
from apps.network.models import ServiceArea
from apps.subscribers.models import Subscriber
from apps.subscribers.phones import find_subscriber_by_phone
from apps.support.models import SupportCase

SWAHILI = re.compile(r"\b(yangu|imekuwa|tangu|asubuhi|haifanyi|mtandao|tafadhali|huduma)\b", re.IGNORECASE)
PHONE_TOKEN = re.compile(r"\+?\d[\d\s-]{8,}\d")
REPLY_PROMPT = """You write the customer-facing reply for an ISP support workflow.
Use only the JSON facts. Write one or two short sentences.
If language is sw, reply in Swahili. Otherwise reply in English.
Say a case was created only when case_created is true.
If duplicate is true, say the open case already exists and include case_number.
Say a technician was assigned only when assigned is true.
Do not claim an SMS or WhatsApp message was delivered.
Do not invent repairs, speeds, invoices, or balances.
"""


def resolve_subscriber(message="", phone="", subscriber_id=None):
    subscriber = _load_subscriber(subscriber_id) if subscriber_id not in (None, "", 0, "0") else None
    if subscriber is not None:
        return subscriber
    if phone:
        found = find_subscriber_by_phone(phone)
        if found is not None:
            return found
    for token in PHONE_TOKEN.findall(message or ""):
        found = find_subscriber_by_phone(token)
        if found is not None:
            return found
    looked = find_subscriber(phone or message or "")
    if looked.get("status") == "success" and not looked.get("ambiguous"):
        return _load_subscriber(looked["subscriber"]["id"])
    return None


def build_facts(subscriber, diagnostics_fact):
    facts = ["customer-active" if subscriber.status == Subscriber.Status.ACTIVE else "customer-inactive"]
    area_status = subscriber.service_area.status
    if area_status == ServiceArea.Status.OUTAGE:
        facts.append("service-outage")
    elif area_status == ServiceArea.Status.OPERATIONAL:
        facts.append("service-active")
    elif area_status == ServiceArea.Status.DEGRADED or area_status == ServiceArea.Status.INVESTIGATING:
        facts.append("service-degraded")
    else:
        facts.append("service-inactive")
    facts.append(f"connection-{subscriber.connection_status.lower()}")
    if _active_incidents_for(subscriber):
        facts.append("incident-active")
    facts.append(diagnostics_fact)
    return facts


def assess_subscriber(subscriber_id):
    subscriber = _load_subscriber(subscriber_id)
    if subscriber is None:
        return {
            "status": "failed",
            "error": "Subscriber not found.",
            "actions": [_action("subscriber_lookup", "Subscriber not found", "failed")],
        }
    before = decide(build_facts(subscriber, "diagnostics-not-run"))
    diagnostics = run_recorded_diagnostics(subscriber.id)
    after = decide(build_facts(subscriber, diagnostics.get("outcome") or "diagnostics-not-run"))
    return {
        "status": "success",
        "subscriber_id": subscriber.id,
        "diagnostics": {key: value for key, value in diagnostics.items() if key != "actions"},
        "initial_decision": before["decision"],
        "decision": after["decision"],
        "decisions": after["decisions"],
        "facts": after["facts"],
        "engine": after["engine"],
        "actions": [
            _action("subscriber_lookup", "Subscriber found", "success"),
            _action("connection_check", f"Connection recorded as {subscriber.connection_status.lower()}", "success"),
            _action("metta_reasoning", f"MeTTa: {before['decision'] or 'no decision'}", "success"),
            *(diagnostics.get("actions") or []),
            _action("metta_reasoning", f"MeTTa: {after['decision'] or 'no decision'}", "success"),
        ],
    }


def run_customer_workflow(*, message, phone="", channel="whatsapp", context=None, model=None):
    context = context or {}
    channel = channel or "whatsapp"
    session = OmegaSession()
    channel_token = assistant_channel.set(channel)
    message_token = assistant_message.set(message or "")
    try:
        if re.search(r"\b(owe|owes|owing|balance|invoice|m-?pesa)\b", message or "", re.IGNORECASE):
            run = session.remember(
                channel=channel,
                message=message,
                provider="template",
                reply=BILLING_REPLY,
                actions=[],
            )
            return _payload(BILLING_REPLY, [], "", [], [], "template", "metta-file", session, run)

        subscriber = resolve_subscriber(message, phone, context.get("subscriber_id"))
        if subscriber is None:
            actions = [_action("subscriber_lookup", "Subscriber not found", "failed")]
            reply = "No subscriber matched that phone number or account."
            run = session.remember(channel=channel, message=message, provider="template", reply=reply, actions=actions)
            return _payload(reply, actions, "", [], [], "template", "metta-file", session, run)

        history = session.recall(subscriber)
        before = decide(build_facts(subscriber, "diagnostics-not-run"))
        diagnostics = run_recorded_diagnostics(subscriber.id)
        outcome = diagnostics.get("outcome") or "diagnostics-not-run"
        after = decide(build_facts(subscriber, outcome))
        decision = after["decision"]
        actions = [
            _action("subscriber_lookup", f"Customer identified: {subscriber.full_name}", "success"),
            _action("service_area_lookup", f"Service area {subscriber.service_area.name} checked", "success"),
            _action("connection_check", f"Connection checked: {subscriber.connection_status.lower()}", "success"),
            _action("metta_reasoning", f"MeTTa: {before['decision'] or 'no decision'}", "success"),
            *(diagnostics.get("actions") or []),
            _action("metta_reasoning", f"MeTTa: {decision or 'no decision'}", "success"),
        ]
        flags, write_actions = _execute(decision, subscriber, message, outcome)
        actions.extend(write_actions)
        reply, provider = _phrase(
            model,
            message,
            subscriber,
            decision,
            flags,
            after["facts"],
            history,
        )
        notice = _persist_channel_reply(channel, subscriber, message, reply)
        if notice is not None:
            actions.append(notice)
        run = session.remember(
            channel=channel,
            subscriber=subscriber,
            message=message,
            facts=after["facts"],
            decisions=after["decisions"],
            decision=decision,
            reasoning_engine=after["engine"],
            provider=provider,
            reply=reply,
            actions=actions,
        )
        return _payload(reply, actions, decision, after["decisions"], after["facts"], provider, after["engine"], session, run)
    finally:
        assistant_message.reset(message_token)
        assistant_channel.reset(channel_token)


def _execute(decision, subscriber, message, outcome):
    flags = {
        "case_created": False,
        "case_open": False,
        "duplicate": False,
        "case_number": "",
        "assigned": False,
        "already_assigned": False,
        "technician": "",
        "incident_number": "",
        "case_failed": False,
    }
    actions = []
    if decision not in {"technician-required", "troubleshooting-required", "human-escalation-required", "billing-action-required"}:
        actions.append(_action("workflow", "No support case was required", "success"))
        return flags, actions

    category = _category(decision, subscriber, outcome)
    created = create_support_case(
        subscriber.id,
        category,
        _subject(message, category),
        f"{message}\n\nMeTTa decision: {decision}.",
    )
    actions.extend(created.get("actions") or [])
    flags["case_number"] = created.get("case_number") or ""
    flags["duplicate"] = bool(created.get("duplicate"))
    flags["case_open"] = created.get("status") == "success" and bool(flags["case_number"])
    flags["case_created"] = flags["case_open"] and not flags["duplicate"]
    flags["case_failed"] = created.get("status") == "failed"
    if decision != "technician-required" or not flags["case_open"]:
        return flags, actions

    incidents = check_active_incidents(subscriber.id)
    active = incidents.get("active_incidents") or []
    if not active:
        actions.append(_action("incident_lookup", "No open incident to assign", "unavailable"))
        return flags, actions
    incident_number = active[0]["incident_number"]
    flags["incident_number"] = incident_number
    context = get_incident_assignment_context(incident_number)
    current = ((context.get("incident") or {}).get("assigned_technician")) if context.get("status") == "success" else None
    if current:
        flags["already_assigned"] = True
        flags["technician"] = current.get("name") or ""
        actions.append(_action("incident_assignment", f"{incident_number} is already assigned to {flags['technician']}", "success"))
        return flags, actions
    found = find_available_technicians(incident_number=incident_number)
    actions.extend(found.get("actions") or [])
    matches = [item for item in found.get("technicians") or [] if item.get("matches_incident_area")]
    if len(matches) != 1:
        label = "No available technician in the incident area" if not matches else "Several area technicians are available; none was assigned"
        actions.append(_action("technician_lookup", label, "unavailable"))
        return flags, actions
    assigned = assign_incident_to_technician(incident_number, matches[0]["id"], False)
    actions.extend(assigned.get("actions") or [])
    flags["assigned"] = bool(assigned.get("changed"))
    flags["technician"] = assigned.get("technician_name") or ""
    return flags, actions


def _category(decision, subscriber, outcome):
    if decision == "human-escalation-required":
        return SupportCase.Category.ACCOUNT
    if decision == "billing-action-required":
        return SupportCase.Category.BILLING
    if subscriber.connection_status == Subscriber.ConnectionStatus.DEGRADED or outcome == "diagnostics-not-run":
        if subscriber.connection_status == Subscriber.ConnectionStatus.OFFLINE:
            return SupportCase.Category.INTERNET_DOWN
        if subscriber.connection_status == Subscriber.ConnectionStatus.DEGRADED:
            return SupportCase.Category.SLOW_INTERNET
        return SupportCase.Category.TECHNICAL
    return SupportCase.Category.INTERNET_DOWN


def _subject(message, category):
    if category == SupportCase.Category.ACCOUNT:
        return "Account needs review"
    if category == SupportCase.Category.BILLING:
        return "Billing question"
    if category == SupportCase.Category.SLOW_INTERNET:
        return "Slow internet"
    if re.search(r"asubuhi|morning", message or "", re.IGNORECASE):
        return "Internet down since morning"
    return "Internet down"


def _phrase(model, message, subscriber, decision, flags, facts, history):
    template = _template(message, subscriber, decision, flags)
    language = "sw" if SWAHILI.search(message or "") else "en"
    if model is False:
        return template, "template"
    try:
        chat = model if model is not None else build_chat_model()
    except ProviderNotConfigured:
        return template, "template"
    payload = {
        "language": language,
        "customer": subscriber.full_name,
        "decision": decision,
        "facts": facts,
        "previous_turns": history,
        **flags,
    }
    try:
        reply_message = chat.invoke(
            [
                SystemMessage(content=REPLY_PROMPT),
                HumanMessage(content=json_dumps(payload)),
            ]
        )
    except (ProviderError, ProviderNotConfigured, Exception):
        return template, "template"
    text = _message_text(reply_message)
    if not text or not _reply_is_safe(text, flags):
        return template, "template"
    provider = getattr(chat, "last_provider", "") or "model"
    if getattr(chat, "used_fallback", False):
        provider = "groq"
    return text, provider or "model"


def _reply_is_safe(text, flags):
    lowered = text.lower()
    if not flags["case_created"] and re.search(r"\b(created|opened|tumefungua)\b", lowered) and "already" not in lowered and "ipo wazi" not in lowered and "not created" not in lowered:
        return False
    mentions_assignment = re.search(r"\b(assigned|imepewa|reassigned)\b", lowered)
    if mentions_assignment and not flags["assigned"]:
        if not (flags.get("already_assigned") and ("already" in lowered or "tayari" in lowered)):
            return False
    if re.search(r"\b(sms sent|message sent|delivered|imewasilishwa)\b", lowered):
        return False
    if re.search(r"\b(ksh|invoice|balance|m-pesa)\b", lowered):
        return False
    return True


def _template(message, subscriber, decision, flags):
    swahili = bool(SWAHILI.search(message or ""))
    name = subscriber.full_name
    case_number = flags["case_number"]
    if flags["case_failed"]:
        if swahili:
            return f"Hatukuweza kufungua kesi ya {name}. Uamuzi wa MeTTa ulikuwa {decision or 'haujakamilika'}, lakini hatujasema kesi imefunguliwa."
        return f"The support case for {name} was not created. The MeTTa decision was {decision or 'unresolved'}."
    if decision == "technician-required" and flags["assigned"]:
        if swahili:
            return (
                f"{name} yuko hai na muunganisho umeandikwa kuwa offline. "
                f"Uchunguzi wa rekodi haukuweza kurejesha huduma. Kesi {case_number} ipo wazi na {flags['incident_number']} imepewa {flags['technician']}."
            )
        return (
            f"{name} is active and the recorded connection is offline. "
            f"Recorded diagnostics could not restore service. Case {case_number} is open and {flags['incident_number']} is assigned to {flags['technician']}."
        )
    if decision == "technician-required" and flags["already_assigned"]:
        if swahili:
            return (
                f"{name} bado yuko offline. Kesi {case_number} ipo wazi. "
                f"{flags['incident_number']} tayari imepewa {flags['technician']}. Hakuna mabadiliko yaliyofanywa."
            )
        return (
            f"{name} is still offline. Case {case_number} is already open. "
            f"{flags['incident_number']} is already assigned to {flags['technician']}. The assignment was not changed."
        )
    if decision == "technician-required":
        if swahili:
            extra = f"Kesi {case_number} ipo wazi. " if case_number else ""
            return f"{name} anahitaji fundi kwa sababu muunganisho uko offline na uchunguzi wa rekodi umeshindwa. {extra}Hakuna fundi mmoja wa eneo hilo aliyewekwa."
        extra = f"Case {case_number} is open. " if case_number else ""
        return f"{name} needs a technician because the recorded connection is offline and diagnostics failed. {extra}No single area technician was assigned."
    if decision == "human-escalation-required":
        if swahili:
            return f"Akaunti ya {name} haijaandikwa kuwa hai. Kesi {case_number} inahitaji mhudumu. Hatujatuma fundi wa mtandao."
        return f"{name} is not an active account. Case {case_number} needs a person to review it. No field technician was assigned."
    if decision == "troubleshooting-required":
        if swahili:
            return f"Tunaangalia muunganisho wa {name}. Kesi {case_number} ipo wazi. Hatujahitaji fundi bado."
        return f"{name} needs troubleshooting from the recorded connection. Case {case_number} is open. A technician was not required."
    if decision == "service-appears-online":
        if swahili:
            return f"Rekodi zinaonyesha muunganisho wa {name} uko online na hakuna tukio hai. Ikiwa bado haifanyi kazi, tuambie."
        return f"Records show {name} is online and no active incident is open. No case or technician was assigned."
    if swahili:
        return f"Hatukuweza kuamua hatua inayofuata kwa {name} kutoka rekodi zilizopo."
    return f"ISPBora could not decide a next action for {name} from the stored records."


def _persist_channel_reply(channel, subscriber, message, reply):
    if channel not in {"whatsapp", "sms"}:
        return _action("reply", "Reply ready for the operator", "success")
    message_channel = Message.Channel.WHATSAPP if channel == "whatsapp" else Message.Channel.SMS
    Message.objects.create(
        subscriber=subscriber,
        channel=message_channel,
        direction=Message.Direction.INBOUND,
        message_type="SUPPORT",
        body=message,
        status=Message.Status.DELIVERED,
    )
    Message.objects.create(
        subscriber=subscriber,
        channel=message_channel,
        direction=Message.Direction.OUTBOUND,
        message_type="SUPPORT",
        body=reply,
        status=Message.Status.PENDING,
    )
    label = "WhatsApp reply queued" if channel == "whatsapp" else "SMS reply queued"
    return _action("customer_notification", label, "queued")


def _message_text(message):
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return " ".join(content.replace("**", "").split())
    return ""


def _payload(reply, actions, decision, decisions, facts, provider, engine, session, run):
    return {
        "reply": reply,
        "actions": actions,
        "decision": decision,
        "decisions": decisions,
        "facts": facts,
        "provider": provider,
        "engine": engine,
        "omega": session.describe(run),
    }


def json_dumps(payload):
    import json

    return json.dumps(payload, default=str)
