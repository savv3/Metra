"""Admin and Board may write to one unit from its page."""

from django.db import migrations

ROLES = ["Admin", "Board"]


def grant(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    permission = Permission.objects.get(
        content_type__app_label="messaging", codename="send_unit_message"
    )
    for group in Group.objects.filter(name__in=ROLES):
        group.permissions.add(permission)


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    permissions = Permission.objects.filter(
        content_type__app_label="messaging", codename="send_unit_message"
    )
    for group in Group.objects.filter(name__in=ROLES):
        group.permissions.remove(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0011_payment_reminder_templates"),
        ("accounts", "0001_roles"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="messagebatch",
            options={
                "ordering": ["-created_at", "-pk"],
                "permissions": [
                    ("send_broadcast", "Can send messages and alerts to everyone"),
                    ("send_newsletter", "Can send newsletters"),
                    ("send_unit_message", "Can send a message to one unit"),
                ],
                "verbose_name": "send-out",
                "verbose_name_plural": "send-outs",
            },
        ),
        migrations.RunPython(grant, revoke),
    ]
