from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("readings/<int:pk>/send/", views.round_send, name="round_send"),
    path("messages/", views.batch_list, name="batch_list"),
    path("messages/<int:pk>/", views.batch_detail, name="batch_detail"),
    path("messaging/46elks/delivery/<str:secret>/", views.elks_delivery, name="elks_delivery"),
]
