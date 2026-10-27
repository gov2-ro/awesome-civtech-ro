# Brief — a variables page for each project, data set facts, and fields added by an editor

Date: 2026-10-27. Baseline: commit `ad20dda`.
Status: ready for implementation.

## 1. Start here

Read these files first:

- `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md` (the 2026-10-26 and 2026-10-27 entries).
- `scripts/inventory_site.py`: `publish_finder`, `publish_overview` (`/date/lista/`), `publish_preview` (the files `inventar/<slug>.json`), `dataset_summary` and `source_licence`.
- In `site/app.js`, the „Date & metodă” panel (`inventoryHTML` and the code that fills `data-inventory-body`). This brief calls that panel the field browser.
- The inventory sections of `docs/DATA-SCHEMA.md`.
- `scripts/check_inventory_preview.py` and `scripts/check_data_finder.py`.

Copy this prompt into the implementation session:

> Implement `docs/briefs/variable-pages.md`, parts A, B and C, in this order.
> Make no network request. Show no value of a data body that the site does not show today.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 6.

## 2. Goal

The owner approved three backlog items on 2026-10-27:

- **A.** A variables page for each project: the source field names of one project, by family and by source.
- **B.** The data set facts that a page declares, shown in the field browser and on the page of part A.
- **C.** A file in which an editor adds a field that the readers missed.

## 3. Decisions

### A. The variables page of a project

1. `build.py --with-inventory` writes `site/date/<slug>/index.html` for each entry that has field records. Use the scope rule of `/date/`: entries out of scope get no page.
2. Make the page a static HTML page, like `/date/` and `/date/lista/`. It uses the same stylesheet and the same header and footer. A visitor can read it without JavaScript.
3. Put these parts on the page, in this order:
   1. **Header.** The name of the entry and its link to the explorer entry (`/<kind>/<slug>/`). Then the relation to data (the label of `relatie_date`), the count of sources and the count of fields. Add the note „Inventar parțial” that the field browser uses.
   2. **„Pe familii”.** Show one block for each family, in the order of the families on `/date/lista/`. In each block, list the groups, and for each group the source fields that match it (source title, then the path of the field). Then add a block „Altele” with the fields that match no group.
   3. **„Pe surse”.** Show one block for each structured source:
      - the source title, its address, its format and its licence (`source_licence`);
      - its data set facts (part B);
      - its fields: name, path, observed or declared type, unit, description, group.
4. Link every row of `/date/lista/` to the page of its entry. In the field browser, add a link „Toate variabilele” to the page of the entry.
5. Use the same source titles as the field browser, for example the sheet titles of `sheet_titles`. Use the same rules for which fields the browser folds or ranks. Do not make a second set of rules.
6. Show only what the field browser and `inventar/<slug>.json` show today: names, paths, types, units, descriptions and groups. Show no value of a data body, no example value and no evidence fragment.
7. Design for the desktop first. At a width of 375 px, the page must not scroll sideways. A wide table may scroll inside its own frame, as on `/date/lista/`.
8. Add the pages to the sitemap or the index that `build.py` writes, if such a list exists for the other pages.

### B. Data set facts

1. Show the facts that a source declares about its data sets:
   - The `seturi` of a page with described data sets (`html-lista-seturi`): the title, the category, the description and the related reports.
   - The `seturi_ld` of a page with a schema.org `Dataset`: the name, the period, the licence and `isBasedOn`.
   - The `set_date` that `dataset_summary` reads today.
2. Show a fact only when the source declares it. Name its basis with the labels of the review interface (`BASIS_LABELS`), for example „declarat”.
3. Show the facts in the field browser, under the source, and in the „Pe surse” part of the page of part A.
4. Keep the size of `inventar/<slug>.json` small. Cut a long description at 300 characters, and keep the full text only on the page of part A.

### C. Fields added by an editor

1. Add the hand-edited file `data/taxonomy-v2/observatii/inventare/campuri-editor.csv`, with these columns: `slug`, `url_sursa`, `nume`, `cale`, `rol`, `tip_declarat`, `unitate`, `descriere`, `fragment`, `nota`.
   - Keep the file UTF-8 and comma-separated, so that it goes through Google Sheets.
   - Start it with the header row only. Put the test rows in the tests, not in the file.
2. `inventory.py` reads the file. It adds each row as a field record of the source with that URL, with `stare_tip` `adaugat-de-editor`.
   - Merge the row into the field records before the group matching runs, so that a group selector can match it.
   - A row for a URL that is not a source of that entry is an error.
3. Each row must carry evidence. `fragment` is a text that occurs in the retained body or snapshot of `url_sursa`. `inventory.py --check` finds the fragment and records its hash, as for the other evidence.
   - A fragment that does not occur is an error.
   - A fragment that the check cannot read is reported as „not verified”, not as an error, as for the other bodies that are not in the cache.
   - For a source marked `persoane`, the fragment must not hold a value that identifies a person. Run the leak check of `inventory_persons` on the file.
4. `validate.py` checks the columns and the code lists (`rol`, `tip_declarat`), as for the other hand-edited files.
5. The field browser and the page of part A show an editor-added field with the label „adăugat de editor”.
6. Do not add a form for this file to the review interface. Add a backlog item for the form instead.
7. Document the file in `docs/DATA-SCHEMA.md` and in the Romanian guide `data/taxonomy-v2/README.md`.

## 4. Limits

- Make no network request. The work uses the cache, the generated files and the retained bodies only.
- Do not write into `data/taxonomy-v2/source/`, `reference/` or `runs/`. Do not decide a review item. Do not change a group or a member.
- No test may pin data that the owner edits. For example, a test must not pin the count of entries with pages or the count of fields of an entry. Compare with the data, or use temporary copies.
- A change to `site/app.js` or `site/style.css` needs the commit of `site/index.html` with its new `?v=` hashes (see `CLAUDE.md`).
- Every new `href` and `src` must resolve from `/date/<slug>/`. Check the relative paths and the `<base>`.

## 5. Work

1. Implement A, then B, then C. Add offline unit tests for each part, and run a mutation check on each new rule.
2. Extend the browser checks:
   - `check_data_finder.py`: every row of `/date/lista/` links to a page that exists. Each page has the families and the sources that its `inventar/<slug>.json` has. The page does not scroll sideways at 375 px.
   - `check_inventory_preview.py`: the link „Toate variabilele”, and the data set facts of a source that declares them.
3. Run all checks:
   - `validate.py --publication`, `inventory.py --check` and `inventory_report.py --check`;
   - the full unit suite (831 tests and 6 skipped before);
   - the three package checks;
   - a `--with-inventory` build into a separate `--site-dir`, with `check_preview.py`, `check_inventory_preview.py` and `check_data_finder.py`.
4. Take screenshots of two pages, one with many sources and one with a single source. Take them at the desktop width and at 375 px, and put them in a temporary folder for the review.
5. Add the activity entry. Flip the three backlog items to `[x]`, and add the backlog item for the form of part C.

## 6. Report

Give these items:

- The count of pages written, and the entries without a page with the reason.
- The data set facts shown, by kind (`seturi`, `seturi_ld`, `set_date`), and the count of sources with facts.
- The format of `campuri-editor.csv` and the checks on it.
- The change in the size of the `inventar/*.json` files and of the build.
- The paths of the screenshots.
- The test counts before and after, the commits, and what you measured and what you assumed.
