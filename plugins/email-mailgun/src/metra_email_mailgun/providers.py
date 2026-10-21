"""Email through Mailgun (https://www.mailgun.com), EU region by default."""

import base64
import json
import secrets
import urllib.error
import urllib.request

from apps.plugins import api

# The plugin's name in METRA_PLUGINS and under Settings > Add-ons.
NAME = "mailgun"
HOSTS = {"eu": "https://api.eu.mailgun.net", "us": "https://api.mailgun.net"}


def config():
    """The plugin's settings: from its settings page under Settings > Add-ons,
    or from the environment (METRA_MAILGUN_*), which wins."""
    values = api.plugin_settings(NAME)
    region = values.get("region") or "eu"
    return {
        "domain": (values.get("domain") or "").strip(),
        "api_key": values.get("api_key") or "",
        "host": HOSTS.get(region, HOSTS["eu"]),
        "webhook_key": values.get("webhook_key") or "",
    }


def message_id(value):
    """Mailgun's id without angle brackets, as its webhooks report it."""
    return (value or "").strip().strip("<>")


def multipart(fields, files=()):
    """(body, content type) for a multipart/form-data request: ``fields`` are
    (name, text) pairs and ``files`` (name, filename, bytes, mimetype)."""
    boundary = "metra-" + secrets.token_hex(16)
    lines = []
    for name, value in fields:
        lines += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"'.encode(),
            b"",
            str(value).encode(),
        ]
    for name, filename, content, mimetype in files:
        quoted = filename.replace('"', "'")
        lines += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{quoted}"'.encode(),
            f"Content-Type: {mimetype or 'application/octet-stream'}".encode(),
            b"",
            content,
        ]
    lines += [f"--{boundary}--".encode(), b""]
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


class Mailgun(api.Provider):
    channel = api.EMAIL
    name = NAME
    description = "Mailgun"

    @classmethod
    def is_configured(cls):
        settings_ = config()
        return bool(settings_["domain"] and settings_["api_key"])

    def send(self, recipient, body, subject="", callback_url=None, headers=None, attachments=None):
        from_email, reply_to = api.email_from()
        fields = [("from", from_email), ("to", recipient), ("subject", subject), ("text", body)]
        if reply_to:
            fields.append(("h:Reply-To", reply_to))
        for name, value in (headers or {}).items():
            if name == api.SEND_OUT_HEADER:
                # Mailgun groups its statistics and logs by tag.
                fields.append(("o:tag", f"send-out-{value}"))
            else:
                fields.append((f"h:{name}", value))
        files = [
            ("attachment", filename, content, mimetype)
            for filename, content, mimetype in attachments or []
        ]
        return self._post("messages", fields, files)

    def send_email_message(self, message):
        """The app's own mail (login codes, invitations) as it is, with its
        HTML part, through Mailgun's MIME endpoint."""
        fields = [("to", recipient) for recipient in message.recipients()]
        files = [("message", "message.mime", message.message().as_bytes(), "message/rfc822")]
        return self._post("messages.mime", fields, files)

    def _post(self, endpoint, fields, files):
        settings_ = config()
        if not (settings_["domain"] and settings_["api_key"]):
            raise api.ProviderError(
                "Enter the Mailgun sending domain and API key under Settings > Add-ons > Mailgun."
            )
        body, content_type = multipart(fields, files)
        credentials = base64.b64encode(f"api:{settings_['api_key']}".encode()).decode()
        request = urllib.request.Request(
            f"{settings_['host']}/v3/{settings_['domain']}/{endpoint}",
            data=body,
            headers={"Authorization": "Basic " + credentials, "Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read(300).decode(errors="replace")
            raise api.ProviderError(f"Mailgun: {error.code} {detail}") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise api.ProviderError(f"Mailgun: {error}") from error
        return api.SendResult(provider_id=message_id(payload.get("id")))
