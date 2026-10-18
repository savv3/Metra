from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter

from .twofactor import requires_two_factor


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Accounts are created by an admin under Settings, never by visitors."""
        return False


class MFAAdapter(DefaultMFAAdapter):
    def can_delete_authenticator(self, authenticator):
        """Staff must keep two-factor on; they can replace it, not remove it."""
        return not requires_two_factor(authenticator.user)
