from django.http import Http404, HttpResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.plugins import api

from .providers import FortySixElks, accepted_secrets


@csrf_exempt
@require_POST
def delivery(request, secret):
    """46elks reports here whether an SMS was delivered (the "whendelivered" URL).
    No login: the secret in the address is the check."""
    if not any(constant_time_compare(secret, known) for known in accepted_secrets()):
        raise Http404
    status = request.POST.get("status", "")
    if status in ("delivered", "failed"):
        api.record_delivery(FortySixElks.name, request.POST.get("id", ""), status == "delivered")
    # 46elks retries anything but 200, so unknown ids are acknowledged too.
    return HttpResponse("")
