import mimetypes

from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static

from apps.register.models import Organisation

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
    return JsonResponse({"status": "ok"})
