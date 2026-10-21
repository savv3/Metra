"""Periodic readings: what is read (a reading type), when (a round) and the
value each unit reported, such as a household's water meter once a year."""

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from apps.register.models import Archivable, Person, Unit, UnitType


class ReadingType(Archivable):
    """Something read periodically from units of one type, e.g. a water meter.

    Set up by an admin under Settings. Archived instead of deleted, so old
    rounds and readings keep their meaning.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)
    unit_type = models.ForeignKey(
        UnitType,
        verbose_name=_("unit type"),
        on_delete=models.PROTECT,
        related_name="reading_types",
        help_text=_("The kind of unit that reports this reading."),
    )
    unit_label = models.CharField(
        _("unit of measure"), max_length=20, blank=True, help_text=_("For example m³ or kWh.")
    )
    decimals = models.PositiveSmallIntegerField(
        _("decimals"), default=0, validators=[MaxValueValidator(3)]
    )
    cumulative = models.BooleanField(
        _("cumulative meter"),
        default=False,
        help_text=_(
            "The value is a meter position that only grows. Usage is the value minus "
            "the previous reading."
        ),
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("reading type")
        verbose_name_plural = _("reading types")

    def __str__(self):
        return self.name


class ReadingRoundQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_draft=False)

    def open_now(self):
        """Published rounds whose dates include today."""
        today = timezone.localdate()
        return self.published().filter(opens_on__lte=today, closes_on__gte=today)

    def in_state(self, state):
        """Rounds in one of the states of ``ReadingRound.State``."""
        today = timezone.localdate()
        if state == ReadingRound.State.DRAFT:
            return self.filter(is_draft=True)
        published = self.published()
        if state == ReadingRound.State.UPCOMING:
            return published.filter(opens_on__gt=today)
        if state == ReadingRound.State.OPEN:
            return published.filter(opens_on__lte=today, closes_on__gte=today)
        if state == ReadingRound.State.CLOSED:
            return published.filter(closes_on__lt=today)
        return self.none()


class ReadingRound(models.Model):
    """One collection of a reading type, e.g. the water meter readings for 2026.

    A published round is open between its dates; a draft is never open."""

    class State(models.TextChoices):
        DRAFT = "draft", _("Draft")
        UPCOMING = "upcoming", _("Not yet open")
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")

    reading_type = models.ForeignKey(
        ReadingType,
        verbose_name=_("reading type"),
        on_delete=models.PROTECT,
        related_name="rounds",
    )
    period_label = models.CharField(
        _("period"), max_length=50, help_text=_("Shown to members, for example 2026.")
    )
    opens_on = models.DateField(_("opens"))
    closes_on = models.DateField(_("closes"))
    is_draft = models.BooleanField(
        _("draft"),
        default=True,
        help_text=_(
            "A draft is never open. Clear this to publish the round: it then opens and "
            "closes on its dates."
        ),
    )
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)

    objects = ReadingRoundQuerySet.as_manager()

    class Meta:
        ordering = ["-opens_on", "-pk"]
        verbose_name = _("reading round")
        verbose_name_plural = _("reading rounds")
        constraints = [
            models.UniqueConstraint(
                fields=["reading_type", "period_label"], name="unique_round_period"
            ),
        ]

    def __str__(self):
        return f"{self.reading_type} {self.period_label}"

    def get_absolute_url(self):
        return reverse("readings:round_detail", args=[self.pk])

    def clean(self):
        if self.opens_on and self.closes_on and self.closes_on < self.opens_on:
            raise ValidationError({"closes_on": _("The round closes before it opens.")})

    @property
    def state(self):
        """Draft, not yet open, open or closed, worked out from the flag and the dates."""
        if self.is_draft:
            return self.State.DRAFT
        today = timezone.localdate()
        if today < self.opens_on:
            return self.State.UPCOMING
        if today > self.closes_on:
            return self.State.CLOSED
        return self.State.OPEN

    @property
    def status(self):
        """The state as a plain value for the API: draft, upcoming, open or closed."""
        return self.state.value

    @property
    def state_label(self):
        """The state in words, with the date that matters: when it opens or closes."""
        state = self.state
        if state == self.State.UPCOMING:
            return _("Opens %(date)s") % {"date": date_format(self.opens_on, "SHORT_DATE_FORMAT")}
        if state == self.State.OPEN:
            return _("Open until %(date)s") % {
                "date": date_format(self.closes_on, "SHORT_DATE_FORMAT")
            }
        return state.label

    @property
    def accepts_member_readings(self):
        """Members can submit or change their reading while the round is open."""
        return self.state == self.State.OPEN

    def expected_units(self):
        """Units that should report: active units of the type, plus any that did."""
        return Unit.objects.filter(
            models.Q(
                unit_type_id=self.reading_type.unit_type_id,
                archived_at__isnull=True,
                status=Unit.Status.ACTIVE,
            )
            | models.Q(readings__round=self)
        ).distinct()

    def earlier_rounds(self):
        """Rounds of the same type that opened before this one, newest first."""
        return ReadingRound.objects.filter(
            models.Q(opens_on__lt=self.opens_on) | models.Q(opens_on=self.opens_on, pk__lt=self.pk),
            reading_type_id=self.reading_type_id,
        ).order_by("-opens_on", "-pk")


class Reading(models.Model):
    """The value one unit reported in one round."""

    class Source(models.TextChoices):
        STAFF = "staff", _("Staff")
        MEMBER = "member", _("Member")

    round = models.ForeignKey(
        ReadingRound, verbose_name=_("round"), on_delete=models.PROTECT, related_name="readings"
    )
    unit = models.ForeignKey(
        Unit, verbose_name=_("unit"), on_delete=models.PROTECT, related_name="readings"
    )
    value = models.DecimalField(_("value"), max_digits=15, decimal_places=3)
    source = models.CharField(
        _("source"), max_length=10, choices=Source.choices, default=Source.STAFF
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("entered by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    submitted_by_person = models.ForeignKey(
        Person,
        verbose_name=_("reported by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("The member who reported it through a self-service link."),
    )
    submitted_at = models.DateTimeField(_("submitted"), default=timezone.now)
    note = models.TextField(_("note"), blank=True)

    class Meta:
        ordering = ["round", "unit"]
        verbose_name = _("reading")
        verbose_name_plural = _("readings")
        constraints = [
            models.UniqueConstraint(fields=["unit", "round"], name="unique_reading_per_round"),
        ]

    def __str__(self):
        return f"{self.unit} – {self.round}"

    def get_additional_data(self):
        """Stored with each audit entry, so a unit's readings history can be found."""
        return {"unit_id": self.unit_id, "round_id": self.round_id}


auditlog.register(ReadingType, exclude_fields=["created_at", "updated_at"])
auditlog.register(ReadingRound, exclude_fields=["created_at", "updated_at"])
auditlog.register(Reading)
