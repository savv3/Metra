"""Create the four roles as Django groups.

An admin gives someone a role under Settings > Users by adding them to one
of these groups. Admins also need "staff status" to open Settings.
"""

from django.db import migrations

REGISTER_MODELS = [
    "organisation",
    "tag",
    "unittype",
    "customfield",
    "unit",
    "person",
    "unitcontact",
]
VIEW_REGISTER = [f"register.view_{model}" for model in REGISTER_MODELS]

ROLES = {
    "Board": VIEW_REGISTER
    + [
        "register.add_unit",
        "register.change_unit",
        "register.add_person",
        "register.change_person",
        "register.add_tag",
        "register.change_tag",
        "register.add_unitcontact",
        "register.delete_unitcontact",
        "auditlog.view_logentry",
    ],
    # Invoicing permissions are added when invoicing exists.
    "Treasurer": VIEW_REGISTER,
    "Read-only": VIEW_REGISTER,
}


def create_roles(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    # Permissions are normally created after all migrations have run; create
    # them now so the groups can be given them.
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    admin, _ = Group.objects.get_or_create(name="Admin")
    admin.permissions.set(Permission.objects.all())

    for name, codenames in ROLES.items():
        group, _ = Group.objects.get_or_create(name=name)
        permissions = []
        for dotted in codenames:
            app_label, codename = dotted.split(".")
            permissions.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        group.permissions.set(permissions)


def remove_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Admin", *ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("register", "0001_initial"),
        ("auditlog", "0017_add_actor_email"),
        ("account", "0009_emailaddress_unique_primary_email"),
        ("mfa", "0003_authenticator_type_uniq"),
    ]

    operations = [migrations.RunPython(create_roles, remove_roles)]
