from django.urls import path

from . import views

app_name = "help"

urlpatterns = [
    path("help/", views.index, name="index"),
    path("help/<slug:slug>/", views.article, name="article"),
]
