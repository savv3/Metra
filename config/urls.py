from allauth.account.decorators import secure_admin_login
from django.contrib import admin
from django.urls import include, path

# Settings uses the app's login page, so admins pass two-factor there too.
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.register.urls")),
    path("", include("apps.readings.urls")),
    path("", include("apps.selfservice.urls")),
    path("", include("apps.core.urls")),
]
