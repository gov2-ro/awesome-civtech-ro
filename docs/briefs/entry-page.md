# Brief — the entry as a full page, with structured data

Date: 2026-11-18. Author: coordinator (Opus). Executor: Sonnet. Status: ready.

## Goal

Today a click in the list opens the entry in a drawer over the list (`renderDetail()` in `site/app.js`).
The drawer holds too much, and search engines see only a `<noscript>` summary of each entry.

Replace the drawer with a full page for each entry. The page has the layout of a documentation site:
a list of the section on the left, like a table of contents, and the entry on a "sheet" to the right.
The same page goes into the static HTML that `build.py` writes, with JSON-LD and breadcrumbs.

This brief covers three backlog items in `docs/BACKLOG.md`: "SEO steps 2–3" and "Entry as a full page".

## The reference: the mock-up

`docs/briefs/entry-page-mock/index.html` is the approved mock-up. The owner reviewed it on 2026-11-18.
It is one HTML file with its own CSS and JS. It reads `../data.json` and `../style.css`.

To see it, build a preview and copy the mock-up into it:

```sh
python3 scripts/build.py --data-dir data/taxonomy-v2/integrare --site-dir /tmp/civtech-v2 --allow-draft
mkdir -p /tmp/civtech-v2/mock && cp docs/briefs/entry-page-mock/index.html /tmp/civtech-v2/mock/
python3 -m http.server -d /tmp/civtech-v2 8765   # http://localhost:8765/mock/?slug=sicap-ai
```

Copy its layout, its CSS and its order of sections. Do not copy its code structure: it is a throw-away file.
Where this brief and the mock-up differ, this brief wins.

## Decisions (do not reopen)

### Navigation

1. **A click in the list opens the full page.** The drawer goes away. Remove its code (`renderDetail()` drawer branch, the drawer
   slot, its touch handlers, its focus trap) when nothing uses it. The filter sheet for phones (`slot('sheet')`) stays.
2. **One app, two views.** `site/app.js` stays one script. When `state.p` is set, it shows the entry view; else it shows the list view.
   The address stays `/<kind>/<slug>/?<filters>`, as today (`writeURL`, `hrefFor`). The old `?p=<slug>` links still open the entry.
3. **The filters of the list ride along.** The entry view keeps the list's query. The left list shows the same entries as the
   list view, in the same order and with the same groups (`matches`, `sorted`, the subject groups of the sort `subiect`).
4. **Back to the list.** "← filtre" at the top of the left list, `Esc`, and the browser's back button return to the list view.
   The list keeps its filters and its scroll position, and the focus goes to the row of the entry that was open.
5. **Keys.** `j` / `→` go to the next entry, `k` / `←` to the previous one, in the order of the left list. `o` opens the entry's
   site. `/` focuses the search. Typing a query while an entry is open returns to the list view with the query.
   On a touch screen, a horizontal swipe on the sheet steps like `j`/`k` (the drawer has this code today; move it).
6. **Previous and next** at the bottom of the sheet follow the left list's order, not A–Z. Between them: "înapoi la <section>".
7. **Focus and scroll.** Opening an entry scrolls the page to the top and moves the focus to the `h1` (`tabindex="-1"`).
   The title, the canonical link and the share tags follow the address, as `syncTitle()` does today.

### Layout (see the mock-up)

0. **The entry view keeps the site's header as it is**: the rotating title, the tabs with their counts, the search, the links
   "[?]" and GitHub (owner, 2026-11-18). The mock-up's header is a simplification: do not copy it. The tab of the entry's section
   is the current tab.

8. **Three zones at 1200 px and wider:** the left list (260 px), the sheet with the main column, and the facts box (300 px) on the
   right of the main column, sticky. From 900 to 1199 px the facts box goes under the top block of the sheet. Below 900 px there is
   one column: the left list is hidden, and a button "☰ <Section> · N" opens it full screen, with a button "Închide".
9. **The sheet.** The page behind it is `var(--surface)`. The sheet is `var(--bg)`, with a 1 px left border, a 2 px top-left radius
   and a soft shadow on its left edge. The current entry in the left list has the sheet's colour, so that it seems to join the sheet.
10. **The left list.** Each row has the icon (20 px) and the name, on one line. A long name runs under the sheet: it does not wrap
    and does not end in "…". The list scrolls, with no visible scrollbar. The group headers (subjects) stay visible while it scrolls.
    At the top there is only the link "← filtre" (title "Înapoi la lista cu filtre"); the section name is not shown, because the tab
    names it. When a filter is set, a line under it names the filters and offers "toată secțiunea". Inactive entries are greyed.
    On load, the list scrolls so that the current entry is in the middle.
11. **The top block of the sheet:** breadcrumbs (section › primary subject, both links to the filtered list); the icon and the `h1`;
    the tagline; the description with no heading; then one row with the site as a plain link with "↗" (muted, not linked, when the
    entry is offline or archived), the buttons "Arhivă" and "Datele proiectului" when they apply, and the badges. The share image is
    on the right at 1200 px and wider.
12. **The main column**, in this order: "Date & metodă" (the existing `inventoryHTML()` and `structureHTML()`, unchanged in
    behaviour); "Clasificare" (each label is a link to the list filtered by that label); "Conține (N)" (every `parte_din` child);
    "Proiecte și resurse (N)" on an organisation, "Același autor (N)" elsewhere (every entry, no cap); "Tot din <subject>" (6 entries).
    The cards are the mock-up's `.p-card`. An organisation's projects stay after "Clasificare".
13. **The facts box:** Autor (links to the organisation's page), Parte din, Site, Linkuri, Cod sursă, the repository statistics
    (`repoRow`), Licență, Contact, Acoperire, Date, Surse de date (links to the filtered list), Arhivă, Prima urmă, Actualizat, Stare.
    Under it: the existing "Semnalează o problemă" (`flagHTML`).
    - Links to networks show the network's logo (`NETWORK` in `app.js`), with the name in `title` and `aria-label`; the other links
      stay as text, after the logos.
    - "Cod sursă" shows the forge's logo and the path without the host. `codeLink()` in `app.js` does this already.
14. **Nothing is lost.** Everything that the drawer shows today is on the page. One exception: the organisation card
    (`orgCard`) goes away, because "Autor" links to the organisation's page.

### Static HTML and structured data (SEO steps 2 and 3)

15. **`build.py` writes the entry view into each entry page**, in place of today's `<noscript>` summary: the top block, the facts
    box, the main column's sections with their links, and the left list of the whole section (no filters, the default grouping).
    Use the same elements and classes as `app.js`, so that the page does not jump when `app.js` renders over it.
    `app.js` may render over the static markup; it does not need to reuse it.
    The static "Date & metodă" may be a short summary (count, examples, a link to `/date/<slug>/`).
16. **JSON-LD** in `<head>` of each entry page, one `<script type="application/ld+json">` with an `@graph`:
    - a `WebPage` for our page (`url`, `name`, `inLanguage: "ro"`, `breadcrumb`, `mainEntity`, `isPartOf` the `WebSite`);
    - a `BreadcrumbList`: "CivTech România" › the section › the entry;
    - the entry itself, with a type by section: `proiect` → `WebApplication`; `organizatie` → `NGO` when its organisation type is
      an NGO, else `Organization`; `resursa` → `CreativeWork`; `publicatie` → `Report`.
      Fields when the data has them: `name`, `description`, `url` (the entry's own site), `image`, `sameAs` (the links),
      `author` or `creator` (from the attributions; an organisation in the catalogue gets its page as `@id`), `isPartOf` (`parte_din`),
      `about` (the subjects, as `DefinedTerm` with their labels), `spatialCoverage` (the areas), `dateModified` (`updated`),
      `license`, `codeRepository` on a `WebApplication`, `inLanguage`.
    - Leave out a field with no value. Do not invent a value (no ratings, no prices, no dates of launch).
    - The home page gets a `WebSite` with a `publisher` (`Organization` "gov2.ro", `https://gov2.ro`).
17. **The stub pages of moved entries** (`redirect_stubs`) do not change. The sitemap does not change.

## Out of scope

- The list view, the header and the footer. (Uncommitted header and footer changes may be in the tree when you start; keep them.)
- `/date/` and its `noindex`.
- New data, new fields in `data.json` (if the static page needs a value that `data.json` has, read it there; stop and ask before
  you add a field to `data.json`).

## Tests and checks

- `scripts/test_taxonomy_v2.py` (or a new test file next to it): the static page of one entry per section has the `h1`, the
  description, one left-list link for each entry of the section with `aria-current` on its own, the breadcrumbs, and valid JSON-LD
  (`json.loads`, the type by section, the `BreadcrumbList` with 3 items). An entry with no description and no image builds.
- `scripts/check_preview.py`: replace the drawer checks with checks of the entry view. At least: a click on a row opens the full
  page at `/<kind>/<slug>/` with no drawer; the left list marks the entry; `j`/`k` follow the left list; `Esc` returns to the list
  with the filters, the scroll position and the focus on the row; a filter in the query narrows the left list; `?p=<slug>` opens
  the entry; at 390 px the button opens the left list and there is no horizontal scroll; no page errors, in both themes.
- Keep the other three browser suites passing: `check_inventory_preview.py`, `check_data_finder.py`, `check_structure_preview.py`.
  They open entries through the drawer in places; move those steps to the entry view.
- Run all of `python3 -m unittest discover -s scripts -p "test_*.py"` and the four browser suites before you report. CI runs them.
- Validate two JSON-LD blocks by hand in a schema validator if you have network access; else say that you did not.

## Process

- Work on `main` in this tree. Commit in two or more steps (for example: the entry view in `app.js`/`style.css`; the static page and
  JSON-LD in `build.py`; the checks). Do not push.
- Commit `site/index.html` after a CSS or JS change (`build.py` rewrites the `?v=` hashes).
- Bump the minor version: a line in `docs/RELEASES.md`, a tag. Update `docs/ACTIVITY.md` (Done / Hard / Decided, with measured
  numbers: page size of a static entry page before and after, number of links in it) and flip the two backlog items.
- Update `CLAUDE.md` and `docs/ARCHITECTURE.md` where they describe the drawer or the `<noscript>` summary.
- **Stop and ask** before you change a decision above, add a field to `data.json`, or change a file outside `site/`, `scripts/`
  and `docs/`.

## Report

What you changed, file by file; the test and check counts; the page sizes; screenshots at 1440, 1024 and 390 px in both themes
(paths); what you assumed; what you could not do.
