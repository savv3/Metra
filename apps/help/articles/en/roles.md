# Users, roles and two-factor login

## Roles

Everyone who works in Metra has an account with one role:

| Role | Can |
| --- | --- |
| Admin | Everything, including Settings |
| Board | See and edit units, people, contacts and tags, enter readings, write to one household, see history |
| Treasurer | See the register, and run invoicing and payments |
| Read-only | See the register |

An admin invites users under **Settings > Users and roles > Users > Add
user**, or with the setup wizard's **Invite the board** step. You enter a name,
email and role, no password: the new user gets an email with a link where they
choose their own password, and an admin then sets up two-factor login. The
link works for a few days and only once.

If the link has stopped working, tick the user in the list, choose the action
**Send a new invitation link** and press **Go**. When email is not set up, the
link is shown once on the page so you can send it yourself.

## Two-factor login

Two-factor login protects the register with a code from an authenticator
app on your phone, such as Aegis, Google Authenticator or 1Password. Every
user must turn it on before they can use Metra, because every role can see
members' personal details. (An installation can be set to require it of
admins only.)

To turn it on, open **My account** in the menu under your name and choose
**Turn on two-factor login**. Scan the QR code with the app, enter the
six-digit code, and save the recovery codes somewhere safe: they let you in
if you lose your phone. From then on, every login asks for a code.

Some actions, such as restoring a backup, ask for your password or code again
even when you are logged in.

## History

Every change to the register, every role change and every opened unit or
person page is recorded. Admin and Board see the history at the bottom of
unit and person pages.
