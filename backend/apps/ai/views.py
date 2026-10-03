from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.ai.graph import AssistantError, run_assistant
from apps.ai.workflow import run_customer_workflow

CHANNELS = {"dashboard", "whatsapp", "sms", "ussd", "voice"}


@api_view(["POST"])
def assistant_view(request):
    message = request.data.get("message")
    if not isinstance(message, str) or not message.strip():
        return Response({"detail": "Enter a question for the AI Operations Assistant."}, status=status.HTTP_400_BAD_REQUEST)
    channel = request.data.get("channel") or "dashboard"
    if channel not in CHANNELS:
        return Response({"detail": "Unsupported assistant channel."}, status=status.HTTP_400_BAD_REQUEST)
    context = request.data.get("context") or {}
    if context is None:
        context = {}
    if not isinstance(context, dict):
        return Response({"detail": "Assistant context must be an object."}, status=status.HTTP_400_BAD_REQUEST)
    history = request.data.get("history") or []
    if not isinstance(history, list):
        return Response({"detail": "Assistant history must be a list."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = run_assistant(message=message.strip(), context=context, channel=channel, history=history)
    except AssistantError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.category in {"not_configured", "unavailable"} else status.HTTP_400_BAD_REQUEST
        return Response({"detail": exc.message}, status=code)
    return Response(result)


@api_view(["POST"])
def customer_workflow_view(request):
    message = request.data.get("message")
    if not isinstance(message, str) or not message.strip():
        return Response({"detail": "Enter the customer message."}, status=status.HTTP_400_BAD_REQUEST)
    channel = request.data.get("channel") or "whatsapp"
    if channel not in CHANNELS:
        return Response({"detail": "Unsupported assistant channel."}, status=status.HTTP_400_BAD_REQUEST)
    context = request.data.get("context") or {}
    if not isinstance(context, dict):
        return Response({"detail": "Assistant context must be an object."}, status=status.HTTP_400_BAD_REQUEST)
    phone = request.data.get("phone") or ""
    if phone and not isinstance(phone, str):
        return Response({"detail": "Phone must be a string."}, status=status.HTTP_400_BAD_REQUEST)
    result = run_customer_workflow(message=message.strip(), phone=phone.strip(), channel=channel, context=context)
    return Response(result)
