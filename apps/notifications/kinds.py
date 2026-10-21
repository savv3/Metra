"""The kinds of notification: what each says, who gets it by default, and
whether it is on before a user chooses.

Core kinds are listed here; plugins add theirs with
``api.add_notification_kind``. A notification stores its kind's name and
parameters, and its text is made from the kind's message when it is shown,
in the reader's language.
"""

from dataclasses import dataclass, field

from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy

from apps.plugins.hooks import NOTIFICATION_KINDS, hooks


@dataclass
class Kind:
    """A kind of notification.

    ``name`` is a stable slug such as "backup_failed". ``label`` is shown on
    the notification settings page. ``message`` is the text, with
    ``%(name)s`` parameters filled from the notification's params; for a
    count use ``ngettext_lazy(singular, plural, "count")``. ``variants`` are
    other messages of the same kind, chosen with ``params["variant"]``.
    ``roles`` get it when ``notify`` names no users or roles. Only users with
    ``permission`` (one name, or a list that all must be held) get it, and
    only when they have not turned it off; a kind with ``default_on=False``
    is sent only to users who turned it on.
    """

    name: str
    label: str
    message: str
    roles: list = field(default_factory=list)
    permission: str | list | tuple = ""
    default_on: bool = True
    variants: dict = field(default_factory=dict)

    @property
    def permissions(self):
        if not self.permission:
            return []
        return [self.permission] if isinstance(self.permission, str) else list(self.permission)

    def allowed(self, user):
        return user.has_perms(self.permissions)


CORE = [
    Kind(
        "backup_failed",
        _("A snapshot failed"),
        _("A snapshot failed: %(error)s"),
        roles=["Admin"],
        permission="backups.view_backuprun",
        variants={"offsite": _("A snapshot could not be sent offsite: %(error)s")},
    ),
    Kind(
        "backup_done",
        _("The nightly snapshot was taken"),
        _("The nightly snapshot was taken."),
        roles=["Admin"],
        permission="backups.view_backuprun",
        default_on=False,
    ),
    Kind(
        "restore_done",
        _("A snapshot was restored"),
        _("The snapshot %(snapshot)s was restored by %(user)s."),
        roles=["Admin"],
        permission="backups.view_backuprun",
    ),
    Kind(
        "restore_failed",
        _("A restore failed"),
        _("Restoring %(snapshot)s failed, so the data from before it was put back: %(error)s"),
        roles=["Admin"],
        permission="backups.view_backuprun",
    ),
    Kind(
        "messages_failed",
        _("SMS or email could not be delivered"),
        ngettext_lazy(
            "%(count)s message in a send-out could not be delivered.",
            "%(count)s messages in a send-out could not be delivered.",
            "count",
        ),
        roles=["Admin"],
        permission="messaging.view_messagebatch",
    ),
    Kind(
        "self_service_change",
        _("Members sent in a reading or a change through their link"),
        ngettext_lazy(
            "A member sent in a reading or a change through their link.",
            "Members sent in %(count)s readings or changes through their links.",
            "count",
        ),
        roles=["Admin", "Board"],
        permission=[
            "selfservice.view_selfservicelink",
            "register.view_person",
            "auditlog.view_logentry",
        ],
    ),
    Kind(
        "invoices_overdue",
        _("Invoices became overdue"),
        ngettext_lazy(
            "%(count)s invoice became overdue.",
            "%(count)s invoices became overdue.",
            "count",
        ),
        roles=["Admin", "Treasurer"],
        permission="invoicing.view_invoice",
    ),
]


def register(kind):
    """Add a kind (for plugins, through ``api.add_notification_kind``)."""
    return hooks.register(NOTIFICATION_KINDS, kind)


def all_kinds():
    """Every kind by name: the core ones, then those plugins added. A plugin
    cannot replace a core kind or one added before it."""
    found = {}
    for kind in [*CORE, *hooks.get(NOTIFICATION_KINDS)]:
        found.setdefault(kind.name, kind)
    return found


def get(name):
    return all_kinds().get(name)
