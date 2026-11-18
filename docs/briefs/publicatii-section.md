# Brief — a fourth section for publications

Date: 2026-11-18. Author: coordinator (Opus). Executor: Sonnet. Status: ready.

## Goal

The tab "Resurse & liste" mixes two kinds of entry:

- lists and collections that point to other things (9 entries, for example `site-uri-utile-funky`, `ghiduri-efor`, `hack-for-facts`);
- publications with their own content: investigations, reports, data stories (14 entries with `tip_entitate=publicatie`; 12 of them are by Marius Comper).

The publications bury the lists. Give the publications their own section, `sectiune_url=publicatie`, with its own tab and the address `/publicatie/<slug>/`.

## Decisions (do not reopen)

1. **No new entity type.** `tip_entitate=publicatie` exists. Exposés, reports, guides and data stories stay `formate` values (`format:raport`, `format:ghid`, `format:articol`, `format:vizualizare`).
2. **A new `sectiune_url` code `publicatie`.** Add it to `valori.csv` with `ordine` 3. Tab label: "Analize & investigații" (English: "Analyses & investigations"). The owner may rename the label later; the code stays.
3. **The section follows the column `sectiune_url`, row by row.** Do not derive it from `tip_entitate`, and do not add a validation rule that ties the two.
4. **Entries that move** (set `sectiune_url=publicatie`): the 12 Comper publications (`statul-digital`, `complet-online`, `prima-cifra`, `pe-datorie`, `ultima-noapte-pib`, `constru-pentru-cine`, `orasul-care-se-intinde`, `trei-din-patru`, `unde-se-termina-asfaltul`, `de-unde-vine-apa`, `recontorizarea`, `pensie-din-bursa`) and `piratii-digitali-ai-kremlinului` (Snoop investigation).
   `apti-unelte-democratie` stays in `resursa`: it is a list article (`format:colectie`).
5. **Marius Comper is one collection entry**, `marius-comper` (`resursa`, URL `https://mariuscomper.uk/viata-publica/`). His 19 entries have `parte_din` → `marius-comper` (L410–L428, `stare=propus`). The owner chose this on 2026-11-18. The children stay separate in the lists: no folding in the list view. The parent page lists them (the `parte_din` code in `site/app.js` exists).
6. **Old addresses keep working.** GitHub Pages has no server redirects. For each moved entry, `build.py` writes `site/resursa/<slug>/index.html` as a stub page: `<link rel="canonical">` to the new address, `<meta http-equiv="refresh" content="0; url=...">` and one visible link. Do not write a stub for an entry that never was in `resursa`.
7. **Feed identity stays stable.** The `<guid>` of a moved entry in `site/feed.xml` must not change, so that feed readers do not show the item again. The `<link>` takes the new address.

## Scope

Change these places. Find others with `grep -rn "resursa" scripts site`; report each one you change.

- `data/taxonomy-v2/valori.csv`: the new code (decision 2).
- `data/taxonomy-v2/integrare/intrari.csv`: `sectiune_url` of the 13 entries in decision 4. Change only that cell; check with `git diff --word-diff`.
- `scripts/build.py`: `PAGE_KINDS`, the archive page and its lead text (line ~356), the stub pages (decision 6), the feed (decision 7), `llms.txt`.
- `scripts/common.py` (line ~398 checks `kind`), `scripts/taxonomy_v2.py` if it lists the sections.
- `site/app.js`: `KINDS` (line ~141), the tabs, the counts, the URL state (`/publicatie/<slug>/` and the old `?p=<slug>`).
- `scripts/inventory_views.py` and the `/date/` pages, if they link entries by kind.
- Tests: `scripts/test_taxonomy_v2.py` and the build tests; `scripts/check_preview.py` (one browser check: the new tab, an entry page under `/publicatie/`, and an old `/resursa/<slug>/` stub that reaches the new page).
- Docs: `docs/DATA-SCHEMA.md`, `data/taxonomy-v2/README.md` (Romanian), CONTRIBUTING.md, and the `sectiune_url` line in `CLAUDE.md`.

## Out of scope

- A new `format:investigatie`. If you think the formats are not enough, add a line to `propuneri-vocabular.csv` and say so; do not add the concept.
- Folding children under a parent in the list view.
- The v1 root (`--data-dir data`). It is frozen; it keeps three sections. If a shared code path breaks the v1 build, stop and report.
- `clasificare_stare`. `hack-for-facts` and `marius-comper` are `propus`; the owner accepts them. Until then, the full unit suite has about 20 failures with the message `classification state 'propus'`. These are expected; report any other failure.

## Stop and ask

- If a step changes a spec in `docs/specs/` or an ADR.
- If the feed or the stub pages need a different approach than decisions 6 and 7.
- If an entry in decision 4 does not fit the new tab when you read it.

## Checks

`validate.py`, `build.py --allow-draft --site-dir <scratch>`, the full unit suite, `actionlint`, and `uv run scripts/check_preview.py` on a served preview.
Confirm by hand: the tab "Resurse & liste" shows 10 entries (9 lists + `marius-comper`, plus `hack-for-facts` when accepted); the new tab shows 13; `/resursa/pe-datorie/` reaches `/publicatie/pe-datorie/`; the page of `marius-comper` lists 19 children.

## Report

Files changed and why; counts per tab before and after; feed GUIDs before and after for two moved entries; test counts; what you measured and what you assumed. Add the ACTIVITY and BACKLOG entries. Do not commit until the owner reviews.
