# metra-sms-46elks

Sends Metra's SMS through [46elks](https://46elks.com), a Swedish SMS
provider that charges per message, and records delivery reports.

It comes with Metra and is on by default. It sends once its settings are in
`.env`:

| Setting | Meaning |
| --- | --- |
| `METRA_ELKS_API_USER` | API username from the 46elks dashboard |
| `METRA_ELKS_API_PASSWORD` | API password |
| `METRA_ELKS_DRY_RUN` | `true` to have 46elks accept messages without sending them |

The sender name (`METRA_SMS_SENDER`) and country code
(`METRA_SMS_COUNTRY_CODE`) are Metra's own SMS settings. With
`METRA_SMS_PROVIDER` left at `auto`, Metra uses 46elks as soon as the API
user and password are set.

Delivery reports come to `/plugins/46elks/delivery/<secret>/`; 46elks only
reports to a public HTTPS address, so `METRA_BASE_URL` must start with
`https://`. To turn the plugin off, set `METRA_PLUGINS_DISABLED=46elks`.

The plugin stores no personal data of its own: messages and their delivery
status are kept by Metra.
