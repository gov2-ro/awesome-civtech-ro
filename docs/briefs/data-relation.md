# Brief — the relation to data (`relatie_date`) and the scope of `/date/`

Date: 2026-10-26. Baseline: commit `7bbfef2` (tag `v0.27.0`).
Status: ready for implementation. The decisions in section 3 are the owner's (2026-10-26).

## 1. Start here

Read `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md`.
Read the `intrari.csv`, `valori.csv` and inventory sections of `docs/DATA-SCHEMA.md`, and `docs/specs/taxonomy-v2.md`.
Read `scripts/taxonomy_v2.py` (the checks of `intrari.csv`), `scripts/common.py` (the v2 loader), `scripts/build.py` (`items_v2`, the vocabulary in `data.json`),
`scripts/inventory_site.py` (`publish_finder`, `publish_overview`, `publish_preview`), `scripts/inventory_report.py` and the facets in `site/app.js` (`FACETS`, `MORE`, the `ent` facet).

Copy this prompt into the implementation session:

> Implement `docs/briefs/data-relation.md` in the order of section 5.
> Stop after step B and give the proposal file to the owner. Continue with step C only after the owner's answer.
> Keep the public build unchanged until step C: an empty column changes nothing.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 7.

This brief changes `docs/DATA-SCHEMA.md`, `docs/specs/taxonomy-v2.md` and `data/taxonomy-v2/schema.json` for one new column. That change is authorised.
Any other change to a spec or to the package rules needs the owner.

## 2. Goal

Some catalogue entries have no data: guides, courses, campaigns, articles, lists of links.
Today the coverage report counts them as "not investigated" and says "Lipsa extragerii nu înseamnă lipsa datelor". For these entries that is wrong, and it hides the real inventory backlog.

After this work:

- Each project and resource can say how it relates to data.
- `/date/` lists only active entries that are not clearly without data.
- The explorer can filter by the relation to data and by status.

## 3. Decisions

**The column.** `intrari.csv` gets the column `relatie_date`, after `dovada_detaliere`. One code or empty. The code list `relatie_date` goes into `valori.csv`:

| Code | Label (RO) | Meaning | In `/date/` |
| --- | --- | --- | --- |
| `date-publice` | Date publice | The entry uses or republishes data from public-sector sources. | yes |
| `date-proprii` | Date proprii | The entry collects or curates its own data: reports from users, quiz positions, an editorial database. | yes |
| `calcul` | Calculator sau formular | The entry takes user inputs and applies rules or parameters, with no data set behind it. | yes |
| `fara-date` | Fără date | A guide, course, campaign, article or list of links. There is nothing to extract. | no |
| (empty) | Neevaluat | Not assessed yet. | no (owner, 2026-10-26) |

When two codes apply, use the first one in the table. Organisations may stay empty: the finder does not list them.
A single code was chosen over a list cell: the finder needs one answer, and the order above settles the mixed cases.
The format facet (`formate`) does not replace the column: a quiz (`testvot`) holds a data set, and a publication can be data journalism.

**The scope of the variable inventory.** An entry is in scope when all three are true:

1. `kind` is `proiect` or `resursa`.
2. Its built status is not in the group `inactiv` (`offline`, `arhivat`), the same rule as `isInactive` in `site/app.js`.
3. `relatie_date` is `date-publice`, `date-proprii` or `calcul`. An empty value and `fara-date` both leave the entry out (owner, 2026-10-26; the first version of this brief kept empty values in).

The same rule applies to `/date/`, `/date/lista/`, `inventar/<slug>.json`, the inventory markers in the explorer, and the default selection of `collect_docs.py` and `inventory.py`.
An explicit `--only` still runs on an out-of-scope entry (the owner may want an archived source), and the script prints that the entry is out of scope.
Retained evidence of an out-of-scope entry stays in `observatii/`; only the public output leaves it out. Measured on 2026-10-26: no inactive entry has extracted fields.

**The explorer.** Two facets under "Mai multe filtre", in the pattern of the `ent` facet:

- `dat` — "Date": the four codes plus `neevaluat`. Example: `?dat=fara-date` shows only entries without data.
- `st` — "Stare": the status groups `activ`, `inactiv`, `neconfirmat` (`STATUS` in `app.js`).
  Inactive entries stay hidden by default (`ina`). When `st` selects `inactiv`, the inactive entries show without `ina=1`.

`/date/` links to the explorer with the matching selection, so a visitor can see what the finder leaves out.

## 4. Measured starting point (2026-10-26)

- 128 projects and resources in `data.json`: 108 `activ`, 10 `arhivat`, 9 `offline`, 1 `necunoscut`.
- `acoperire.csv`: 100 `neinvestigat-in-lot`, 28 `cu-surse-structurate`, 13 `in-afara-ariei`, 1 `blocat`.
- A first guess from `formate` over the 100 uninvestigated entries: 49 have a data format, 22 have only formats without data, 21 have no format, 8 are publications. The guess is often wrong (see section 3).

Recompute these numbers before you start.

## 5. Work

### A. Data model (no values yet)

1. Add the code list to `valori.csv` and the column to `schema.json` (type `code`, list `relatie_date`, not required, public).
2. `taxonomy_v2.py`: the code must be in the list. `fara-date` together with `detaliere_date` is an error. `relatie_date` on an organisation is an error.
3. `validate.py`: a warning when an entry with `fara-date` has extracted fields in the inventory.
4. `common.py`: load the value as `data_relation`. `build.py`: write `dataRelation` on each item and `vocabulary.dataRelations` (the code list) in `data.json`.
5. `sheets.py`: the column round-trips, and its dropdown comes from the code list, like `clasificare_stare`. Not in the Form: the column is for editors.
6. Docs: `DATA-SCHEMA.md`, `specs/taxonomy-v2.md`, `data/taxonomy-v2/README.md` (one Romanian paragraph for editors).

### B. Proposals (no new requests) — then stop

Write `data/taxonomy-v2/observatii/inventare/relatie-date-propuneri.csv` with the columns `slug`, `propunere`, `baza`, `incredere` (`mare`, `medie`, `mica`), one row for each project and resource.
Use only what the repository already holds: `formate`, `functionalitati`, `tip_entitate`, `descriere`, the page text in `observatii/documentare/` and `profil.csv`, and the inventory.
An entry with `cu-surse-structurate` is never `fara-date`. Leave `propunere` empty when the evidence does not settle it.
`baza` names the evidence in one sentence. Then stop and give the file to the owner.

### C. Apply the owner's answer

Write the accepted values into `intrari.csv`. Run `validate.py --publication`. Push to the Sheet only through the normal workflow (a merge to `main`).

### D. Scope of the public inventory

1. `inventory_site.py`: apply the scope rule of section 3 in `publish_finder`, `publish_overview` and `publish_preview`, through one shared function.
2. `/date/lista/`: under the table, say how many entries the page leaves out (without data; inactive) and link to the explorer with `dat=fara-date` and with `st=inactiv`.
   Keep the note "Lipsa câmpurilor nu înseamnă lipsa datelor" only for the entries in scope without fields.
3. `inventory_report.py`: two new states for `stare_investigare`: `fara-date` and `inactiv`. Their `urmatorul_pas` is empty. Document them in `DATA-SCHEMA.md`.
4. `collect_docs.py` and `inventory.py`: the default selection skips out-of-scope entries; `--only` runs with a printed note.

### E. Explorer facets

Add `dat` and `st` to `site/app.js` (`DEFAULTS`, `FACETS`, `MORE`, labels, counts, pills, URL state), in the pattern of `ent`.
Old URLs keep their meaning. Commit `site/index.html` after the JS change (`build.py` rewrites the `?v=` hash).

## 6. Tests

- `test_taxonomy_v2.py`: an unknown code is refused; `fara-date` with `detaliere_date` is refused; the code on an organisation is refused; an empty value passes the publication gate.
- `test_inventory_site.py`: a `fara-date` entry and an inactive entry are absent from `inventar/index.json`, `/date/lista/` and `inventar/`; an empty value is present; the counts in the note are right.
- `test_inventory_report.py`: the two new states.
- `test_sheets_form.py`: the column round-trips.
- Browser: extend `check_preview.py` (`dat=fara-date`, `st=inactiv` without `ina`) and `check_data_finder.py` (the out-of-scope entries are absent; the explorer links work).
- Each new test must fail without the code change. Say which ones you checked that way.

## 7. Report

Numbers before and after: entries in `/date/`, entries in `/date/lista/` with and without fields, states in `acoperire.csv`, test counts.
The proposal counts by code and by `incredere`, and the entries left empty. What was measured and what was assumed.

## 8. Status on 2026-10-26 (after the owner's review)

- Steps A and B are done (v0.29.0). Step C is done: the owner edited the proposals; 106 values are in `integrare/intrari.csv` (`testvot` became `calcul`).
- The owner hid `didi365` (not specific to Romania) and `harta-tv-locale` (`clasificare_stare` `ascuns`).
- Changed decision: an empty value leaves the entry out of `/date/`, like `fara-date`. Section 3 says so now. In `/date/lista/`, the note counts the entries left out by reason: without data, not assessed, inactive.
  The explorer link for „not assessed” uses `dat=neevaluat`.
- Steps D and E are done on the branch `data-relation-de` (2026-10-26); the numbers and decisions are in `docs/ACTIVITY.md`. The Opus session merges the branch and tags it.
