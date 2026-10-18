from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _

from .twofactor import has_two_factor, requires_two_factor


class RequireStaffTwoFactorMiddleware:
    """Send staff who have not set up an authenticator app to do so first.

    Only the account pages (to set up two-factor, change password or log
    out), the language switch, static files and the health check stay open.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if requires_two_factor(request.user) and not self._is_exempt(request.path):
            if not has_two_factor(request.user):
                messages.warning(
                    request,
                    _("Set up two-factor login with an authenticator app before you continue."),
                )
                return redirect("mfa_activate_totp")
        return self.get_response(request)

    @staticmethod
    def _is_exempt(path):
        exempt = [
            "/accounts/",
            reverse("set_language"),
            reverse("core:healthz"),
            "/" + settings.STATIC_URL.lstrip("/"),
        ]
        return any(path.startswith(prefix) for prefix in exempt)
