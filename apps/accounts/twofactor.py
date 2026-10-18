from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings


def is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def requires_two_factor(user):
    """Staff and superusers can open Settings, so they must use two-factor login,
    unless METRA_REQUIRE_MFA turns that off (the default in development)."""
    return settings.REQUIRE_MFA and is_staff(user)


def has_two_factor(user):
    return is_mfa_enabled(user, types=[Authenticator.Type.TOTP])
