"""Give the roles the readings permissions (the roles were created before
this app existed). Admin gets everything; Board runs rounds and enters
readings; Treasurer and Read-only can look."""

from django.db import migrations

VIEW = ["view_readingtype", "view_readinground", "view_reading"]
ROLES = {
    "Board": VIEW
    + ["add_readinground", "change_readinground", "add_reading", "change_reading"],
    "Treasurer": VIEW,
    "Read-only": VIEW,
}


def grant(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    readings = Permission.objects.filter(content_type__app_label="readings")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.add(*readings)
    for name, codenames in ROLES.items():
        if group := Group.objects.filter(name=name).first():
            group.permissions.add(*readings.filter(codename__in=codenames))


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    readings = Permission.objects.filter(content_type__app_label="readings")
    for group in Group.objects.filter(name__in=["Admin", *ROLES]):
        group.permissions.remove(*readings)


class Migration(migrations.Migration):
    dependencies = [
        ("readings", "0001_initial"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
