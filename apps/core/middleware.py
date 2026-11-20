from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from apps.register.models import Organisation


class NoIndexMiddleware:
    """Ask search engines not to index any page except the public page at /."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if "X-Robots-Tag" not in response and not self._indexable(request, response):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @staticmethod
    def _indexable(request, response):
        if request.path != "/" or response.status_code != 200 or request.user.is_authenticated:
            return False
        organisation = Organisation.current()
        return organisation is not None and organisation.public_page


class DemoMiddleware:
    """On a demo site, keep the shared demo account usable for the next visitor.

    Nobody may change passwords, two-factor login, email addresses, users or
    roles there: one visitor could otherwise lock everyone out until the
    nightly reset. Everything else can be tried.
    """

    LOCKED = (
        "/accounts/password/",
        "/accounts/2fa/",
        "/accounts/email/",
        "/admin/auth/",
        "/admin/mfa/",
        "/admin/account/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEMO:
            from apps.setup.demo import forget_old_database

            forget_old_database()
        if (
            settings.DEMO
            and request.method not in ("GET", "HEAD", "OPTIONS")
            and request.path.startswith(self.LOCKED)
        ):
            messages.info(request, _("Accounts and passwords cannot be changed on the demo site."))
            return redirect("accounts:profile")
        return self.get_response(request)
