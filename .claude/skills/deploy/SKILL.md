---
name: deploy
description: Deploy a tagged Metra release to the offline server with scripts/deploy.sh. Use when asked to deploy, upgrade or roll out a version.
---

# Deploy Metra

Follow [docs/deploying.md](../../../docs/deploying.md). This skill runs on a
machine that has internet and SSH access to the server (the maintainer's
laptop), never on the server itself.

## Before deploying

1. Deploy only when the maintainer asked for it in this conversation, and only
   the version they named. "Latest" means the newest `vX.Y.Z` tag
   (`git fetch --tags && git tag --sort=-v:refname | head -n 1`). Never deploy
   a branch, `edge` or uncommitted code.
2. Read the version's section and its **Upgrade notes** in `CHANGELOG.md` at
   that tag. Stop and ask if there are upgrade notes, if the major version
   changes, or if the server is more than one minor version behind.
3. Run the dry run and read its output:

   ```sh
   scripts/deploy.sh -n X.Y.Z
   ```

   Stop and report if it fails (no tag, SSH refused, no install folder).

## Deploying

```sh
scripts/deploy.sh X.Y.Z
```

Pass `-H` or `-d` only if the maintainer named another server or install.
The build can take several minutes on Apple silicon.

## Afterwards

- On success, report the version now running and the backup name the
  script printed.
- On failure, the script has already gone back to the previous image. Report
  the error and the last log lines. Do **not** restore the backup, delete
  volumes or containers, or edit `.env` on the server without the
  maintainer's explicit go-ahead: say what you would do and wait.
- Never change SSH, firewall, user or Cloudflare settings on the server.
