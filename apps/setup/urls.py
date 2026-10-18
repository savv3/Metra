from django.urls import path

from . import views

app_name = "setup"

urlpatterns = [
    path("setup/", views.start, name="start"),
    path("setup/done/", views.done, name="done"),
    path("setup/finish/", views.finish, name="finish"),
    path("setup/<slug:name>/", views.step, name="step"),
]
