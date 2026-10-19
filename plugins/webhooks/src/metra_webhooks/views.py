from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import service
from .forms import EndpointForm
from .models import WebhookDelivery, WebhookEndpoint

PREFIX = "metra_webhooks"


@login_required
@permission_required(f"{PREFIX}.view_webhookendpoint", raise_exception=True)
def endpoint_list(request):
    latest = WebhookDelivery.objects.filter(endpoint=OuterRef("pk")).order_by("-created_at")
    endpoints = WebhookEndpoint.objects.annotate(
        last_status=Subquery(latest.values("status")[:1]),
        last_at=Subquery(latest.values("created_at")[:1]),
    )
    statuses = dict(WebhookDelivery.Status.choices)
    for endpoint in endpoints:
        endpoint.last_status_label = statuses.get(endpoint.last_status, "")
    return render(request, "metra_webhooks/endpoint_list.html", {"endpoints": endpoints})


@login_required
@permission_required(f"{PREFIX}.add_webhookendpoint", raise_exception=True)
def endpoint_create(request):
    form = EndpointForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        endpoint = form.save(commit=False)
        endpoint.created_by = request.user
        endpoint.save()
        messages.success(request, _("The endpoint was added. Copy its secret to the receiver."))
        return redirect(endpoint)
    return render(request, "metra_webhooks/endpoint_form.html", {"form": form, "endpoint": None})


@login_required
@permission_required(f"{PREFIX}.change_webhookendpoint", raise_exception=True)
def endpoint_edit(request, pk):
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk)
    form = EndpointForm(request.POST or None, instance=endpoint)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The endpoint was saved."))
        return redirect(endpoint)
    return render(
        request, "metra_webhooks/endpoint_form.html", {"form": form, "endpoint": endpoint}
    )


@require_POST
@login_required
@permission_required(f"{PREFIX}.change_webhookendpoint", raise_exception=True)
def endpoint_rotate(request, pk):
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk)
    endpoint.rotate_secret()
    messages.success(
        request, _("A new secret was made. Give it to the receiver; the old one no longer works.")
    )
    return redirect(endpoint)


@require_POST
@login_required
@permission_required(f"{PREFIX}.change_webhookendpoint", raise_exception=True)
def endpoint_test(request, pk):
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk)
    service.send_ping(endpoint)
    messages.success(request, _("A test event was sent. The result is on this page."))
    return redirect("metra_webhooks:delivery_list", pk=endpoint.pk)


@login_required
@permission_required(f"{PREFIX}.delete_webhookendpoint", raise_exception=True)
def endpoint_delete(request, pk):
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk)
    if request.method == "POST":
        endpoint.delete()
        messages.success(request, _("The endpoint was deleted."))
        return redirect("metra_webhooks:endpoint_list")
    return render(request, "metra_webhooks/endpoint_confirm_delete.html", {"endpoint": endpoint})


@login_required
@permission_required(f"{PREFIX}.view_webhookdelivery", raise_exception=True)
def delivery_list(request, pk):
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk)
    deliveries = endpoint.deliveries.all()[:100]
    return render(
        request,
        "metra_webhooks/delivery_list.html",
        {"endpoint": endpoint, "deliveries": deliveries},
    )


@require_POST
@login_required
@permission_required(f"{PREFIX}.change_webhookendpoint", raise_exception=True)
def delivery_retry(request, pk, delivery_id):
    delivery = get_object_or_404(
        WebhookDelivery,
        pk=delivery_id,
        endpoint_id=pk,
        status__in=[WebhookDelivery.Status.FAILED, WebhookDelivery.Status.GIVEN_UP],
    )
    service.retry_now(delivery)
    messages.success(request, _("The delivery was sent again."))
    return redirect("metra_webhooks:delivery_list", pk=pk)
