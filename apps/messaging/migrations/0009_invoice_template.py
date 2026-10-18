"""The default email for sending an invoice (Swedish; edit it under Settings >
Message templates). The PDF is attached."""

from django.db import migrations

SUBJECT = "Faktura {number} från {organisation}"
BODY = (
    "Hej {first_name},\n\n"
    "här kommer faktura {number} för {unit}. Summan är {total} € och den förfaller "
    "{due_date}. Använd referensnumret {reference} när du betalar.\n\n"
    "Fakturan finns som PDF i det här meddelandet.\n\n"
    "Hälsningar\n{organisation}"
)


def forwards(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    MessageTemplate.objects.get_or_create(
        purpose="invoice", channel="email", defaults={"subject": SUBJECT, "body": BODY}
    )


def backwards(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.filter(purpose="invoice").delete()


class Migration(migrations.Migration):
    dependencies = [("messaging", "0008_invoice_purpose")]

    operations = [migrations.RunPython(forwards, backwards)]
