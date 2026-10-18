"""Creating links for many units at once, for letters now and messages later."""

from dataclasses import dataclass

from django.db import transaction

from .models import SelfServiceLink, primary_contact


@dataclass
class IssuedLink:
    unit: object
    person: object
    link: SelfServiceLink
    token: str

    @property
    def url(self):
        return SelfServiceLink.url_for(self.token)


def issue_links(units, round_=None, created_by=None):
    """One new link per unit, for its primary contact.

    Returns (issued, skipped): the links with their tokens, which exist only
    here and must be printed or sent now, and the units that have no contact.
    """
    issued, skipped = [], []
    with transaction.atomic():
        for unit in units:
            person = primary_contact(unit)
            if person is None:
                skipped.append(unit)
                continue
            link, token = SelfServiceLink.create_for(unit, person, round_, created_by)
            issued.append(IssuedLink(unit, person, link, token))
    return issued, skipped
