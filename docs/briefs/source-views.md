# Brief — views of the projects by source data

Date: 2026-11-02. Baseline: commit `10c7da8`.
Status: open.

## 1. Start here

Read these files first:

- `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md` (the entries from 2026-10-26 to 2026-11-02).
- `scripts/inventory_site.py`: `publish_overview` (`/date/lista/`), `publish_variable_pages`, `left_out_section`, `scope_reason`, `FORMATS`, `SOURCE_LABELS`, `source_licence` and `dataset_summary`.
- `scripts/templates/inventory-list.html` and `scripts/templates/inventory-vars.html`.
- `scripts/common.py`: the relations loader (`data_sources`, predicate `date_din`), `inventory_exclusion` and `DATA_GROUPS`.
- `data/taxonomy-v2/integrare/relatii.csv` (rows with `predicat=date_din`) and `data/taxonomy-v2/observatii/inventare/campuri.csv` (column `format`) and `descoperiri.json` (column `url`).
- `scripts/check_data_finder.py` and `docs/briefs/variable-pages.md` (the format of this work).

Copy this prompt into the implementation session:

> Implement `docs/briefs/source-views.md`, parts A to F, in this order.
> Make no network request. Do not decide a review item for the owner.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 7.

## 2. Goal

The owner asked on 2026-11-02 for other views of the projects, by source data, similar to `/date/lista/`, "by everything possible".
`/date/lista/` groups the projects by the families of their variables. This brief adds four views that group the same projects by their sources:

| Page | Groups by | Data | Measured on 2026-11-02 |
|---|---|---|---|
| `/date/furnizori/` | the provider of the data | `relatii.csv`, `date_din`, `acceptat` | 118 relations, 44 entries, 58 provider names (all `obiect_literal`) |
| `/date/formate/` | how a source can be read | `campuri.csv`, `format` | 25 formats; json 32 entries, json-esantion 13, js-literale 10, csv 9, html-tabele 8, metadate-ins 7 |
| `/date/licente/` | the licence that a source declares | `source_licence`, the dataset facts | not measured; measure it (section 7) |
| `/date/gazde/` | the host of a source | the `url` of the structured sources | mariuscomper.uk 16, raw.githubusercontent.com 11, ins.gov2.ro 8; most others are one host for one entry |

## 3. Decisions

### Common to all views

1. `build.py --with-inventory` writes each page as static HTML, like `/date/lista/`. A visitor can read it without JavaScript. Use the same stylesheets and the `<base href="../../">`.
2. Use the scope rule of `/date/lista/` (`scope_reason`). Each page ends with `left_out_section`, as on `/date/lista/`.
3. Add a view switcher to all five pages (`/date/lista/` and the four new pages), below the header: „Pe familii de variabile · Pe furnizori · Pe formate · Pe licențe · Pe gazde”. Mark the current page with `aria-current="page"`. Put the switcher in one function, not five copies.
4. Link each entry name to its explorer entry (`/<kind>/<slug>/`). Link „Toate variabilele” to `/date/<slug>/` when that page exists (`has_page`).
5. Reserve the slugs `lista`, `furnizori`, `formate`, `licente` and `gazde` in one constant. `publish_variable_pages` skips a reserved slug (it skips `lista` today). `validate.py` reports an entry with a reserved slug as an error. No entry uses these slugs today (checked 2026-11-02).
6. Show only what the site shows today: names, formats, hosts, licences and counts. Show no value of a data body.
7. Design for the desktop first. At 375 px, the page must not scroll sideways. A wide table scrolls inside its own frame (`ov-scroll`).
8. Each page has a short note under the title (`ov-note`) that says what the grouping counts and what it does not prove. For example: „Același furnizor nu înseamnă același set de date.”

### A. The provider file (hand-edited)

The 58 provider names in `relatii.csv` are free text. Some name the same provider: „SEAP” and „SICAP / SEAP”; „Ministerul Finanțelor” and „Ministerul Finanțelor (situații financiare, prin data.gov.ro)”. Some are persons or organisations of the catalogue whose data is their own (for example „Marius Comper”, 19 rows; `funky-citizens`, `code4ro`).

1. Add `data/taxonomy-v2/furnizori.csv`. One row per name as it occurs in `relatii.csv`. Columns:
   - `nume_sursa`: the name exactly as in `obiect_literal` (or `obiect`).
   - `furnizor`: the id of the normalised provider (kebab-case).
   - `nume`: the display name of the normalised provider.
   - `eticheta`: a short label, optional. It replaces `SOURCE_LABELS` in `inventory_site.py`; move those labels into the file.
   - `tip`: `institutie-publica`, `ue-international`, `ong`, `companie`, `comunitate` (OpenStreetMap, geo-spatial.org) or `autor` (the author's own data or own collection).
   - `stare`: `propus` or `acceptat`.
   - `nota`: free text, optional.
2. Fill the file with a proposal for each of the 58 names. Every row is `propus`. Do not set `acceptat`: the owner decides (`CLAUDE.md`: never decide a review item for the owner).
3. The build applies a row only when it is `acceptat`. A name without an accepted row stays a provider of its own, with `tip` unknown. This keeps the page honest before the review.
4. `validate.py` checks the file: the columns, the code list of `tip` and `stare`, one row per `nume_sursa`, one `nume` and one `tip` per `furnizor`. A name in `relatii.csv` without a row is a warning, not an error. A row whose name is not in `relatii.csv` is a warning.
5. Document the file in `docs/DATA-SCHEMA.md` and in `data/taxonomy-v2/README.md` (Romanian). Add it to the Sheet only if the owner asks (backlog item).
6. Do not add a form to the review interface. Add a backlog item for the form. The owner can accept the rows in bulk, as for D189–D210.

### B. `/date/furnizori/`

1. Group the providers by `tip`, in the order of the list in A.1. Put the unknown `tip` last, as „Neclasificat”.
2. For each provider: its name, the count of entries, and the entries (links). Sort the providers by the count of entries, then by name.
3. Above the groups, add a matrix of the 12 providers with the most entries (columns) × the entries that use at least one of them (rows). A cell holds a mark (✓) only. If the matrix does not fit the frame at 1280 px, keep it scrolling in `ov-scroll`.
4. Add a line for the entries in scope that have no accepted `date_din` relation, with a count and the names. Note that a missing provider does not mean missing data.
5. Show the relation to data (`relatie_date`) of each entry as a small label, because `date-proprii` and `calcul` explain an `autor` provider.

### C. `/date/formate/`

1. Put the formats into five kinds. Put the map in `inventory_site.py`, next to `FORMATS`, and make a test fail when a format in `FORMATS` has no kind:
   - **API și JSON**: `openapi`, `json-schema`, `json`, `json-esantion`, `html-api-docs`, `llms-api`, `rsc-json`, `baza-datasette`, `json-comentat`.
   - **Fișiere și seturi descrise**: `csv`, `html-carduri-csv`, `html-lista-seturi`, `lista-ins`, `metadate-ins`, `markdown`.
   - **Tabele în pagină**: `html-tabele`, `html-tabele-eurostat`, `html-glosar`.
   - **Scriptul paginii**: `js-literale`, `js-pozitii`, `js-acces`.
   - **Cod sursă**: `php`, `sql`, `typescript`, `csharp`, `django-modele`.
2. Make a table like `/date/lista/`: one row per entry with fields, one column per kind. A cell lists the format labels (`FORMATS`) with the count of fields of each. The number under a column header counts the entries with at least one source of that kind.
3. Below the table, list each format with its label and its entries, so that a visitor can find all entries of one format.

### D. `/date/licente/`

1. Use `source_licence` and the declared dataset facts (`declared_facts`), as the variables pages do. Do not make a second rule.
2. Group the sources by licence name. Put „Licență nedeclarată” last. For each licence: the link of the licence if it is declared, then the entries and their sources.
3. Do not normalise licence names in this brief. If two names are clearly the same licence (for example „CC BY 4.0” and „CC-BY-4.0”), report them in section 7 and add a backlog item.
4. The note says that a declared licence is what the source says, not a legal opinion.

### E. `/date/gazde/`

1. Take the host of each structured source of an entry in scope. Strip `www.`.
2. Show the hosts that serve two or more entries, each with its entries. Sort by the count of entries.
3. Then add one line: the count of entries whose sources are all on hosts of one entry only („pe domeniul propriu”).
4. Group the hosts of one public portal under one name only if the host ends with the same registered domain (for example `executii-bugetare.g4d.ro` and `data.g4d.ro` under `g4d.ro`). Show the full hosts in the list of that group. Do not use a public-suffix library: the project has no dependencies. A short list of two-level suffixes (`gov.ro`, `com.ro`, `org.ro`, `github.io`, `co.uk`) is enough. Treat `github.io`, `vercel.app` and `githubusercontent.com` as platforms: group by the full host, not by the platform.

### F. Links

1. Add a link to the four pages from `/date/` (the finder header), next to „Listă pe proiecte”.
2. On `/date/<slug>/`, in the header, link each provider of the entry to its anchor on `/date/furnizori/`, and each format to its anchor on `/date/formate/`.
3. Add the pages to the sitemap or the index that `build.py` writes, if the other inventory pages are in it.

## 4. Views not done, with the reason

- **By discovery method** (`metoda` in `descoperiri.json`: `adaugat-explicit`, `link-in-documentatie`, `repo-la-revizie`): this is how the inventory found a source, not a property of the data. It stays internal.
- **Provider × variable family**: `date_din` belongs to an entry, not to a source or a field. A cross table would claim that a provider feeds a variable, and the data does not show it.
- **By period or geographic level of the data**: only the INS metadata sources (7 entries) declare these facts. The explorer already has `nivel_acoperire` and `arii_acoperite` for the entries. Add a backlog item to measure the declared facts again when more sources have them.

## 5. Limits

- Make no network request. Use the generated files and the cache only.
- Do not write into `data/taxonomy-v2/source/`, `reference/` or `runs/`. Do not set `acceptat` in `furnizori.csv`. Do not change `relatii.csv`.
- No test may pin data that the owner edits (counts of entries, providers or hosts). Compare with the data, or use temporary copies.
- Every new `href` must resolve from `/date/<page>/` with `<base href="../../">`.
- A change to `site/style.css` or `site/inventory.css` needs the new `?v=` hashes (see `CLAUDE.md`).

## 6. Work

1. Implement A to F in order. Add offline unit tests for each part, in `scripts/test_inventory_site.py`, and run a mutation check on each new rule (the kind map, the reserved slugs, the accepted-only provider rule, the host grouping).
2. Extend `check_data_finder.py`: each of the five pages has the switcher with the current page marked; every entry link resolves; no page scrolls sideways at 375 px; the anchors of part F exist.
3. Run all checks: `validate.py --publication`, `inventory.py --check`, the full unit suite, the package checks, and a `--with-inventory` build into a separate `--site-dir` with `check_preview.py`, `check_inventory_preview.py` and `check_data_finder.py`.
4. Take screenshots of the four new pages at the desktop width and at 375 px. Put them in a temporary folder for the review.
5. Add the activity entry. Flip the backlog item to `[x]`. Add the backlog items for the review of `furnizori.csv`, its form, its Sheet tab (if wanted) and the licence names.

## 7. Report

Give these items:

- For each page: the count of groups and of entries shown.
- `furnizori.csv`: the count of rows, of normalised providers, and of rows by proposed `tip`. List the proposed merges (more than one `nume_sursa` for one `furnizor`) for the owner's review.
- The licence names found, the count of sources with a declared licence, and the names that look like the same licence.
- The hosts grouped by registered domain.
- The test counts before and after, the commits, and what you measured and what you assumed.
