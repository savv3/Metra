from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.setup import demo


class Command(BaseCommand):
    help = (
        "On a demo site (METRA_DEMO=true), delete everything and load the made-up "
        "demo data and the demo/demo login again. The worker runs this every night. "
        "Refuses to run on any other install."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-new",
            action="store_true",
            help="Only reset a demo site that has no demo account yet (used on start); "
            "do nothing when METRA_DEMO is off.",
        )

    def handle(self, *args, **options):
        if options["if_new"]:
            if not settings.DEMO or demo.has_demo_account():
                return
        try:
            demo.reset(stdout=self.stdout)
        except demo.NotADemo as error:
            raise CommandError(str(error)) from None
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo site reset. Log in as {settings.DEMO_USERNAME} / {settings.DEMO_PASSWORD}."
            )
        )
