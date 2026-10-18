from huey.contrib.djhuey import db_task

from apps.messaging.models import MessageBatch

from .delivery import send_invoices
from .models import Invoice


@db_task()
def send_invoices_task(batch_id, invoice_ids):
    batch = MessageBatch.objects.filter(pk=batch_id).first()
    if batch is not None:
        invoices = Invoice.objects.filter(pk__in=invoice_ids).select_related("person", "unit")
        send_invoices(batch, invoices.order_by("sequence"))


@db_task()
def send_reminders_task(batch_id, invoice_ids, user_id=None):
    from django.contrib.auth import get_user_model

    from .payments import send_reminders

    batch = MessageBatch.objects.filter(pk=batch_id).first()
    if batch is not None:
        user = get_user_model().objects.filter(pk=user_id).first()
        invoices = Invoice.objects.filter(pk__in=invoice_ids).select_related("person", "unit")
        send_reminders(batch, invoices.order_by("sequence"), user)
