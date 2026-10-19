# Backlog

Statuses: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` dropped.

## v2 migration completion — execution checklist (brief: `docs/briefs/v2-migration-completion.md`)

Branch `taxonomy-v2-migration`. Production stays on v1. No Google, workflow, deploy or release action.

- [x] A. Enrichment on explicit roots: `profile.py`, `search.py`, `review.py --data-dir`; profile merge; label hashes and coverage; copyright date.
- [x] B. Sheets and Form for v2: new tabs, `_sync` marker as the base, 3-way pull, blocking validation, offline round trips, Form plan and importer.
- [x] C. Frontend audit defects in `site-v2/`: failed data load, noscript, canonical, observed dates, methodology page.
- [~] D. Review queue: reconcile R001–R066 with the integration copy; `tehnic` state for non-editorial items; a recommendation on every open item.
- [x] E. CI: tests, v2 validation and preview build, JS syntax, browser checks, workflow lint; path filters for `site/`, `site-v2/`, workflows.
- [ ] F. Cutover preparation: runbook, a dry-run check of the cutover, documentation of the v2 model.

## Taxonomy v2 — isolated proposal (spec: `docs/specs/taxonomy-v2.md`)

- [x] Copy all 122 entries into `data/taxonomy-v2/intrari.csv`, with separate subject, purpose, capability, format, technology, and geography facets.
- [x] Supply 125 defined concepts, including 13 local browsing subjects, and a complete crosswalk for the used v1 terms.
- [x] Preserve all eight original top-level data files as hashed snapshots. Keep working observation copies separate.
- [x] Verify 22 EuroVoc target identifiers and Romanian/English labels through the official endpoint. Leave semantic mappings proposed.
- [x] Preserve 86 source attributions without guessing their roles. Supply 66 specific review items and the initial assignment evidence.
- [x] Document the column contract, editing process, integration functions, migration order, and acceptance checks.
- [x] Validate the initial copy and JSON export. Run 12 focused integrity checks on temporary copies.
- [x] Add the Mermaid model overview and complete vocabulary diagrams, with an exporter that reads all 125 concepts.
- [x] Specify the visible filter labels, progressive disclosure, multi-select logic, counts, and grouping behaviour.
- [x] Record the agreed draft.2 revision: single-valued maturity with four stages, CSV-owned code lists/roles, and structural JSON rules.
- [x] Prepare the fresh-session implementation handoff and the automated classifier prompt with its JSON output schema.
- [x] Consolidate all 122 original entries into a single inference input CSV, without leaking the manual v2 classifications into the experiment.
- [x] Implement core handoff slice 1: upgrade the isolated package and validator to draft.2 without reclassifying entries.
- [x] Classify all 122 original entries and evaluate against the withheld draft. Preserve the sealed run in `data/taxonomy-v2/runs/2026-10-19-reasoned-evidence/`.
- [x] Resolve the evaluation's three semantic concerns in a separate integration copy (`data/taxonomy-v2/integrare/`, change log `modificari.csv`).
- [ ] Owner review of the integration queue (103 open items, 28 high priority): partial records, the abstention, attribution roles, external mappings, and 10 vocabulary proposals. Accept entries only after that review.
- [ ] Rewrite or close review items R001–R066 against the integration copy. Their texts describe the draft.1 manual proposal.
- [ ] Choose the ID style for proposed areas before accepting them (`tara:republica-moldova` now; existing countries use ISO codes, `tara:RO`).
- [ ] Implement an automated inference runner and no-call dry run if a later repeatable experiment needs them. This does not block the current preview.
- [x] Implement the v2 loaders, validator branch, build contract, and browser facets together. Keep the current data source as the default until cutover.
- [x] Verify the isolated preview: 40 unit tests (`scripts/test_taxonomy_v2.py`) and 63 browser checks (`scripts/check_preview.py`).
- [x] Run `scripts/test_taxonomy_v2.py` in `validate.yml`, with the CI slice. Include `site-v2/` changes in PR validation.
      Done 2026-10-20: `validate.yml` runs every `scripts/test_*.py` and the browser checks.
- [ ] At the cutover, replace `site/app.js` with `site-v2/app.js`, merge `site-v2/v2.css` into `style.css`, and remove `site-v2/`.
- [ ] Adapt enrichment, Sheets, Form, and CI to the accepted schema. Use separate v2 Sheet tabs during migration.

The public site does not consume this package. Production data and the v1 build output are unchanged; the scripts read v2 only with `--data-dir`.

## Audit — 2026-10-19

- [ ] `site/app.js`: a quick click on a choice just after opening a facet can close that facet again. The `toggle` event
      arrives after the re-render, so `closed` still lists the facet. `site-v2/app.js` reads the open state from the page first.

- [x] Make Sheets validation a blocking check. `sheets-pull.yml` records both exit codes, but opens the PR even when either command fails.
      The workflow uses `GITHUB_TOKEN`; its PR does not start the normal validation workflow.
      Done 2026-10-20: the job fails after it opens the PR and sets the status `validate / sheets-pull` (slice B).
- [ ] Add data-load error handling and a retry to `site/app.js`. An aborted `data.json` request leaves the results blank.
      Offer the static archives when JavaScript fails. The home page also has no main content without JavaScript.
- [ ] Repair dialog focus. Ctrl/Cmd+K can focus the background search while a dialog stays open.
      Shift+Tab from Close selects a hidden link inside the collapsed report panel; focus stays on Close.
      Changing a mobile filter rebuilds the sheet and drops focus to the body.
      `site-v2/app.js` fixes all three (v0.6.1, with browser checks); `site/app.js` keeps them until the cutover.
- [ ] Separate observed dates from confirmed launch dates. `isLaunched` uses `since`, which comes from Wayback, repo creation, or TLS.
      Rename inferred badges or add a curated launch date. Do not treat the first observed trace as a confirmed launch.
- [x] Remove the future date from `last_activity`. A 2026 copyright footer produces `2026-12-31` during October.
      Give copyright evidence less weight than a dated content update.
      Done 2026-10-20 (slice A): a dated update wins; the copyright year is `<year>-01-01`, never after today.
- [ ] Explain the status and ranking methodology. HTTP reachability does not confirm an operating service.
      A source-code link does not establish an open-source licence. The score favours age, page count, and visibility.
- [ ] Fill the 12 live entries with neither a tagline nor a description in the audit build.
      Validation passes with 28 warnings. Separate publication requirements from optional enrichment.
- [x] Invalidate review labels when the input URL set or entry changes. `review.py` only detects the old format without `mentiuni_map`.
      Report label coverage: once any label exists for a slug, `reach_features` ignores its unlabelled mentions.
      Done 2026-10-20 (slice A): input hashes per answer; per-URL label join; coverage line in `review.py` and `build.py`.
- [ ] Keep canonical and share metadata aligned with SPA navigation. Opening Factual directly, then closing it, leaves its canonical URL on the home view.
- [ ] Clarify the primary audience and catalogue scope in the visible introduction. Review the rotating political jokes against that audience.
      Simplify the competing relevance sorts and explain the abbreviated date columns.
- [ ] Add focused regression checks for profile preservation, label invalidation, score dates, dialog focus, and failed data loads.
      Include site changes in PR validation; the current workflow filters only `data/**` and `scripts/**`.

Existing items below also cover profile refresh data loss, Sheets merge conflicts, proposal intake, inactive discovery, and sitemap generation.

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
- [x] `README.md` line 54 still lists `profile.py --search --gdelt --opr` (flags removed)
- [x] `declic`: `url` de-clic.ro is offline; the search finds the live site at declic.ro. Editor
      decides whether to change the url. The `url` is now declic.ro
- [x] `profile.py --force` replaces the whole profile row and drops `mentions`, `search_social`
      and `opr`. Run `search.py --prune-only` after it, or make `profile.py` keep these columns
      Done 2026-10-20: `common.merge_profile` keeps the columns of other stages (slice A).
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
- [x] Trim the trailing space in `orgs.csv`, `descriere_scurta` of `code4ro` and `techsoup`. `pull`
      strips it (D2), so the next pull otherwise rewrites the file.
- [x] `pull` copies the Sheet over the CSVs with no base. A CSV edit on `main` that `sheets-push` has
      not written yet shows as a revert in the next pull request. Option: a 3-way merge with the last
      synced commit (needs a marker: a git tag or a cell in the Sheet).
      Done 2026-10-20: the Sheet's `_sync` tab names the last pushed commit; `pull` merges three ways and stops on a conflict (exit 3).
- [x] `push --since REF` stops with "row 1 differs" when the columns changed between REF and now.
      Run `push --force` once after a column change (README says so). Option: detect this case.
      Done 2026-10-20: `push` reads by column name and clears stale columns; `--force` is no longer needed after a column change.
- [x] GitHub keeps one pending run per concurrency group. If `sheets-push` runs are superseded, the
      next run's `before` is not the state the Sheet was synced from, and the check can give a false
      exit 3. Recovery: run `sheets-push` by hand with `since` or `force`.
      Done 2026-10-20: `sheets-push` uses the `_sync` marker, not `before`.
- [ ] The Sheet has a third tab, `propuneri` (Form responses). `sheets.py` ignores it. The
      "Propune un proiect" form is not wired to the pipeline.
- [x] `CLAUDE.md`: add `sheets.py` to *Commands*, the pipeline sketch and the *Deployment* section.

## Proposal Form (brief: `docs/briefs/form-generator.md`)

- [x] `scripts/form.py`: plans the 13 questions from `data/taxonomy.json`; default mode prints them and
      reads the Form; `--apply` replaces all items in one `forms.batchUpdate` (D1–D3). Tested read only
      on 2026-10-18; the owner ran `--apply` the same day.
- [x] Owner: read the dry run (`uv run scripts/form.py`), then run `--apply` once.
- [ ] After `--apply`: check row 1 of the tab `propuneri`. Before it, it holds `Timestamp` and
      `Untitled Question` (the Form's one default question). The deleted question may leave its column;
      delete that column by hand (0 responses).
- [ ] Importer for `propuneri`: map the answers to a `proiecte.csv` / `orgs.csv` row with `ANSWER_KEYS`
      in `form.py` (needs a `slug`; the editor accepts each row by hand, as for `review.py`).
- [x] Order the Form questions like the `proiecte` columns, so one paste moves a `propuneri` row to
      the tab `proiecte`: Ce propui? (`fel`), Nume, Pe scurt, Descriere, Adresa (URL), Alte linkuri,
      Domeniu, Tip, Acoperire, Oraș, Autor. Today "Adresa (URL)" comes before "Pe scurt". The first
      row pasted by hand (`registrul-firmelor`, 2026-10-18) has `descriere_scurta` and `descriere`
      swapped; it is not known whether the swap came from the Form or from the paste.
      Done for v2 2026-10-20: `form.py --data-dir` plans the questions in `intrari.csv` column order. The live v1 Form is unchanged.
- [ ] The Form's first question ("Ce propui?") offers only Proiect, Resursă and Organizație. It does not
      offer `articol`, `ghid`, `campanie` or `cercetare`. Decide whether to add them (`FEL_CHOICES` in
      `form.py`, then `form.py --apply`) or to let the editor set `fel` when copying a row.
- [x] Authors that look like a slug but have no row in `orgs.csv`: `gabriel-popa` (3 entries) and `gov2`
      (3 entries; the entry `gov2` is no longer in the Sheet). Add the rows to `orgs.csv`, or write the
      names in full. `validate.py` warns about each. The names are now written in full (Gabriel Popa, GOV2).
- [ ] Filter by `fel` in the "Resurse & liste" tab (article, guide, campaign, research). The label shows on
      each entry, but there is no facet yet.
- [ ] Owner: set `email` in `data/site.json`, or the report-a-problem panel has no e-mail option. Check that
      the Sheet's sharing lets the people you want edit it (or only comment); the panel links to its row.
- [ ] `sitemap.xml` and `robots.txt`, written by `build.py`, so that search engines find the
      `/<kind>/<slug>/` pages and the three archives. The home page lists the entries only through JavaScript
      (the footer links the archives).
- [ ] `site/404.html` for a removed slug: send `/<kind>/<old-slug>/` to `/?p=<old-slug>` or to the
      home page. Today a removed entry returns the GitHub Pages 404.
- [ ] The og images are WebP. Check a link preview on the networks that matter (Facebook, LinkedIn,
      Telegram, WhatsApp) once the pages are live.
- [ ] `docs/DATA-SCHEMA.md` can drift from `scripts/common.py`. Add a check to `validate.py` (or CI) that
      every column in `PROIECTE_COLS`, `ORGS_COLS`, `PROFIL_COLS`, `MENTIUNI_COLS` and `ETICHETE_COLS` appears
      in that file.
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
- [x] `profile.py --only` / `--force` drops `cert_first` while crt.sh answers 502 (2026-10-18:
      factual, code4ro; restored later with `--extra --only`). `extras_one` keeps an old value only
      when the profile row survives.
      Done 2026-10-20: the merge keeps `cert_first` when the new fetch has none.
- [ ] `profile.py --extra` runs a GitHub search for every live entry without a repo, on every run
      (about 75 requests, about 3 minutes at the 30 per minute limit). Store the miss to skip it.
- [ ] A link host whose favicon fails is fetched again on every run (no stored miss). Today: 0 failures.
- [ ] Orphans: 23 files in `site/img/icon/` and 12 rows in `profil.csv` have no entry in the CSVs
      (deleted entries, e.g. `rescue-4x4`). Nothing shows them.
- [x] `CLAUDE.md` pipeline sketch names `site/img/{og,icon}/`; add `linkicon`.

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

- [ ] Check doubtful GitHub matches (`rescue-4x4` is deleted): `harta-banilor-publici` → `initiativaromania/HBP-Android`,
      `harta-tv-locale` → `geospatialorg/geospatialorg.github.io`
- [ ] Decide `stare=arhivat` for sites up with no edit in 3+ years: monitor-social,
      calitate-aer-radauti, data-expertforum, onorata-instanta. (pmb-plus and median-research-centre are
      deleted; parlament-transparent has `stare=offline`.)

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
- [x] `site/llms.txt` from `build.py` (llmstxt.org): summary, data links, every entry linked to its page
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
