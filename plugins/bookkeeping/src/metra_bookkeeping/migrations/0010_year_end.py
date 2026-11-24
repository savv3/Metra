"""Locked periods, closing, the chart of a closed year, the asset register,
bank statement balances and notes.

SQLite rebuilds the voucher table to widen its kind column, and the
triggers of 0003 and 0005 that read that table would stop the rebuild, so
they are dropped first; 0011 makes them again."""

from importlib import import_module

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

locks = import_module("metra_bookkeeping.migrations.0003_locks")
more = import_module("metra_bookkeeping.migrations.0005_more_locks")


class Migration(migrations.Migration):

    dependencies = [
        ("metra_bookkeeping", "0009_roles_budget"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            [f"DROP TRIGGER IF EXISTS {name}" for name in [*locks.TRIGGERS, *more.TRIGGERS]],
            migrations.RunSQL.noop,
        ),
        migrations.AlterModelOptions(
            name="fiscalyear",
            options={
                "ordering": ["-start"],
                "permissions": [
                    ("close_fiscalyear", "Can lock periods and close financial years")
                ],
                "verbose_name": "financial year",
                "verbose_name_plural": "financial years",
            },
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="closed"),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="closed by",
            ),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="locked_until",
            field=models.DateField(blank=True, null=True, verbose_name="locked until"),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="retained_earnings",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="metra_bookkeeping.account",
                verbose_name="result carried to",
            ),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="signers",
            field=models.TextField(
                blank=True,
                help_text="The board members, one per line. Printed under the signature lines.",
                verbose_name="who signs the financial statements",
            ),
        ),
        migrations.AddField(
            model_name="voucher",
            name="corrects",
            field=models.ForeignKey(
                blank=True,
                help_text="For an error found in a closed year, corrected in this one.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrections",
                to="metra_bookkeeping.fiscalyear",
                verbose_name="corrects the year",
            ),
        ),
        migrations.AlterField(
            model_name="voucher",
            name="kind",
            field=models.CharField(
                choices=[
                    ("normal", "Voucher"),
                    ("opening", "Opening balances"),
                    ("reversal", "Reversal"),
                    ("accrual", "Accrual"),
                    ("depreciation", "Depreciation"),
                ],
                default="normal",
                max_length=15,
                verbose_name="kind",
            ),
        ),
        migrations.CreateModel(
            name="FixedAsset",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150, verbose_name="name")),
                (
                    "acquired",
                    models.DateField(
                        help_text="Depreciation starts from the month it is taken into use.",
                        verbose_name="acquired",
                    ),
                ),
                (
                    "cost",
                    models.DecimalField(
                        decimal_places=2, max_digits=12, verbose_name="acquisition cost"
                    ),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("straight", "Straight line over a number of years"),
                            ("reducing", "Reducing balance, a percentage a year"),
                            ("none", "Not depreciated (land, for example)"),
                        ],
                        default="straight",
                        max_length=10,
                        verbose_name="depreciation plan",
                    ),
                ),
                (
                    "years",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="years"
                    ),
                ),
                (
                    "percent",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        verbose_name="per cent a year",
                    ),
                ),
                (
                    "disposed",
                    models.DateField(
                        blank=True,
                        help_text="Empty while still in use.",
                        null=True,
                        verbose_name="sold or scrapped",
                    ),
                ),
                (
                    "note",
                    models.CharField(blank=True, max_length=200, verbose_name="note"),
                ),
                (
                    "account",
                    models.ForeignKey(
                        limit_choices_to={"kind": "asset"},
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="fixed_assets",
                        to="metra_bookkeeping.account",
                        verbose_name="asset account",
                    ),
                ),
                (
                    "depreciation_account",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"kind": "expense"},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="metra_bookkeeping.account",
                        verbose_name="depreciation account",
                    ),
                ),
            ],
            options={
                "verbose_name": "fixed asset",
                "verbose_name_plural": "fixed assets",
                "ordering": ["account__number", "acquired", "pk"],
            },
        ),
        migrations.CreateModel(
            name="BankBalance",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "balance",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        verbose_name="balance on the statement",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True,
                        help_text="For example: statement 12/2026.",
                        max_length=100,
                        verbose_name="statement",
                    ),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="metra_bookkeeping.account",
                        verbose_name="account",
                    ),
                ),
                (
                    "year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_balances",
                        to="metra_bookkeeping.fiscalyear",
                        verbose_name="financial year",
                    ),
                ),
            ],
            options={
                "verbose_name": "bank statement balance",
                "verbose_name_plural": "bank statement balances",
                "ordering": ["account__number"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("year", "account"), name="bankbalance_one_per_account"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ChartEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("number", models.CharField(max_length=8, verbose_name="number")),
                ("name", models.CharField(max_length=100, verbose_name="name")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("asset", "Asset"),
                            ("liability", "Liability"),
                            ("equity", "Equity"),
                            ("income", "Income"),
                            ("expense", "Expense"),
                        ],
                        max_length=10,
                        verbose_name="kind",
                    ),
                ),
                ("active", models.BooleanField(default=True, verbose_name="in use")),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="metra_bookkeeping.account",
                        verbose_name="account",
                    ),
                ),
                (
                    "year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chart_entries",
                        to="metra_bookkeeping.fiscalyear",
                        verbose_name="financial year",
                    ),
                ),
            ],
            options={
                "verbose_name": "account of a closed year",
                "verbose_name_plural": "chart of accounts of a closed year",
                "ordering": ["number"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("year", "account"), name="chartentry_one_per_year"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="YearNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.CharField(max_length=40, verbose_name="note")),
                ("language", models.CharField(max_length=5, verbose_name="language")),
                ("text", models.TextField(blank=True, verbose_name="text")),
                (
                    "year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notes",
                        to="metra_bookkeeping.fiscalyear",
                        verbose_name="financial year",
                    ),
                ),
            ],
            options={
                "verbose_name": "note to the financial statements",
                "verbose_name_plural": "notes to the financial statements",
                "ordering": ["pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("year", "key", "language"), name="yearnote_one_per_key"
                    )
                ],
            },
        ),
    ]
