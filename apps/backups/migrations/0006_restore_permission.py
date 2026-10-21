"""Only Admin may restore a snapshot."""

from django.db import migrations

from apps.plugins.roles import grant_to_roles


class Migration(migrations.Migration):
    dependencies = [
        ("backups", "0005_restore"),
        ("accounts", "0001_roles"),
    ]

    operations = [grant_to_roles({"Admin": ["backups.restore_snapshot"]})]
