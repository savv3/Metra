"""The register: configurable record types, the units registered under them,
the people you contact, and the roles that link the two."""

import os

from auditlog.registry import auditlog
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

COUNTRY_CHOICES = [
    ("FI", _("Finland")),
    ("AX", _("Åland")),
    ("SE", _("Sweden")),
    ("NO", _("Norway")),
    ("DK", _("Denmark")),
    ("IS", _("Iceland")),
]


LOGO_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
LOGO_MAX_BYTES = 1024 * 1024


def validate_logo(file):
    """PNG, JPEG or WebP up to 1 MB, checked by content, not only by name.
    (No SVG: it can carry scripts.)"""
    extension = os.path.splitext(file.name)[1].lower()
    if extension not in LOGO_TYPES:
        raise ValidationError(_("Upload a PNG, JPEG or WebP image."))
    if file.size > LOGO_MAX_BYTES:
        raise ValidationError(_("The image is larger than 1 MB."))
    head = file.read(12)
    file.seek(0)
    if not (
        head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"\xff\xd8\xff")
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    ):
        raise ValidationError(_("The file is not a PNG, JPEG or WebP image."))


class Organisation(models.Model):
    """The company or association running this installation. One row.

    The "public" fields are shown to anyone on the public page at /, on
    member pages and in letters: organisation data only, never personal data.
    """

    name = models.CharField(_("name"), max_length=200)
    business_id = models.CharField(_("business ID"), max_length=50, blank=True)
    vat_number = models.CharField(_("VAT number"), max_length=50, blank=True)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=50, blank=True)
    street_address = models.CharField(_("street address"), max_length=200, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=20, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    country = models.CharField(_("country"), max_length=2, choices=COUNTRY_CHOICES, default="FI")
    # Public contact information
    public_page = models.BooleanField(
        _("show the public page"),
        default=True,
        help_text=_("A page at the site's address with the details below, for anyone to see."),
    )
    display_name = models.CharField(
        _("public name"), max_length=200, blank=True, help_text=_("If different from the name.")
    )
    description = models.TextField(
        _("short description"), blank=True, help_text=_("A few sentences about what you do.")
    )
    website = models.URLField(_("website"), blank=True)
    emergency_phone = models.CharField(
        _("emergency phone"),
        max_length=50,
        blank=True,
        help_text=_("For urgent matters, also outside opening hours."),
    )
    opening_hours = models.TextField(
        _("opening hours or availability"),
        blank=True,
        help_text=_("For example: Weekdays 9–16. Calls answered evenings in emergencies."),
    )
    logo = models.FileField(
        _("logo"),
        upload_to="organisation/",
        blank=True,
        validators=[validate_logo],
        help_text=_("PNG, JPEG or WebP, up to 1 MB."),
    )

    class Meta:
        verbose_name = _("organisation")
        verbose_name_plural = _("organisation")

    def __str__(self):
        return self.name

    @classmethod
    def current(cls):
        return cls.objects.order_by("pk").first()

    @property
    def public_name(self):
        return self.display_name or self.name


class Tag(models.Model):
    name = models.CharField(_("name"), max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("tag")
        verbose_name_plural = _("tags")

    def __str__(self):
        return self.name


class UnitType(models.Model):
    """A kind of record an organisation keeps, such as "Household" or "Member"."""

    name = models.CharField(_("name"), max_length=100, unique=True)
    name_plural = models.CharField(
        _("plural name"),
        max_length=100,
        blank=True,
        help_text=_(
            'For example "Households". Used in the menu and headings when this is '
            "the only unit type. Empty means the general word for units is used."
        ),
    )
    description = models.TextField(_("description"), blank=True)
    order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("unit type")
        verbose_name_plural = _("unit types")

    def __str__(self):
        return self.name


class CustomField(models.Model):
    """An admin-defined field shown on units of one type, or on every person."""

    class Target(models.TextChoices):
        UNIT = "unit", _("Unit")
        PERSON = "person", _("Person")

    class FieldType(models.TextChoices):
        TEXT = "text", _("Text")
        NUMBER = "number", _("Number")
        DATE = "date", _("Date")
        CHOICE = "choice", _("Choice")
        BOOLEAN = "boolean", _("Yes/no")

    target = models.CharField(_("applies to"), max_length=10, choices=Target.choices)
    unit_type = models.ForeignKey(
        UnitType,
        verbose_name=_("unit type"),
        on_delete=models.CASCADE,
        related_name="custom_fields",
        null=True,
        blank=True,
    )
    key = models.SlugField(
        _("key"),
        max_length=50,
        help_text=_("Short identifier used in CSV files and the API, e.g. meter_number."),
    )
    label = models.CharField(_("label"), max_length=100)
    field_type = models.CharField(
        _("field type"), max_length=10, choices=FieldType.choices, default=FieldType.TEXT
    )
    choices = models.TextField(
        _("choices"), blank=True, help_text=_("For choice fields: one option per line.")
    )
    required = models.BooleanField(_("required"), default=False)
    help_text = models.CharField(_("help text"), max_length=200, blank=True)
    order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["order", "label"]
        verbose_name = _("custom field")
        verbose_name_plural = _("custom fields")
        constraints = [
            models.UniqueConstraint(
                fields=["unit_type", "key"],
                condition=models.Q(target="unit"),
                name="unique_unit_custom_field_key",
            ),
            models.UniqueConstraint(
                fields=["key"],
                condition=models.Q(target="person"),
                name="unique_person_custom_field_key",
            ),
        ]

    def __str__(self):
        return self.label

    def clean(self):
        if self.target == self.Target.UNIT and self.unit_type_id is None:
            raise ValidationError({"unit_type": _("Choose the unit type this field belongs to.")})
        if self.target == self.Target.PERSON and self.unit_type_id is not None:
            raise ValidationError({"unit_type": _("Person fields apply to everyone.")})
        if self.field_type == self.FieldType.CHOICE and not self.choice_list:
            raise ValidationError({"choices": _("Add at least one option.")})

    @property
    def choice_list(self):
        return [line.strip() for line in self.choices.splitlines() if line.strip()]


class ArchivableQuerySet(models.QuerySet):
    def active(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)


class Archivable(models.Model):
    """Records are archived, not deleted, so history and invoices keep their links.
    Erasing personal data is a separate, deliberate privacy action."""

    archived_at = models.DateTimeField(_("archived"), null=True, blank=True)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)

    objects = ArchivableQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_archived(self):
        return self.archived_at is not None

    def archive(self):
        self.archived_at = timezone.now()
        self.save(update_fields=["archived_at", "updated_at"])

    def restore(self):
        self.archived_at = None
        self.save(update_fields=["archived_at", "updated_at"])


class Address(models.Model):
    street_address = models.CharField(_("street address"), max_length=200, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=20, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    country = models.CharField(_("country"), max_length=2, choices=COUNTRY_CHOICES, default="FI")

    class Meta:
        abstract = True

    @property
    def address_line(self):
        place = " ".join(part for part in [self.postal_code, self.city] if part)
        return ", ".join(part for part in [self.street_address, place] if part)


class Person(Archivable, Address):
    class Channel(models.TextChoices):
        EMAIL = "email", _("Email")
        SMS = "sms", _("SMS")
        POST = "post", _("Post")

    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100, blank=True)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=50, blank=True)
    preferred_channel = models.CharField(
        _("preferred channel"), max_length=10, choices=Channel.choices, default=Channel.EMAIL
    )
    notes = models.TextField(_("notes"), blank=True)
    custom_data = models.JSONField(_("custom fields"), default=dict, blank=True)
    tags = models.ManyToManyField(Tag, verbose_name=_("tags"), blank=True, related_name="people")
    # Set when the email provider reports that mail to ``email`` bounced
    # (see apps.messaging.delivery_reports); cleared when the address changes.
    email_bounced_at = models.DateTimeField(_("email bounced"), null=True, blank=True)
    email_bounce_reason = models.CharField(_("bounce reason"), max_length=300, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = _("person")
        verbose_name_plural = _("people")

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        # A new address has not bounced.
        if self.email_bounced_at and self.pk:
            before = Person.objects.filter(pk=self.pk).values_list("email", flat=True).first()
            if before is not None and before.lower() != self.email.lower():
                self.email_bounced_at, self.email_bounce_reason = None, ""
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = {
                        *kwargs["update_fields"],
                        "email_bounced_at",
                        "email_bounce_reason",
                    }
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("register:person_detail", args=[self.pk])

    @property
    def full_name(self):
        return " ".join(part for part in [self.first_name, self.last_name] if part)


class Unit(Archivable, Address):
    """One registered thing: a household, a member, a client company."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")

    unit_type = models.ForeignKey(
        UnitType, verbose_name=_("type"), on_delete=models.PROTECT, related_name="units"
    )
    name = models.CharField(_("name"), max_length=200)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    start_date = models.DateField(_("start date"), null=True, blank=True)
    end_date = models.DateField(_("end date"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    custom_data = models.JSONField(_("custom fields"), default=dict, blank=True)
    tags = models.ManyToManyField(Tag, verbose_name=_("tags"), blank=True, related_name="units")
    contacts = models.ManyToManyField(
        Person, through="UnitContact", related_name="units", verbose_name=_("contacts")
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("unit")
        verbose_name_plural = _("units")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("register:unit_detail", args=[self.pk])

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": _("The end date is before the start date.")})


class UnitContact(models.Model):
    """Links a person to a unit with a role, e.g. the owner of a household."""

    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        BILLING = "billing", _("Billing contact")
        CONTACT = "contact", _("Contact")

    unit = models.ForeignKey(
        Unit, verbose_name=_("unit"), on_delete=models.CASCADE, related_name="unit_contacts"
    )
    person = models.ForeignKey(
        Person, verbose_name=_("person"), on_delete=models.CASCADE, related_name="unit_contacts"
    )
    role = models.CharField(_("role"), max_length=10, choices=Role.choices, default=Role.CONTACT)

    class Meta:
        ordering = ["role", "person__last_name", "person__first_name"]
        verbose_name = _("contact")
        verbose_name_plural = _("contacts")
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "person", "role"], name="unique_unit_person_role"
            ),
        ]

    def __str__(self):
        return f"{self.person} ({self.get_role_display()}) – {self.unit}"

    def get_additional_data(self):
        """Stored with each audit entry so it shows on the unit's and the person's history."""
        return {"unit_id": self.unit_id, "person_id": self.person_id}


# Every change to register data is logged with who made it. The timestamps
# are left out: they change on every save and the log has its own.
TIMESTAMPS = ["created_at", "updated_at"]
auditlog.register(Organisation)
auditlog.register(Tag)
auditlog.register(UnitType)
auditlog.register(CustomField)
auditlog.register(Person, exclude_fields=TIMESTAMPS, m2m_fields={"tags"})
auditlog.register(Unit, exclude_fields=TIMESTAMPS, m2m_fields={"tags"})
auditlog.register(UnitContact)
