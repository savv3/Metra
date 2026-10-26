from django.urls import path

from . import views

app_name = "metra_bookkeeping"

urlpatterns = [
    path("", views.index, name="index"),
    path("setup/", views.setup, name="setup"),
    path("years/", views.year_list, name="year_list"),
    path("years/new/", views.year_create, name="year_create"),
    path("years/<int:pk>/", views.year_detail, name="year_detail"),
    path("years/<int:pk>/edit/", views.year_edit, name="year_edit"),
    path("accounts/", views.account_list, name="account_list"),
    path("accounts/new/", views.account_create, name="account_create"),
    path("accounts/<int:pk>/edit/", views.account_edit, name="account_edit"),
    path("accounts/<int:pk>/delete/", views.account_delete, name="account_delete"),
    path("accounts/<int:pk>/", views.account_ledger, name="account_ledger"),
    path("series/new/", views.series_create, name="series_create"),
    path("series/<int:pk>/", views.series_edit, name="series_edit"),
    path("vouchers/", views.voucher_list, name="voucher_list"),
    path("vouchers/new/", views.voucher_create, name="voucher_create"),
    path("vouchers/<int:pk>/", views.voucher_detail, name="voucher_detail"),
    path("vouchers/<int:pk>/edit/", views.voucher_edit, name="voucher_edit"),
    path("vouchers/<int:pk>/post/", views.voucher_post, name="voucher_post"),
    path("vouchers/<int:pk>/delete/", views.voucher_delete, name="voucher_delete"),
    path("vouchers/<int:pk>/reverse/", views.voucher_reverse, name="voucher_reverse"),
    path("vouchers/<int:pk>/receipts/", views.receipt_upload, name="receipt_upload"),
    path(
        "vouchers/<int:pk>/receipts/<int:receipt_pk>/",
        views.receipt_download,
        name="receipt_download",
    ),
    path(
        "vouchers/<int:pk>/receipts/<int:receipt_pk>/remove/",
        views.receipt_delete,
        name="receipt_delete",
    ),
    path("journal/", views.journal, name="journal"),
    path("ledger/", views.ledger, name="ledger"),
    path("trial-balance/", views.trial_balance, name="trial_balance"),
]
