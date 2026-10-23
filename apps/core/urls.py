from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("status", views.status, name="status"),
    path("robots.txt", views.robots, name="robots"),
    path("logo", views.logo, name="logo"),
    path("settings/", views.settings_page, name="settings"),
    path("favicon.ico", views.favicon, name="favicon"),
]
