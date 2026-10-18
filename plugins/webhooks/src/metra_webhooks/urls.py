from django.urls import path

from . import views

app_name = "metra_webhooks"

urlpatterns = [
    path("", views.endpoint_list, name="endpoint_list"),
    path("new/", views.endpoint_create, name="endpoint_create"),
    path("<int:pk>/", views.endpoint_edit, name="endpoint_edit"),
    path("<int:pk>/rotate/", views.endpoint_rotate, name="endpoint_rotate"),
    path("<int:pk>/test/", views.endpoint_test, name="endpoint_test"),
    path("<int:pk>/delete/", views.endpoint_delete, name="endpoint_delete"),
    path("<int:pk>/deliveries/", views.delivery_list, name="delivery_list"),
    path(
        "<int:pk>/deliveries/<uuid:delivery_id>/retry/", views.delivery_retry, name="delivery_retry"
    ),
]
