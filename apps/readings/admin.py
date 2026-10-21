from auditlog.mixins import AuditlogHistoryAdminMixin
from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .models import ReadingRound, ReadingType


@admin.register(ReadingType)
class ReadingTypeAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["name", "unit_type", "unit_label", "decimals", "cumulative", "archived_at"]
    list_filter = ["unit_type", "cumulative"]
    fields = ["name", "unit_type", "unit_label", "decimals", "cumulative", "description"]
    actions = ["archive", "restore"]

    def has_delete_permission(self, request, obj=None):
        # Archived instead, so old rounds and readings keep their meaning.
        return False

    @admin.action(description=_("Archive selected reading types"), permissions=["change"])
    def archive(self, request, queryset):
        for reading_type in queryset.active():
            reading_type.archive()
        messages.success(request, _("Archived."))

    @admin.action(description=_("Restore selected reading types"), permissions=["change"])
    def restore(self, request, queryset):
        for reading_type in queryset.archived():
            reading_type.restore()
        messages.success(request, _("Restored."))


@admin.register(ReadingRound)
class ReadingRoundAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["reading_type", "period_label", "opens_on", "closes_on", "is_draft"]
    list_filter = ["reading_type", "is_draft"]
