"""When entries are due. Cash payments are to be booked promptly, day by
day, and other entries at the latest about four months after the end of the
month they belong to (KPL 2:4). The add-on does not refuse late entries; it
shows the treasurer what is waiting."""

import datetime

from django.utils import timezone

from .models import Voucher

MONTHS_ALLOWED = 4


def due_date(date):
    """The last day for booking an entry dated ``date``: the end of the
    fourth month after its month."""
    month = date.month + MONTHS_ALLOWED
    year = date.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    next_month = datetime.date(year + month // 12, month % 12 + 1, 1)
    return next_month - datetime.timedelta(days=1)


def late_drafts(today=None):
    """Draft vouchers whose booking date has passed."""
    today = today or timezone.localdate()
    drafts = Voucher.objects.filter(status=Voucher.Status.DRAFT).select_related("series")
    return [voucher for voucher in drafts if due_date(voucher.date) < today]
