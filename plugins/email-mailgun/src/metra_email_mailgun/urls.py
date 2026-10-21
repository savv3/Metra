from django.urls import path

from . import views

app_name = "metra_email_mailgun"

urlpatterns = [path("events/", views.events, name="events")]
