"""Set up a new install from the command line: the organisation's name and
its first admin, who gets a one-time link to choose a password. Used by
hosting tools (such as metra-admin) right after the first migrate."""

import json

from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.urls import reverse

from apps.register.models import Organisation


class Command(BaseCommand):
    help = (
        "Name the organisation and create its first admin. Prints a link where the "
        "admin chooses a password; it works for a few days and only once."
    )

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="The organisation's name.")
        parser.add_argument("--admin-email", required=True, help="Also the admin's username.")
        parser.add_argument("--admin-first-name", default="")
        parser.add_argument("--admin-last-name", default="")
        parser.add_argument(
            "--json", action="store_true", help="Print the result as JSON for scripts."
        )

    @transaction.atomic
    def handle(self, *args, name, admin_email, admin_first_name, admin_last_name, **options):
        name = name.strip()
        email = admin_email.strip().lower()
        if not name:
            raise CommandError("--name must not be empty.")
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError(f"{email!r} is not an email address.") from error
        User = get_user_model()
        if User.objects.filter(is_staff=True).exists():
            raise CommandError("This install already has an admin; nothing changed.")
        if User.objects.filter(username=email).exists():
            raise CommandError(f"A user {email} already exists; nothing changed.")

        organisation = Organisation.current() or Organisation()
        organisation.name = name
        organisation.save()

        user = User(
            username=email,
            email=email,
            first_name=admin_first_name.strip(),
            last_name=admin_last_name.strip(),
            is_staff=True,
        )
        user.set_unusable_password()
        user.save()
        user.groups.add(Group.objects.get(name="Admin"))

        path = reverse(
            "account_reset_password_from_key",
            kwargs={
                "uidb36": user_pk_to_url_str(user),
                "key": default_token_generator.make_token(user),
            },
        )
        link = settings.BASE_URL.rstrip("/") + path
        if options["json"]:
            self.stdout.write(json.dumps({"organisation": name, "username": email, "link": link}))
        else:
            self.stdout.write(f"Created {name} with the admin {email}.")
            self.stdout.write(f"Choose a password here: {link}")
