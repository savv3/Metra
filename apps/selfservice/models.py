"""Personal links that let a member report a reading and check their contact
details without a password.

The token is only ever shown in the link itself (in a letter, SMS or email);
the database keeps its SHA-256 hash, so a copy of the database or a backup
cannot be used to open anyone's page. Links are personal data: they belong to
a person and are covered by the per-person export and erasure tools.
"""

import datetime
import hashlib
import secrets

from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.readings.models import ReadingRound
from apps.register.models import Person, Unit, UnitContact

# 32 random bytes: 256 bits, well above the 128 a link needs.
TOKEN_BYTES = 32

# The contact who gets a unit's link: the owner first, then the billing contact.
ROLE_PREFERENCE = [UnitContact.Role.OWNER, UnitContact.Role.BILLING, UnitContact.Role.CONTACT]


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def primary_contact(unit):
    """The active person a unit's letters and messages go to, or None."""
    contacts = [c for c in unit.unit_contacts.all() if not c.person.is_archived]
    contacts.sort(key=lambda c: ROLE_PREFERENCE.index(c.role))
    return contacts[0].person if contacts else None


def default_expiry(round_=None):
    """The end of the round's last day, or SCR_SELF_SERVICE_LINK_DAYS from now."""
    if round_ is not None:
        end = datetime.datetime.combine(round_.closes_on, datetime.time.max)
        return timezone.make_aware(end)
    return timezone.now() + datetime.timedelta(days=settings.SELF_SERVICE_LINK_DAYS)


class SelfServiceLinkQuerySet(models.QuerySet):
    def active(self):
        return self.filter(revoked=False, expires_at__gt=timezone.now())


class SelfServiceLink(models.Model):
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    unit = models.ForeignKey(
        Unit, verbose_name=_("unit"), on_delete=models.CASCADE, related_name="self_service_links"
    )
    person = models.ForeignKey(
        Person,
        verbose_name=_("person"),
        on_delete=models.CASCADE,
        related_name="self_service_links",
    )
    round = models.ForeignKey(
        ReadingRound,
        verbose_name=_("reading round"),
        on_delete=models.CASCADE,
        related_name="self_service_links",
        null=True,
        blank=True,
    )
    expires_at = models.DateTimeField(_("expires"))
    revoked = models.BooleanField(_("revoked"), default=False)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    last_used_at = models.DateTimeField(_("last opened"), null=True, blank=True)

    objects = SelfServiceLinkQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = _("self-service link")
        verbose_name_plural = _("self-service links")

    def __str__(self):
        label = f"{self.person} – {self.unit}"
        return f"{label} ({self.round})" if self.round_id else label

    @classmethod
    def create_for(cls, unit, person, round_=None, created_by=None, expires_at=None):
        """A new link and its token. Earlier links of the person for the same
        unit and round stop working, so only the newest letter or message counts."""
        cls.objects.active().filter(unit=unit, person=person, round=round_).update(revoked=True)
        token = secrets.token_urlsafe(TOKEN_BYTES)
        link = cls.objects.create(
            token_hash=hash_token(token),
            unit=unit,
            person=person,
            round=round_,
            created_by=created_by,
            expires_at=expires_at or default_expiry(round_),
        )
        return link, token

    @classmethod
    def find(cls, token):
        """The active link for a token, or None (unknown, expired and revoked alike)."""
        if not token or len(token) > 100:
            return None
        return (
            cls.objects.active()
            .select_related("unit", "person", "round__reading_type")
            .filter(token_hash=hash_token(token))
            .first()
        )

    @staticmethod
    def url_for(token):
        return settings.BASE_URL + reverse("selfservice:member", args=[token])

    @property
    def is_active(self):
        return not self.revoked and self.expires_at > timezone.now()

    def get_additional_data(self):
        return {"unit_id": self.unit_id, "person_id": self.person_id}


# The hash is left out of the log; last_used_at changes on every visit and
# visits are logged as views instead.
auditlog.register(SelfServiceLink, exclude_fields=["token_hash", "last_used_at"])
