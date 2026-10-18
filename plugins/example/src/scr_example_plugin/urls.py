from django.urls import path

from . import views

app_name = "scr_example_plugin"

urlpatterns = [path("", views.index, name="index")]
