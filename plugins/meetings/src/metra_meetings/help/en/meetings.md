# Meetings and minutes

With the meetings plugin, the association calls, holds and minutes its
meetings in Metra: annual meetings, extraordinary meetings and board
meetings. Approved minutes are kept as the association's records and members
can read them on their personal page.

The plugin is turned on by the person running the installation
(`METRA_PLUGINS=meetings`). **Meetings** then shows under Communication in the main menu.

## Who can do what

- **Admin** can do everything, including deleting a meeting that is not approved.
- **Board** prepares meetings, keeps the attendance and writes the minutes.
- **Treasurer** and **Read-only** can look at meetings and their minutes.
- The **minute checkers** of a meeting approve its minutes. Anyone with a
  login can be a checker, whatever their role.

## Prepare the meeting

1. Under **Meetings**, click **New meeting**. Choose the kind, write a title,
   the date, time and place, and anything else the invitation should say. Under
   **Agenda**, the meeting starts with the agenda template for its kind
   (see below), or another template, or an empty agenda.
2. Tick **One vote per unit** if each unit (household or member) has one
   vote. Otherwise everyone present has a vote.
3. Choose the chair, the secretary and the minute checkers if you already
   know them. You can change them until the minutes are approved.
4. Check the agenda, and add items with **Add an item**, one item
   (paragraph, §) at a time. Items are listed by their order number; the
   description is shown on the agenda.

## Agenda templates

An agenda template is the usual agenda of a kind of meeting. Metra starts
with one for annual meetings and one for board meetings, with the items the
Associations Act expects; adapt them to your rules. Open them with
**Agenda templates** on the Meetings page, or under **Settings**
(**Organisation**), or under **Settings > Add-ons > Meetings > Settings**.

Write one item per line, in order. **For** says which kind of meeting starts
with the template; leave it empty for a template you choose by hand, for
example for a spring cleaning day. Changing a template does not change
meetings already added. Admins and the board edit templates; the others can
look at them.

## Call the meeting

Click **Send invitations**. A new message opens with the invitation written,
the agenda attached as a PDF and a calendar file attached, so people can add
the meeting to their calendar with one click. It is set to go by email;
choose who gets it (for example everyone, only each unit's main contact, or
the people tagged as the board), check the text and send as with any
message. If you choose SMS as well, SMS recipients get a link to the files.
Once the invitation is sent, the meeting is marked as called. You can send
more invitations later, for example to someone who was missed.

Sending messages to everyone needs the right to send messages, which only
admins have unless they give it to the board.

## Reminders

**Reminder, days before** on the meeting says when everyone who got the
invitation gets a reminder, with the agenda and the calendar file again. It
is 3 days unless you change it; leave it empty for no reminder. The reminder
goes out once, in the morning of that day, by the same channel as the
invitation. It is skipped if the invitation itself went out on or after that
day. To remind people sooner, click **Send a reminder now** under
**Invitations and reminders** on the meeting's page.

If you change the date, time or place after the invitations went out, the
meeting's page offers **Send an updated invitation**. Everyone invited then
gets the new details and a calendar file that moves the meeting in their
calendar. A meeting that moved gets its reminder again before the new date.

Each invitation, reminder and update is listed on the meeting's page and
under **Messages**, with who got it.

## At the meeting

Open **Attendance** and add the people present from the register. When the
meeting has one vote per unit, the first person present for a unit gets its
vote and the others none; write a proxy if someone votes for another unit.
The page shows the number present and the total of votes.

Afterwards, click **Write the minutes** and write what was discussed and
decided under each item. Then click **Mark as held**.

## Approve the minutes

When the meeting is marked as held, each minute checker sees
**Check and approve the minutes** on the meeting's page and on the Meetings
page. They read the minutes (also as a PDF) and click
**Approve the minutes**.

If the minutes are changed before everyone has approved, the approvals so
far are removed, so the checkers always approve the final text. When every
checker has approved, the minutes are **approved** and can no longer be
changed. A mistake found later is corrected in the minutes of a later
meeting.

## What members see

Approved minutes of meetings marked **Show the approved minutes to members**
are listed on each member's personal page, newest first, and open as a PDF.
Minutes that are not approved are never shown to members.
