from django.urls import path

from . import views

app_name = "backups"

urlpatterns = [
    path("backups/", views.backup_list, name="list"),
    path("backups/take/", views.take, name="take"),
    path("backups/delete/", views.delete, name="delete"),
    path("backups/restore/<str:name>/", views.restore_snapshot, name="restore"),
]
