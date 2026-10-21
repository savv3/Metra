# Deploying to a server without internet access

This is how a release gets onto a server that has no internet access, such as
a Fedora server behind a Cloudflare Tunnel. A machine that does have internet
(your laptop) builds the image and copies it over SSH, and the server only runs
it. The same steps work by hand or from a Claude Code session using the
`deploy` skill in `.claude/skills/deploy/`.

## Once: set up the server

Run Metra as an ordinary user with rootless Podman, so SSH never needs to
allow root and the containers have no root rights on the host.

1. Install Podman and podman-compose (`sudo dnf install podman podman-compose`;
   without internet, download the RPMs elsewhere with `dnf download --resolve`
   in a `fedora` container and install them with `sudo dnf install ./*.rpm`).
2. Create the user and let its containers run without anyone logged in:

   ```sh
   sudo useradd --create-home metra
   sudo loginctl enable-linger metra
   ```

   Fedora gives new users the subordinate ids rootless Podman needs.
3. Put your laptop's SSH public key in `/home/metra/.ssh/authorized_keys`
   (mode 600, folder mode 700, owned by `metra`). Key login is enough; the
   user needs no password and no sudo.
4. As `metra` (`ssh metra@server`), make the install folder and start Podman's
   restart service, which brings the containers back after a reboot:

   ```sh
   mkdir ~/metra
   systemctl --user enable --now podman-restart.service
   ```

5. Copy `compose.yaml` and `.env.example` from the release into `~/metra/`.
   Copy `.env.example` to `.env`, `chmod 600 .env`, and set at least
   `METRA_SECRET_KEY`, `METRA_DEBUG=false`, `METRA_ALLOWED_HOSTS`,
   `METRA_CSRF_TRUSTED_ORIGINS` and `METRA_TIME_ZONE`.
   `docker/new-instance.sh` does this for you, including the next step; see
   [multiple-organisations.md](multiple-organisations.md).
6. Publish the app on localhost only, for the tunnel, in
   `~/metra/compose.override.yaml`:

   ```yaml
   services:
     web:
       ports:
         - "127.0.0.1:8000:8000"
   ```

   Then point the Cloudflare Tunnel's public hostname at
   `http://localhost:8000`. Skip the `caddy` service: Cloudflare handles TLS.

If Metra already runs as root, move it: take a snapshot
(`podman-compose exec web python manage.py snapshot`), copy it to the
new user, deploy there, and restore it as [INSTALL.md](../INSTALL.md#restore-onto-a-fresh-install)
describes. Then stop the root containers.

## Once: set up your laptop

- Docker or Podman. Builds for the server's CPU; on Apple silicon an
  `x86_64` server's image is built under emulation, which is slower.
- An SSH entry for the server, so the scripts need no host names:

  ```
  Host metra
      HostName <the server's address>
      User metra
  ```

- A checkout of this repository with the release tags.

## Each release

Tag the release on `main` first (see [releasing.md](releasing.md)), then from
the checkout:

```sh
scripts/deploy.sh -n 0.2.0   # dry run: checks the tag, the server and the install
scripts/deploy.sh 0.2.0
```

`deploy.sh` builds the image from the tag `v0.2.0` for the server's CPU,
copies it and `docker/upgrade.sh` to the server, and runs the upgrade there.
`upgrade.sh`:

1. takes a snapshot (`manage.py snapshot`) if the app is running,
2. loads the image as `metra:0.2.0` and sets `METRA_IMAGE=metra:0.2.0` in
   `.env`,
3. recreates the `web` and `worker` containers (migrations run on start),
4. waits for `/healthz` to answer, and goes back to the previous image if it
   does not.

Going back to the previous image does not undo migrations. If the new version
ran migrations before it failed, restore the backup taken in step 1.

Options: `-H HOST` for another SSH host (default `metra`), `-d FOLDER` for
another install folder in the user's home (default `metra`, for example
`-d metra/vatten` with several organisations). `METRA_PLUGIN_PACKAGES` is
passed to the build, and `METRA_DOCKER=podman` builds with Podman.

Read the release's **Upgrade notes** in `CHANGELOG.md` before deploying, and
never skip a major version.
