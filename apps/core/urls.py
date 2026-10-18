from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("robots.txt", views.robots, name="robots"),
    path("logo", views.logo, name="logo"),
    path("favicon.ico", views.favicon, name="favicon"),
]
