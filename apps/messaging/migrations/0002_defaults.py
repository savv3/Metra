"""Default message templates (in Swedish, the default language; edit them
under Settings > Message templates), and the roles' messaging permissions:
Admin gets everything, Board sends, Treasurer and Read-only can look."""

from django.db import migrations

TEMPLATES = [
    (
        "link",
        "sms",
        "",
        "Hej {first_name}! Dags att läsa av {reading_type} för {period}. "
        "Rapportera senast {closes} här: {link} /{organisation}",
    ),
    (
        "reminder",
        "sms",
        "",
        "Hej {first_name}! Vi saknar fortfarande din avläsning av {reading_type} "
        "för {period}. Rapportera senast {closes}: {link} /{organisation}",
    ),
    (
        "link",
        "email",
        "{reading_type} {period}: rapportera din avläsning",
        "Hej {first_name},\n\n"
        "det är dags att läsa av {reading_type} för {unit}. Rapportera "
        "mätarställningen senast {closes} på din personliga sida:\n\n"
        "{link}\n\n"
        "Där kan du också kontrollera dina kontaktuppgifter. Länken är personlig, "
        "så dela den inte med någon.\n\n"
        "Hälsningar\n{organisation}",
    ),
    (
        "reminder",
        "email",
        "Påminnelse: {reading_type} {period}",
        "Hej {first_name},\n\n"
        "vi har ännu inte fått din avläsning av {reading_type} för {unit}. "
        "Rapportera den senast {closes} här:\n\n"
        "{link}\n\n"
        "Om du redan har rapporterat kan du bortse från det här meddelandet.\n\n"
        "Hälsningar\n{organisation}",
    ),
]

VIEW = ["view_messagebatch", "view_message"]
ROLES = {
    "Board": VIEW + ["add_messagebatch"],
    "Treasurer": VIEW,
    "Read-only": VIEW,
}


def forwards(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    for purpose, channel, subject, body in TEMPLATES:
        MessageTemplate.objects.get_or_create(
            purpose=purpose, channel=channel, defaults={"subject": subject, "body": body}
        )

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    messaging = Permission.objects.filter(content_type__app_label="messaging")
    if admin := Group.objects.filter(name="Admin").first():
        admin.permissions.add(*messaging)
    for name, codenames in ROLES.items():
        if group := Group.objects.filter(name=name).first():
            group.permissions.add(*messaging.filter(codename__in=codenames))


def backwards(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    messaging = Permission.objects.filter(content_type__app_label="messaging")
    for group in Group.objects.filter(name__in=["Admin", *ROLES]):
        group.permissions.remove(*messaging)


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0001_initial"),
        ("accounts", "0001_roles"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
