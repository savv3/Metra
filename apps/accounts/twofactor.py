from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled


def requires_two_factor(user):
    """Staff and superusers can open Settings, so they must use two-factor login."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def has_two_factor(user):
    return is_mfa_enabled(user, types=[Authenticator.Type.TOTP])
