"""Only Admin may send messages and alerts to everyone. An admin can give
the permission to Board (or another role) under Settings > Groups."""

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
        admin.permissions.add(
            Permission.objects.get(content_type__app_label="messaging", codename="send_broadcast")
        )


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.remove(
            *Permission.objects.filter(content_type__app_label="messaging", codename="send_broadcast")
        )


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0003_written_messages"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
