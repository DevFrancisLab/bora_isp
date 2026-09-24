from apps.subscribers.models import Subscriber


def normalize_kenyan_phone(value):
    raw = value or ""
    digits = "".join(character for character in raw if character.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = f"254{digits[1:]}"
    elif len(digits) == 9:
        digits = f"254{digits}"
    if digits.startswith("254") and len(digits) == 12:
        return f"+{digits}"
    return ""


def find_subscriber_by_phone(value):
    normalized = normalize_kenyan_phone(value)
    if not normalized:
        return None
    return Subscriber.objects.filter(phone_number=normalized).first()
