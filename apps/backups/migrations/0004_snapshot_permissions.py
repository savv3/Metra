"""Admin may take snapshots and delete the ones taken by hand. Runs recorded
by the nightly schedule are now called nightly."""

from django.db import migrations

from apps.plugins.roles import grant_to_roles


def rename_trigger(apps, schema_editor):
    BackupRun = apps.get_model("backups", "BackupRun")
    BackupRun.objects.filter(trigger="schedule").update(trigger="nightly")


def restore_trigger(apps, schema_editor):
    BackupRun = apps.get_model("backups", "BackupRun")
    BackupRun.objects.filter(trigger="nightly").update(trigger="schedule")


class Migration(migrations.Migration):
    dependencies = [
        ("backups", "0003_snapshots"),
        ("accounts", "0001_roles"),
    ]

    operations = [
        migrations.RunPython(rename_trigger, restore_trigger),
        grant_to_roles({"Admin": ["backups.take_snapshot", "backups.delete_snapshot"]}),
    ]
