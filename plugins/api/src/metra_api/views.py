"""Staff pages: the API clients and a list of the endpoints."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import ApiClientForm
from .models import ApiClient


@login_required
@permission_required("metra_api.view_apiclient", raise_exception=True)
def client_list(request):
    clients = ApiClient.objects.select_related("user", "created_by")
    return render(request, "metra_api/client_list.html", {"clients": clients})


def _show_token(request, client, token):
    response = render(request, "metra_api/client_token.html", {"client": client, "token": token})
    # The token is shown once: never keep the page in a cache.
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@login_required
@permission_required("metra_api.add_apiclient", raise_exception=True)
def client_create(request):
    form = ApiClientForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        client, token = ApiClient.create(
            name=data["name"],
            description=data["description"],
            role=data["role"],
            read_only=data["read_only"],
            expires_at=form.expires_at(),
            created_by=request.user,
        )
        return _show_token(request, client, token)
    return render(request, "metra_api/client_form.html", {"form": form})


@never_cache
@login_required
@permission_required("metra_api.change_apiclient", raise_exception=True)
@require_POST
def client_rotate(request, pk):
    client = get_object_or_404(ApiClient, pk=pk, revoked_at__isnull=True)
    return _show_token(request, client, client.rotate())


@login_required
@permission_required("metra_api.change_apiclient", raise_exception=True)
@require_POST
def client_revoke(request, pk):
    client = get_object_or_404(ApiClient, pk=pk)
    if not client.is_revoked:
        client.revoke()
        messages.success(
            request, _("Revoked %(name)s. Its token no longer works.") % {"name": client}
        )
    return redirect("metra_api:client_list")


# What each group of endpoints is for, on the docs page.
RESOURCES = {
    "units": gettext_lazy("Units: list, read, add, change; DELETE archives."),
    "people": gettext_lazy("People: list, read, add, change; DELETE archives."),
    "unit-contacts": gettext_lazy("Who is linked to which unit, and in what role."),
    "unit-types": gettext_lazy("Unit types and their custom fields. Read only."),
    "person-fields": gettext_lazy("The custom fields people have. Read only."),
    "reading-rounds": gettext_lazy("Reading rounds. Read only."),
    "readings": gettext_lazy("Readings: list, read, enter and correct."),
    "invoices": gettext_lazy("Invoices and credit notes, with their lines. Read only."),
    "payments": gettext_lazy("Payments recorded on invoices. Read only."),
}
METHODS = ["get", "post", "put", "patch", "delete"]


@login_required
@permission_required("metra_api.view_apiclient", raise_exception=True)
def docs(request):
    from drf_spectacular.generators import SchemaGenerator

    from .urls import API_PREFIX

    schema = SchemaGenerator(patterns=None).get_schema(request=None, public=True)
    endpoints = []
    for path, operations in schema["paths"].items():
        resource = path.removeprefix(API_PREFIX).strip("/").split("/")[0]
        endpoints.append(
            {
                "path": path,
                "methods": [method.upper() for method in METHODS if method in operations],
                "description": RESOURCES.get(resource, "") if path.count("{") == 0 else "",
            }
        )
    return render(request, "metra_api/docs.html", {"endpoints": endpoints})
