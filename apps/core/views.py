import hmac
import mimetypes

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static

from apps.register.models import Organisation

from . import settings_page as settings_menu
from .language import switch_language
from .models import Notice


def home(request):
    """Staff go to the register; everyone else sees the organisation's public
    page, or a plain welcome page when it is switched off."""
    if request.user.is_authenticated:
        return redirect("register:unit_list")
    if switched := switch_language(request):
        return switched
    organisation = Organisation.current()
    if organisation is None or not organisation.public_page:
        return render(request, "core/home.html")
    context = {"organisation": organisation, "notices": Notice.objects.current()}
    return render(request, "core/public.html", context)


def logo(request):
    organisation = Organisation.current()
    if organisation is None or not organisation.logo:
        raise Http404
    content_type = mimetypes.guess_type(organisation.logo.name)[0] or "application/octet-stream"
    response = FileResponse(organisation.logo.open("rb"), content_type=content_type)
    response["Cache-Control"] = "public, max-age=3600"
    return response


def favicon(request):
    """Browsers ask for /favicon.ico even when the page names another icon."""
    return redirect(static("favicon.svg"), permanent=True)


def robots(request):
    """Search engines may index the public page at / and nothing else."""
    organisation = Organisation.current()
    lines = ["User-agent: *"]
    if organisation is not None and organisation.public_page:
        lines.append("Allow: /$")
    lines.append("Disallow: /")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def healthz(request):
    """Used by the Docker health check: the app is up and can reach its database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok", "version": settings.METRA_VERSION})


def _iso(value):
    return value.isoformat() if value else None


def status(request):
    """Version, backup and add-on state for a hosting tool that runs many
    installs (such as metra-admin). Only with the token in METRA_STATUS_TOKEN,
    sent as "Authorization: Bearer <token>"; without that setting the page
    does not exist. Counts and dates only, never personal data."""
    token = settings.STATUS_TOKEN
    if not token:
        raise Http404
    sent = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(sent.encode(), token.encode()):
        return JsonResponse({"error": "forbidden"}, status=403)

    from apps.backups.models import BackupRun
    from apps.plugins import state
    from apps.register.models import Unit
    from apps.setup.models import SetupState

    organisation = Organisation.current()
    setup = SetupState.objects.order_by("pk").first()
    last = BackupRun.objects.filter(finished_at__isnull=False).first()
    last_ok = BackupRun.objects.filter(success=True).first()
    staff = get_user_model().objects.filter(is_active=True, is_staff=True)
    latest_login = staff.exclude(last_login=None).order_by("-last_login").first()
    return JsonResponse(
        {
            "status": "ok",
            "version": settings.METRA_VERSION,
            "organisation": organisation.name if organisation else None,
            "setup_finished": bool(setup and setup.finished_at),
            "addons": {name: state.is_enabled(name) for name in sorted(settings.PLUGIN_APPS)},
            "backup": {
                "last_at": _iso(last.finished_at) if last else None,
                "last_succeeded": last.success if last else None,
                "last_success_at": _iso(last_ok.finished_at) if last_ok else None,
                "last_offsite_at": _iso(last_ok.uploaded_at) if last_ok else None,
            },
            "units": Unit.objects.active().count(),
            "staff_users": staff.count(),
            "last_staff_login_at": _iso(latest_login.last_login) if latest_login else None,
        }
    )


@login_required
def settings_page(request):
    """The Settings page: links to every setting the user may change, grouped
    by task. It needs no single permission of its own; each entry checks the
    one it needs, and a user with none of them is refused."""
    groups = settings_menu.visible_groups(request.user)
    if not groups:
        raise PermissionDenied
    return render(request, "core/settings.html", {"groups": groups})
