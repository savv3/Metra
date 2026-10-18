"""Admin may publish and remove notices on the public page (the roles were
created before notices existed)."""

from django.db import migrations


def grant(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.add(*Permission.objects.filter(content_type__app_label="core"))


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.remove(*Permission.objects.filter(content_type__app_label="core"))


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
