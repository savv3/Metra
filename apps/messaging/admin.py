from auditlog.mixins import AuditlogHistoryAdminMixin
from django.contrib import admin

from .models import Message, MessageBatch, MessageTemplate


@admin.register(MessageTemplate)
class MessageTemplateAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["purpose", "channel", "subject"]


class ReadOnlyAdmin(admin.ModelAdmin):
    """Messages are a record of what was sent; they are not edited by hand."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MessageBatch)
class MessageBatchAdmin(ReadOnlyAdmin):
    list_display = ["__str__", "status", "created_by", "created_at"]
    list_filter = ["kind", "status"]


@admin.register(Message)
class MessageAdmin(ReadOnlyAdmin):
    list_display = ["channel", "recipient", "person", "status", "sent_at"]
    list_filter = ["channel", "status", "provider"]
    search_fields = ["recipient", "person__first_name", "person__last_name"]
