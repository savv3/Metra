"""Token authentication, permissions and rate limits for the API."""

import datetime
import hmac
import os

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions, permissions, throttling

from .models import ApiClient, hash_token

DEFAULT_RATE = "120/min"
LAST_USED_EVERY = datetime.timedelta(minutes=1)


class BearerTokenAuthentication(authentication.BaseAuthentication):
    """``Authorization: Bearer <token>``. ``request.auth`` is the ApiClient."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed(_("Give the token after Bearer, without spaces."))
        try:
            token = header[1].decode()
        except UnicodeError:
            raise exceptions.AuthenticationFailed(_("The token is not valid.")) from None
        return self.authenticate_token(token)

    def authenticate_token(self, token):
        # Looking up the hash, not the token, means the time a lookup takes
        # says nothing about how much of a guess was right.
        digest = hash_token(token)
        client = ApiClient.objects.select_related("user").filter(token_hash=digest).first()
        if client is None or not hmac.compare_digest(client.token_hash, digest):
            raise exceptions.AuthenticationFailed(_("The token is not valid."))
        if not client.is_usable:
            raise exceptions.AuthenticationFailed(_("The token has been revoked or has expired."))
        now = timezone.now()
        if client.last_used_at is None or now - client.last_used_at >= LAST_USED_EVERY:
            # A queryset update: no audit entry for every call.
            ApiClient.objects.filter(pk=client.pk).update(last_used_at=now)
            client.last_used_at = now
        return client.user, client

    def authenticate_header(self, request):
        return f'{self.keyword} realm="api"'


class ModelPermissions(permissions.DjangoModelPermissions):
    """The role's model permissions: view_<model> to read, add/change/delete
    to write. A read-only client can never write."""

    perms_map = {
        **permissions.DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
    }

    def has_permission(self, request, view):
        client = request.auth if isinstance(request.auth, ApiClient) else None
        if client and client.read_only and request.method not in permissions.SAFE_METHODS:
            return False
        return super().has_permission(request, view)


class ArchivePermissions(ModelPermissions):
    """For units and people: DELETE archives, which needs change_<model>."""

    perms_map = {
        **ModelPermissions.perms_map,
        "DELETE": ["%(app_label)s.change_%(model_name)s"],
    }


def api_rate():
    return (
        getattr(settings, "METRA_API_RATE", None)
        or os.environ.get("METRA_API_RATE", "").strip()
        or DEFAULT_RATE
    )


class ClientRateThrottle(throttling.UserRateThrottle):
    """Calls per client (its user), METRA_API_RATE, for example 120/min."""

    scope = "metra_api"

    def get_rate(self):
        return api_rate()
