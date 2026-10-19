# Versions and releases

## The app

Metra uses [semantic versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
The version in `pyproject.toml` is the only place it is written down; the app
reads it from there (`settings.METRA_VERSION`) and shows it in the account
menu.

- **Patch** (0.4.1 → 0.4.2): bug and security fixes only, no migrations.
  Always safe to install.
- **Minor** (0.4 → 0.5): new features. May add migrations, which the web
  container runs on start.
- **Major** (1.x → 2.0): an upgrade that needs an admin to do something by
  hand, or a breaking change to the plugin API.

Until 1.0, minor releases may also break things; the changelog's upgrade
notes say how. Metra becomes 1.0 once the first organisation has run it
through a full season.

**Upgrade path.** You can upgrade from any release of the previous major
version straight to the new one. Migrations are squashed only in a major
release. Take a backup before upgrading (`manage.py backup`).

## Docker images

Tagging `vX.Y.Z` on main publishes the image to the GitHub container
registry (`.github/workflows/release.yml`):

| Tag | Moves with |
| --- | --- |
| `ghcr.io/savv3/metra:0.4.2` | never, one exact release |
| `ghcr.io/savv3/metra:0.4` | patch releases |
| `ghcr.io/savv3/metra:0` | minor and patch releases |
| `ghcr.io/savv3/metra:edge` | every push to main, for testing only |

There is no `latest`. An install follows a major version, for example
`METRA_IMAGE=ghcr.io/savv3/metra:0`, so it never crosses a major release
without someone reading the upgrade notes. Installs that build their own
image (the default in `compose.yaml`) tag it with the release version
instead, as [multiple-organisations.md](multiple-organisations.md) shows.

## The plugin API

`apps/plugins/api.py` has its own version, `API_VERSION`, a plain integer
separate from the app version:

- Adding something to the API does not change it.
- Removing or changing something in a way that can break a plugin bumps it,
  and is a major release of the app.
- `SUPPORTED_API_VERSIONS` keeps the previous API version working for one
  more major release, so plugins have time to catch up.

Each plugin names the API versions it works with in `metra_api` on its
AppConfig (see [plugins.md](plugins.md)). If none is supported, the app
refuses to start and says which plugin is the problem (`plugins.E001`).

## Plugins

Each plugin package has its own semantic version in its `pyproject.toml`,
independent of the app. While a plugin lives in `plugins/`, its releases are
tagged `<plugin>-vX.Y.Z`, for example `example-v0.2.0`. The scheme stays the
same when it moves to its own repository. A plugin release that drops an
API version is a major release of the plugin.

## Changelog

[CHANGELOG.md](../CHANGELOG.md) follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Every pull request
that changes something users, admins or plugin authors notice adds a line
under **Unreleased**. Write for an admin of a small association, not for a
developer.

## Making a release

1. Rename **Unreleased** in `CHANGELOG.md` to `[X.Y.Z] - YYYY-MM-DD`, add
   **Upgrade notes** if an admin must do anything, and start a new empty
   **Unreleased** section.
2. Set the same version in `pyproject.toml` and run `uv lock`.
3. Merge that as a pull request, then tag the merge commit and push the tag:
   `git tag vX.Y.Z && git push origin vX.Y.Z`.

The release workflow checks that the tag matches `pyproject.toml`, publishes
the images and creates the GitHub release from that changelog section.
