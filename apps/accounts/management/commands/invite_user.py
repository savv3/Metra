"""Make a new invitation link for a user who has not chosen a password yet,
for example when the first one expired. Used by hosting tools (such as
metra-admin) to resend the first admin's invitation."""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import invites

from ._invite import report
from ._invite import send as send_link


class Command(BaseCommand):
    help = (
        "Print a new link where a user who has not chosen a password yet chooses one; "
        "with --send also email it to them."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="The user's username (their email).")
        parser.add_argument(
            "--send",
            action="store_true",
            help="Also email the link, when this install's email is set up.",
        )
        parser.add_argument(
            "--json", action="store_true", help="Print the result as JSON for scripts."
        )

    def handle(self, *args, email, send=False, **options):
        username = email.strip().lower()
        user = get_user_model().objects.filter(username__iexact=username, is_active=True).first()
        if user is None:
            raise CommandError(f"There is no active user {username}.")
        if not invites.is_pending(user):
            raise CommandError(f"{username} has already chosen a password.")
        link = invites.make_link(user)
        result = {"username": user.username, "link": link}
        if send:
            result.update(send_link(user, link))
        if options["json"]:
            self.stdout.write(json.dumps(result))
        else:
            report(self.stdout, result)
