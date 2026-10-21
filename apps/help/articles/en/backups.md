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

Restoring puts the whole register and all files back as they were when the
backup was taken. Only admins can do it.

1. Open **Settings > Backups** and choose **Restore…** next to the backup.
2. Enter your password or two-factor code again.
3. Check what changes: how many units, people, readings, messages, invoices and payments there are now and in the backup. Invoices issued and payments recorded since the backup are listed, and must be confirmed separately, because they may already be in the bookkeeping.
4. Tick the box and choose **Restore this snapshot**.

A backup of the data as it is now is taken first, so a restore can be undone
by restoring that one ("Before a restore" in the list). While the restore
runs, everyone sees a short "Back in a moment" page; it usually takes less
than a minute, and you may need to log in again afterwards. If anything goes
wrong, the data from just before is put back by itself.

A backup made by a newer version of Metra cannot be restored. If the app
does not start at all, whoever runs the server can restore a backup from the
command line, as the installation guide describes.
