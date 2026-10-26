"""Statements, budget and VAT periods: long-term accounts, a year's average
staff, the VAT period of a registration, and budget lines.

SQLite adds the new columns by rebuilding the account table, which drops
its triggers (see 0005), so they are made again at the end."""

from importlib import import_module

import django.db.models.deletion
from django.db import migrations, models

locks = import_module("metra_bookkeeping.migrations.0005_more_locks")
ACCOUNT_TRIGGERS = ["bookkeeping_account_no_change", "bookkeeping_account_no_delete"]


class Migration(migrations.Migration):

    dependencies = [
        ("metra_bookkeeping", "0007_supply_period"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="long_term",
            field=models.BooleanField(
                default=False,
                help_text="For receivables and liabilities due after more than a year. The balance sheet shows them separately; keep the part due within a year on an account of its own.",
                verbose_name="long-term",
            ),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="staff",
            field=models.DecimalField(
                decimal_places=1,
                default=0,
                help_text="The average number of employees during the year. With the balance sheet total and turnover, it decides the size class of the financial statements.",
                max_digits=7,
                verbose_name="average staff",
            ),
        ),
        migrations.AddField(
            model_name="vatregistration",
            name="period",
            field=models.CharField(
                choices=[
                    ("month", "Month"),
                    ("quarter", "Quarter"),
                    ("year", "Calendar year"),
                ],
                default="month",
                help_text="How often the VAT return is filed, as agreed with the Tax Administration.",
                max_length=10,
                verbose_name="VAT period",
            ),
        ),
        migrations.CreateModel(
            name="Budget",
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
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=12, verbose_name="budget"
                    ),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="budget",
                        to="metra_bookkeeping.account",
                        verbose_name="account",
                    ),
                ),
                (
                    "year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="budget",
                        to="metra_bookkeeping.fiscalyear",
                        verbose_name="financial year",
                    ),
                ),
            ],
            options={
                "verbose_name": "budget line",
                "verbose_name_plural": "budget lines",
                "ordering": ["account__number"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("year", "account"), name="budget_one_per_account"
                    )
                ],
            },
        ),
        *(locks.again(name, locks.TRIGGERS[name]) for name in ACCOUNT_TRIGGERS),
    ]
