# Activity

## 2026-10-18 — New organisations and resources filled in

**Done**
- Sonnet filled the empty cells of 13 `orgs.csv` rows and 3 `proiecte.csv` rows from each site
  (about/contact/donate pages; Wayback for techsoup.ro, which blocks bots, and for the-sponge).
  Profiled all 16; searched the 13 without rows (48 requests, ~$0.10, 0 errors).
- Owner request: removed `safe-companii-de-stat` (its URL is a meta-refresh to monitorsafe.ro,
  already `monitor-safe`), with its 26 `mentiuni.csv` rows.
- Taxonomy: new types `colectie` and `serviciu`, as the owner used them. Slug `expert-forum` →
  `efor` carried into `mentiuni.csv` (34 rows, editor marks kept) and `profil.csv`.
- `split_list` also splits on a comma before a space or the end: the owner typed `a, b` links,
  and the comma had become part of the URL (seen in `ghiduri-efor`).
- Site: on desktop, first visit opens only the "Domeniu" filter; the sidebar lost a 2 px horizontal
  scroll; list thumbnails are 75 px. Footer reads "actualizat:". Header logo removed.

**Measured**
- 116 entries: activ 93, arhivat 11, offline 10, neverificat 1, necunoscut 1. `validate.py`: 0 errors.

**Decided**
- The two local NGOs (Rădăuțiul Civic, Civica Iași) get `domeniu=local`, not `civic`.
- No `orgs.csv` row for Quickdata Studio (PressPay co-author): a commercial studio.

## 2026-10-18 — Share preview, RSS, `/add-new-url`

**Done**
- `site/index.html`: Open Graph and Twitter tags (title "Colecție proiecte CivTech"), canonical
  URL, RSS `<link rel="alternate">`, and an RSS link in the footer.
- `site/img/share.png` (1200×630): logo `civtech-ro-1.png` plus title, made once with Pillow.
- `build.py` writes `site/feed.xml`: the 40 newest live projects by `since`.
- `.claude/commands/add-new-url.md`: check for a duplicate, audit the site, write the row, profile,
  search, validate, build.

**Decided**
- The feed orders by `since` (first trace on the web), because the catalogue has no "date added".
  A date from git history would need a full clone in CI (`fetch-depth: 0`). Cost: a project
  added today with an old site does not show at the top.

## 2026-10-18 — Dead sites out of the main list; automatic `arhivat`

**Done**
- `build.py` `status_of`: a profiler `offline` whose last Wayback capture is over a year old shows
  as `arhivat`. Manual `stare` still wins. Parked domains stay `offline`.
- `stare=offline` by hand for parlament-transparent (connection timeout, repo archived 2023) and
  piata-de-spaga (origin Apache 403 at the root; a reddit thread says it has been down for about a
  year). Both showed as "Neconfirmat", which the main list does not hide.
- CeRe moved: `orgs.csv` url `ce-re.ro` → `cere.ong` (the old site returns 500). Re-profiled
  `cere` and `declic` (declic.ro answers 200 now) and re-ran their search (`--force`, ~6 requests).
  Cleared 2 `editor` marks that pointed at their now-own domains.

**Measured**
- Statuses after: activ 87, arhivat 11, offline 10, neverificat 1, necunoscut 1
  (before: activ 85, arhivat 4, offline 19, necunoscut 3).
- Automatic `arhivat` (7): domnule-primar, harta-taierilor, harta-tv-locale, hoover,
  jailando, oradea-city-report, political-colours (+ the manual ones).

**Decided**
- The rule reads `last_capture`, not `first_seen`: an old project with a recent capture of an
  error page is "offline", not ended. Cost of the alternative (a fixed age): live-but-old projects
  would flip.

## 2026-10-18 — First pruning pass on `data/mentiuni.csv`

**Done**
- 12 Haiku agents (about 240 rows each) read the 2,841 rows that had no `editor` value and were
  not on the project's own site. They had the editor's 45 marks as calibration. Opus checked a
  sample, then set the obvious cases among the rows that Haiku left empty.
- Merged into the `editor` column. The editor's own marks were never changed. Haiku `0` on rows that
  a rule already drops were not written. Log of every cell (source, value, reason):
  `data/review/pruning-2026-10-18.csv` (gitignored, local only).
- Fix pushed for CI (`bce0efa`): `dignitas` had no `domeniu`.

**Measured**
- Haiku: 955 × `1`, 1,123 × `0`, 31 `0`s on rule-dropped rows not written. Opus: 114 × `0`, 2 × `1`,
  2 Haiku `1`s turned to `0` (site checkers: intodns, similarweb).
- After the merge: 3,386 rows, 1,128 kept (was 2,043), `editor` values 978 × `1`, 1,259 × `0`, 1,149 empty.
- Sample check (45 Haiku `0`s, 25 Haiku `1`s): no wrong `0` found; 2 weak `1`s (a tag page, a DNS checker).
- Top 10 by `score` unchanged as a set; expert-forum moved to first place (85).

**Hard**
- Batch 9 wrote its output outside the session scratchpad; it was collected by hand.
- Row ids were the line index in `mentiuni.csv`. Before the merge, every id was checked against slug
  and host, with 0 mismatches.

**Decided**
- `1` also covers the project's own channels and its author's pages, as the editor's marks do. The
  labelling step (`independent`) separates them later. Cost of the alternative: own-channel rows
  would need a third value, which the spec does not have.
- Left empty on purpose: author/organisation pages, generic topic news that may cite the project's
  data, and NGO pages for "redirecționează 3,5%". The editor decides these.

## 2026-10-18 — Search → labelled relevance: build and first run

**Done**
- `scripts/search.py` (new, `uv run`, httpx only). Flags: `--only`, `--force`, `--provider serper|brave|all`,
  `--dry-run`, `--prune-only`. It writes `data/mentiuni.csv` (D3), keeps the `editor` column on every
  rewrite, and recomputes `mentions`, `mention_hosts` and `search_social` in `profil.csv` from the kept rows.
  It saves the file after each entry, so a crash does not lose paid results.
- Prune rules (D5) in a list at the top of `search.py`: `propriu`, `social`, `registru`, `magazin`, `ferma`,
  and two more, `cod` and `zgomot` (see *Decided*). Rules only mark rows (`regula`).
- `profile.py`: removed `--search`, `--gdelt`, `search_mentions()`, `gdelt()` and `SKIP_MENTION`. `gdelt` is
  gone from `PROFIL_COLS` and from `score()`. `SOCIAL_HOSTS` and `SHARE` moved to `common.py`.
- `review.py` (D6): the kept results (at most 40, best rank first) go into the request as `mentiuni`; the schema
  has `mentiuni[{id, despre_proiect, tip_sursa, independent}]` and `atentie`; the system prompt warns about name
  collisions ("when unsure, false"). Labels go to `data/mentiuni_etichete.csv`. An older answer without labels is
  asked again when the entry has results. `--dry-run --only factual,declic` prints both requests (20 and 21 results).
- `build.py` (D7): `reach_features()` reads both CSVs; new `reach` weights; every item has `reach: {indep, stiri,
  cercetare, guvern, ultima}`.
- `validate.py` checks that `editor` in `mentiuni.csv` is empty, `0` or `1`. CONTRIBUTING.md and CLAUDE.md
  describe the new column, commands and pipeline.

**Measured** (all runs of 2026-10-18; prices from the providers' lists: Serper $1/1k, Brave $5/1k)
- Requests: Serper 294 credits (pilot 14, full run 277, force test 2, one date-format probe 1; two bad-key
  requests answered 403 and cost nothing). Brave 104 (pilot 4, full run 100). No error, no retry in the real
  runs. Cost ≈ $0.29 + $0.52 = **$0.81** (budget ≈ $1). The full run took 2 min 19 s.
- Rows: **3386** in 110 entries (10 to 50 per entry, median 32; file 1.3 MB). Kept **2043**.
  By rule: none (kept) 2043, social 633, propriu 503, zgomot 59, cod 51, magazin 47, registru 34, ferma 16.
  The first full run, before the extra rules, kept 2291 of the same 3386 rows.
- Dates: 1140 rows (34 %) have one. Serper 776 of 2616 (30 %), Brave 364 of 770 (47 %). So Serper dates are
  less rare than the spec assumed.
- Most frequent kept hosts (rows / entries): reddit.com 56/34, ro.wikipedia.org 42/33, adevarul.ro 27/23,
  digi24.ro 26/24, hotnews.ro 23/21, expertforum.ro 17/6, stirileprotv.ro 16/13, libertatea.ro 15/12,
  agerpres.ro 14/13, en.wikipedia.org 12/8, redirectioneaza.ro 12/12, romania-actualitati.ro 12/12,
  romaniapozitiva.ro 11/8, iqads.ro 9/7, cere.ong 8/2, galasocietatiicivile.ro 8/7, gov.ro 8/6,
  openpolitics.ro 8/2, researchgate.net 8/7, rfi.fr 8/7.
- Score, top 10 by `score`, old → new (old = HEAD scripts and `profil.csv` on today's catalogue; new = this
  work, **no labels yet**, so `indep` is the kept-host count): sicap-ai 86→86, expert-forum 85→85,
  companii-de-stat 83→83, factual 83→82, apador-ch 81→80, fdsc 75→75, interoperabilitate 74→74, testvot 72→72,
  redirectioneaza 71→71, onesti-city 70→70. The top-10 set is the same. 57 of 110 scores moved (mean +0.74,
  from −1 to +5); the largest rises are entries that had no search before (dignitas 63→68, dupa-cutremur 44→49,
  etherpad-situri-civice 16→21, accesinfo 28→32).
- Editor column: set 3 cells (one `0`, one `1` on a rule-dropped row, one `1` on a row the search does not
  return); `--prune-only` and a real `--force` run on `465` kept all three. The test copy of the file was
  restored afterwards, so no `editor` cell is set now.
- Errors: a run with invalid keys logged `ERR … HTTP 403` per entry, left the rows unchanged and exited 1.

**Hard**
- Name collisions are as bad as the handoff said. `465.ro` (domain query) returns USGS monitoring sites and
  railway wikis; `the-sponge` returns Seinfeld, cryptography and sea sponges; `declic` returns French
  dictionaries and a clothing brand. Rules cannot fix this; the LLM labels and the editor can.
- Author sites dominated the kept hosts: funky.ong had 77 rows in 9 entries and code4.ro 38 in 8. The
  handoff says an author's own channel is not independent, so `propriu` now covers the author's sites too.
- Author names collide as well: "Gabriel Popa" returns footballers and politicians.
- `declic` has `url` = de-clic.ro, which is offline; the search finds the live site at declic.ro. The editor
  decides (not changed: `proiecte.csv` is out of scope).
- Wrong turn: I ran `git stash` by mistake in a chained command and restored it with `git stash pop --index` at
  once; the tree was verified afterwards. Other people had uncommitted edits in `proiecte.csv`, `README.md` and
  `site/` at that time, and they were restored too.
- `validate.py` first reported one error: `dignitas` had an empty `domeniu` in `proiecte.csv`. It was fixed in the
  catalogue by somebody else during the work; the check passes now (28 warnings, all about missing descriptions).

**Decided**
- Queries use the first author only (without a bracketed note) and no author at all when the name already
  contains it ("gov2 gov2"). Three authors in one query narrow the results; the spec says `<autor>` only.
- A failed query leaves all rows of its entry unchanged; the entry is listed at the end and the run exits 1.
  The alternative (keep the rows of the queries that worked) would leave an entry that looks done but misses a
  query, because a slug with rows is skipped without `--force`. Cost: a paid query can be thrown away.
- A row with an `editor` value survives a rewrite even when the search no longer returns it. Cost: a few stale
  rows. The alternative loses editorial work.
- `propriu` also covers the sites of the authors: an organisation in `orgs.csv` with the same name, an author
  written as a domain, and the table `AUTOR_SITES` (funky.ong, funkycitizens.org, code4.ro). This is data
  from the first run; the editor extends it. Without it the top hosts are the authors' own sites.
- Two rules beyond the five named in D5: `cod` (GitHub, GitLab, Codeberg, Bitbucket; the repo is profiled
  already, and the old code skipped them) and `zgomot` (dictionaries, job boards, music, film and football
  databases: sites that answer any name). `magazin` includes online shops, `ferma` includes site checkers and
  review aggregators. All are host lists from what the first run showed.
- `search_social` is computed from every row except those with `editor = 0`, not only from kept rows: a profile
  page is dropped by the `social` rule by design, and it is the thing `search_social` reports.
- `reddit.com` and Wikipedia stay kept. Their pages can be independent attention; the LLM decides.
- Until `review.py` has run, `build.py` counts kept hosts as `indep`, as the spec says. It saturates at 15
  hosts, so name-collision noise counts as reach. The rank is provisional until the labels exist.
- Not done by choice: no change to `README.md` (outside the brief; line 54 still lists `--search --gdelt`),
  and no edit of `proiecte.csv` or `orgs.csv`.

**Not run**
- `review.py` against the API: `ANTHROPIC_API_KEY` is empty in `~/devbox/ePtm/puzzes/.env`. The label code is
  tested with a fake model answer only (ids map to URLs, unknown ids are ignored, `build.py` counts 6 hosts, 3 news,
  1 research, 1 government). `data/mentiuni_etichete.csv` does not exist yet.

## 2026-10-18 — Site: logo, title effects, recent launches, "Active și relevante" sort

**Done**
- Logo 40 px (44 px on desktop) instead of `scale(1.6)`, which overlapped the title on phones.
- Title: a blue–yellow–red band sweeps across the ink text (7 s); each swap picks one of seven
  effects (rise, drop, flip, wipe, zoom, slide, spread). Reduced motion turns both off.
- "Pe domenii": inside each domain, active first, then by last sign of life, then A–Z.
- "lansat recent" (filled tag) for `since` under 60 days; "nou" stays for 60–183 days.
- New sort "Active și relevante" (`o=top`). Fonts one pixel larger; list columns widened to fit.

**Decided**
- "Last sign of life" = the later of `updated` and, for a recent launch, `since`. So a launch
  sorts like an update. This is the "slight bump" in the domain sort.
- `topScore = score × (0.5 + 0.5·e^(−days/365)) + 8 if launched`; unknown date counts as 0.25.
  Measured: `updated` exists for 45 of 74 live projects (61 %), so a pure "updated" sort would
  push 29 projects to the end. The formula keeps them, at a discount. It lives in `app.js` because
  `build.py` belongs to the search work right now. Top 5: factual, sicap-ai, companii-de-stat,
  testvot, redirectioneaza; 3 launches enter the top 15.
- `score` already gives activity 30 %, so the sort counts recency twice. That is intended here.

## 2026-10-18 — Site: keyboard navigation, fresh projects, sort by age

**Done**
- `site/app.js`: `j`/`k` and `←`/`→` move focus through the results in display order. With the
  drawer open, they change the open entry (URL replaced, not pushed). `o` opens the entry's site
  or its Wayback copy. Esc returns focus to the last entry seen.
- `nou` tag on cards, rows and the drawer; "Doar proiecte noi" toggle (`nou=1`); sort
  "Cele mai noi" (`o=nou`). Footer lists the keys (hidden on touch devices).
- Fix: after the drawer re-renders (a related entry, or `j`/`k`), focus goes back to its close
  button. Before, focus fell to `body` and the Tab trap did not hold.

**Hard**
- A second session edits `scripts/` and `data/` at the same time. This work stays in `site/*`
  and uses only fields that `data.json` already has.

**Decided**
- "Fresh" = `since` under 183 days. Measured on the 2026-10-17 data: 24 of 77 live projects.
  `since` is mostly the first Wayback capture (78 of 110), so a new site can show as fresh
  only after its first capture.
- Arrow keys and `j`/`k` do nothing when focus is in a field or the filter sheet is open.
- Checked in headless Chrome (Playwright): focus order, drawer stepping, `o`, filter count,
  sort order. No console errors. Not checked: screen readers, touch devices.

## 2026-10-18 — Spec and brief for search → labelled relevance

**Done**
- Wrote `docs/specs/search-relevance.md` (decisions D1–D7) and `docs/briefs/search-relevance.md`
  from `docs/handoff-search-relevance.md`. Started `docs/BACKLOG.md`.

**Hard**
- The editor's pruning must survive reruns and reach CI, but the result rows are generated.
  Resolved with one generated CSV that carries one human column (`editor`), merged by (slug, url).
- `data/review/` is gitignored, so labels written there never reach the CI build. Labels go to a
  tracked, generated `data/mentiuni_etichete.csv` instead.

**Decided**
- New `scripts/search.py`; `profile.py` loses `--search`. Cost of the alternative: a fourth mode in
  a 690-line script, writing two files with different merge rules.
- Drop GDELT (no usable data measured). See backlog, *Verified limits*.
- The LLM labels each result; `build.py` turns labels into named counts. An LLM score would be
  cheaper to wire, but nobody could explain or tune a rank built on it.
- Brave for the name query, because it accepts quoted phrases and returns dates. Cost: ~$0.55 of
  the ~$0.80 budget.
