# Changelog

All notable changes to Metra are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[semantic versioning](https://semver.org/) as described in
[docs/releasing.md](docs/releasing.md).

Every pull request that changes what users, admins or plugin authors see adds
a line under **Unreleased**. A release renames that section to the version
and date. **Upgrade notes** says what an admin must do when upgrading
(beyond pulling the new image), and is left out when there is nothing.

## [Unreleased]

## [0.2.0] - 2026-10-19

### Added

- The release version is shown in the account menu.
- Plugins declare the plugin API versions they work with (`metra_api`), and a
  plugin made for another API version stops the app with a clear error.
- Tagged releases publish Docker images to the GitHub container registry.
- `scripts/deploy.sh` builds a release on a laptop and deploys it over SSH to
  a server without internet access; `docker/upgrade.sh` on the server takes a
  backup first and goes back to the previous image if the new one is not
  healthy. See `docs/deploying.md`.

## [0.1.0]

Development version before the first release: everything built
from the start of the project until versioning was set up.
