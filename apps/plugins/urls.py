from django.urls import path

from . import views

app_name = "plugins"

urlpatterns = [
    path("settings/plugins/", views.plugin_list, name="list"),
    path("settings/plugins/<str:name>/", views.plugin_settings, name="settings"),
    path("settings/plugins/<str:name>/turn/", views.plugin_toggle, name="toggle"),
]
