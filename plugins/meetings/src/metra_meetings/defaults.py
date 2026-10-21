"""The agenda templates a new installation starts with, which admins then adapt."""

from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

# (name, kind, items). Usual items under the Finnish Associations Act; each
# association adapts them to its own rules.
TEMPLATES = [
    (
        gettext_noop("Annual meeting"),
        "annual",
        [
            gettext_noop("Opening of the meeting"),
            gettext_noop(
                "Election of a chair, a secretary, two minute checkers and two vote counters"
            ),
            gettext_noop("Establishing that the meeting is lawful and has a quorum"),
            gettext_noop("Approval of the agenda"),
            gettext_noop("The annual report, the accounts and the auditor's report"),
            gettext_noop("Adoption of the accounts and discharge from liability for the board"),
            gettext_noop("The plan of action, the budget and the fees for the coming year"),
            gettext_noop("Election of the board"),
            gettext_noop("Election of the auditor"),
            gettext_noop("Other matters"),
            gettext_noop("Closing of the meeting"),
        ],
    ),
    (
        gettext_noop("Board meeting"),
        "board",
        [
            gettext_noop("Opening of the meeting"),
            gettext_noop("Establishing that the meeting is lawful and has a quorum"),
            gettext_noop("Approval of the agenda"),
            gettext_noop("The minutes of the previous meeting"),
            gettext_noop("Other matters"),
            gettext_noop("Next meeting"),
            gettext_noop("Closing of the meeting"),
        ],
    ),
]


def create(model, language=None):
    """Add the usual templates, in the installation's language, unless any
    template exists. ``model`` is AgendaTemplate (or a migration's copy)."""
    if model.objects.exists():
        return
    with translation.override(language or settings.LANGUAGE_CODE):
        for name, kind, items in TEMPLATES:
            model.objects.create(
                name=_(name), kind=kind, items="\n".join(_(item) for item in items)
            )
