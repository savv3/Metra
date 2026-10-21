from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.plugins import url_patterns

# Settings uses the app's login page, so admins pass two-factor there too.
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.register.urls")),
    path("", include("apps.readings.urls")),
    path("", include("apps.selfservice.urls")),
    path("", include("apps.messaging.urls")),
    path("", include("apps.invoicing.urls")),
    path("", include("apps.banking.urls")),
    path("", include("apps.setup.urls")),
    path("", include("apps.backups.urls")),
    path("", include("apps.help.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.core.urls")),
]

# Enabled plugins' pages, each under its own /plugins/<name>/ prefix.
urlpatterns += url_patterns(settings.PLUGIN_APPS)
