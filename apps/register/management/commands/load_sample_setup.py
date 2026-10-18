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
        # One base fee for every household, and a price per m³ (delete that
        # line under Settings > Fee plans if usage is not charged).
        "fee_plan": {
            "name": "Kommunal vattenavgift",
            "lines": [
                ("fixed", "Grundavgift {period}", "120.00", None),
                ("usage", "Vatten {period}", "1.50", "Vattenmätare"),
            ],
        },
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
        if config.get("fee_plan") and apps.is_installed("apps.invoicing"):
            self._fee_plan(config["fee_plan"], unit_type)
        self.stdout.write(self.style.SUCCESS(f"Loaded the {sample} setup."))

    @staticmethod
    def _fee_plan(config, unit_type):
        from decimal import Decimal

        from apps.invoicing.models import BillingSettings, FeeLine, FeePlan
        from apps.readings.models import ReadingType

        plan, created = FeePlan.objects.get_or_create(
            name=config["name"], defaults={"unit_type": unit_type}
        )
        if not created:
            return
        rate = BillingSettings.current().default_vat_rate
        for order, (kind, description, price, reading_type) in enumerate(config["lines"]):
            FeeLine.objects.create(
                plan=plan,
                kind=kind,
                description=description,
                unit_price=Decimal(price),
                unit_label="" if reading_type else "st",
                vat_rate=rate,
                reading_type=ReadingType.objects.get(name=reading_type) if reading_type else None,
                order=order,
            )
