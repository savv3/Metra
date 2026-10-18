from django.urls import path

from . import views

app_name = "register"

urlpatterns = [
    path("units/", views.unit_list, name="unit_list"),
    path("units/new/", views.unit_create, name="unit_create"),
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
    path("people/<int:pk>/", views.person_detail, name="person_detail"),
    path("people/<int:pk>/edit/", views.person_edit, name="person_edit"),
    path("people/<int:pk>/archive/", views.person_archive, name="person_archive"),
]
