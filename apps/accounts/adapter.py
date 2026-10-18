from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from django.urls import reverse

from .twofactor import requires_two_factor


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Accounts are created by an admin under Settings, never by visitors."""
        return False

    def get_login_redirect_url(self, request):
        """An admin of an installation not set up yet starts in the setup wizard."""
        from apps.setup.models import needs_setup

        if needs_setup(request.user):
            return reverse("setup:start")
        return super().get_login_redirect_url(request)


class MFAAdapter(DefaultMFAAdapter):
    def can_delete_authenticator(self, authenticator):
        """Staff must keep two-factor on; they can replace it, not remove it."""
        return not requires_two_factor(authenticator.user)
