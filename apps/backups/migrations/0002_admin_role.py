"""Give the Admin role the backup permissions (the roles were created before
this app existed). Only Admin sees the backup status."""

from django.db import migrations


def grant(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    admin = Group.objects.filter(name="Admin").first()
    if admin:
        admin.permissions.add(*Permission.objects.filter(content_type__app_label="backups"))


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    admin = Group.objects.filter(name="Admin").first()
    if admin:
        admin.permissions.remove(*Permission.objects.filter(content_type__app_label="backups"))


class Migration(migrations.Migration):
    dependencies = [
        ("backups", "0001_initial"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
