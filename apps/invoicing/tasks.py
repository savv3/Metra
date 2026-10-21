import datetime

from django.urls import reverse
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from apps.messaging.models import MessageBatch
from apps.notifications.models import Notification
from apps.notifications.service import notify

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


OVERDUE = "invoices_overdue"
# How far back the daily check looks when it has not run for a while.
OVERDUE_LOOKBACK_DAYS = 7


def notify_overdue(today=None):
    """Notify the treasurer and admins about invoices that became overdue since
    the last check. Safe to run more than once a day: the day's notification
    is sent once. Returns how many invoices it counted."""
    today = today or timezone.localdate()
    group = f"day-{today.isoformat()}"
    if Notification.objects.filter(kind=OVERDUE, group=group).exists():
        return 0
    since = today - datetime.timedelta(days=1)
    last = Notification.objects.filter(kind=OVERDUE).order_by("-created_at").first()
    if last is not None and last.group.startswith("day-"):
        # The last check counted due dates before its day; count from there on.
        try:
            since = datetime.date.fromisoformat(last.group.removeprefix("day-"))
        except ValueError:
            pass
    since = max(since, today - datetime.timedelta(days=OVERDUE_LOOKBACK_DAYS))
    count = sum(
        1
        for invoice in Invoice.objects.overdue(today)
        if since <= (invoice.reminded_due or invoice.due_date) < today
    )
    if count:
        notify(OVERDUE, {"count": count}, link=reverse("invoicing:overdue_list"), group=group)
    return count


@db_periodic_task(crontab(hour="7", minute="0"))
def overdue_invoices():
    """Each morning, tell the treasurer about invoices that became overdue."""
    notify_overdue()
