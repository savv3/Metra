from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from . import service
from .models import WebhookDelivery


@db_task()
def deliver(delivery_id):
    """Make an attempt if the delivery is due. The result is recorded on it; a
    failure is retried by the sweep, as the schedule is kept in the database."""
    if delivery := service.claim(delivery_id):
        service.attempt(delivery)


@db_periodic_task(crontab(minute="*"))
def sweep():
    """Start deliveries that are due: retries, and any that never got started
    because the worker was down or restarted."""
    due = WebhookDelivery.objects.filter(
        status__in=[WebhookDelivery.Status.PENDING, WebhookDelivery.Status.FAILED],
        next_attempt_at__lte=timezone.now(),
    ).values_list("pk", flat=True)[:200]
    for delivery_id in list(due):
        deliver(str(delivery_id))


@db_periodic_task(crontab(hour="3", minute="45"))
def clean_up():
    service.delete_old()
