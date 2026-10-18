"""Default payment reminder texts (Swedish; edit under Settings > Message
templates). The email has the reminder PDF attached."""

from django.db import migrations

TEMPLATES = [
    (
        "sms",
        "",
        "Hej {first_name}! Faktura {number} från {organisation} är obetald. Att betala "
        "{amount} € senast {new_due_date} till {iban}, ref {reference}. Har du redan "
        "betalat kan du bortse från detta.",
    ),
    (
        "email",
        "Betalningspåminnelse: faktura {number}",
        "Hej {first_name},\n\n"
        "vi har inte fått betalning för faktura {number}, som förföll {due_date}. "
        "Att betala är {amount} € (inklusive en påminnelseavgift på {fee} €). Betala "
        "senast {new_due_date} till kontot {iban} med referensnumret {reference}.\n\n"
        "Påminnelsen finns som PDF i det här meddelandet. Om du redan har betalat kan "
        "du bortse från den.\n\n"
        "Hälsningar\n{organisation}",
    ),
]


def forwards(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    for channel, subject, body in TEMPLATES:
        MessageTemplate.objects.get_or_create(
            purpose="payment_reminder",
            channel=channel,
            defaults={"subject": subject, "body": body},
        )


def backwards(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.filter(
        purpose="payment_reminder"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("messaging", "0010_payment_reminders")]

    operations = [migrations.RunPython(forwards, backwards)]
