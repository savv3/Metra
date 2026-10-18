"""Giving a plugin's permissions to Metra's roles, from its migrations.

Roles are the groups Admin, Board, Treasurer and Read-only (see
apps/accounts/migrations/0001_roles.py). A plugin that adds models or
permissions gives them to the right roles in a migration:

    from apps.plugins import api

    class Migration(migrations.Migration):
        dependencies = [("my_plugin", "0001_initial"), ("accounts", "0001_roles")]
        operations = [
            api.grant_to_roles({"Admin": ["my_plugin.view_thing", "my_plugin.change_thing"],
                                "Board": ["my_plugin.view_thing"]}),
        ]

Migrating backwards takes the permissions away again.
"""

from django.db import migrations


def _create_permissions(apps):
    # Permissions are normally made after all migrations have run; make them
    # now so they can be given out.
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


def _permissions(apps, dotted_names):
    Permission = apps.get_model("auth", "Permission")
    found = []
    for dotted in dotted_names:
        app_label, codename = dotted.split(".")
        found.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return found


def grant_to_roles(roles):
    """A migration operation giving each role (by name) the listed
    "app_label.codename" permissions. Roles that do not exist are skipped."""

    def grant(apps, schema_editor):
        _create_permissions(apps)
        Group = apps.get_model("auth", "Group")
        for name, dotted_names in roles.items():
            if group := Group.objects.filter(name=name).first():
                group.permissions.add(*_permissions(apps, dotted_names))

    def revoke(apps, schema_editor):
        Group = apps.get_model("auth", "Group")
        Permission = apps.get_model("auth", "Permission")
        for name, dotted_names in roles.items():
            if group := Group.objects.filter(name=name).first():
                for dotted in dotted_names:
                    app_label, codename = dotted.split(".")
                    group.permissions.remove(
                        *Permission.objects.filter(
                            content_type__app_label=app_label, codename=codename
                        )
                    )

    return migrations.RunPython(grant, revoke)
