# Brief — the data-set card: file, checks and pages

Date: 2026-11-23. Baseline: commit `v0.84.0` plus the spec update of the same day.
Status: ready.
Spec: [`docs/specs/data-set-card.md`](../specs/data-set-card.md) (accepted 2026-11-23). The spec wins over this brief; report any conflict.

## 1. Start here

Read these files first:

- `CLAUDE.md`, `docs/BACKLOG.md` (section "External review of `/date/` and the taxonomy — 2026-11-23") and the top entry of `docs/ACTIVITY.md`.
- The spec, all of it. Sections 4.1 (the columns), 5 (the pages), 6 (the docs) and 8 (the checks) are the contract.
- `scripts/common.py`: the `furnizori.csv` constants and checks (`PROVIDER_COLS`, `provider_problems`, `provider_table`), the `date_din` loader, `inventory_exclusion`, `RESERVED_DATA_SLUGS`.
- `scripts/validate.py`: the provider check (around line 257); copy its shape.
- `scripts/taxonomy_v2.py` and `data/taxonomy-v2/integrare/pachet.json` (`local_files`): how a file of `integrare/` is loaded.
- `data/taxonomy-v2/valori.csv`: the shape of a value list.
- `scripts/build.py` (the item dict near `dataSources`, around line 700), `scripts/entry_page.py` (`data_summary`), `site/app.js` (`inventoryHTML`, `inventoryFacts`).
- `scripts/inventory_site.py` (`publish_variable_pages`, the finder index) and the templates in `scripts/templates/`.
- Tests: `scripts/test_entry_page.py`, `test_inventory_pages.py`, `test_inventory_site.py`, `test_taxonomy_v2.py`; browser checks `check_preview.py`, `check_data_finder.py`, `check_inventory_preview.py`.

Copy this prompt into the implementation session:

> Implement `docs/briefs/data-set-card-build.md`, parts A to F, in this order, on a branch `data-set-card`.
> Make no network request. Write no card row into the real `integrare/fise-date.csv`: it stays a header only.
> Stop and report if a step needs a decision that the brief or the spec does not make. Finish with the report in section 4.

## 2. Goal

Build the data-set card of the spec with no data: the file, its value lists, its checks, the build output and the three page changes. The pilot cards come later, in [`data-set-card-pilot.md`](data-set-card-pilot.md).
An entry without an accepted card must look exactly as it does today. The public site therefore does not change with this brief.

## 3. Parts

### A. The file and the value lists

1. Add `data/taxonomy-v2/integrare/fise-date.csv` with the header of spec 4.1, in that order, and no row.
2. Register it where the package loader needs it (probably `pachet.json` `local_files`, and `integrare.py` headers if `--check` reads them). Report what you changed. If the loader refuses an extra file in a way that needs a change of an invariant, stop and ask.
3. Add three lists to `valori.csv`, `statut` `propus`:
   - `acces_set`: `web`, `fisier`, `api`, `api-cheie`, `la-cerere`.
   - `rol_identificator`: `autoritate-contractanta`, `furnizor`, `firma`, `institutie`, `uat`, `obiect`, `contribuabil`, `creditor`.
   - `granularitate_set`: one Romanian code for each `record_grain` value of `data/taxonomy-v2/structura/recipes/*.json` except `unknown` (22 values on 2026-11-23). Give each an `eticheta_ro` and a `definitie_ro`. Report the mapping table.
4. Constants in `common.py`: the column list, the identifier codes (`cui`, `siruta`, `euid`, `cpv`, `caen`, `local`), `baza` (`declarat`, `observat`, `editorial`) and `stare` (`propus`, `acceptat`). One loader that returns the rows of one entry.

### B. The checks

Add the errors and warnings of spec section 8 to `validate.py`, in the shape of the provider check (Romanian messages, GitHub annotations under `GITHUB_ACTIONS=true`).
Notes:
- `local:<namespace>`: the namespace must be a namespace id of the entry's structure recipe. No recipe means an error.
- `variabile_cheie`: a group id must exist in `inventar-concepte.json` and match a field of the entry (`inventory_site.group_hits` or the finder's rule); `<sursa_id>#<path>` must be a row of `campuri.csv` for the entry.
- An error makes `validate.py --publication` fail, as the other checks do.
One unit test for each error and each warning, on a temporary copy of the data root (the pattern of `test_review_ui.py`).

### C. The build output

1. `data.json`: key `datasets` on each item, a list of the accepted cards of the entry, in `id` order: `id`, `set`, `provider` (`furnizor`, display `nume` from `furnizori.csv`, the anchor `f-<furnizor>`), `record`, `grain` (code and label), `period`, `access` (`[{code, label, url}]`), `identifiers` (`[{code, role, roleLabel}]`), `keyVariables` (`[{id or source+path, label}]`), `methodNote`, `evidence`, `basis`, `checked`. No `nota`, no `propus` row. An entry without cards has `[]`.
2. `inventar/index.json`: the same summary on the entry (set, provider, access codes, identifiers) for the finder.

### D. The entry page ("Date & metodă")

1. One function in `entry_page.py` and one in `app.js` that write the same HTML for one card (the fields of spec 4.1 as in the spec's example in section 1). Empty `period`: „perioada: nedeclarată”. The provider links to `date/furnizori/#f-<furnizor>` (relative to the `<base>`).
2. With at least one card: the cards first, then „Vedere tehnică: N câmpuri din M documente →” to `/date/<slug>/` when the page exists. The field count and examples stay, under that link.
3. Without a card: the panel is byte-identical to today. Add a test that proves it on the current data (all entries).
4. The facts box „Surse de date” does not change.

### E. The data pages

1. `/date/<slug>/`: a part „Seturi de date” before „Pe familii”, with the same card HTML. When the entry has a card, put „Pe familii” and „Pe surse” under one heading „Vedere tehnică” with the sentence of spec section 5. Without a card, the page is unchanged.
2. `/date/` finder: a result whose entry has a card shows one line for each card (set · provider · access · identifiers), above the field examples. No new facet (review item 2).
3. Which entries get a page does not change.

### F. Documentation

`DATA-SCHEMA.md` as in spec section 6; one paragraph in `METODOLOGIE.md`; the `CLAUDE.md` list of hand-edited files if it names the files of `integrare/`; a `docs/ACTIVITY.md` entry; in `docs/BACKLOG.md`, a line under item 1 for this brief. Do not flip item 1 to `[x]`: the pilot is still open. Add the optional schema.org `Dataset` JSON-LD (spec section 5) as an open backlog item; do not build it.

### Tests and browser checks

- The real file has no row, so the browser checks need fixture cards. Build an isolated preview (`--site-dir`) from a temporary copy of the data root with two fixture cards: one on `sicap-ai` (two access codes, three identifiers, one key variable) and one on an entry with no inventory fields. Do not commit the fixture rows into the real file; a fixture file under the tests is fine.
- Check: the card on the entry page with and without JavaScript; the „Vedere tehnică” link; `/date/<slug>/` order of parts; the finder line; no sideways scroll at 375 px; an entry without a card unchanged.
- Run everything that CI runs (`CLAUDE.md`, „Commands”), including `validate.py --publication` and the full unit test suite.

## 4. Report

- The files changed, and what you changed in the loader or `pachet.json` (part A.2).
- The `granularitate_set` mapping table.
- Test counts (unit: run, skipped; each browser check file: passed/total) and `validate.py --publication` errors and warnings.
- Byte comparison: the public build (`site/`) before and after, for all entry pages and `/date/` pages. Expected: no difference except the `?v=` hash and the new `datasets: []` key. List any other difference.
- What you assumed and what you measured.
