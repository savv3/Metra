# metra-email-mailgun

Sends Metra's email through [Mailgun](https://www.mailgun.com), EU region by
default, and records what Mailgun reports back: delivered, bounced and
marked as spam.

It comes with Metra and is on by default, but sends nothing until an admin
chooses **Mailgun** under **Settings > Email**. Its settings are under
**Settings > Add-ons > Mailgun**:

| Setting | Meaning | Environment variable |
| --- | --- | --- |
| Sending domain | The domain added and verified at Mailgun, for example `mg.example.fi` | `METRA_MAILGUN_DOMAIN` |
| API key | A sending API key for the domain. Stored encrypted, never shown again | `METRA_MAILGUN_API_KEY` |
| Region | `eu` (default, api.eu.mailgun.net) or `us` (api.mailgun.net) | `METRA_MAILGUN_REGION` |
| Webhook signing key | Mailgun's HTTP webhook signing key, to check the reports | `METRA_MAILGUN_WEBHOOK_KEY` |

A variable set in the server environment wins over the page and shows there
as locked. The from and Reply-To addresses come from Settings > Email.

Messages and newsletters go through Mailgun's `messages` API with their
attachments and headers (List-Unsubscribe on newsletters); the email of a
send-out is tagged `send-out-<id>`. The app's own mail (login codes,
invitations) is sent as it is, HTML part included, through `messages.mime`.

At Mailgun, add the webhook `<METRA_BASE_URL>/plugins/mailgun/events/` for
*Delivered messages*, *Permanent failure* and *Spam complaints*. Reports with
a wrong signature are refused. A permanent failure marks the message failed
and flags the person's address as bouncing (shown on their page until the
address changes); a spam complaint is noted on the message. Temporary
failures are ignored while Mailgun retries.

The plugin stores no personal data of its own: messages, their status and
bounce flags are kept by Metra. Mailgun receives each recipient's address and
the email's content, so list it as a processor in your GDPR records. To turn
the plugin off, use Settings > Add-ons or set `METRA_PLUGINS_DISABLED=mailgun`.
