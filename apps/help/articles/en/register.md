# The register

The register holds **units** (for example households, properties or boat
berths) and **people**. A person is linked to a unit as its owner, billing
contact or other contact, and one person can be a contact of several units.

## Unit types and fields

An admin sets up the kinds of units under **Settings > Unit types**, each with
its own fields, such as a property ID or meter number. Fields can also be
added for every person. Deleting a unit type or a field takes a backup first,
because it removes that data from every unit.

## Working with units and people

- **Units** and **People** list the register. Search and filter the list, then use **Export as CSV** to download what you see.
- **Add** a unit or person with the button above the list. On a unit's page, add an existing person as a contact or create a new one.
- **Archive** instead of deleting: an archived unit or person is kept, but leaves the lists and send-outs.
- **Tags** group units, for example a village or a pipe section, and messages can go to everyone with a tag.

Every change, and every time someone opens a unit or person page, is kept in
the history. Admin and Board see it at the bottom of the page.

## Importing from a spreadsheet

**Units > Import CSV** brings in units of one type, each with up to one contact:

1. Choose the unit type and the file. Save it from Excel as *CSV UTF-8*.
2. Check which column goes to which field. Matching column names are chosen for you.
3. Check the preview. Every row is marked OK, skipped (the unit already exists) or shown with its errors. Nothing is imported while any row has errors.

People are matched to those already in the register by email, then phone, so
nobody is added twice. A backup is taken before the import.

## The public page

Visitors who are not logged in see your organisation's public page: name,
logo, a short description and contact details. An admin edits it under
**Settings > Organisation**. **Notices**, such as "Water off until 18:00", are
shown on the public page and on members' pages.
