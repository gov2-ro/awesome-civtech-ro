---
description: Audit a site and add it to the v2 catalogue (intrari.csv, relatii.csv), then profile, search and inventory it
argument-hint: <url> [notes]
---

Add this URL to the CivTech România catalogue: $ARGUMENTS

The live data root is `data/taxonomy-v2/integrare/`. The v1 files `data/proiecte.csv` and `data/orgs.csv` are frozen: a row there never reaches the site. Do not write them.
Read these first: `data/taxonomy-v2/README.md` (facets, in Romanian), `docs/DATA-SCHEMA.md` (columns), and the code lists `data/taxonomy-v2/concepte.csv`, `valori.csv` and `arii.csv`.
The owner allows direct edits to `intrari.csv` and `relatii.csv`.

## 1. Check for a duplicate

- Compare the URL's domain with `url` and `linkuri` in `integrare/intrari.csv` (use `domain_of` in `scripts/common.py`).
- Also compare the site's name with `nume`.
- If the entry exists, stop. Report the row, and say what the new URL changes (moved site, extra link). Do not add a second row.

## 2. Audit the site

- First check the host with `forbidden(url)` in `scripts/common.py`. If the host is in `data/taxonomy-v2/colectare-interzisa.csv`, do not fetch or render it. Say so, and ask the owner for pages saved by hand.
- Fetch the homepage, and the about, methodology and contact pages if they exist. If the page needs JavaScript, render it with Playwright.
- Record what the site says. Do not guess. Leave a cell empty when the site does not say it.
- Decide `tip_entitate` (`proiect`, `organizatie`, `resursa`, `publicatie`, `set-date`, `campanie`) and the matching `sectiune_url` (`proiect`, `organizatie`, `resursa`).
- If the site is down, parked or redirects elsewhere, say so. Ask before you add it.

## 3. Write the rows

Write `integrare/intrari.csv`. Take the column order from its header.

- `slug`: lowercase, digits, hyphens; unique in `intrari.csv`.
- `nume`: the name the site uses.
- `descriere_scurta`: one line under 90 characters, in Romanian with diacritics, no slogans.
- `descriere`: two or three sentences: what it does, for whom, from which data.
- `url`: the canonical address. `linkuri`: the project's own repository, social profiles, donation and data/API pages. No share buttons, no agency or funder links, and no other project of the author.
- Facets: use codes from `concepte.csv`, `valori.csv` and `arii.csv` only.
  - `subiect_principal`, `subiecte`, `teme`: `subiecte` must hold the root group of every `teme` value and of `subiect_principal`. `validate.py` names the missing root.
  - `scopuri`, `functionalitati`, `formate`, `tehnologii`, `institutii_vizate`, `maturitate`, `nivel_acoperire`, `arii_acoperite`, `relatie_date`.
  - If no concept fits, do not invent one. Add a line to `propuneri-vocabular.csv` and say so in the report.
- `civictech_original`: `1` for civil society, volunteers, journalists, researchers; `0` for government portals and commercial products.
- `clasificare_stare`: `propus`. `incredere`: `mica`, `medie` or `mare` (required). Leave `stare` empty.
- `nota_clasificare`: the date, `/add-new-url`, and what the site does not say.
- Author: when the site names an author or operator, add a row to `integrare/relatii.csv` with the next `L` number, `predicat` `atribuit_in_sursa`, `stare` `rol_neconfirmat`, `camp_sursa` `autor`. Put the slug of an existing entry in `obiect`, or the name in `obiect_literal`. If the site names nobody, add no row.
- Write with Python's `csv` module (`lineterminator="\n"`) in append mode, so that other rows keep their bytes. Check with `git diff --stat` that only the new rows changed.

## 4. Profile, search, check

```sh
uv run scripts/profile.py --only <slug>       # observatii/profil.csv, og image or screenshot, icon
set -a; source .env; set +a
uv run scripts/search.py --only <slug>        # mentions: ~3 paid requests, under 1 US cent
python3 scripts/validate.py
```

If the search keys are missing, skip the search step and say so.
Read the stored rows in `observatii/mentiuni.csv`. A name that is also a common word gives many unrelated results. Report this. Do not prune the rows unless the owner asks.

## 5. Inventory (the data finder `/date/`)

A new entry needs a profile in the inventory. Without it, `test_inventory_report` fails with `KeyError: '<slug>'` in CI.

```sh
uv run scripts/collect_docs.py --only <slug>  # a few requests to the site; writes observatii/documentare/
python3 scripts/inventory.py --only <slug>    # 0 requests when no structured source exists
python3 scripts/inventory_report.py           # acoperire.csv and docs/reports/inventory-expansion.md
python3 -m unittest discover -s scripts -p "test_*.py"
```

Do not use `--add-source` or `--lot` here. A new data source for the entry is a separate task for the owner.

## 6. Check the build

- `python3 scripts/build.py --allow-draft --site-dir <scratchpad>/site` builds a preview with the draft entry.
- `python3 scripts/build.py` fails for a `propus` entry: the publication gate accepts only `acceptat` and `ascuns`. This is expected.

## 7. Report

- The new rows, cell by cell, with the source of each value (page text, link, your inference).
- The profiler result: status, image, first capture, last update.
- The number of search results kept, and how many look unrelated.
- The inventory result: pages found, requests made, tests run and failed.
- Anything you left empty and why.
- Do not commit. Do not set `acceptat`: the owner decides.

## When the owner asks to publish

1. Set `clasificare_stare` to `acceptat`. Say so in the reply.
2. Run `python3 scripts/validate.py --publication` and `python3 scripts/build.py`.
3. Commit `intrari.csv`, `relatii.csv`, `observatii/`, the new image in `site/img/`, `docs/reports/inventory-expansion.md`, and `site/data.json`, `site/feed.xml` and `site/llms.txt`. A rebuild that changes only a timestamp stays out of the commit.
4. Push, then check that the `validate` and `pages` runs pass (`gh run list`).
