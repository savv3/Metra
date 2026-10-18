from django.urls import path

from . import public, views

app_name = "selfservice"

urlpatterns = [
    path("m/<str:token>/", public.member_page, name="member"),
    path("readings/<int:pk>/links/", views.round_links, name="round_links"),
    path("readings/<int:pk>/links/print/", views.round_print, name="round_print"),
    path("readings/<int:pk>/links/revoke/", views.round_revoke, name="round_revoke"),
    path("units/<int:pk>/letter/", views.unit_print, name="unit_print"),
    path("self-service/links/<int:pk>/revoke/", views.link_revoke, name="link_revoke"),
    path("self-service/changes/", views.recent_changes, name="recent_changes"),
]
