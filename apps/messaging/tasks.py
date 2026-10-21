import datetime

from django.conf import settings
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from apps.readings.models import ReadingRound

from . import attachments, newsletter
from .models import MessageBatch
from .sending import send_batch


@db_task()
def send_batch_task(batch_id):
    batch = MessageBatch.objects.filter(pk=batch_id).first()
    if batch is None:
        return
    if batch.kind == MessageBatch.Kind.NEWSLETTER:
        if newsletter.send_part(batch):
            # More to send: the next part after a pause, to spare the mail server.
            send_batch_task.schedule(
                (batch_id,), delay=settings.MESSAGING["newsletter_pause_seconds"]
            )
        return
    send_batch(batch)


@db_periodic_task(crontab(hour="10", minute="0"))
def automatic_reminders():
    """Remind units missing a reading METRA_READING_REMINDER_DAYS before a published
    round closes. Off unless the setting is given; each round is reminded once."""
    days = settings.MESSAGING["reminder_days_before_close"]
    if days is None:
        return
    today = timezone.localdate()
    closes = today + datetime.timedelta(days=days)
    rounds = (
        ReadingRound.objects.published()
        .filter(closes_on=closes, opens_on__lte=today)
        .exclude(message_batches__kind=MessageBatch.Kind.AUTO_REMINDER)
    )
    for round_ in rounds:
        batch = MessageBatch.objects.create(
            kind=MessageBatch.Kind.AUTO_REMINDER,
            scope=MessageBatch.Scope.MISSING,
            round=round_,
        )
        send_batch(batch)


@db_periodic_task(crontab(hour="3", minute="15"))
def remove_unsent_attachments():
    """Files uploaded for a message that was never sent are kept for a day."""
    attachments.remove_unsent()
