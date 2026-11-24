from auditlog.mixins import AuditlogHistoryAdminMixin
from django.contrib import admin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from .models import Notice

# Shown in the admin's index to superusers only. The others reach settings
# from the Settings page, and these are either technical or have their own
# pages in the menu (units, people, invoices, send-outs, backups).
HIDDEN_FROM_STAFF = {
    "account.emailaddress",
    "auditlog.logentry",
    "backups.backuprun",
    "invoicing.invoice",
    "messaging.message",
    "messaging.messagebatch",
    "mfa.authenticator",
    "readings.readinground",
    "register.person",
    "register.unit",
}
_get_app_list = admin.site.get_app_list


def get_app_list(request, app_label=None):
    app_list = _get_app_list(request, app_label)
    if request.user.is_superuser:
        return app_list
    for app in app_list:
        app["models"] = [
            model
            for model in app["models"]
            if f"{app['app_label']}.{model['object_name'].lower()}" not in HIDDEN_FROM_STAFF
        ]
    return [app for app in app_list if app["models"]]


admin.site.get_app_list = get_app_list
admin.site.site_header = "Metra"
admin.site.site_title = "Metra"
admin.site.index_title = _("All data tables")
# Settings open admin pages one at a time from Metra's Settings page; the
# admin's own list of every table would lead people away from it.
admin.site.enable_nav_sidebar = False


class BackToSettingsMixin:
    """For settings kept in one row (organisation, invoice settings): after
    saving, go back to Metra's Settings page instead of the admin's list."""

    def _back(self, request, obj):
        # The admin has already said what was saved.
        if "_continue" in request.POST or "_addanother" in request.POST:
            return None
        return redirect("core:settings")

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        return self._back(request, obj) or response

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue)
        return self._back(request, obj) or response


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
