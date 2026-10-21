from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.notification_list, name="list"),
    path("notifications/settings/", views.notification_settings, name="settings"),
    path("notifications/read-all/", views.mark_all_read, name="read_all"),
    path("notifications/<int:pk>/open/", views.open_notification, name="open"),
    path("notifications/<int:pk>/read/", views.mark_read, name="read"),
    path("notifications/<int:pk>/unread/", views.mark_unread, name="unread"),
    path("notifications/<int:pk>/dismiss/", views.dismiss, name="dismiss"),
]
