from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import translation

from . import restore


class MaintenanceMiddleware:
    """While a snapshot is being restored, every page says so instead of
    touching the database, which is being replaced."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        static = "/" + settings.STATIC_URL.lstrip("/")
        if restore.in_maintenance() and not request.path.startswith(static):
            # In the visitor's language (from the cookie or the browser), rendered
            # without a request: no context processor may read the database.
            language = translation.get_language_from_request(request)
            with translation.override(language):
                html = render_to_string("backups/maintenance.html", {"language": language})
            response = HttpResponse(html, status=503)
            response["Retry-After"] = "15"
            response["Cache-Control"] = "no-store"
            return response
        return self.get_response(request)
