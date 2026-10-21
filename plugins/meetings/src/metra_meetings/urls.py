from django.urls import path

from . import member, views

app_name = "metra_meetings"

urlpatterns = [
    path("", views.meeting_list, name="meeting_list"),
    path("new/", views.meeting_create, name="meeting_create"),
    path("<int:pk>/", views.meeting_detail, name="meeting_detail"),
    path("<int:pk>/edit/", views.meeting_edit, name="meeting_edit"),
    path("<int:pk>/delete/", views.meeting_delete, name="meeting_delete"),
    path("<int:pk>/status/", views.meeting_status, name="meeting_status"),
    path("<int:pk>/items/new/", views.item_create, name="item_create"),
    path("<int:pk>/items/<int:item_pk>/", views.item_edit, name="item_edit"),
    path("<int:pk>/items/<int:item_pk>/delete/", views.item_delete, name="item_delete"),
    path("<int:pk>/minutes/", views.minutes_edit, name="minutes_edit"),
    path("<int:pk>/attendance/", views.attendance, name="attendance"),
    path("<int:pk>/attendance/add/", views.attendance_add, name="attendance_add"),
    path("<int:pk>/attendance/<int:attendance_pk>/", views.attendance_edit, name="attendance_edit"),
    path(
        "<int:pk>/attendance/<int:attendance_pk>/remove/",
        views.attendance_remove,
        name="attendance_remove",
    ),
    path("<int:pk>/agenda.pdf", views.agenda_pdf, name="agenda_pdf"),
    path("<int:pk>/minutes.pdf", views.minutes_pdf, name="minutes_pdf"),
    path("<int:pk>/notice/", views.send_notice, name="send_notice"),
    path("<int:pk>/approve/", views.approve, name="approve"),
    path("templates/", views.template_list, name="template_list"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/", views.template_edit, name="template_edit"),
    path("templates/<int:pk>/delete/", views.template_delete, name="template_delete"),
    # For members, through their personal link (no login).
    path("m/<str:token>/<int:pk>/minutes.pdf", member.minutes_pdf, name="member_minutes"),
]
