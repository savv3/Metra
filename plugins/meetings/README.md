# Meetings plugin

Annual meetings, extraordinary meetings and board meetings in Metra:

- the meeting's date, time, place and agenda;
- the notice of meeting, opened as a new message with the agenda attached
  as a PDF, so staff choose the recipients and check it before sending;
- attendance from the register, with one vote per unit or one per person
  present, proxies and the total of votes;
- minutes and a decision for each agenda item, with the chair, the
  secretary and the minute checkers;
- a PDF of the minutes, which the minute checkers approve in the app. Once
  everyone has approved, the minutes never change;
- approved minutes listed on the members' personal pages, as PDFs;
- agenda templates: the usual agenda of each kind of meeting, which new
  meetings start with. Templates for annual and board meetings are added in
  the installation's language when the add-on is first migrated. They are
  edited under Meetings > Agenda templates, also linked from Settings >
  Organisation and Settings > Add-ons > Meetings.

Official, but off until `METRA_PLUGINS=meetings`. The Admin role can do
everything, Board runs meetings (but cannot delete them), Treasurer and
Read-only can look. Each meeting's minute checkers approve its minutes,
whatever their role. Sending the notice to everyone needs the
`messaging.send_broadcast` permission (Admin by default).

Personal data: the attendance (who was present, for which unit, with how
many votes and any proxy). Approved minutes keep the names as they were,
since they are the association's records.

The guide for users is in `src/metra_meetings/help/` (Swedish, English and
Finnish), shown in the app's help pages.
