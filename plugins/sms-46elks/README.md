# metra-sms-46elks

Sends Metra's SMS through [46elks](https://46elks.com), a Swedish SMS
provider that charges per message, and records delivery reports.

It comes with Metra and is on by default. An admin enters its settings under
**Settings > Add-ons > 46elks SMS**:

| Setting | Meaning | Environment variable |
| --- | --- | --- |
| API username | From *Account* in the 46elks dashboard | `METRA_ELKS_API_USER` |
| API password | Stored encrypted, never shown again | `METRA_ELKS_API_PASSWORD` |
| Sender | Name shown on the phone (up to 11 letters and digits) or a 46elks number | `METRA_SMS_SENDER` |
| Test mode | 46elks accepts messages without sending them or charging | `METRA_ELKS_DRY_RUN` |

A variable set in the server environment wins over the page and shows there
as locked. Without a sender, Metra's `METRA_SMS_SENDER` (or "Register") is
used. The country code (`METRA_SMS_COUNTRY_CODE`) is Metra's own SMS
setting. With `METRA_SMS_PROVIDER` left at `auto`, Metra uses 46elks as soon
as the API user and password are set.

Delivery reports come to `/plugins/46elks/delivery/<secret>/`; 46elks only
reports to a public HTTPS address, so `METRA_BASE_URL` must start with
`https://`. To turn the plugin off, set `METRA_PLUGINS_DISABLED=46elks`.

The plugin stores no personal data of its own: messages and their delivery
status are kept by Metra.
