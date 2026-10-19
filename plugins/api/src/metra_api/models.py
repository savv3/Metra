"""API clients: another system that reads or changes the register with a token.

Each client acts as its own Django user, made for it and never able to log in
to the web pages. The user is in exactly one role (Admin, Board, Treasurer,
Read-only), which decides what the client may do. The token is shown once and
only its SHA-256 hash is stored.
"""

import hashlib
import secrets

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

ROLES = ["Admin", "Board", "Treasurer", "Read-only"]
ROLE_CHOICES = [
    ("Admin", _("Admin")),
    ("Board", _("Board")),
    ("Treasurer", _("Treasurer")),
    ("Read-only", _("Read-only")),
]
PREFIX_LENGTH = 8
USERNAME_PREFIX = "api-"


def new_token():
    return secrets.token_urlsafe(32)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


class ApiClient(models.Model):
    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(
        _("description"), blank=True, help_text=_("What the client is and who runs it.")
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="api_client",
        editable=False,
    )
    role = models.CharField(_("role"), max_length=20, choices=ROLE_CHOICES)
    read_only = models.BooleanField(
        _("read only"),
        default=False,
        help_text=_("Refuse every change, whatever the role allows."),
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    token_prefix = models.CharField(_("token starts with"), max_length=PREFIX_LENGTH)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    last_used_at = models.DateTimeField(_("last used"), null=True, blank=True)
    expires_at = models.DateTimeField(_("expires"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("revoked"), null=True, blank=True)

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = _("API client")
        verbose_name_plural = _("API clients")

    def __str__(self):
        return self.name

    @classmethod
    def create(
        cls, *, name, role, created_by=None, read_only=False, description="", expires_at=None
    ):
        """A new client with its own user. Returns (client, token); the token
        is not stored and cannot be shown again."""
        if role not in ROLES:
            raise ValueError(f"Unknown role {role!r}")
        token = new_token()
        with transaction.atomic():
            user = get_user_model()(username=_free_username(name), is_staff=False)
            user.set_unusable_password()
            user.save()
            user.groups.set([Group.objects.get(name=role)])
            client = cls.objects.create(
                name=name,
                description=description,
                user=user,
                role=role,
                read_only=read_only,
                expires_at=expires_at,
                created_by=created_by,
                token_hash=hash_token(token),
                token_prefix=token[:PREFIX_LENGTH],
            )
        return client, token

    def rotate(self):
        """Replace the token; the old one stops working at once. Returns the new one."""
        token = new_token()
        self.token_hash = hash_token(token)
        self.token_prefix = token[:PREFIX_LENGTH]
        self.save(update_fields=["token_hash", "token_prefix"])
        return token

    def revoke(self):
        """Stop the client for good: the token stops working and its user is deactivated."""
        with transaction.atomic():
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])
            self.user.is_active = False
            self.user.save(update_fields=["is_active"])

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_usable(self):
        return not self.is_revoked and not self.is_expired and self.user.is_active


def _free_username(name):
    base = USERNAME_PREFIX + (slugify(name)[:100] or "client")
    username, number = base, 1
    User = get_user_model()
    while User.objects.filter(username=username).exists():
        number += 1
        username = f"{base}-{number}"
    return username


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def keep_client_users_out_of_the_web(sender, instance, **kwargs):
    """A client's user never gets a password or staff status, even if someone
    edits it under Settings, so it can never log in to the web pages."""
    if instance.pk is None or not ApiClient.objects.filter(user_id=instance.pk).exists():
        return
    if instance.has_usable_password():
        instance.set_unusable_password()
    instance.is_staff = False
    instance.is_superuser = False


@receiver(post_delete, sender=ApiClient)
def deactivate_deleted_client_user(sender, instance, **kwargs):
    get_user_model().objects.filter(pk=instance.user_id).update(is_active=False)


# The token hash is left out: the log shows that a token was rotated (the
# prefix changes), never anything that helps to guess it.
auditlog.register(ApiClient, exclude_fields=["token_hash", "last_used_at"])
