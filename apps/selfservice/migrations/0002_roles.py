"""Give the roles the self-service link permissions. Admin gets everything;
Board makes, prints and stops links; Treasurer and Read-only can see them."""

from django.db import migrations

VIEW = ["view_selfservicelink"]
ROLES = {
    "Board": VIEW + ["add_selfservicelink", "change_selfservicelink"],
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
    links = Permission.objects.filter(content_type__app_label="selfservice")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.add(*links)
    for name, codenames in ROLES.items():
        if group := Group.objects.filter(name=name).first():
            group.permissions.add(*links.filter(codename__in=codenames))


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    links = Permission.objects.filter(content_type__app_label="selfservice")
    for group in Group.objects.filter(name__in=["Admin", *ROLES]):
        group.permissions.remove(*links)


class Migration(migrations.Migration):
    dependencies = [
        ("selfservice", "0001_initial"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
