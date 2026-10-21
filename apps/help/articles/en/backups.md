# Backups and restore

Metra keeps **backups**: copies of the whole register and all uploaded files.

## When a backup is taken

- every night,
- when a new version of Metra starts, before it changes anything,
- before a CSV import, before deleting a unit type or a field, and before a restore,
- whenever an admin clicks **Take a snapshot now** under **Settings > Backups**.

If the backup before a risky action cannot be taken, the action is stopped.

Every backup is kept for 7 days, then one a week for 4 weeks and one a month
for a year. Backups taken by hand stay until an admin deletes them. When the
installation is set up for it, each backup is also sent, encrypted, to
storage outside the server.

## The Backups page

**Settings > Backups** lists every backup with when and why it was taken, the
Metra version, its size, and whether it is on this server, offsite, or both.
Recent problems are shown at the top.

## Restoring a backup

Restoring a backup from the Backups page is coming in the next version: an
admin will pick a backup, see what it holds and what would be removed, and
confirm. Until then, whoever runs the server can restore one as described in
the installation guide.
