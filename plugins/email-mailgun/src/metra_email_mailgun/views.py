import hashlib
import hmac
import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.plugins import api

from .providers import NAME, config, message_id

# Mailgun's event: what Metra records (failed only when it is permanent).
EVENTS = {"delivered": api.DELIVERED, "failed": api.BOUNCED, "complained": api.COMPLAINED}


def signed(signature, key):
    """True when Mailgun signed the webhook with the domain's signing key.
    A replayed event records the same thing again, so old ones are accepted."""
    if not key or not isinstance(signature, dict):
        return False
    text = f"{signature.get('timestamp', '')}{signature.get('token', '')}"
    expected = hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature.get("signature", "")))


def reason(data):
    status = data.get("delivery-status") or {}
    text = status.get("description") or status.get("message") or data.get("reason") or ""
    return " ".join(str(text).split())[:300]


@csrf_exempt
@require_POST
def events(request):
    """Mailgun's webhooks (delivered, permanent failure, spam complaint) post
    here. No login: Mailgun's signature is the check."""
    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    if not isinstance(payload, dict) or not signed(
        payload.get("signature"), config()["webhook_key"]
    ):
        # 406 tells Mailgun not to retry.
        return HttpResponse(status=406)
    data = payload.get("event-data") or {}
    event = EVENTS.get(data.get("event"))
    if event == api.BOUNCED and data.get("severity") != "permanent":
        event = None  # Mailgun is still retrying
    if event:
        headers = (data.get("message") or {}).get("headers") or {}
        api.record_email_event(NAME, message_id(headers.get("message-id")), event, reason(data))
    # Unknown messages and events are acknowledged too, so Mailgun stops sending them.
    return HttpResponse("")
