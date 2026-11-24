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
from django.utils.translation import ngettext

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
    # A short state shown beside the link, such as "Bank account missing":
    # a function returning (text, "ok" | "warn"), or None when there is
    # nothing to say.
    status: object = None

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


# Each group's icon on the Settings page, a name from the main menu's icons.
ICONS = {
    "organisation": "building",
    "register": "home",
    "readings": "gauge",
    "invoicing": "invoice",
    "messages": "mail",
    "users": "people",
    "integrations": "box",
    "backups": "server",
    "setup": "list",
    "advanced": "settings",
}


@dataclass
class Link:
    url: str
    label: str
    description: str = ""
    status: tuple | None = None  # (text, "ok" | "warn")


def _organisation_status():
    from apps.register.models import Organisation

    organisation = Organisation.current()
    if organisation is None or not organisation.name:
        return (_("Not filled in"), "warn")
    return None


def _billing_status():
    from apps.invoicing.models import BillingSettings

    billing = BillingSettings.objects.order_by("pk").first()
    if billing is None or not billing.iban:
        return (_("Bank account missing"), "warn")
    return None


def _email_status():
    from apps.messaging import email_config

    if not email_config.current().from_is_set:
        return (_("From address missing"), "warn")
    return None


def _users_status():
    from django.contrib.auth import get_user_model

    count = get_user_model().objects.filter(is_active=True).count()
    return (ngettext("%(count)s user", "%(count)s users", count) % {"count": count}, "")


def _plugins_status():
    from django.conf import settings

    from apps.plugins import state

    count = sum(1 for name in settings.PLUGIN_APPS if state.is_enabled(name))
    return (ngettext("%(count)s on", "%(count)s on", count) % {"count": count}, "")


def _backups_status():
    from django.utils import formats, timezone

    from apps.backups.models import BackupRun

    last = BackupRun.objects.filter(success=True).order_by("-started_at").first()
    if last is None:
        return (_("No backup yet"), "warn")
    when = timezone.localtime(last.finished_at or last.started_at)
    return (formats.date_format(when, "SHORT_DATETIME_FORMAT"), "ok")


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
                    status=_organisation_status,
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
                    status=_billing_status,
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
                    _("Email"),
                    _("How email is sent: the mail server or service, and the from address."),
                    "messaging:email_settings",
                    "messaging.change_emailsettings",
                    status=_email_status,
                ),
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
                    status=_users_status,
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
                    status=_plugins_status,
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
                    status=_backups_status,
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
    """[(group, [Link, ...])] the user may use; empty groups left out."""
    if not user.is_authenticated:
        return []
    result = []
    for group in _groups():
        links = [
            Link(e.href(), e.label, e.description, e.status() if e.status else None)
            for e in group.entries
            if e.allowed(user)
        ]
        links += [Link(*link) for link in settings_links(user, group=group.key)]
        if links:
            group.icon = ICONS.get(group.key, "settings")
            result.append((group, links))
    return result


def can_open(user):
    """Whether the Settings page has anything for the user (without building its links)."""
    if not user.is_authenticated:
        return False
    if any(e.allowed(user) for group in _groups() for e in group.entries):
        return True
    return bool(settings_links(user))
