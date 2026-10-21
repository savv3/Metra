"""Turning plugins on and off and changing their settings: admins only."""

from django.db import migrations

from apps.plugins.roles import grant_to_roles

ADMIN = [
    f"plugins.{action}_{model}"
    for model in ["pluginstate", "pluginsetting"]
    for action in ["add", "change", "delete", "view"]
]


class Migration(migrations.Migration):
    dependencies = [
        ("plugins", "0001_initial"),
        ("accounts", "0001_roles"),
    ]

    operations = [grant_to_roles({"Admin": ADMIN})]
