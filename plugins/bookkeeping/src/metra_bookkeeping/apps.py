from pathlib import Path

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BookkeepingConfig(AppConfig):
    name = "metra_bookkeeping"
    verbose_name = _("Bookkeeping")
    description = _("Double-entry books with vouchers, journal and ledger, under Finnish rules.")
    default_auto_field = "django.db.models.BigAutoField"

    # Voucher descriptions and receipts can name people (a member paid, a
    # supplier's invoice). They are bookkeeping material, kept for the legal
    # period and left out of erasure.
    personal_data = [
        "Vouchers: descriptions and attached receipts, which may name people",
    ]
    # The plugin API versions (apps.plugins.api.API_VERSION) this plugin works with.
    metra_api = [1]

    def ready(self):
        from apps.plugins import api

        api.add_navigation(
            api.NavItem(
                _("Bookkeeping"), "metra_bookkeeping:index", "metra_bookkeeping.view_voucher"
            )
        )
        api.add_help_articles(
            api.HelpArticles(
                str(Path(__file__).parent / "help"),
                order=["bookkeeping"],
                pages={"metra_bookkeeping": "bookkeeping"},
            )
        )

    def turn_off_refused(self):
        """Books with posted vouchers are kept, and kept readable, for the
        legal period (KPL 2:10), so the add-on stays on once it has them."""
        from .models import Voucher

        if Voucher.objects.filter(status=Voucher.Status.POSTED).exists():
            return _(
                "The books have posted vouchers, which must be kept readable for the legal "
                "period, so bookkeeping stays on."
            )
        return None
