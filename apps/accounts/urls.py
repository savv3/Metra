from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("account/", views.profile, name="profile"),
]
