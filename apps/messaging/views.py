from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.models import Notice
from apps.readings.models import ReadingRound

from . import attachments, broadcast, newsletter
from .forms import ConsentForm, MessageForm, NewsletterForm
from .models import Attachment, ConsentRecord, Message, MessageBatch, MessageTemplate
from .providers import elks_callback_secret
from .registry import EMAIL, SMS, provider_for
from .sms import segments
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


@login_required
@permission_required("messaging.send_broadcast", raise_exception=True)
def compose(request):
    """Write a message to many people: edit, then check who gets what, then send."""
    urgent = request.GET.get("urgent") == "1"
    initial = {"filters": request.GET.get("filters", "")}
    if initial["filters"]:
        initial["scope"] = broadcast.FILTERED
    form = MessageForm(
        request.POST or None,
        request.FILES or None,
        initial=initial,
        urgent=urgent,
        can_publish_notice=request.user.has_perm("core.add_notice"),
        user=request.user,
    )
    context = {"form": form, "channels_set_up": channel_status(), "step": "edit"}
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        files = form.save_attachments()
        context["attachments"] = files
        pairs = broadcast.people_for(form.units(), data["contacts"])
        plan = broadcast.plan(pairs, data["channels"])
        if request.POST.get("step") == "confirm" and "edit" not in request.POST:
            if not plan.recipients:
                messages.error(request, _("Nobody can be reached with these choices."))
            else:
                batch = MessageBatch.objects.create(
                    kind=MessageBatch.Kind.ALERT if data["urgent"] else MessageBatch.Kind.BROADCAST,
                    channels=data["channels"],
                    subject=data["subject"],
                    body=data["body"],
                    email_body=data["email_body"],
                    audience=form.audience_label(),
                    recipients=[[p.pk, u.pk] for p, u in pairs],
                    created_by=request.user,
                )
                form.attach(batch, files)
                if data.get("notice"):
                    batch.notice = Notice.objects.create(
                        text=data["notice_text"],
                        level=Notice.Level.URGENT if data["urgent"] else Notice.Level.INFO,
                        ends_at=data.get("notice_until"),
                        created_by=request.user,
                    )
                    batch.save(update_fields=["notice"])
                send_batch_task(batch.pk)
                messages.success(request, _("Sending has started. This page shows how it goes."))
                return redirect(batch)
        if "edit" not in request.POST:
            per_person, total = broadcast.sms_estimate(data["body"], plan, files=bool(files))
            first = plan.recipients[0] if plan.recipients else None
            values = broadcast.placeholders(first and first.person, first and first.unit)
            context |= {
                "example": MessageTemplate.fill(data["body"], values),
                "example_for": first.person if first else None,
                "step": "confirm",
                "plan": plan,
                "sms_count": plan.count(SMS),
                "email_count": plan.count(EMAIL),
                "sms_per_person": per_person,
                "sms_total": total,
                "audience": form.audience_label(),
            }
    return render(request, "messaging/compose.html", context)


@login_required
@permission_required("messaging.send_broadcast", raise_exception=True)
def sms_count(request):
    """The live "1 SMS, 42 of 160 characters" line under the message box (HTMX)."""
    text = MessageTemplate.fill(request.GET.get("body", ""), broadcast.placeholders())
    count, used, per_sms = segments(text)
    return render(
        request,
        "messaging/_sms_count.html",
        {"count": count, "used": used, "per_sms": per_sms},
    )


@login_required
@permission_required("core.change_notice", raise_exception=True)
@require_POST
def notice_end(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    if notice.is_current:
        notice.end_now()
    messages.success(request, _("The notice is no longer shown."))
    batch = notice.batches.first()
    return redirect(batch or "messaging:batch_list")


@login_required
@permission_required("messaging.send_newsletter", raise_exception=True)
def newsletter_compose(request):
    """Write a newsletter, see who gets it, and send it to those who said yes."""
    form = NewsletterForm(request.POST or None, request.FILES or None, user=request.user)
    people = list(newsletter.recipients())
    context = {"form": form, "count": len(people), "email": channel_status()["email"]}
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        files = form.save_attachments()
        context["attachments"] = files
        if request.POST.get("step") == "confirm" and "edit" not in request.POST and people:
            batch = MessageBatch.objects.create(
                kind=MessageBatch.Kind.NEWSLETTER,
                channels=MessageBatch.Channels.EMAIL,
                subject=data["subject"],
                body=data["subject"],
                email_body=data["body"],
                audience=_("Everyone who wants the newsletter"),
                recipients=[[person.pk, None] for person in people],
                created_by=request.user,
            )
            form.attach(batch, files)
            send_batch_task(batch.pk)
            messages.success(request, _("Sending has started. This page shows how it goes."))
            return redirect(batch)
        if "edit" not in request.POST:
            first = people[0] if people else None
            values = broadcast.placeholders(first)
            context |= {
                "step": "confirm",
                "example_for": first,
                "example": MessageTemplate.fill(data["body"], values)
                + (newsletter.footer(first) if first else ""),
            }
    return render(request, "messaging/newsletter_compose.html", context)


@login_required
@permission_required("register.change_person", raise_exception=True)
@require_POST
def person_consent(request, pk):
    from apps.register.models import Person

    person = get_object_or_404(Person, pk=pk)
    form = ConsentForm(request.POST)
    if form.is_valid():
        ConsentRecord.record(
            person,
            form.cleaned_data["subscribed"],
            ConsentRecord.Source.STAFF,
            by=request.user,
            note=form.cleaned_data["note"],
        )
        messages.success(request, _("Saved the newsletter choice."))
    return redirect(person.get_absolute_url() + "#newsletter")


@csrf_exempt
def unsubscribe(request, token):
    """The link at the end of every newsletter. Opening it asks for a click (so
    mail scanners that open links do not unsubscribe anyone); mail programs'
    one-click unsubscribe posts here directly (RFC 8058), without a CSRF token."""
    from apps.core.language import switch_language
    from apps.register.models import Organisation

    if switched := switch_language(request):
        return switched
    person = newsletter.person_for_token(token)
    context = {"organisation": Organisation.current(), "person": person, "done": False}
    if person is not None and request.method == "POST":
        ConsentRecord.record(person, False, ConsentRecord.Source.UNSUBSCRIBE_LINK)
        context["done"] = True
    status = 200 if person is not None else 404
    response = render(request, "messaging/unsubscribe.html", context, status=status)
    response["Referrer-Policy"] = "same-origin"
    return response


def _download(attachment):
    response = FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=attachment.name,
        content_type=attachment.content_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@permission_required("messaging.view_messagebatch", raise_exception=True)
def attachment_download(request, pk, file_pk):
    attachment = get_object_or_404(Attachment, pk=file_pk, batch_id=pk)
    return _download(attachment)


def files(request, token):
    """The page an SMS links to: the files sent with that message. No login,
    like a self-service link; the link expires."""
    from apps.register.models import Organisation

    batch = attachments.batch_for_token(token)
    if batch is None:
        return render(
            request,
            "messaging/files_unavailable.html",
            {"organisation": Organisation.current()},
            status=404,
        )
    return render(
        request,
        "messaging/files.html",
        {
            "batch": batch,
            "token": token,
            "files": batch.attachments.all(),
            "organisation": Organisation.current(),
        },
    )


def file_download(request, token, pk):
    batch = attachments.batch_for_token(token)
    if batch is None:
        raise Http404
    return _download(get_object_or_404(Attachment, pk=pk, batch=batch))
