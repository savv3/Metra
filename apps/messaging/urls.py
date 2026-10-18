from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("readings/<int:pk>/send/", views.round_send, name="round_send"),
    path("messages/", views.batch_list, name="batch_list"),
    path("messages/new/", views.compose, name="compose"),
    path("messages/new/sms-count/", views.sms_count, name="sms_count"),
    path("messages/<int:pk>/", views.batch_detail, name="batch_detail"),
    path("messages/notices/<int:pk>/end/", views.notice_end, name="notice_end"),
    path("messaging/46elks/delivery/<str:secret>/", views.elks_delivery, name="elks_delivery"),
]
