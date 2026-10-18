from django.contrib import admin

from .models import BackupRun


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    list_display = ["started_at", "success", "archive_name", "size", "target", "trigger"]
    list_filter = ["success", "trigger"]

    # The list is a record of what happened; it is not edited by hand.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
