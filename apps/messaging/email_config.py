"""How email is sent: the settings saved on the Email settings page, with
the server environment (METRA_EMAIL_*) winning field by field.

When the environment sets METRA_EMAIL_BACKEND or METRA_EMAIL_HOST it also
decides the provider, as before this page existed, so an existing install
keeps sending the same way. Otherwise the page chooses: SMTP, the console
(development), a provider added by an add-on such as Mailgun, or none.

All email goes the same way: messages and newsletters through
``provider_for(EMAIL)``, and the app's own mail (login codes, password
links, invitations) through ``ConfiguredBackend``, Django's EMAIL_BACKEND.
"""

import logging
import os
from dataclasses import dataclass, field

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

from apps.plugins import secrets

logger = logging.getLogger(__name__)

SMTP = "smtp"
CONSOLE = "console"
NONE = "none"
# The registry name of the built-in provider that sends through Django's mail.
DJANGO = "django"

TRANSPORTS = {
    SMTP: "django.core.mail.backends.smtp.EmailBackend",
    CONSOLE: "django.core.mail.backends.console.EmailBackend",
}

# Field: environment variable that wins over the saved value.
ENVIRONMENT = {
    "host": "METRA_EMAIL_HOST",
    "port": "METRA_EMAIL_PORT",
    "user": "METRA_EMAIL_USER",
    "password": "METRA_EMAIL_PASSWORD",
    "from_email": "METRA_EMAIL_FROM",
    "reply_to": "METRA_EMAIL_REPLY_TO",
}
SECURITY_ENVIRONMENT = ("METRA_EMAIL_USE_TLS", "METRA_EMAIL_USE_SSL")


def _env(name):
    value = os.environ.get(name, "").strip()
    return value or None


@dataclass
class EmailConfig:
    provider: str = ""  # a provider's registry name; "" when email is not set up
    transport: str = ""  # for the built-in provider: SMTP or CONSOLE
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    security: str = "tls"
    from_email: str = "register@localhost"
    reply_to: str = ""
    choice: str = ""  # what the page shows as chosen: SMTP, CONSOLE, NONE or a provider
    locked: set = field(default_factory=set)  # fields set in the environment
    password_unreadable: bool = False

    @property
    def domain(self):
        return self.from_email.rpartition("@")[2] or "localhost"


def _security_from_env():
    tls, ssl = (_env(name) for name in SECURITY_ENVIRONMENT)
    if ssl is not None and ssl.lower() in {"1", "true", "yes", "on"}:
        return "ssl"
    if tls is not None:
        return "tls" if tls.lower() in {"1", "true", "yes", "on"} else "none"
    return None


def current():
    """The email settings in effect now."""
    from .models import EmailSettings

    saved = EmailSettings.current()
    config = EmailConfig()
    if saved is not None:
        config.host, config.port, config.user = saved.host, saved.port, saved.user
        config.security = saved.security
        config.from_email = saved.from_email or config.from_email
        config.reply_to = saved.reply_to
        if saved.password:
            try:
                config.password = secrets.decrypt(saved.password)
            except secrets.SecretUnreadable:
                config.password_unreadable = True
    for name, variable in ENVIRONMENT.items():
        if (value := _env(variable)) is not None:
            if name == "port":
                try:
                    value = int(value)
                except ValueError:
                    continue
            setattr(config, name, value)
            config.locked.add(name)
    if (security := _security_from_env()) is not None:
        config.security = security
        config.locked.add("security")

    from_environment = settings.MESSAGING.get("email_provider")
    if from_environment is not None:
        # METRA_EMAIL_BACKEND or METRA_EMAIL_HOST decide, as they always have.
        config.locked.add("provider")
        config.provider = from_environment
        config.transport = settings.MESSAGING.get("email_transport", SMTP)
        config.choice = config.transport if config.provider == DJANGO else (config.provider or NONE)
    else:
        choice = (saved.provider if saved else "") or (CONSOLE if settings.DEBUG else NONE)
        config.choice = choice
        if choice in (SMTP, CONSOLE):
            config.provider, config.transport = DJANGO, choice
        elif choice != NONE:
            config.provider = choice
    return config


def connection(config, fail_silently=False):
    """A Django mail connection for the built-in provider's transport."""
    if config.transport == SMTP:
        return get_connection(
            TRANSPORTS[SMTP],
            fail_silently=fail_silently,
            host=config.host,
            port=config.port,
            username=config.user,
            password=config.password,
            use_tls=config.security == "tls",
            use_ssl=config.security == "ssl",
            timeout=30,
        )
    return get_connection(TRANSPORTS[CONSOLE], fail_silently=fail_silently)


class ConfiguredBackend(BaseEmailBackend):
    """Django's EMAIL_BACKEND: the app's own mail goes the way the email
    settings say, with their from and Reply-To addresses."""

    def send_messages(self, email_messages):
        from .registry import EMAIL, ProviderError, registry

        config = current()
        for message in email_messages:
            if message.from_email in (None, "", settings.DEFAULT_FROM_EMAIL):
                message.from_email = config.from_email
            if config.reply_to and not message.reply_to:
                message.reply_to = [config.reply_to]
        if not config.provider:
            logger.warning("Email is not set up; %s message(s) not sent.", len(email_messages))
            return 0
        if config.provider == DJANGO:
            return connection(config, self.fail_silently).send_messages(email_messages)
        try:
            provider = registry.get(EMAIL, config.provider)
            for message in email_messages:
                provider.send_email_message(message)
        except ProviderError:
            if not self.fail_silently:
                raise
            logger.exception("Sending email through %s failed", config.provider)
            return 0
        return len(email_messages)
