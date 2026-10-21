from django.urls import path

from . import views

app_name = "banking"

urlpatterns = [
    path("invoices/bank/", views.statement_list, name="statement_list"),
    path("invoices/bank/upload/", views.statement_upload, name="statement_upload"),
    path("invoices/bank/<int:pk>/", views.statement_detail, name="statement_detail"),
]
