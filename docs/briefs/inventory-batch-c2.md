# Brief — variable inventory, batch C2

Date: 2026-10-26. Baseline: commit `7bbfef2` (tag `v0.27.0`).
Status: ready for implementation.

## 1. Start here

Read `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md`.
Read `docs/briefs/inventory-expansion.md`, sections 5 (evidence contract) and 6.C (batch method). This brief reuses both.
Read the inventory sections of `docs/DATA-SCHEMA.md` and the list of forbidden hosts (`data/taxonomy-v2/colectare-interzisa.csv`).

Copy this prompt into the implementation session:

> Implement `docs/briefs/inventory-batch-c2.md`.
> Investigate the three entries with the method of `inventory-expansion.md` section 6.C, inside the limits of section 4 of this brief.
> Keep the evidence contract of `inventory-expansion.md` section 5.
> Propose variable groups and providers for the owner; do not decide them.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 6.

## 2. Goal

Three active projects that publish public-sector data get a field inventory.
Each inventory says which datasets the project uses or exposes, which fields they have, and where the evidence comes from.

## 3. The batch

The owner named six entries. Three are inactive in the public build (`status` `offline` or `arhivat`), and the owner removed every inactive entry from the variable inventory. They are not in this batch.

| Slug | URL | Starting question |
| --- | --- | --- |
| `data-expertforum` | https://data.expertforum.ro/ | Which data sets does the portal publish (format, period, geographic level), and which fields do they have? |
| `bani-partide` | https://banipartide.ro/ | Which records of party finance (donations, expenses, subsidies, loans) does the site show, and which provider supplies each one (AEP, the parties' reports in Monitorul Oficial)? |
| `romania-interactiva` | https://romaniainteractiva.ro/ | Which indicators do the charts show, with which unit, period and geographic level, and which provider is named for each one? |

Removed from the batch: `harta-banilor-publici`, `parlament-transparent`, `bani-pierduti`. Do not request their hosts.
`data-expertforum` and `bani-partide` belong to Expert Forum (`efor`). A data set that both use is one source with two project uses; do not count it twice.

Lot code: `C2` (column `investigat_in_lot` of `acoperire.csv`).

## 4. Limits

- At most 60 direct HTTP fetches in all, retries included. Report browser navigations separately: at most two pages for each entry.
- At most ten new structured sources for each entry. Read bounded samples; do not download a full archive.
- Check `common.forbidden(url)` before each request. The scripts already do this; a new request path must do it too.
- No paid search, no `review.py`, no message to the project owners.
- Party-finance records name private donors. Record the schema and the aggregates; do not copy individual donor records into the repository.
- If a source answers 401, 403 or 429, or its terms forbid automated access: stop on that host and record it. Propose a row for `colectare-interzisa.csv` in the report; do not add it yourself.

## 5. Work

1. Run `collect_docs.py --only data-expertforum,bani-partide,romania-interactiva` to find documentation, methodology and data pages.
2. Add the sources that you find with `inventory.py --only …`. Use the existing readers. Write a new reader only if a source needs one, and test it offline with a fixture.
3. Map the fields to the existing groups in `data/taxonomy-v2/inventar-concepte.json` (families: identifiers, geography, time, subject areas).
   Add a selector to an existing group only when the evidence supports the same meaning. A new group is a proposal with the state `propus`.
4. Put each new provider as a review item in `integrare/revizuire.csv` (`camp=surse_date`, the next free D number). Do not accept it.
5. Run `inventory_report.py`, `inventory.py --check`, `validate.py --publication`, the unit tests and a build with `--with-inventory` into a separate `--site-dir`.
6. Add the activity entry and flip the backlog items.

## 6. Report

For each entry: sources found, sources parsed, field records, fields in existing groups, proposed groups, proposed providers, blockers.
Also: requests made (from `jurnal-cereri.csv`), browser navigations, test counts before and after, and what was assumed and not measured.

## 7. Part 2 — `data-expertforum` from the owner's copy and the Google Sheets (added 2026-10-26)

Status: ready. `bani-partide` waits for the owner (section 8).

`expertforum.ro` is in `colectare-interzisa.csv` (the row covers `data.expertforum.ro`). Do not request these hosts.
The owner saved the page `https://data.expertforum.ro/` from a browser: `tmp/data.expertforum.ro.html` (saved 2026-10-26T20:23:00+02:00).

Measured by the Opus session on 2026-10-26:
- The page is a table of data sets (category, name, description, related EFOR reports, link). The links go to about 16 Google Sheets and Drive files, some through `https://www.google.com/url?q=…` wrappers, and one Drive folder.
- Two requests to `https://docs.google.com/spreadsheets/d/<id>/export?format=csv` (one native Sheet, one Office file opened in Sheets) answered HTTP 200 with `text/csv`, after a redirect to `doc-…-sheets.googleusercontent.com`. The endpoint ignores a byte range: each response was the whole tab (188,840 and 246,624 bytes).
  The headers include `SIRUTA`, `CIF`, `UAT`, `judet` and `partid`. These are candidates for the groups `siruta`, `cui`, `localitate` and `judet`.

Work:
1. Import the owner's copy: `collect_docs.py --import-saved` and `inventory.py --import-saved data-expertforum https://data.expertforum.ro/ tmp/data.expertforum.ro.html --saved-at 2026-10-26T20:23:00+02:00`. The copy is the discovery locator of every sheet.
2. Unwrap the `google.com/url?q=` links offline (read the `q` parameter). Make no request to `www.google.com`.
3. For each sheet, request the CSV export of the tab that the link names (`gid`), once. Add the sources with `inventory.py --add-source` and the existing CSV reader.
   A Drive folder cannot be listed without the API: record it and do not request it. A Drive file that is not a spreadsheet: record it and do not request it.
4. Each data set gets the facts that the page declares: category, name, description, the related report. The page says „Datele sunt prelucrate de EFOR, pornind de la informații existente în spațiul public sau obținute pe baza legii accesului la informații de interes public”.
   A provider item needs a named provider in the page or in the sheet (for example, a column `sursa` with „HG 1088/2021”). Do not infer a provider from the topic.
5. Map the columns to the existing groups only where the meaning is clear. A reviewed group needs the owner's confirmation for a new member: list the candidates, as in Part 1.
6. The finance data set on this page links to `https://www.banipartide.ro/`. Record that as a relation between the two entries in the notes; it is not a source.

Limits: at most 30 requests, all to `docs.google.com` and the redirect host. One request for each sheet tab; no retry on 4xx. A response over 2,000,000 bytes is not parsed; record it.
The sheets hold aggregate data about public bodies. If a sheet holds data about private persons, keep the header only.

Lot code: `C2` (the same lot). Report as in section 6, for this entry only.

## 8. `bani-partide` — waiting for the owner

The owner develops `banipartide.ro` (local checkout `/opt/homebrew/var/www/banipartide`, outside this repository). Its data is a SQLite database with 21 tables and views, published with Datasette at `https://db.banipartide.ro/` (DNS: Google front-end addresses, not the host that answers 403).
The row `banipartide.ro` in `colectare-interzisa.csv` covers `db.banipartide.ro` too. Two options, for the owner:
- The owner saves `https://db.banipartide.ro/banipartide.json` (tables, columns and row counts) from a browser, and the session imports it with `--import-saved`. No change to the list.
- The owner allows `db.banipartide.ro`. The list has no exception for a subdomain today, so this needs a small change to `common.forbidden()`, `validate.py`, the docs and the tests.
The local checkout is not public evidence. Use it only to check a reading, and copy no rows: the donor tables name private persons.

### 8.1 Decision (2026-10-26): the owner's saved copy

The owner chose option 1 and saved `https://db.banipartide.ro/banipartide.json` at 2026-10-26T20:30:00+02:00 (`tmp/banipartide.json`, 11,493 bytes). The list does not change.
Measured: Datasette database `banipartide`, 18 visible tables with their columns and row counts, 20 hidden full-text tables (`*_fts*`), 4 views (names only, no columns).
The page declares `source` „Expert Forum”, `source_url` `https://expertforum.ro/tag/finantare-politica/` and the licence CC BY 4.0.

Work:
1. Import the copy with `inventory.py --import-saved bani-partide https://db.banipartide.ro/banipartide.json FILE --saved-at 2026-10-26T20:30:00+02:00`. Make no request.
2. Read it with a reader for a Datasette database listing: one field for each column of a visible table (path `<table>.<column>`), the table's row count as a fact, the views by name only. Leave out the hidden tables. If no existing reader fits, write one and test it offline with a fixture.
3. Record the declared licence and source, as for Harta Firmelor (`licence` in the field browser).
4. Map the columns to groups as in Part 1 and Part 2: candidate members for reviewed groups are listed, not added; a new group is `propus`.
   A provider needs a name in the copy. The table titles do not name one; the project's own notes name Monitorul Oficial, and a table title names the Ministry of Finance (`Venituri anuale partide de la MF`), but the copy names no provider. Propose a provider only from text in the copy.
5. The donor tables name private persons. The copy holds only column names, so nothing more is needed; do not request rows.
