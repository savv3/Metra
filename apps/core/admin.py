from auditlog.mixins import AuditlogHistoryAdminMixin
from django.contrib import admin

from .models import Notice


@admin.register(Notice)
class NoticeAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["text", "level", "starts_at", "ends_at"]
    list_filter = ["level"]
    fields = ["text", "level", "starts_at", "ends_at"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
