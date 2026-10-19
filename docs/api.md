# REST API

Other systems, such as a bookkeeping program, a meter-reading app or a
script, can read and change the register through a JSON API. It comes with
Metra as the `api` plugin ([plugins/api](../plugins/api)), installed in the
Docker image but **off until you turn it on**:

```sh
METRA_PLUGINS=api     # in .env, then: docker compose up -d
```

## API clients and tokens

Each system that calls the API is an **API client** with its own token.
Admins manage them under **Settings → API clients**
(`/plugins/api/`).

1. Choose **New client**. Give it a name, a **role** and, if it only reads,
   tick **Read only**. You can also set the last day the token works.
2. Copy the token shown on the next page. It is shown **only once**: Metra
   stores only its SHA-256 fingerprint. If it is lost, choose **New token**
   (the old token stops working at once).
3. **Revoke** a client that is no longer used. Its token stops working for
   good.

Each client acts as a user of its own, `api-<name>`, made for it. That user
has exactly the client's role and can never log in to the web pages (it has
no password, and none can be given to it). Every change the client makes
is in the audit log under that user's name, like a person's changes.

Send the token in every request:

```
Authorization: Bearer <token>
```

A missing, wrong, revoked or expired token gets `401 Unauthorized`.

## What a client may do

The client may do exactly what its role may do on the web pages:

| Role | Register (units, people, contacts) | Readings | Invoices and payments |
| --- | --- | --- | --- |
| Admin | read and change | read, enter and correct | read |
| Board | read and change | read, enter and correct | read |
| Treasurer | read | read | read |
| Read-only | read | read | – |

A client marked **Read only** can only read, whatever its role. Give every
client the narrowest role that does its job.

Only Admins can create, rotate and revoke clients; a person can give a
client only a role whose permissions they have themselves.

## Endpoints

All endpoints are under `/plugins/api/v1/`. Requests and answers are JSON.

| Endpoint | Methods | |
| --- | --- | --- |
| `units/`, `units/{id}/` | GET, POST, PUT, PATCH, DELETE | DELETE archives |
| `people/`, `people/{id}/` | GET, POST, PUT, PATCH, DELETE | DELETE archives |
| `unit-contacts/`, `unit-contacts/{id}/` | GET, POST, DELETE | Link a person to a unit in a role (`owner`, `billing`, `contact`) |
| `unit-types/` | GET | With their custom fields |
| `person-fields/` | GET | The custom fields people have |
| `reading-rounds/` | GET | |
| `readings/`, `readings/{id}/` | GET, POST, PUT, PATCH | |
| `invoices/` | GET | With their lines. Read only |
| `payments/` | GET | Read only |
| `schema/` | GET | The OpenAPI 3 description |
| `docs/` | (web page) | The endpoints, for staff who can see API clients |

List filters:

- `units/`: `unit_type` (id), `status` (`active`, `inactive`), `tag` (name or
  id), `archived` (`true` for archived ones only; default `false`), `search`
- `people/`: `tag`, `archived`, `search`
- `unit-contacts/`: `unit`, `person`
- `reading-rounds/`: `reading_type`, `status`
- `readings/`: `round`, `unit`
- `invoices/`: `status`, `kind`, `unit`, `person`
- `payments/`: `invoice`

Lists come in pages of 50: `?page=2`, and `?page_size=` up to 200. The
answer has `count`, `next`, `previous` and `results`.

Errors are JSON, for example `{"detail": "..."}`, or for invalid data a
list of messages per field: `{"name": ["This field is required."]}`.

## Archive, not delete

Units and people are never deleted through the API. `DELETE` archives the
record, as **Archive** does on its page: it leaves the lists (unless you ask
for `?archived=true`) but keeps its history, readings and invoices. Erasing
a person's personal data is a separate step on the web pages.

Invoices and payments are read only: issued invoices never change, and
corrections are credit notes made in Metra.

## Custom fields

The fields an admin set up for a unit type (or for all people) are in
`custom_fields`, keyed by the field's key:

```json
{"name": "Byvägen 4", "unit_type": 1, "custom_fields": {"meter_number": "M-100"}}
```

`unit-types/` and `person-fields/` list each field's key, label, type
(`text`, `number`, `date` as `YYYY-MM-DD`, `choice`, `boolean`), choices and
whether it is required. Values are checked exactly as the web form checks
them: a required field must be there, a date must be a date, a choice one of
its options. An unknown key is refused.

A `PATCH` changes only the fields you send, custom fields included. A `PUT`
replaces the record: fields left out become empty.

## Examples

```sh
TOKEN=...   # the client's token
BASE=https://register.example.com/plugins/api/v1

# Active households
curl -H "Authorization: Bearer $TOKEN" "$BASE/units/?unit_type=1"

# A new unit
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"unit_type": 1, "name": "Strandvägen 1", "custom_fields": {"meter_number": "M-200"}}' \
  "$BASE/units/"

# Enter a reading in round 3
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"round": 3, "unit": 12, "value": 1234}' "$BASE/readings/"

# Correct its note
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"note": "Read by the meter company"}' "$BASE/readings/45/"

# Archive a person
curl -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE/people/7/"

# The OpenAPI description, for code generators
curl -H "Authorization: Bearer $TOKEN" "$BASE/schema/" > metra-openapi.json
```

## Rate limits

Each client may make 120 calls a minute. Set another limit with
`METRA_API_RATE`, for example `METRA_API_RATE=600/hour` (per `sec`, `min`,
`hour` or `day`). Above it the API answers `429 Too Many Requests`, with
`Retry-After` saying how many seconds to wait.

## Privacy

The API gives other systems the register's personal data: names, addresses,
email addresses, phone numbers and invoices. Under the GDPR the organisation
is responsible for where that data goes.

- Give each system its own client, the narrowest role and **Read only** when
  it only reads.
- Set an expiry date for clients made for a one-off job.
- Revoke clients that are no longer used.
- Opening a single person or unit through the API is logged as a view in the
  audit log, as on the web pages; every change is logged with the client's
  user.
- Keep tokens out of email, chat and code repositories.
