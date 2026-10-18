---
description: Audit a site and add it to proiecte.csv or orgs.csv, then profile it
argument-hint: <url> [notes]
---

Add this URL to the CivTech România catalogue: $ARGUMENTS

Columns and allowed values are in `CONTRIBUTING.md` and `data/taxonomy.json`. Read both first.
The owner allows direct edits to `data/proiecte.csv` and `data/orgs.csv`.

## 1. Check for a duplicate

- Compare the URL's domain with `url` and `linkuri` in `data/proiecte.csv` and `data/orgs.csv`
  (use `domain_of` in `scripts/common.py`).
- Also compare the site's name with `nume`.
- If the entry exists, stop. Report the row, and say what the new URL changes (moved site, extra
  link). Do not add a second row.

## 2. Audit the site

- Fetch the homepage, and the about/contact pages if they exist. If the page needs JavaScript,
  render it with Playwright.
- Record what the site says. Do not guess. Leave a cell empty when the site does not say it.
- Decide the table:
  - `orgs.csv` for an organisation (NGO, collective, newsroom).
  - `proiecte.csv` with `fel=proiect` for a tool, map, database or campaign site.
  - `proiecte.csv` with `fel=resursa` for a list, guide or collection.
- If the site is down, parked or redirects elsewhere, say so. Ask before you add it.

## 3. Write the row

- `slug`: lowercase, digits, hyphens; unique in both files.
- `nume`: the name the site uses.
- `descriere_scurta`: one line under 90 characters, in Romanian with diacritics, no slogans.
- `descriere`: two or three sentences: what it does, for whom, from which data.
- `domeniu`, `tip` (main type first), `acoperire`, `oras`: taxonomy keys only.
- `cuvinte`: 2–6 keywords. Use the existing vocabulary in `proiecte.csv` when a word fits.
- `autor`: match the `nume` of an `orgs.csv` row when the author is there. If the author is a
  real organisation that is missing, propose an `orgs.csv` row too.
- `linkuri`: the project's own social profiles, repository, donation and data/API pages from the
  page's links. No share buttons, no agency or funder links.
- `civictech`: `1` for civil society, volunteers, journalists, researchers; `0` for government
  portals and commercial products.
- Leave `stare` empty.
- Write with Python's `csv` module (`lineterminator="\n"`), so that other rows keep their bytes.
  Check with `git diff --stat` that only the new row changed.

## 4. Profile and check

```sh
uv run scripts/profile.py --only <slug>       # profil.csv, og image, icon, screenshot
set -a; source ~/devbox/ePtm/puzzes/.env; set +a
uv run scripts/search.py --only <slug>        # mentions: ~3 paid requests, under 1 US cent
python3 scripts/validate.py
python3 scripts/build.py
```

If the search keys are missing, skip the search step and say so.

## 5. Report

- The new row, cell by cell, with the source of each value (page text, link, your inference).
- The profiler result: status, image, first capture, last update.
- The number of search results kept.
- Anything you left empty and why.
- Do not commit.
