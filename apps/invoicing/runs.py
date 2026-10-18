"""Building draft invoices for an invoice run from fee plans and readings."""

from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _

from apps.readings.models import Reading
from apps.readings.usage import assess, earlier_values
from apps.register.models import Unit, UnitContact

from .models import FeeLine, Invoice, InvoiceLine

RECIPIENT_ROLES = [UnitContact.Role.BILLING, UnitContact.Role.OWNER, UnitContact.Role.CONTACT]


def recipient(unit):
    """Who gets the unit's invoice: the billing contact, else the owner, else a contact."""
    contacts = [c for c in unit.unit_contacts.all() if not c.person.is_archived]
    contacts.sort(key=lambda c: RECIPIENT_ROLES.index(c.role))
    return contacts[0].person if contacts else None


def run_units(run):
    """Active units that at least one of the run's fee plans applies to."""
    plans = list(run.plans.prefetch_related("lines__tiers"))
    units = (
        Unit.objects.active()
        .filter(status=Unit.Status.ACTIVE, unit_type__in=[p.unit_type_id for p in plans])
        .prefetch_related("tags", "unit_contacts__person")
        .order_by("name", "pk")
    )
    return [(unit, [p for p in plans if p.applies_to(unit)]) for unit in units], plans


def tiered(line, usage):
    """[(quantity, price, label)] for usage under a line's tiers."""
    tiers = list(line.tiers.all())
    if not tiers:
        return [(usage, line.unit_price, "")]
    parts, start = [], Decimal(0)
    for tier in tiers:
        end = tier.up_to
        if end is None or usage <= end:
            if usage > start:
                parts.append((usage - start, tier.unit_price, _tier_label(start, end)))
            return parts
        if end > start:
            parts.append((end - start, tier.unit_price, _tier_label(start, end)))
        start = end
    # Usage above the last limited tier: priced like that tier.
    if usage > start:
        parts.append((usage - start, tiers[-1].unit_price, _tier_label(start, None)))
    return parts


def _tier_label(start, end):
    def fmt(value):
        return f"{value.normalize():f}"

    if end is None:
        return _("over %(start)s") % {"start": fmt(start)}
    return f"{fmt(start)}–{fmt(end)}"


def usage_for(run, unit, reading_type):
    """(usage, problem) for a unit from the run's round for this reading type."""
    round_ = next((r for r in run.rounds.all() if r.reading_type_id == reading_type.pk), None)
    if round_ is None:
        return None, _("No reading round chosen for %(type)s.") % {"type": reading_type}
    reading = Reading.objects.filter(round=round_, unit=unit).first()
    if reading is None:
        return None, _("No %(type)s reading in %(round)s.") % {
            "type": reading_type,
            "round": round_,
        }
    earlier = earlier_values(round_, [unit.pk]).get(unit.pk, [])
    result = assess(reading_type, reading.value, earlier)
    if result.usage is None:
        return None, _("No earlier %(type)s reading to count usage from.") % {"type": reading_type}
    if result.usage < 0:
        return None, _("%(type)s is lower than the previous reading.") % {"type": reading_type}
    return result.usage, None


def build_lines(run, unit, plans):
    """(lines as dicts, problems) for one unit."""
    lines, problems = [], []
    for plan in plans:
        for fee in plan.lines.all():
            if not fee.applies_to(unit):
                continue
            text = fee.description.replace("{period}", run.period_label)
            common = {"vat_rate": fee.vat_rate, "fee_line": fee}
            if fee.kind == FeeLine.Kind.FIXED:
                lines.append(
                    {
                        **common,
                        "description": text,
                        "quantity": fee.quantity,
                        "unit_label": fee.unit_label,
                        "unit_price": fee.unit_price,
                    }
                )
                continue
            usage, problem = usage_for(run, unit, fee.reading_type)
            if problem:
                problems.append(problem)
                continue
            for quantity, price, label in tiered(fee, usage):
                lines.append(
                    {
                        **common,
                        "description": f"{text} {label}".strip(),
                        "quantity": quantity,
                        "unit_label": fee.unit_label or fee.reading_type.unit_label,
                        "unit_price": price,
                    }
                )
    return lines, problems


@transaction.atomic
def build_run(run):
    """Create or rebuild the run's draft invoices. Issued ones are left alone.

    Returns (created, rebuilt, skipped): skipped are units without a contact.
    """
    created = rebuilt = 0
    skipped = []
    pairs, _plans = run_units(run)
    for unit, plans in pairs:
        if not plans:
            continue
        person = recipient(unit)
        if person is None:
            skipped.append(unit)
            continue
        invoice = Invoice.objects.filter(run=run, unit=unit, kind=Invoice.Kind.INVOICE).first()
        if invoice is not None and not invoice.is_draft:
            continue
        lines, problems = build_lines(run, unit, plans)
        if invoice is None:
            invoice = Invoice(run=run, unit=unit, kind=Invoice.Kind.INVOICE)
            created += 1
        else:
            invoice.lines.all().delete()
            rebuilt += 1
        invoice.person = person
        invoice.period_label = run.period_label
        invoice.problems = problems
        invoice.save()
        for order, line in enumerate(lines):
            InvoiceLine.objects.create(invoice=invoice, order=order, **line)
        invoice.compute_totals()
        invoice.save(update_fields=["total_net", "total_vat", "total"])
    return created, rebuilt, skipped


def rebuild_invoice(invoice):
    """Rebuild one draft from its run, e.g. after a missing reading was entered."""
    if not invoice.is_draft or invoice.run is None:
        return
    run = invoice.run
    unit = Unit.objects.prefetch_related("tags", "unit_contacts__person").get(pk=invoice.unit_id)
    plans = [p for p in run.plans.prefetch_related("lines__tiers") if p.applies_to(unit)]
    lines, problems = build_lines(run, unit, plans)
    with transaction.atomic():
        invoice.lines.all().delete()
        invoice.problems = problems
        for order, line in enumerate(lines):
            InvoiceLine.objects.create(invoice=invoice, order=order, **line)
        invoice.compute_totals()
        invoice.save()
