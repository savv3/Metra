from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings


def is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def requires_two_factor(user):
    """Every user sees members' personal details, so all must use two-factor
    login. METRA_REQUIRE_MFA_FOR=staff limits it to staff and superusers, who
    can open Settings; METRA_REQUIRE_MFA=false turns it off (the default in
    development)."""
    if not settings.REQUIRE_MFA or not user.is_authenticated:
        return False
    return settings.REQUIRE_MFA_FOR == "all" or is_staff(user)


def has_two_factor(user):
    return is_mfa_enabled(user, types=[Authenticator.Type.TOTP])
