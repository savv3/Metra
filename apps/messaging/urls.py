from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("readings/<int:pk>/send/", views.round_send, name="round_send"),
    path("messages/", views.batch_list, name="batch_list"),
    path("messages/new/", views.compose, name="compose"),
    path("units/<int:pk>/message/", views.unit_compose, name="unit_compose"),
    path("messages/new/sms-count/", views.sms_count, name="sms_count"),
    path("messages/<int:pk>/", views.batch_detail, name="batch_detail"),
    path(
        "messages/<int:pk>/files/<int:file_pk>/",
        views.attachment_download,
        name="attachment_download",
    ),
    path("f/<str:token>/", views.files, name="files"),
    path("f/<str:token>/<int:pk>/", views.file_download, name="file_download"),
    path("messages/newsletter/new/", views.newsletter_compose, name="newsletter_compose"),
    path("people/<int:pk>/newsletter/", views.person_consent, name="person_consent"),
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
    path("messages/notices/<int:pk>/end/", views.notice_end, name="notice_end"),
    path("messaging/46elks/delivery/<str:secret>/", views.elks_delivery, name="elks_delivery"),
]
