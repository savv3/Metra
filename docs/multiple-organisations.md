# Running several organisations on one server

Each organisation gets its own, fully separate install: its own folder,
`.env`, containers, database, uploads and backups. Nothing is shared except
the image, which only holds the program. There is no multi-tenant mode and
no shared database, so one organisation can never see another's data, and
each can be backed up, upgraded, restored or removed on its own.

## How the installs are kept apart

Docker Compose and podman-compose name every container and volume after the
*project*, which is `COMPOSE_PROJECT_NAME` from `.env`, or else the folder
name. An install in `~/metra/vatten` therefore runs `vatten-web-1` and
`vatten-worker-1` on the volume `vatten_data`, and one in `~/metra/golf` uses
`golf_data`. All of an install's data is in that one volume (`/data`).

The only thing two installs would fight over is the host port, so each one
publishes its web container on its own port on `127.0.0.1`, and the tunnel
(or a reverse proxy on the host) sends each host name to its port.

## Add an organisation

This assumes the setup in the offline Fedora server guide: Podman,
podman-compose, the image loaded with `podman load`, and a Cloudflare
Tunnel in front. Copy `docker/new-instance.sh` to the server once, next to
`compose.yaml` and `.env.example` (for example in `~/metra/`), then for each
organisation:

```sh
cd ~/metra
./new-instance.sh vatten register.example.org 8001
```

The arguments are a short name (lower-case letters, digits, `-` or `_`), the
public host name and a free port. The script creates `~/metra/vatten/` with:

- `compose.yaml`, a copy of the shared one;
- `.env`, from `.env.example`, with `COMPOSE_PROJECT_NAME`, the host name,
  `METRA_ALLOWED_HOSTS`, `METRA_CSRF_TRUSTED_ORIGINS` and a new random
  `METRA_SECRET_KEY` filled in (readable only by you);
- `compose.override.yaml`, which publishes the app on `127.0.0.1:8001`.

It refuses a name whose folder already exists and a port another install in
the same parent folder already uses. Then:

```sh
cd ~/metra/vatten
# edit .env: email, SMS, backups, time zone
podman-compose up -d web worker
podman-compose exec web python manage.py createsuperuser
```

In Cloudflare, add the public hostname `register.example.org` with service
`http://localhost:8001`. Use a separate host name (a subdomain is fine) for
each organisation; installs cannot share one host name under different paths.

`podman-restart.service` (see the server guide) brings every install back
after a reboot; nothing per install is needed.

Without a tunnel, run one reverse proxy on the host for all installs instead
of each install's `caddy` service (they would all want ports 80 and 443).
For example a host Caddyfile:

```
register.example.org {
	reverse_proxy 127.0.0.1:8001
}
golf.example.com {
	reverse_proxy 127.0.0.1:8002
}
```

## Things that must differ per install

- **Offsite backups.** Give each install its own `METRA_BACKUP_REMOTE_PATH`
  (and its own `METRA_BACKUP_ENCRYPTION_PASSWORD`). The backup keeps only the
  newest `METRA_BACKUP_KEEP` archives in that folder, so two installs sharing
  one would delete each other's backups.
- **Email and SMS senders.** `METRA_EMAIL_FROM` and `METRA_SMS_SENDER` should be
  the organisation's own, and each organisation should normally use its own
  46elks and mail accounts, so costs and bounces stay with it.
- **Backup times.** Spread `METRA_BACKUP_TIME` (for example 02:30, 02:45) so
  the installs do not all back up at once.

## Upgrades

All installs run `metra:latest` unless told otherwise. After
`podman load` of a new image, upgrade each install with
`podman-compose up -d web worker` in its folder (migrations run on start).
Upgrade them all at once:

```sh
for d in ~/metra/*/; do (cd "$d" && podman-compose up -d web worker); done
```

To upgrade one organisation first, tag the new image with its release
version (see [releasing.md](releasing.md)) and set `METRA_IMAGE` in that
install's `.env`:

```sh
podman tag metra:latest metra:0.2.0
# in ~/metra/vatten/.env: METRA_IMAGE=metra:0.2.0
```

When the shared `compose.yaml` changes, copy it into each install folder
again; the install's settings live in `.env` and `compose.override.yaml`,
which the copy does not touch.

## Remove an organisation

Take a last snapshot first (`podman-compose exec web python manage.py snapshot`
and copy it off the server), then, in its folder:

```sh
podman-compose down
podman volume rm vatten_data
```

and remove its host name from the tunnel. The other installs are not
affected.

## An existing single install

An install made before this, such as one in `~/metra/` itself, keeps working
as it is (project `metra`, volume `metra_data`, port 8000). New installs can sit
next to it in subfolders, as long as they use other ports.
