# Interface conventions

Read this when you add or change a page or template. Every page follows the
same layout, so people find actions in the same place.

## Buttons and actions

- One primary (blue) button per page or step: what most people came to do.
- Page actions sit in the heading row (`.page-head .actions`), primary
  last. More than three: rarely used ones go in a "More" menu
  (`<details class="more-menu">`), and so do destructive ones such as
  Archive.
- A section's actions sit at the right of its heading (`.section-head`).
  Forms for adding things open from a button (`<details class="add-panel">`)
  instead of always showing.
- Form actions go at the bottom: the primary first, then Cancel as a link
  (`button button--link`).
- Pages below the first level show the way back above the heading with
  `{% crumbs url label ... %}` (from `nav`), never a "back" button named
  after the parent page.
- Sibling pages of one section are tabs (`.filter-tabs`), not buttons.
- Filter bars update as you type (HTMX); their Filter button only shows
  without JavaScript. Keep filters and action buttons in separate rows.

## Help articles

The in-app help articles are Markdown in `apps/help/articles/<language>/`,
in Swedish, English and Finnish. A change users notice updates the article
that describes it, in all three languages.
