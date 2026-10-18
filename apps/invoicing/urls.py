from django.urls import path

from . import views

app_name = "invoicing"

urlpatterns = [
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/runs/", views.run_list, name="run_list"),
    path("invoices/runs/new/", views.run_create, name="run_create"),
    path("invoices/runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("invoices/runs/<int:pk>/rebuild/", views.run_rebuild, name="run_rebuild"),
    path("invoices/runs/<int:pk>/issue/", views.run_issue, name="run_issue"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/issue/", views.invoice_issue, name="invoice_issue"),
    path("invoices/<int:pk>/rebuild/", views.invoice_rebuild, name="invoice_rebuild"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoices/<int:pk>/credit/", views.invoice_credit, name="invoice_credit"),
]
