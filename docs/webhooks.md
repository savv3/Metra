# Webhooks

The webhooks plugin tells outside systems when something changes in Metra: it
sends a signed HTTP `POST` to an address you choose. Use it to connect an
accounting system, a spreadsheet script or an automation service.

It is an official plugin that ships with Metra but is **off by default**.

## Turning it on

Add it to `METRA_PLUGINS` in `.env` and restart:

```sh
METRA_PLUGINS=webhooks
```

The Docker image already contains it. Without Docker, `uv sync` installs it
(`plugins/webhooks`). Only the **Admin** role can use it. `METRA_WEBHOOK_KEEP_DAYS`
(default 30) sets how long the record of what was sent is kept.

## Adding an endpoint

Open **Settings, Webhooks** (or `/plugins/webhooks/`) and choose **Add an
endpoint**.

1. Give the address of the receiving system. It must start with `https://`.
2. Tick the events it should get. An endpoint with no event ticked gets nothing.
3. Save, then copy the **secret** shown on the endpoint's page to the
   receiver. It is used to check that requests come from Metra. **Make a new
   secret** replaces it; the old one stops working at once.
4. **Send a test event** sends a `ping` and shows how it went under
   **Show deliveries**.

For safety Metra refuses to send to addresses on internal networks (localhost,
private ranges such as `10.x.x.x` and `192.168.x.x`, link-local ones like
`169.254.x.x`), and it does not follow redirects. In development
(`METRA_DEBUG=true`) plain `http://` and local addresses are allowed.

## Events and payloads

Every request body is JSON:

```json
{
  "id": "3f1c6b52-0f43-4c43-8d1a-5e1d0b4f7a10",
  "event": "invoice.issued",
  "occurred_at": "2026-10-18T20:27:41.512345Z",
  "data": { "invoice_id": 42, "number": "2026-0042", "kind": "invoice",
            "unit_id": 7, "total": "132.50", "due_date": "2026-11-17" }
}
```

`id` identifies the delivery and is the same on every retry, so the receiver
can ignore one it has already handled.

| Event | `data` |
| --- | --- |
| `unit.saved` | `unit_id`, `unit_type_id`, `status`, `archived`, `created` |
| `person.saved` | `person_id`, `archived`, `created` |
| `reading.saved` | `reading_id`, `unit_id`, `round_id`, `created` |
| `invoice.issued` | `invoice_id`, `number`, `kind` (`invoice` or `credit_note`), `unit_id`, `total` (text), `due_date` |
| `payment.recorded` | `payment_id`, `invoice_id`, `amount` (text), `paid_on` |
| `ping` | `message`; only from **Send a test event** |

Amounts are text (`"132.50"`), not numbers, so no precision is lost. Events are
sent after the change is saved, never for one that was rolled back. Other
plugins can add their own events with `api.add_webhook_event` (see
[plugins.md](plugins.md)); they show up as checkboxes too.

**Privacy.** Payloads carry ids and non-personal facts only, never names, email
addresses, phone numbers or addresses. The receiver fetches details through
the REST API when it needs them, with its own access. Keep it that way in
plugins that add events.

## Headers

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `User-Agent` | `Metra-Webhooks/1` |
| `Metra-Event` | The event name, like `invoice.issued` |
| `Metra-Delivery` | The delivery id (same as `id` in the body) |
| `Metra-Signature` | `t=<unix time>,v1=<signature>` |

## Checking the signature

The signature is the hex HMAC-SHA256, with the endpoint's secret as key, of the
timestamp `t`, a dot, and the **raw request body** exactly as received. Check
the raw bytes before parsing the JSON, compare in constant time, and reject old
timestamps so a captured request cannot be replayed later.

```python
import hashlib
import hmac
import time

SECRET = "the endpoint's secret"
MAX_AGE = 300  # seconds


def is_from_metra(raw_body: bytes, signature_header: str) -> bool:
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(","))
        timestamp = int(parts["t"])
        received = parts["v1"]
    except (KeyError, ValueError):
        return False
    if abs(time.time() - timestamp) > MAX_AGE:
        return False
    message = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)
```

## Answers and retries

Answer with a `2xx` status within 10 seconds; anything else counts as a
failure (including redirects, `3xx`). Answer first and do slow work after.

A failed delivery is tried again after 1 minute, 5 minutes, 30 minutes,
2 hours and 12 hours; if that fails too it is **given up**, and admins get a
notification under the bell (one per endpoint and day). Retries use the
same body and a new timestamp. If the worker is stopped, whatever is due is
sent when it starts again. Under **Show deliveries** you can see the latest 100
deliveries with their status, attempts, response code and error, and press
**Retry now** on one that failed or was given up. Deliveries older than
`METRA_WEBHOOK_KEEP_DAYS` days are deleted every night.

Changes to endpoints are written to the audit log, but the secret is not.

## Limits

- Delivery order is not guaranteed, particularly across retries. Use the
  `occurred_at` time, or fetch the current state through the REST API.
- Delivery is at least once: a receiver may see the same `id` twice.
