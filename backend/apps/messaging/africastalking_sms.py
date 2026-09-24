import os
from dataclasses import dataclass

from apps.subscribers.phones import normalize_kenyan_phone

_PLACEHOLDER_USERNAME = "your_sandbox_username"
_PLACEHOLDER_API_KEY = "your_sandbox_api_key"


@dataclass(frozen=True)
class SmsResult:
    ok: bool
    phone_number: str = ""
    error: str = ""


def _configured_credentials():
    username = os.getenv("AFRICASTALKING_USERNAME", "").strip()
    api_key = os.getenv("AFRICASTALKING_API_KEY", "").strip()
    if not username or not api_key or username == _PLACEHOLDER_USERNAME or api_key == _PLACEHOLDER_API_KEY:
        return None
    environment = os.getenv("AFRICASTALKING_ENV", "sandbox").strip().lower() or "sandbox"
    if environment not in {"sandbox", "production"}:
        return None
    return username, api_key, environment


def _provider_send(username, api_key, phone_number, message):
    import africastalking

    africastalking.initialize(username, api_key)
    sender_id = os.getenv("AFRICASTALKING_SMS_SENDER_ID", "").strip()
    if sender_id:
        return africastalking.SMS.send(message, [phone_number], sender_id)
    return africastalking.SMS.send(message, [phone_number])


def send_sms(phone_number, message):
    normalized = normalize_kenyan_phone(phone_number)
    if not normalized:
        return SmsResult(ok=False, error="Phone number is not a valid Kenyan number.")
    credentials = _configured_credentials()
    if credentials is None:
        return SmsResult(
            ok=False,
            phone_number=normalized,
            error="Africa's Talking SMS is not configured.",
        )
    username, api_key, _environment = credentials
    try:
        response = _provider_send(username, api_key, normalized, message)
        recipients = (response or {}).get("SMSMessageData", {}).get("Recipients", [])
        if recipients and all(item.get("status") == "Success" for item in recipients):
            return SmsResult(ok=True, phone_number=normalized)
    except Exception:
        return SmsResult(ok=False, phone_number=normalized, error="Africa's Talking SMS request failed.")
    return SmsResult(ok=False, phone_number=normalized, error="Africa's Talking rejected the SMS.")
