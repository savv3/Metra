"""Fill a fresh installation with a made-up water association for demos.

Everything here is invented: names, addresses on Åland, example.org emails,
phone numbers in a fictional range and a well-known test IBAN. Nothing is sent
to anyone; invoices are issued and marked paid in the database only."""

import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone, translation

from apps.core.models import Notice
from apps.invoicing.models import BillingSettings, FeeLine, FeePlan, Invoice, InvoiceRun
from apps.invoicing.payments import record_payment
from apps.invoicing.runs import build_run
from apps.readings.models import Reading, ReadingRound
from apps.register.models import Organisation, Person, Tag, Unit, UnitContact
from apps.setup.examples import water_association
from apps.setup.models import SetupState

SEED = 20260101

# (household name, street, postal code, municipality)
HOUSEHOLDS = [
    ("Nordgård", "Byvägen 4", "22240", "Hammarland"),
    ("Sjöbacka", "Strandvägen 12", "22240", "Hammarland"),
    ("Lillgård", "Kyrkvägen 3", "22240", "Hammarland"),
    ("Backas", "Ängsvägen 7", "22240", "Hammarland"),
    ("Granudden", "Granuddsvägen 1", "22240", "Hammarland"),
    ("Västergård", "Västerbyvägen 15", "22240", "Hammarland"),
    ("Furuholm", "Skogsstigen 2", "22240", "Hammarland"),
    ("Kullen", "Kullavägen 9", "22240", "Hammarland"),
    ("Smedsas", "Smedsvägen 6", "22240", "Hammarland"),
    ("Österbo", "Österbyvägen 21", "22240", "Hammarland"),
    ("Pettas", "Bystigen 8", "22240", "Hammarland"),
    ("Solbacka", "Solvägen 5", "22240", "Hammarland"),
    ("Mattsas", "Mattsvägen 11", "22240", "Hammarland"),
    ("Villa Lugn", "Lugnvägen 3", "22240", "Hammarland"),
    ("Hagagård", "Hagavägen 14", "22240", "Hammarland"),
]

FIRST_NAMES = [
    "Anna", "Johan", "Maria", "Erik", "Karin", "Lars", "Eva", "Mikael", "Sofia",
    "Anders", "Helena", "Henrik", "Ulla", "Mats", "Birgitta", "Patrik", "Lena",
    "Fredrik", "Marika", "Thomas", "Susanne", "Jonas", "Tuula", "Kenneth",
]  # fmt: skip
LAST_NAMES = [
    "Karlsson", "Eriksson", "Mattsson", "Lindholm", "Sjögren", "Nyman", "Hellström",
    "Andersson", "Danielsson", "Söderlund", "Fagerholm", "Backman", "Johansson",
    "Lundberg", "Mäkinen", "Holmström",
]  # fmt: skip

BOARD = {0, 3}  # households whose first contact sits on the board


class Command(BaseCommand):
    help = (
        "Fill a fresh installation with a made-up water association (households, "
        "contacts, readings, invoices) so someone can try Metra. Refuses to run "
        "if any unit already exists. Sends no email or SMS."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        if Unit.objects.exists():
            raise CommandError(
                "The register already has units; demo data is only for fresh installs."
            )
        rng = random.Random(SEED)
        this_year = timezone.localdate().year
        with translation.override("sv"):
            self._organisation()
            household = water_association()
            board_tag, _created = Tag.objects.get_or_create(name="Styrelse")
            units = self._register(rng, household, board_tag)
            rounds = self._readings(rng, units, household, this_year)
            invoices = self._invoices(rng, household, rounds[-1])
            self._notices()
        SetupState.current().finish(None)
        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded demo data: {len(units)} households, "
                f"{Reading.objects.count()} readings, {invoices} invoices."
            )
        )

    @staticmethod
    def _organisation():
        values = {
            "name": "Västerby vattenandelslag",
            "business_id": "0000000-0",
            "email": "demo@example.org",
            "phone": "+358 18 000 000",
            "street_address": "Bystigen 2",
            "postal_code": "22240",
            "city": "Hammarland",
            "country": "AX",
            "public_page": True,
            "description": (
                "Västerby vattenandelslag förser ett femtiotal hushåll i Västerby med "
                "rent dricksvatten. Det här är en påhittad demoorganisation."
            ),
            "opening_hours": "Vardagar 9–16. Vid akuta vattenläckor, ring jouren.",
            "emergency_phone": "+358 40 000 0999",
        }
        organisation = Organisation.current()
        if organisation is None:
            Organisation.objects.create(**values)
        else:
            for key, value in values.items():
                setattr(organisation, key, value)
            organisation.save()

    @staticmethod
    def _register(rng, household, board_tag):
        names = [(first, last) for last in LAST_NAMES for first in FIRST_NAMES]
        rng.shuffle(names)
        names = iter(names)
        choices = ["Vatten", "Vatten och avlopp"]
        units, phone = [], 0
        for index, (name, street, postal, city) in enumerate(HOUSEHOLDS):
            unit = Unit.objects.create(
                unit_type=household,
                name=name,
                street_address=street,
                postal_code=postal,
                city=city,
                country="AX",
                start_date=datetime.date(rng.randint(1985, 2018), rng.randint(1, 12), 1),
                custom_data={
                    "property_id": f"{rng.randint(1, 9)}-{rng.randint(1, 99)}-{rng.randint(1, 99)}",
                    "meter_number": f"VM{rng.randint(10000, 99999)}",
                    "connected_year": rng.randint(1985, 2018),
                    "connection": rng.choice(choices),
                    "residents": rng.randint(1, 5),
                },
            )
            units.append(unit)
            for position in range(rng.choice([1, 2])):
                first, last = next(names)
                phone += 1
                person = Person.objects.create(
                    first_name=first,
                    last_name=last,
                    email=f"{first}.{last}@example.org".lower()
                    .replace("ö", "o")
                    .replace("ä", "a")
                    .replace("å", "a"),
                    phone=f"+358 40 000 {phone:04d}",
                    street_address=street,
                    postal_code=postal,
                    city=city,
                    country="AX",
                    preferred_channel=Person.Channel.EMAIL if phone % 4 else Person.Channel.SMS,
                )
                UnitContact.objects.create(
                    unit=unit,
                    person=person,
                    role=UnitContact.Role.OWNER if position == 0 else UnitContact.Role.CONTACT,
                )
                if position == 0 and index in BOARD:
                    person.tags.add(board_tag)
        return units

    @staticmethod
    def _readings(rng, units, household, this_year):
        from apps.readings.models import ReadingType

        meter = ReadingType.objects.get(unit_type=household)
        rounds = []
        for year in (this_year - 2, this_year - 1):
            rounds.append(
                ReadingRound.objects.create(
                    reading_type=meter,
                    period_label=str(year),
                    opens_on=datetime.date(year, 10, 1),
                    closes_on=datetime.date(year, 10, 31),
                    is_draft=False,
                )
            )
        for index, unit in enumerate(units):
            value = Decimal(rng.randint(800, 4000))
            for number, round_ in enumerate(rounds):
                # A few households have not reported the latest reading yet.
                if number == 1 and index in (4, 9, 12):
                    continue
                Reading.objects.create(round=round_, unit=unit, value=value)
                value += Decimal(rng.randint(60, 260))
        return rounds

    @staticmethod
    def _invoices(rng, household, latest_round):
        billing = BillingSettings.current()
        billing.iban = "FI21 1234 5600 0007 85"  # a well-known test IBAN
        billing.bic = "NDEAFIHH"
        billing.save()
        plan = FeePlan.objects.create(name="Kommunal vattenavgift", unit_type=household)
        meter = latest_round.reading_type
        for order, (kind, text, price, reading_type) in enumerate(
            [
                ("fixed", "Grundavgift {period}", "120.00", None),
                ("usage", "Vatten {period}", "1.50", meter),
            ]
        ):
            FeeLine.objects.create(
                plan=plan,
                kind=kind,
                description=text,
                unit_price=Decimal(price),
                unit_label="" if reading_type else "st",
                vat_rate=billing.default_vat_rate,
                reading_type=reading_type,
                order=order,
            )
        run = InvoiceRun.objects.create(
            period_label=latest_round.period_label,
            supply_start=datetime.date(latest_round.opens_on.year, 1, 1),
            supply_end=datetime.date(latest_round.opens_on.year, 12, 31),
        )
        run.plans.add(plan)
        run.rounds.add(latest_round)
        build_run(run)
        issued = []
        for invoice in Invoice.objects.filter(run=run).order_by("unit__name"):
            if not invoice.problems:  # households without a reading stay drafts
                invoice.issue()
                issued.append(invoice)
        today = timezone.localdate()
        for invoice in issued:
            if rng.random() < 0.6:
                record_payment(
                    invoice,
                    invoice.total,
                    today - datetime.timedelta(days=rng.randint(0, 10)),
                    reference=invoice.reference,
                )
        return Invoice.objects.filter(run=run).count()

    @staticmethod
    def _notices():
        Notice.objects.create(
            text="Välkommen till demon! Allt här är påhittat, prova gärna att ändra.",
            level=Notice.Level.INFO,
        )
        Notice.objects.create(
            text="Vattnet stängs av i Västerby torsdag kl. 9–12 på grund av underhåll.",
            level=Notice.Level.URGENT,
            ends_at=timezone.now() + datetime.timedelta(days=14),
        )
