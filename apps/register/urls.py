from django.urls import path

from . import import_views, views

app_name = "register"

urlpatterns = [
    path("units/", views.unit_list, name="unit_list"),
    path("units/new/", views.unit_create, name="unit_create"),
    path("units/export/", views.unit_export, name="unit_export"),
    path("units/import/", import_views.unit_import, name="unit_import"),
    path("units/import/columns/", import_views.unit_import_map, name="unit_import_map"),
    path("units/import/preview/", import_views.unit_import_preview, name="unit_import_preview"),
    path("units/<int:pk>/", views.unit_detail, name="unit_detail"),
    path("units/<int:pk>/edit/", views.unit_edit, name="unit_edit"),
    path("units/<int:pk>/archive/", views.unit_archive, name="unit_archive"),
    path("units/<int:pk>/contacts/", views.unit_contact_add, name="unit_contact_add"),
    path(
        "units/<int:pk>/contacts/<int:contact_pk>/remove/",
        views.unit_contact_remove,
        name="unit_contact_remove",
    ),
    path("people/", views.person_list, name="person_list"),
    path("people/new/", views.person_create, name="person_create"),
    path("people/export/", views.person_export, name="person_export"),
    path("people/<int:pk>/", views.person_detail, name="person_detail"),
    path("people/<int:pk>/edit/", views.person_edit, name="person_edit"),
    path("people/<int:pk>/archive/", views.person_archive, name="person_archive"),
]
