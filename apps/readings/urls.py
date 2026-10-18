from django.urls import path

from . import views

app_name = "readings"

urlpatterns = [
    path("readings/", views.round_list, name="round_list"),
    path("readings/new/", views.round_create, name="round_create"),
    path("readings/<int:pk>/", views.round_detail, name="round_detail"),
    path("readings/<int:pk>/edit/", views.round_edit, name="round_edit"),
    path("readings/<int:pk>/export/", views.round_export, name="round_export"),
    path("readings/<int:pk>/units/<int:unit_pk>/", views.reading_entry, name="reading_entry"),
]
