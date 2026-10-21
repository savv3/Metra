"""Bank files: Treasurer and Admin import them, Board can look."""

from django.db import migrations

from apps.plugins.roles import grant_to_roles

ALL = [
    f"banking.{action}_{model}"
    for model in ["bankstatement", "banktransaction"]
    for action in ["add", "change", "delete", "view"]
]
VIEW = ["banking.view_bankstatement", "banking.view_banktransaction"]


class Migration(migrations.Migration):
    dependencies = [
        ("banking", "0001_initial"),
        ("accounts", "0001_roles"),
    ]

    operations = [grant_to_roles({"Admin": ALL, "Treasurer": ALL, "Board": VIEW})]
