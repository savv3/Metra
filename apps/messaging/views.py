from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.readings.models import ReadingRound

from .models import Message, MessageBatch
from .providers import elks_callback_secret
from .registry import EMAIL, SMS, provider_for
from .tasks import send_batch_task


def channel_status():
    """Which channels this installation can send on, for the send buttons."""
    return {
        "sms": settings.MESSAGING["sms_provider"] if provider_for(SMS) else "",
        "email": settings.MESSAGING["email_provider"] if provider_for(EMAIL) else "",
    }


@login_required
@permission_required(
    ["messaging.add_messagebatch", "selfservice.add_selfservicelink"], raise_exception=True
)
@require_POST
def round_send(request, pk):
    """Send a round's links, or a reminder to units still missing a reading."""
    round_ = get_object_or_404(ReadingRound, pk=pk)
    kind = request.POST.get("kind")
    if kind == MessageBatch.Kind.REMINDER:
        scope = MessageBatch.Scope.MISSING
    elif kind == MessageBatch.Kind.LINKS:
        scope = request.POST.get("scope")
        if scope not in MessageBatch.Scope.values:
            scope = MessageBatch.Scope.ALL
    else:
        raise Http404
    batch = MessageBatch.objects.create(
        kind=kind, scope=scope, round=round_, created_by=request.user
    )
    send_batch_task(batch.pk)
    messages.success(request, _("Sending has started. This page shows how it goes."))
    return redirect(batch)


@login_required
@permission_required("messaging.view_messagebatch", raise_exception=True)
def batch_list(request):
    batches = MessageBatch.objects.select_related("round", "created_by").annotate(
        total=Count("messages")
    )[:100]
    return render(request, "messaging/batch_list.html", {"batches": batches})


@login_required
@permission_required(
    ["messaging.view_messagebatch", "messaging.view_message"], raise_exception=True
)
def batch_detail(request, pk):
    batch = get_object_or_404(MessageBatch.objects.select_related("round"), pk=pk)
    batch_messages = batch.messages.select_related("person", "unit").order_by("unit__name")
    counts = dict(batch.messages.values_list("status").annotate(n=Count("pk")))
    to_print = [m for m in batch_messages if m.status == Message.Status.TO_PRINT]
    context = {
        "batch": batch,
        "batch_messages": batch_messages,
        "counts": [(label, counts.get(value, 0)) for value, label in Message.Status.choices],
        "to_print": to_print,
    }
    return render(request, "messaging/batch_detail.html", context)


@csrf_exempt
@require_POST
def elks_delivery(request, secret):
    """46elks reports here whether an SMS was delivered (the "whendelivered" URL)."""
    if not constant_time_compare(secret, elks_callback_secret()):
        raise Http404
    provider_id = request.POST.get("id", "")
    status = {"delivered": Message.Status.DELIVERED, "failed": Message.Status.FAILED}.get(
        request.POST.get("status", "")
    )
    if provider_id and status:
        Message.objects.filter(channel=SMS, provider="46elks", provider_id=provider_id).update(
            status=status, status_changed_at=timezone.now()
        )
    # 46elks retries anything but 200, so unknown ids are acknowledged too.
    return HttpResponse("")
