from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.register.models import CustomField, Tag, UnitType

SAMPLES = {
    "water": {
        "unit_type": "Hushåll",
        "description": "Ett hushåll som är anslutet till vattenledningen.",
        "fields": [
            ("property_id", "Fastighetsbeteckning", CustomField.FieldType.TEXT, True, ""),
            ("meter_number", "Mätarnummer", CustomField.FieldType.TEXT, False, ""),
            (
                "connection",
                "Anslutning",
                CustomField.FieldType.CHOICE,
                False,
                "Året runt\nSommar",
            ),
        ],
        "tags": ["Styrelse"],
        # (name, unit label, decimals, cumulative)
        "reading_types": [("Vattenmätare", "m³", 0, True)],
    },
}


class Command(BaseCommand):
    help = "Load a ready-made configuration (unit type, custom fields, tags, reading types)."

    def add_arguments(self, parser):
        parser.add_argument("sample", choices=sorted(SAMPLES))

    @transaction.atomic
    def handle(self, *args, sample, **options):
        config = SAMPLES[sample]
        unit_type, created = UnitType.objects.get_or_create(
            name=config["unit_type"], defaults={"description": config["description"]}
        )
        if not created:
            raise CommandError(f"The unit type {unit_type} already exists; nothing changed.")
        for order, (key, label, field_type, required, choices) in enumerate(config["fields"]):
            CustomField.objects.create(
                target=CustomField.Target.UNIT,
                unit_type=unit_type,
                key=key,
                label=label,
                field_type=field_type,
                required=required,
                choices=choices,
                order=order,
            )
        for name in config["tags"]:
            Tag.objects.get_or_create(name=name)
        if config.get("reading_types") and apps.is_installed("apps.readings"):
            from apps.readings.models import ReadingType

            for name, unit_label, decimals, cumulative in config["reading_types"]:
                ReadingType.objects.get_or_create(
                    name=name,
                    defaults={
                        "unit_type": unit_type,
                        "unit_label": unit_label,
                        "decimals": decimals,
                        "cumulative": cumulative,
                    },
                )
        self.stdout.write(self.style.SUCCESS(f"Loaded the {sample} setup."))
