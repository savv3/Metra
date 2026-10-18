"""Admin may run the setup wizard. An installation that already has an
organisation was set up before the wizard existed, so it is marked as done
and admins are not sent to the wizard after the upgrade."""

from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.add(
            Permission.objects.get(content_type__app_label="setup", codename="run_setup")
        )
    Organisation = apps.get_model("register", "Organisation")
    SetupState = apps.get_model("setup", "SetupState")
    if Organisation.objects.exists() and not SetupState.objects.exists():
        SetupState.objects.create(finished_at=timezone.now())


def backwards(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.remove(
            *Permission.objects.filter(content_type__app_label="setup", codename="run_setup")
        )


class Migration(migrations.Migration):
    dependencies = [
        ("setup", "0001_initial"),
        ("accounts", "0001_roles"),
        ("register", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
