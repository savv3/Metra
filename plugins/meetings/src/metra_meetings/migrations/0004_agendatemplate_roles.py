from django.db import migrations

from apps.plugins import api


def add_defaults(apps, schema_editor):
    from metra_meetings import defaults

    defaults.create(apps.get_model("metra_meetings", "AgendaTemplate"))


def perms(*actions):
    return [f"metra_meetings.{action}_agendatemplate" for action in actions]


class Migration(migrations.Migration):
    dependencies = [("metra_meetings", "0003_agendatemplate"), ("accounts", "0001_roles")]
    operations = [
        # The board prepares meetings, so it keeps the usual agendas too.
        # Only admins delete, as with meetings.
        api.grant_to_roles(
            {
                "Admin": perms("view", "add", "change", "delete"),
                "Board": perms("view", "add", "change"),
                "Treasurer": perms("view"),
                "Read-only": perms("view"),
            }
        ),
        migrations.RunPython(add_defaults, migrations.RunPython.noop),
    ]
