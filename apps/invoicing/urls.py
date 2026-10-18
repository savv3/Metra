from django.urls import path

from . import views

app_name = "invoicing"

urlpatterns = [
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/runs/", views.run_list, name="run_list"),
    path("invoices/overdue/", views.overdue_list, name="overdue_list"),
    path("invoices/overdue/remind/", views.send_reminders, name="send_reminders"),
    path("invoices/export/", views.export_invoices, name="export_invoices"),
    path("invoices/export/payments/", views.export_payments, name="export_payments"),
    path("invoices/runs/new/", views.run_create, name="run_create"),
    path("invoices/runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("invoices/runs/<int:pk>/rebuild/", views.run_rebuild, name="run_rebuild"),
    path("invoices/runs/<int:pk>/issue/", views.run_issue, name="run_issue"),
    path("invoices/runs/<int:pk>/send/", views.run_send, name="run_send"),
    path("invoices/runs/<int:pk>/post.pdf", views.run_print, name="run_print"),
    path("invoices/sendouts/<int:pk>/post.pdf", views.batch_print, name="batch_print"),
    path("invoices/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/issue/", views.invoice_issue, name="invoice_issue"),
    path("invoices/<int:pk>/rebuild/", views.invoice_rebuild, name="invoice_rebuild"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoices/<int:pk>/credit/", views.invoice_credit, name="invoice_credit"),
    path("invoices/<int:pk>/pay/", views.invoice_pay, name="invoice_pay"),
]
