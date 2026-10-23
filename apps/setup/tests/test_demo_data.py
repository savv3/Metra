import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import Notice
from apps.invoicing.models import Invoice
from apps.readings.models import Reading
from apps.register.models import Organisation, Person, Unit
from apps.setup.models import SetupState


@pytest.mark.django_db
def test_load_demo_data_fills_a_fresh_install():
    call_command("load_demo_data")

    assert Organisation.current().name == "Västerby vattenandelslag"
    assert Unit.objects.count() == 15
    assert Person.objects.count() >= 15
    assert Person.objects.filter(tags__name="Styrelse").count() == 2
    assert not Person.objects.exclude(email__endswith="@example.org").exists()
    assert Reading.objects.count() == 15 * 2 - 3
    issued = Invoice.objects.exclude(status=Invoice.Status.DRAFT)
    assert issued.count() == 12
    assert Invoice.objects.filter(status=Invoice.Status.DRAFT).count() == 3
    assert issued.filter(payments__isnull=False).exists()
    assert issued.filter(payments__isnull=True).exists()
    assert Notice.objects.current().count() == 2
    assert SetupState.current().finished_at is not None
    assert mail.outbox == []


@pytest.mark.django_db
def test_load_demo_data_is_repeatable_only_on_an_empty_register():
    call_command("load_demo_data")
    with pytest.raises(CommandError):
        call_command("load_demo_data")
    assert Unit.objects.count() == 15
