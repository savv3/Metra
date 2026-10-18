"""Payments and payment reminders: Treasurer and Admin get every permission,
Board can view."""

from django.db import migrations


def grant(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    invoicing = Permission.objects.filter(content_type__app_label="invoicing")
    for name in ["Admin", "Treasurer"]:
        if group := Group.objects.filter(name=name).first():
            group.permissions.add(*invoicing)
    if board := Group.objects.filter(name="Board").first():
        board.permissions.add(*invoicing.filter(codename__startswith="view_"))


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0006_payments"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(grant, migrations.RunPython.noop)]
