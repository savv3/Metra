"""What the Settings page offers, grouped by task.

Each entry links to the page where the setting is edited, often the admin's
own change form, and is shown only to users who may use it. Entries that
open the admin also need staff status, since the admin lets in no one else.
The register's main pages (units, people, invoices, send-outs) are in the
menu and not repeated here.
"""

from dataclasses import dataclass, field

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.plugins.templatetags.plugins import settings_links


@dataclass
class Entry:
    label: str
    description: str
    url: object  # a URL name, or a function returning the URL
    permission: str = ""
    admin: bool = False  # opens the admin, which needs staff status
    # Only superusers and users with the Admin role, such as the full admin.
    admins_only: bool = False

    def allowed(self, user):
        if self.admins_only and not (
            user.is_superuser or user.groups.filter(name="Admin").exists()
        ):
            return False
        if self.admin and not (user.is_active and user.is_staff):
            return False
        return not self.permission or user.has_perm(self.permission)

    def href(self):
        return self.url() if callable(self.url) else reverse(self.url)


@dataclass
class Group:
    key: str
    title: str
    entries: list = field(default_factory=list)


def _single(model, admin_name):
    """The change form of a model that has one row, or its add form before it exists."""

    def url():
        obj = model.objects.order_by("pk").first()
        if obj is None:
            return reverse(f"admin:{admin_name}_add")
        return reverse(f"admin:{admin_name}_change", args=[obj.pk])

    return url


def _person_fields():
    return reverse("admin:register_customfield_changelist") + "?target__exact=person"


def _groups():
    from apps.invoicing.models import BillingSettings
    from apps.register.models import Organisation

    return [
        Group(
            "organisation",
            _("Organisation"),
            [
                Entry(
                    _("Organisation details"),
                    _("Name, business ID, contact details, logo and the public page."),
                    _single(Organisation, "register_organisation"),
                    "register.change_organisation",
                    admin=True,
                ),
            ],
        ),
        Group(
            "register",
            _("Register"),
            [
                Entry(
                    _("Unit types and their fields"),
                    _("The kinds of units in the register and the fields each one has."),
                    "admin:register_unittype_changelist",
                    "register.change_unittype",
                    admin=True,
                ),
                Entry(
                    _("Person fields"),
                    _("Extra fields on every person, besides name and contact details."),
                    _person_fields,
                    "register.change_customfield",
                    admin=True,
                ),
                Entry(
                    _("Tags"),
                    _("Labels for grouping units and people, for example for send-outs."),
                    "admin:register_tag_changelist",
                    "register.change_tag",
                    admin=True,
                ),
            ],
        ),
        Group(
            "readings",
            _("Readings"),
            [
                Entry(
                    _("Reading types"),
                    _("What is read, for which unit type, and in which unit."),
                    "admin:readings_readingtype_changelist",
                    "readings.change_readingtype",
                    admin=True,
                ),
            ],
        ),
        Group(
            "invoicing",
            _("Invoicing"),
            [
                Entry(
                    _("Invoice settings"),
                    _("Bank account, payment terms, VAT, numbering and reminders."),
                    _single(BillingSettings, "invoicing_billingsettings"),
                    "invoicing.change_billingsettings",
                    admin=True,
                ),
                Entry(
                    _("Fee plans"),
                    _("What units pay: fixed fees and usage fees, with their fee lines."),
                    "admin:invoicing_feeplan_changelist",
                    "invoicing.change_feeplan",
                    admin=True,
                ),
            ],
        ),
        Group(
            "messages",
            _("Messages"),
            [
                Entry(
                    _("Message templates"),
                    _("The texts of invoices, reminders, reading requests and other messages."),
                    "admin:messaging_messagetemplate_changelist",
                    "messaging.change_messagetemplate",
                    admin=True,
                ),
                Entry(
                    _("Notices"),
                    _("Short notices on the public page and members' pages."),
                    "admin:core_notice_changelist",
                    "core.change_notice",
                    admin=True,
                ),
                Entry(
                    _("Newsletter consents"),
                    _("The record of who subscribed to or unsubscribed from the newsletter."),
                    "admin:messaging_consentrecord_changelist",
                    "messaging.view_consentrecord",
                    admin=True,
                ),
            ],
        ),
        Group(
            "users",
            _("Users and roles"),
            [
                Entry(
                    _("Users"),
                    _("Who can log in, and the role each one has."),
                    "admin:auth_user_changelist",
                    "auth.change_user",
                    admin=True,
                ),
                Entry(
                    _("Roles"),
                    _("What each role may see and do."),
                    "admin:auth_group_changelist",
                    "auth.change_group",
                    admin=True,
                ),
            ],
        ),
        Group(
            "integrations",
            _("Integrations"),
            [
                Entry(
                    _("Add-ons"),
                    _("Turn add-ons on or off, and their settings."),
                    "plugins:list",
                    "plugins.change_pluginstate",
                    admins_only=True,
                ),
            ],
        ),
        Group(
            "backups",
            _("Backups"),
            [
                Entry(
                    _("Backups"),
                    _("Snapshots of the register, here and offsite, and restoring one."),
                    "backups:list",
                    "backups.view_backuprun",
                ),
            ],
        ),
        Group(
            "setup",
            _("Setup wizard"),
            [
                Entry(
                    _("Run the setup wizard"),
                    _(
                        "Organisation, language, logo, units and fields, email and SMS, "
                        "invoices and the board, step by step."
                    ),
                    "setup:start",
                    "setup.run_setup",
                ),
            ],
        ),
        Group(
            "advanced",
            _("Advanced"),
            [
                Entry(
                    _("All data tables"),
                    _("The full Django admin, with every table. For technical changes."),
                    "admin:index",
                    admins_only=True,
                    admin=True,
                ),
            ],
        ),
    ]


def visible_groups(user):
    """[(group, [(url, label, description), ...])] the user may use; empty groups left out."""
    if not user.is_authenticated:
        return []
    result = []
    for group in _groups():
        links = [(e.href(), e.label, e.description) for e in group.entries if e.allowed(user)]
        if group.key == "integrations":
            links += settings_links(user)
        if links:
            result.append((group, links))
    return result


def can_open(user):
    """Whether the Settings page has anything for the user (without building its links)."""
    if not user.is_authenticated:
        return False
    if any(e.allowed(user) for group in _groups() for e in group.entries):
        return True
    return bool(settings_links(user))
