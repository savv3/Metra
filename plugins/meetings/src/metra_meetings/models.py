"""Meetings, their agenda, attendance, minutes and the checkers' approvals.

Approved minutes are the association's records: once every minute checker
has approved them, nothing in the meeting changes any more (the models refuse
it). Until then, any change to the minutes clears the approvals given so far,
so checkers always approve what the minutes now say.
"""

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MinutesLocked(ValidationError):
    """The meeting's minutes are approved and can no longer change."""

    def __init__(self):
        super().__init__(_("The minutes are approved and can no longer be changed."))


def user_name(user):
    """How a user is named in the minutes."""
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


class Meeting(models.Model):
    class Kind(models.TextChoices):
        ANNUAL = "annual", _("Annual meeting")
        EXTRAORDINARY = "extraordinary", _("Extraordinary meeting")
        BOARD = "board", _("Board meeting")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Being prepared")
        CALLED = "called", _("Called")
        HELD = "held", _("Held")
        APPROVED = "approved", _("Minutes approved")

    kind = models.CharField(_("kind"), max_length=20, choices=Kind.choices, default=Kind.ANNUAL)
    title = models.CharField(_("title"), max_length=200)
    starts_at = models.DateTimeField(_("date and time"))
    place = models.CharField(_("place"), max_length=200, blank=True)
    notes = models.TextField(
        _("other information"),
        blank=True,
        help_text=_("Shown in the notice and on the agenda, for example how to attend online."),
    )
    votes_by_unit = models.BooleanField(
        _("one vote per unit"),
        default=True,
        help_text=_(
            "Each unit has one vote, carried by one of the people present for it. "
            "Otherwise everyone present has a vote."
        ),
    )
    members_can_read = models.BooleanField(
        _("show the approved minutes to members"),
        default=True,
        help_text=_("On the members' personal pages, once the minutes are approved."),
    )
    chair = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("chair"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    secretary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("secretary"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    checkers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("minute checkers"),
        blank=True,
        related_name="meetings_to_check",
        help_text=_("They approve the minutes in Metra. Everyone listed must approve."),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    approved_at = models.DateTimeField(_("minutes approved"), null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        ordering = ["-starts_at", "-pk"]
        verbose_name = _("meeting")
        verbose_name_plural = _("meetings")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk and Meeting.objects.filter(pk=self.pk, status=self.Status.APPROVED).exists():
            raise MinutesLocked()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("metra_meetings:meeting_detail", args=[self.pk])

    def delete(self, *args, **kwargs):
        self.check_open()
        return super().delete(*args, **kwargs)

    @property
    def chair_name(self):
        return user_name(self.chair)

    @property
    def secretary_name(self):
        return user_name(self.secretary)

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    def check_open(self):
        """Raise MinutesLocked when the minutes are approved."""
        if Meeting.objects.filter(pk=self.pk, status=self.Status.APPROVED).exists():
            raise MinutesLocked()

    # Attendance and votes.

    def total_votes(self):
        return sum(a.votes for a in self.attendances.all())

    # Approval.

    def approvals_by_checker(self):
        return {a.checker_id: a for a in self.approvals.select_related("checker")}

    def missing_approvals(self):
        """The checkers who have not approved yet."""
        approved = set(self.approvals.values_list("checker_id", flat=True))
        return [c for c in self.checkers.all() if c.pk not in approved]

    def can_be_approved_by(self, user):
        return (
            self.status == self.Status.HELD
            and self.checkers.filter(pk=user.pk).exists()
            and not self.approvals.filter(checker=user).exists()
        )

    def approve(self, user):
        """Record ``user``'s approval; the minutes are approved (and locked)
        when every checker has approved. Returns True when that happened."""
        if not self.can_be_approved_by(user):
            raise ValidationError(_("You cannot approve these minutes."))
        Approval.objects.create(meeting=self, checker=user)
        if self.checkers.exists() and not self.missing_approvals():
            self.status = self.Status.APPROVED
            self.approved_at = timezone.now()
            self.save(update_fields=["status", "approved_at"])
            return True
        return False

    def minutes_changed(self):
        """The minutes changed: approvals given so far no longer count.
        Returns how many were removed."""
        self.check_open()
        removed = 0
        for approval in self.approvals.all():
            approval.delete()
            removed += 1
        return removed


class AgendaItem(models.Model):
    """A paragraph (§) of the meeting: on the agenda before, with minutes and
    a decision after."""

    meeting = models.ForeignKey(
        Meeting, verbose_name=_("meeting"), on_delete=models.CASCADE, related_name="items"
    )
    order = models.PositiveSmallIntegerField(
        _("order"), default=0, help_text=_("Items are listed from the lowest number.")
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(
        _("description"), blank=True, help_text=_("Shown on the agenda sent with the notice.")
    )
    minutes = models.TextField(_("minutes"), blank=True, help_text=_("What was discussed."))
    decision = models.TextField(_("decision"), blank=True)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = _("agenda item")
        verbose_name_plural = _("agenda items")
        # Removing an item is part of changing the agenda: it needs the
        # change permission, so there is no delete permission.
        default_permissions = ("add", "change", "view")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.meeting.check_open()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.meeting.check_open()
        return super().delete(*args, **kwargs)


class Attendance(models.Model):
    """Someone from the register present at the meeting. The name and unit are
    kept as they were, so approved minutes stay as approved even if the
    register changes later."""

    meeting = models.ForeignKey(
        Meeting, verbose_name=_("meeting"), on_delete=models.CASCADE, related_name="attendances"
    )
    person = models.ForeignKey(
        "register.Person",
        verbose_name=_("person"),
        null=True,
        on_delete=models.SET_NULL,
        related_name="meeting_attendances",
    )
    unit = models.ForeignKey(
        "register.Unit",
        verbose_name=_("unit"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="meeting_attendances",
        help_text=_("The unit the person represents, if any."),
    )
    name = models.CharField(_("name"), max_length=200, editable=False)
    unit_name = models.CharField(_("unit name"), max_length=200, blank=True, editable=False)
    votes = models.PositiveSmallIntegerField(_("votes"), default=1)
    proxy = models.CharField(
        _("proxy"),
        max_length=200,
        blank=True,
        help_text=_("If the person attends for someone else, for whom and how it was shown."),
    )

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = _("attendance")
        verbose_name_plural = _("attendance")
        # Removing someone is part of keeping the attendance: it needs the
        # change permission, so there is no delete permission.
        default_permissions = ("add", "change", "view")
        constraints = [
            models.UniqueConstraint(fields=["meeting", "person"], name="unique_meeting_person"),
        ]

    def __str__(self):
        return f"{self.name} – {self.meeting}"

    def save(self, *args, **kwargs):
        self.meeting.check_open()
        if self.person_id:
            self.name = self.person.full_name
        self.unit_name = self.unit.name if self.unit_id else ""
        super().save(*args, **kwargs)

    def get_additional_data(self):
        """Stored with each audit entry, so it can be found by person and unit."""
        return {"person_id": self.person_id, "unit_id": self.unit_id}

    def delete(self, *args, **kwargs):
        self.meeting.check_open()
        return super().delete(*args, **kwargs)


class Approval(models.Model):
    """A minute checker approved the minutes."""

    meeting = models.ForeignKey(
        Meeting, verbose_name=_("meeting"), on_delete=models.CASCADE, related_name="approvals"
    )
    checker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("minute checker"),
        on_delete=models.PROTECT,
        related_name="+",
    )
    approved_at = models.DateTimeField(_("approved"), default=timezone.now)

    class Meta:
        ordering = ["approved_at", "pk"]
        verbose_name = _("approval")
        verbose_name_plural = _("approvals")
        # Approvals are given through the approve page, by checkers only.
        default_permissions = ("view",)
        constraints = [
            models.UniqueConstraint(fields=["meeting", "checker"], name="unique_meeting_checker"),
        ]

    def __str__(self):
        return f"{self.checker} – {self.meeting}"

    def delete(self, *args, **kwargs):
        self.meeting.check_open()
        return super().delete(*args, **kwargs)


auditlog.register(Meeting, m2m_fields={"checkers"})
auditlog.register(AgendaItem)
auditlog.register(Attendance)
auditlog.register(Approval)
