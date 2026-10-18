**English** · [Svenska](README.sv.md) · [Suomi](README.fi.md)

# Metra

A simple, self-hostable web app for small companies and associations to keep
track of their members and clients. Free and open source under the MIT
licence.

Metra keeps a register of households or other units and their contacts,
collects annual readings such as water meters, sends SMS, email and urgent
alerts, sends newsletters, and makes invoices. It runs on one small server
with Docker and backs itself up offsite every night. Record types and fields
are set up by an admin, so nothing is tied to one kind of organisation.

## Who it is for

Metra suits any group that keeps a list of households or members, bills them
once or twice a year and sometimes needs to reach everyone fast. It was built
first for a water association with about 50 households. Other good fits:

- **Road associations**, with shares per property, a yearly fee and alerts
  about road closures.
- **Fibre and village network co-ops**, with connections per household,
  monthly or yearly fees and outage alerts.
- **Housing co-ops and small housing companies**, with flats as units, fees
  and notices about water shut-offs or maintenance.
- **Harbour and boat clubs**, with berths as units, seasonal fees and storm
  warnings.
- **Allotment and summer-cottage associations**, with plots, yearly fees and
  water turned on or off by season.
- **Hunting clubs and fishing-water owners**, with members, shares and fees.
- **Sports clubs and small voluntary associations**, with members,
  membership fees and newsletters.
- **Small service firms**, such as chimney sweeps, septic emptying or snow
  ploughing, with customers per address, yearly invoices and visit notices.

## Features

- A configurable register of units, people and contacts, with CSV import and
  export
- Roles, two-factor login for staff and an audit log of every change
- Annual readings, entered by the board or by members themselves
- Member self-service through personal links, with no passwords
- SMS (46elks) and email messages, urgent alerts and a public page with
  notices
- Newsletters with recorded consent and one-click unsubscribe
- Invoicing with Finnish reference numbers, bank barcodes, payment QR codes,
  credit notes and payment reminders
- Nightly backups, encrypted and copied to S3, SFTP or FTPS
- Plugins, and Swedish, English and Finnish in the app (the Finnish is
  machine translated and unreviewed, and the app says so)

**Status:** early development. The register, readings, self-service,
messaging, newsletters and invoicing are in place; see
[docs/architecture.md](docs/architecture.md) for the plan and what comes next.

## Get started

```sh
cp .env.example .env    # then set METRA_DOMAIN and METRA_SECRET_KEY
docker compose up -d --build
```

- [INSTALL.md](INSTALL.md): installing, configuration, email and SMS,
  backups and local development
- [User guide](docs/user-guide.md): how to use readings, self-service,
  messages, newsletters, invoicing, import and roles
- [Several organisations on one server](docs/multiple-organisations.md)
- [Plugins](docs/plugins.md)
- [AGENTS.md](AGENTS.md): conventions for contributors

## Licence

MIT, see [LICENSE](LICENSE).
