"""Invitations: a new user gets an email with a one-time link where they
choose their own password, so no password is ever made up for them or sent
by email. Staff set up two-factor login right after (the middleware sends
them there). A link works for a few days (PASSWORD_RESET_TIMEOUT) and stops
working once the password is chosen; a new one can be sent while the user
has not chosen a password yet."""

from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.messaging.registry import EMAIL, provider_for
from apps.register.models import Organisation

from .twofactor import requires_two_factor


def is_pending(user):
    """True while the user has not chosen a password yet."""
    return not user.has_usable_password()


def make_link(user, request=None):
    """A new one-time link for choosing a password."""
    path = reverse(
        "account_reset_password_from_key",
        kwargs={
            "uidb36": user_pk_to_url_str(user),
            "key": default_token_generator.make_token(user),
        },
    )
    if request is not None:
        return request.build_absolute_uri(path)
    return settings.BASE_URL.rstrip("/") + path


def email_set_up():
    return provider_for(EMAIL) is not None


def send(user, link, inviter=""):
    """Email the invitation. False when email is not set up; a failure to
    send raises the provider's ProviderError."""
    provider = provider_for(EMAIL)
    if provider is None:
        return False
    organisation = Organisation.current()
    values = {
        "name": user.first_name or user.get_username(),
        "organisation": organisation.public_name if organisation else _("Metra"),
        "username": user.get_username(),
        "link": link,
        "inviter": inviter,
    }
    subject = _("Your account for %(organisation)s") % values
    if inviter:
        opening = _("%(inviter)s has made you an account for %(organisation)s in Metra.") % values
    else:
        opening = _("You have an account for %(organisation)s in Metra.") % values
    body = (
        _("Hello %(name)s,") % values
        + "\n\n"
        + opening
        + " "
        + _("Your username is %(username)s.") % values
        + "\n\n"
        + _("Choose your password here:\n%(link)s") % values
        + "\n\n"
        + _(
            "The link works for a few days and only once. If it has stopped working, "
            "ask for a new one."
        )
    )
    if requires_two_factor(user):
        body += "\n\n" + _(
            "After choosing your password you set up two-factor login with an "
            "authenticator app on your phone."
        )
    provider.send(user.email, body, subject=subject)
    return True
