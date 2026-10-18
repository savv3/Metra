from django.urls import path

from . import views

app_name = "metra_sms_46elks"

urlpatterns = [path("delivery/<str:secret>/", views.delivery, name="delivery")]
