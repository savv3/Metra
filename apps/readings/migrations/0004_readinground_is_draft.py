from django.db import migrations, models


def status_to_draft(apps, schema_editor):
    """Open and closed rounds are published; their dates now decide which."""
    ReadingRound = apps.get_model("readings", "ReadingRound")
    ReadingRound.objects.filter(status="draft").update(is_draft=True)
    ReadingRound.objects.exclude(status="draft").update(is_draft=False)


def draft_to_status(apps, schema_editor):
    import datetime

    ReadingRound = apps.get_model("readings", "ReadingRound")
    ReadingRound.objects.filter(is_draft=True).update(status="draft")
    today = datetime.date.today()
    ReadingRound.objects.filter(is_draft=False, closes_on__lt=today).update(status="closed")
    ReadingRound.objects.filter(is_draft=False, closes_on__gte=today).update(status="open")


class Migration(migrations.Migration):
    dependencies = [("readings", "0003_reading_submitted_by_person")]

    operations = [
        migrations.AddField(
            model_name="readinground",
            name="is_draft",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "A draft is never open. Clear this to publish the round: it then opens "
                    "and closes on its dates."
                ),
                verbose_name="draft",
            ),
        ),
        migrations.RunPython(status_to_draft, draft_to_status),
        migrations.RemoveField(model_name="readinground", name="status"),
    ]
