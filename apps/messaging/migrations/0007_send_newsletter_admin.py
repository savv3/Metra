"""Only Admin may send newsletters; an admin can give the permission to
another role under Settings > Groups. Board may view newsletter consents."""

from django.db import migrations


def grant(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    messaging = Permission.objects.filter(content_type__app_label="messaging")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.add(
            *messaging.filter(
                codename__in=["send_newsletter", *(f"{a}_consentrecord" for a in ("add", "change", "delete", "view"))]
            )
        )
    for name in ["Board", "Treasurer", "Read-only"]:
        if group := Group.objects.filter(name=name).first():
            group.permissions.add(*messaging.filter(codename="view_consentrecord"))


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    names = ["send_newsletter", "add_consentrecord", "change_consentrecord", "delete_consentrecord", "view_consentrecord"]
    permissions = Permission.objects.filter(content_type__app_label="messaging", codename__in=names)
    for group in Group.objects.filter(name__in=["Admin", "Board", "Treasurer", "Read-only"]):
        group.permissions.remove(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0006_newsletters"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
