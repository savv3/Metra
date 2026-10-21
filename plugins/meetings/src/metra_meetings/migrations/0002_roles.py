from django.db import migrations

from apps.plugins import api

MODELS = ["meeting", "agendaitem", "attendance"]


def perms(*actions):
    return [f"metra_meetings.{action}_{model}" for model in MODELS for action in actions]


class Migration(migrations.Migration):
    dependencies = [("metra_meetings", "0001_initial"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                "Admin": [
                    *perms("view", "add", "change"),
                    "metra_meetings.delete_meeting",
                    "metra_meetings.view_approval",
                ],
                # The board runs the meetings: it prepares them, keeps the
                # attendance and writes the minutes. Only admins delete meetings.
                "Board": [*perms("view", "add", "change"), "metra_meetings.view_approval"],
                "Treasurer": [*perms("view"), "metra_meetings.view_approval"],
                "Read-only": [*perms("view"), "metra_meetings.view_approval"],
            }
        ),
    ]
