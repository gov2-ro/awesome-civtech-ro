# Backlog

Statuses: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` dropped.

## Search → relevance (spec: `docs/specs/search-relevance.md`)

- [x] `scripts/search.py`: Serper + Brave, full results in `data/mentiuni.csv` (D1, D3, D4).
      First full run 2026-10-18: 3386 rows, ≈ $0.81.
- [x] Rule-based pruning with an `editor` override column (D5)
- [x] Remove `--search` / `--gdelt` from `profile.py`; drop the `gdelt` column (D1, D2)
- [~] `review.py`: label kept results; write `data/mentiuni_etichete.csv` (D6). Code and dry run
      done; not run against the API yet (next item)
- [x] `build.py`: reach features and new `reach` weights (D7)
- [~] Editor: prune `data/mentiuni.csv` (first pass 2026-10-18: Haiku + Opus set 2,194 cells; 1,149 rows still empty for the editor) before the first labelled review run (column `editor`;
      extend the rules in `search.py` from the top hosts, then `search.py --prune-only`)
- [ ] Run `review.py` against the API (needs `ANTHROPIC_API_KEY`; the key in
      `~/devbox/ePtm/puzzes/.env` is empty). Then check `build.py` output: until labels exist,
      `reach.indep` is the kept-host count and the score is provisional
- [ ] `README.md` line 54 still lists `profile.py --search --gdelt --opr` (flags removed)
- [ ] `declic`: `url` de-clic.ro is offline; the search finds the live site at declic.ro. Editor
      decides whether to change the url
- [ ] `profile.py --force` replaces the whole profile row and drops `mentions`, `search_social`
      and `opr`. Run `search.py --prune-only` after it, or make `profile.py` keep these columns
- [ ] Name-collision noise (`465`, `the-sponge`, `declic`, author names such as "Gabriel Popa"):
      check what the labels fix; if too much remains, add per-entry `search_exclude` terms
- [ ] UI: show the reach features (independent mentions, news, latest mention) on the entry card
- [ ] Run Open PageRank (`--opr`, needs `OPR_API_KEY`, free signup)

## Google Sheets sync (brief: `docs/briefs/sheets-sync.md`)

- [x] `scripts/sheets.py`: `diff`, `pull`, `push [--since REF] [--force]` (D1–D4). Tested on two
      temporary tabs of the real spreadsheet; see `docs/ACTIVITY.md`.
- [x] Workflows `sheets-pull.yml` and `sheets-push.yml`, shared `concurrency` group (D5–D7).
      Not run on GitHub yet: the brief forbids triggering workflows.
- [x] README: section "Editing in Google Sheets" describes how it works now.
- [ ] Owner: turn on Settings → Actions → General → "Allow GitHub Actions to create and approve
      pull requests"; check the secret `GOOGLE_SA_KEY` and the variable `SHEET_ID`; then run
      `sheets-pull` by hand once.
- [ ] Owner decides on the real tab `proiecte`: it differs from the CSV in one cell
      (`demoanaf` / `descriere`: the Sheet lacks "Proiect independent." and the line breaks; checked
      2026-10-18). Keep it: `sheets.py pull`, review, commit. Drop it: `sheets.py push --force`.
      The first `push` to the real tabs is not done yet.
- [ ] Trim the trailing space in `orgs.csv`, `descriere_scurta` of `code4ro` and `techsoup`. `pull`
      strips it (D2), so the next pull otherwise rewrites the file.
- [ ] `pull` copies the Sheet over the CSVs with no base. A CSV edit on `main` that `sheets-push` has
      not written yet shows as a revert in the next pull request. Option: a 3-way merge with the last
      synced commit (needs a marker: a git tag or a cell in the Sheet).
- [ ] `push --since REF` stops with "row 1 differs" when the columns changed between REF and now.
      Run `push --force` once after a column change (README says so). Option: detect this case.
- [ ] GitHub keeps one pending run per concurrency group. If `sheets-push` runs are superseded, the
      next run's `before` is not the state the Sheet was synced from, and the check can give a false
      exit 3. Recovery: run `sheets-push` by hand with `since` or `force`.
- [ ] The Sheet has a third tab, `propuneri` (Form responses). `sheets.py` ignores it. The
      "Propune un proiect" form is not wired to the pipeline.
- [ ] `CLAUDE.md`: add `sheets.py` to *Commands*, the pipeline sketch and the *Deployment* section.

## Proposal Form (brief: `docs/briefs/form-generator.md`)

- [x] `scripts/form.py`: plans the 13 questions from `data/taxonomy.json`; default mode prints them and
      reads the Form; `--apply` replaces all items in one `forms.batchUpdate` (D1–D3). Tested read only
      on 2026-10-18; **`--apply` is not run yet**.
- [ ] Owner: read the dry run (`uv run scripts/form.py`), then run `--apply` once.
- [ ] After `--apply`: check row 1 of the tab `propuneri`. Before it, it holds `Timestamp` and
      `Untitled Question` (the Form's one default question). The deleted question may leave its column;
      delete that column by hand (0 responses).
- [ ] Importer for `propuneri`: map the answers to a `proiecte.csv` / `orgs.csv` row with `ANSWER_KEYS`
      in `form.py` (needs a `slug`; the editor accepts each row by hand, as for `review.py`).
- [ ] The longest help text (Domeniu, 11 hints) has 772 characters. If the Forms API or the layout
      rejects it, set `HINT_MAX` in `form.py` to 0 to drop the hints from the help text.

## Link icons and GitHub stats (brief: `docs/briefs/link-icons-github-stats.md`)

- [x] Drawer: a link to a network shows its logo (inline SVG, Simple Icons, `currentColor`) with
      `aria-label` and `title` (D1, D2)
- [x] `profile.py` stores the favicon of each non-network link host in `site/img/linkicon/`; `build.py`
      adds `icon` to the link (D3). 12 hosts, 0 failed.
- [x] `profile.py`: the entry icon prefers a candidate of 64 px or more; header logo images are
      candidates (D4)
- [x] GitHub stats in `profile.py --extra` (6 new `profil.csv` columns) and the "Cod" row in the
      drawer (D5, D6). 19 repos.
- [ ] A logo that is an SVG is skipped: Pillow cannot decode it (factual.ro has an SVG logo and a
      32 px favicon). Option: rasterise it with Playwright in the browser pass.
- [ ] `profile.py --only` / `--force` drops `cert_first` while crt.sh answers 502 (2026-10-18:
      factual, code4ro; restored later with `--extra --only`). `extras_one` keeps an old value only
      when the profile row survives.
- [ ] `profile.py --extra` runs a GitHub search for every live entry without a repo, on every run
      (about 75 requests, about 3 minutes at the 30 per minute limit). Store the miss to skip it.
- [ ] A link host whose favicon fails is fetched again on every run (no stored miss). Today: 0 failures.
- [ ] Orphans: 22 files in `site/img/icon/` and 10 rows in `profil.csv` have no entry in the CSVs
      (deleted entries, e.g. `rescue-4x4`). Nothing shows them.
- [ ] `CLAUDE.md` pipeline sketch names `site/img/{og,icon}/`; add `linkicon`.

## Site (from README *Backlog*)

- [ ] "Vezi și proiectele inactive (N)" link: at the end of each domain section (sort "Pe domenii"),
      or at the end of the list (other sorts). It opens a list of only `arhivat` / `offline` entries
      of that section or tab, for all three tabs (proiecte, resurse & liste, organizații). Today the
      only way in is the "Ascunde proiecte inactive" toggle (`ina=1`), which mixes them into the list.
      Open question: does the inactive-only list replace `ina=1`, or does it get its own URL value
      (e.g. `ina=doar`)?
- [x] Keyboard navigation: `j`/`k` or `←`/`→` step through results (and the open entry),
      `o` opens the entry's own site; key hints in the footer
- [x] Mark fresh projects: `nou` tag when `since` is under 183 days, plus a "Doar proiecte noi"
      toggle (`nou=1`)
- [x] Sort by age: "Cele mai noi" (`o=nou`), by `since`; entries without a date go last
- [x] Update logo: `site/img/logo.png` from `docs/reference/logo/civtech-ro-favicon-2.png`,
      resized to 180 px (apple-touch-icon size)
- [x] GitHub link (icon) in the header instead of "Despre", and in the footer
- [x] Self-host the fonts: `site/fonts/` (latin + latin-ext woff2, 150 KB). The site now loads
      no third-party resource.
- [x] Logo at 40/44 px (no `scale()`); title text with a tricolour sweep and seven swap effects
- [x] "Pe domenii" sorts each group by last sign of life (last update, or launch date if later)
- [x] "Lansat recent" tag (under 60 days), separate from "nou" (60–183 days)
- [x] Sort "Active și relevante" (`o=top`): `score × (0.5 + 0.5·e^(−days/365)) + 8` for a recent launch
- [ ] Move the "Active și relevante" formula into `build.py` once the reach labels exist, if it
      stays; tune the half-life and the bump on real use
- [-] "Remove catalog column": no such column in `proiecte.csv` or the UI. Owner dropped it
      on 2026-10-18.
- [ ] Bookmarks in the browser, with CSV export (site-only; README marks it "later")
- [ ] Wait for search → relevance: static page per project, more than one domain per
      entry, "Altele" domain, methodology text. Each one changes `build.py` or the score.

- [x] Show `arhivat` when the profiler says `offline` and the last Wayback capture is over a year old
      (`build.py` `status_of`). 7 entries switched on 2026-10-18.

- [ ] Profiler: a connection timeout gives `blocat` → "Neconfirmat", which the main list shows.
      Two such entries were dead (parlament-transparent, piata-de-spaga; set `stare=offline` by hand
      2026-10-18). Retry from a second network, or count repeated timeouts as `offline`.
- [ ] CI: actions target Node.js 20 (deprecated); bump `actions/checkout` and the Pages actions.

## Editorial checks

- [ ] Check doubtful GitHub matches: `rescue-4x4` → `mihaituhari/rescue4x4-language`,
      `harta-banilor-publici` → `initiativaromania/HBP-Android`,
      `harta-tv-locale` → `geospatialorg/geospatialorg.github.io`
- [ ] Decide `stare=arhivat` for sites up with no edit in 3+ years: pmb-plus, monitor-social,
      median-research-centre, calitate-aer-radauti, data-expertforum, onorata-instanta,
      parlament-transparent (archived repo)

## Verified limits

- [-] GDELT news counts. GDELT answered "please limit requests" at 12 s spacing, and the
      queries that passed returned 0, also for factual.ro. Dropped (spec D2).
- [-] ROTLD WHOIS for domain age. Their terms forbid automated queries.
- [-] Quoted phrases on Serper's free tier: the API rejects them with HTTP 400. Use Brave for
      phrase queries.
- [-] SerpApi as a provider: ~$25 per 1k queries, 25× Serper.
- [-] Format the cells as text before writing the values. A `values.update` with `RAW` resets the
      number format of the cells it writes (measured 2026-10-18). `sheets.py` writes first and
      formats after.
- [-] A scratch spreadsheet for tests. The service account gets 403 on `spreadsheets.create`. Tests
      used two temporary tabs (`zz-test-*`) of the real spreadsheet, deleted after each run.
- [-] URL validation on "Adresa (URL)" in the Form. The Forms REST API (v1 discovery document,
      checked 2026-10-18) has no text validation: `TextQuestion` has only `paragraph`. `validate.py`
      checks the URL when a person copies an answer to a CSV.
- [-] A dry run of `forms.batchUpdate`. The API has none. The body was checked offline against
      the discovery schema (a scratch check, not in the repo); the first real test is `--apply`
      (all or nothing, guarded by the revision ID).
- [-] Host rules alone against name collisions. Measured 2026-10-18: after all rules, generic
      news sites (digi24.ro, hotnews.ro, adevarul.ro) stay in 21–24 entries each, because the
      name or author query matches common words. Only the page text can decide; that is the LLM
      step.

---


## Misc / unfilled
- assign a resource to more than one domain (and more keywords per resource; the Tip filter is already multi-select)
- maybe an "Altele" domain for things that fit nowhere
- [x] ranking by popularity / relevance — `score` in `build.py`, "Relevanță" sort; reach signals being reworked (`docs/specs/search-relevance.md`)
- [x] sort by age — "Cele mai noi" sort, by `since`
- [x] RSS feed — `site/feed.xml` from `build.py`: 40 newest live projects by `since`
- [x] update logo — `site/img/logo.png` from `civtech-ro-favicon-2.png` (180 px)
- [x] og image / description — `site/img/share.png` (1200×630), og/twitter tags in `index.html`
- [ ] initial ranking: by domain, then by relevance x last updated x age x novelty – we cam call this "relevanță". Remove active și relevante. Add "cele mai vechi"
- add manual ranking - recomandarea redacției?
- [x] mark fresh projects — `nou` tag (under 6 months) and "Doar proiecte noi" filter
- [x] navigate projects with keyboard, left/right, j/k, open original (`o`)
- [x] more links per resource, plus stats: social media, GitHub, search-engine result counts
- international mirror (projects, orgs, tools — seed: `data/international.csv`), shown contextually next to related Romanian resources
- "Propune un proiect", two ways in: a PR on GitHub, or a Google Form feeding a Google Sheet. Two-way sync via a GitHub workflow: (built 2026-10-18: see *Google Sheets sync*; the Form is not wired yet)
  - auth: Google service account, key stored as a GitHub Actions secret (or keyless via Workload Identity Federation); share only this one Sheet with the service account
  - Sheet → repo: new/changed rows become a PR, checked by `scripts/validate.py`; never commit straight to main
  - repo → Sheet: after merge, rewrite the mirror tabs from `proiecte.csv` / `orgs.csv` and mark proposals as accepted/rejected
  - runs on schedule / push to main only (secrets aren't available to PRs from forks)
- [x] hosting: GitHub Pages mirror, or host there with its own domain
- static HTML page per project at build time (own share preview, indexable)
- profiler: detect donation, terms, about/contact and data-access (download / API / MCP) pages from homepage links, feeding the same `links` roles
- write methodology? In Romanian. 
- later: allow bookmarks. saved in browser, but allow csv export.
