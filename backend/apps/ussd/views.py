from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.ussd.services import handle_ussd


@csrf_exempt
@require_POST
def ussd_callback(request):
    body = handle_ussd(
        text=request.POST.get("text", ""),
        phone_number=request.POST.get("phoneNumber", ""),
    )
    return HttpResponse(body, content_type="text/plain")
