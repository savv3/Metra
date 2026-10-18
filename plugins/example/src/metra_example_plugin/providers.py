import logging

from apps.plugins import api

logger = logging.getLogger(__name__)


class LogSMS(api.Provider):
    """Pretends to send SMS by writing them to the log. Enable it with
    METRA_SMS_PROVIDER=example-log."""

    channel = api.SMS
    name = "example-log"

    def send(self, recipient, body, subject="", callback_url=None, headers=None):
        logger.info("Example SMS to %s: %s", recipient, body)
        return api.SendResult(provider_id="example")
