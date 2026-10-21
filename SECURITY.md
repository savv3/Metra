# Security policy

Metra keeps people's names, addresses, phone numbers and invoices, so we take
reports of security problems seriously.

## Reporting a vulnerability

Please do not open a public issue. Report it privately through GitHub's
[private vulnerability reporting](https://github.com/savv3/Metra/security/advisories/new)
instead, with:

- what the problem is and what an attacker could do with it,
- the steps or a request that shows it,
- the Metra version (shown in the account menu, or the image
  tag) and whether it runs with Docker Compose.

You should get an answer within a week. We will tell you when a fix is
released and, if you want, credit you in the changelog.

## Supported versions

Security fixes go into the latest minor release (for example 0.3.x) and are
published as a new patch version. Upgrade by pulling the new image, as
[docs/releasing.md](docs/releasing.md) describes.

## Scope

In scope: the Metra app and the official add-ons in `plugins/`, and the
Docker, Caddy and deploy files in this repository.

Out of scope: problems that need an admin account or access to the server
or its `.env` file, and third-party add-ons not kept in this repository.
