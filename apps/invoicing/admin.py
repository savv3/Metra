from auditlog.mixins import AuditlogHistoryAdminMixin
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import BillingSettings, FeeLine, FeePlan, FeeTier, Invoice


@admin.register(BillingSettings)
class BillingSettingsAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    fieldsets = [
        (_("VAT"), {"fields": ["vat_registered", "default_vat_rate", "vat_exemption_text"]}),
        (_("Payment"), {"fields": ["iban", "bic", "payment_terms_days", "late_interest_text"]}),
        (_("Numbering"), {"fields": ["number_prefix", "next_number"]}),
        (_("Invoice text"), {"fields": ["footer"]}),
    ]

    def has_add_permission(self, request):
        return not BillingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class FeeLineInline(admin.StackedInline):
    model = FeeLine
    extra = 0
    fields = [
        ("kind", "order"),
        "description",
        ("unit_price", "quantity", "unit_label", "vat_rate"),
        "reading_type",
        ("condition_field", "condition_value"),
        "tiers_link",
    ]
    readonly_fields = ["tiers_link"]

    @admin.display(description=_("price tiers"))
    def tiers_link(self, line):
        if not line.pk or line.kind != FeeLine.Kind.USAGE:
            return "–"
        count = line.tiers.count()
        url = f"../../../feeline/{line.pk}/change/"
        return format_html(
            '<a href="{}">{}</a>', url, _("Edit tiers (%(count)s)") % {"count": count}
        )


@admin.register(FeePlan)
class FeePlanAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["name", "unit_type", "tag", "active"]
    list_filter = ["active", "unit_type"]
    inlines = [FeeLineInline]


class FeeTierInline(admin.TabularInline):
    model = FeeTier
    extra = 1


@admin.register(FeeLine)
class FeeLineAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    """Reached from a fee plan, to set a usage fee's price tiers."""

    show_auditlog_history_link = True
    list_display = ["description", "plan", "kind", "unit_price", "vat_rate"]
    list_filter = ["plan", "kind"]
    inlines = [FeeTierInline]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """A read-only list: invoices are made, changed and issued on the Invoices pages."""

    list_display = ["__str__", "unit", "person", "issue_date", "total", "status"]
    list_filter = ["status", "kind", "run"]
    search_fields = ["number", "unit__name", "person__last_name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
