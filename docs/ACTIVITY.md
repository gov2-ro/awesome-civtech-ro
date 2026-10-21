# Activity

## 2026-10-22 — v2 editorial decisions taken on the recommendations; 19 entries added to the integration copy

The owner detached the copy on 2026-10-21 and asked for the decisions "as much as possible", because the project is not live. These are assistant decisions, not owner review.

**Done**
- Review queue: 65 of 66 open items closed with `decizie_editor` text. Most recommendations said "keep"; 10 items changed 12 entries in `intrari.csv`:
  `format:ghid` removed from 2 entries (R062, R063) and `format:vizualizare` from `ins-gov2` (C003); `nu-astepta-supereroi` is `national` + `tara:RO` (C013);
  `data-expertforum` and `crpe` cover `tara:MD`; the two hybrid-war entries cover `regiune:Europa`; `tehnologie:retea-de-senzori` and `scop:sustenabilitate-presa` are assigned.
- Vocabulary: `tara:MD`, `tehnologie:retea-de-senzori` and `scop:sustenabilitate-presa` added (130 concepts). Of the other proposals: 6 deferred, `regiune:europa-de-est` rejected.
- Entries: 121 of 122 set to `acceptat` in one pass. The pass checked only that each has a primary subject. It did not review each entry.
- The 19 mariuscomper.uk entries added to `integrare/intrari.csv` (7 `proiect`, 12 `publicatie`), `acceptat`, confidence `medie`.
  Their profile and search rows (19 and 213) were first copied from `data/` into `observatii/`, then taken out again: CI runs `validate.py --baseline` on the package,
  which compares `observatii/` with `source/` byte for byte, and failed on `main`. The cutover drops that flag. Until the rows are copied back, the v2 build shows the 19 as "neverificat", without images.
- Three tests pinned entry counts (122 and 121). They now read the counts from the data. 269 tests pass.
- `cutover_v2.py --plan`: 3 blockers, down from 4 on 2026-10-20 (detach done by the owner): `incentru` not accepted, C009 open, `tabs.intrari` null.
- Later the same day the owner gave up `incentru` and created the tab `v2-intrari`. `incentru` left v1 (`proiecte.csv`, `profil.csv`, `mentiuni.csv`: 34 rows)
  and v2 (`intrari.csv`, `rezultate.csv`, and its three review items: the validator refuses an item for an unknown entry). Its rows in `observatii/` stay: that folder keeps records of entries that left.
  `setari.json` has `tabs.intrari = 541482181`, read from the Sheet. `--plan` now shows no blocker: 140 entries, all `acceptat`. The `sursa_rand` of the 19 new entries was recomputed (the removal shifted `proiecte.csv` by one row).
- `check_preview.py` opened `incentru` to test the abstention panel. It now tests that panel only when an entry has no primary subject. 97 of 97 checks pass.

**Hard**
- The validator requires the top-level parent of every theme in `subiecte`. `subiect:statistica` has the parent `guvernare-democratie` and `subiect:populatie` has `comunitati-teritoriu`.
  Adding those parents would misdescribe the entries, so five entries dropped the theme `statistica`, and `ani-de-pensie` and `pensie-din-bursa` use `situatie-sociala`. Statistics is not searchable as a theme for them.
- `incentru` had no description, a parked domain (last capture 2025-08-16) and no evidence of its purpose. The Wayback lookup timed out. The owner decided to give it up.
- The two new concepts follow the existing `propus` convention for `statut`.
- After the push of `main`, `validate.yml` failed twice. The baseline check above was one. The other was `astral-sh/setup-uv@v10`, a version that does not exist;
  the file now uses `@v6`, as the Sheets workflows do. The local rehearsal passes (24 edits, 269 tests); actionlint was not available locally.
- After the push, `sheets-push` exited 3 ("Tabelul are modificări nesincronizate; rulează sheets-pull"): it refused to overwrite the Sheet, as designed. The 19 rows are not in the v1 tabs yet.

**Decided**
- `modificari.csv` is not extended. After the detach the file is not applied, and its rows must match the sealed assembly. Git history and `decizie_editor` are the record.
- Calculators use `format:formular` (no better format in the vocabulary). Articles use `format:raport` (research) or `format:articol` (explainers). `maturitate` is empty where the page does not state it.
- Not done: the Form, the v1 tab freeze, the 26 entries without text, and the cutover itself. The tab `v2-intrari` has 141 rows and needs a new push from the committed `intrari.csv`.

## 2026-10-21 — 19 mariuscomper.uk pages added to the v1 data

**Done**
- Added 20 rows to `data/proiecte.csv`: 7 `proiect`, 10 `cercetare`, 3 `articol`. Author Marius Comper, `civictech=1`. Each text comes from the live page
  (meta description and page text). A script checked every figure in the descriptions against the page text.
- On 2026-10-22 the owner dropped `tuneluri-feroviare` (weak civic fit). Its rows left `proiecte.csv`, `profil.csv` and `mentiuni.csv` (4 rows, 0 kept),
  and its two images were deleted. 19 entries remain: 7 `proiect`, 10 `cercetare`, 2 `articol`.
- Profiled the 20 (`profile.py --only`): all `activ`, HTTP 200. Image (19 entries after the drop): 16 OG, 3 screenshots (`ani-de-pensie`, `achizitii-directe-ti-2026`, `trei-din-patru`).
  Icon: 18 (`achizitii-directe-ti-2026` has none).
- Searched the 20 (`search.py --only`): 22 Serper and 20 Brave requests, 0 errors, ≈ $0.12. 217 result rows (213 after the drop); 103 kept by the rules, 84 after pruning.
- Measured: `validate.py` 0 errors, 28 warnings (all in older rows). `build.py` writes 141 entries after the drop; the pages build with scores from 25 to 43.
- `test_cutover.py` pinned the v1 entry count at 122, so it failed at 142. It now counts the rows of `proiecte.csv` and `orgs.csv`. 269 tests pass.

**Hard**
- The `mc-i` index row for `achizitii-directe-ti-2026` described another page (AFCN funding). The live page is a dashboard of direct-procurement
  signals. The row uses the live page; the `mc-i` summary for that id is not used.
- Surname collision: 19 kept results came from `concursurilecomper.ro` and `edituracomper.ro` (a competitions publisher). They are `editor=0` now.
  Open: 6 `iqads.ro` and 3 `republica.ro` results name a "Marius Comper"; nobody confirmed that it is the same person.
- `search.py --prune-only` re-applies the rules to all entries. It changed `regula` on 53 older rows and `mentions` on 10 other entries in
  `profil.csv`: the stored values were older than the current rules. The import reverted both, so the diff holds only the 20 entries.

**Decided**
- `fel`: v1 has no content tab. Explainers and investigations use `cercetare` or `articol` (tab "Resurse & liste"); tools use `proiect`.
  The v2 plan moves `cercetare` and `articol` to a new tab. Cost of the alternative (`proiect` for all 20): the pieces would crowd the main tab.
- The pages have no repository or social links of their own. `linkuri` holds only four dataset links (`date:`).
- Three entries use `altele`, because v1 has no domain for pensions or education.
- Not done: classification of the 19 in the v2 integration copy (see BACKLOG). No runbook step covers entries added to v1 after the sealed run.

## 2026-10-20 — Cutover prepared as one tested command; documentation of the v2 preview (slice F)

**Done**
- `integrare.py --detach` (owner, once): records the commit in `pachet.json`. After it, `integrare/` is editorial, and the check proves
  only that the overlay at the detach commit still assembles from the sealed run. Tested on temporary copies; the real overlay is not detached.
- `common.PUBLIC_ROOT` (today `data/`) is the default root of all seven scripts and the loaders. Only the public root may write `site/`;
  a v2 public root always runs the publication gate, and `--allow-draft` can never target `site/`.
- `scripts/cutover_v2.py`: `--plan` (blockers and steps), `--apply` (24 exact text edits in 10 files plus the `site-v2/` move; refuses
  while a blocker exists and writes nothing on any mismatch), `--rehearse DIR` (the whole cutover on a clone, then validation, build,
  script dry runs, unit tests and `actionlint` there). CI runs the rehearsal on every PR.
- Runbook `docs/briefs/cutover-taxonomy-v2.md`: owner decisions in order, external actions with commands, post-deploy checks, rollback.
- Documentation: `DATA-SCHEMA.md` (v1 and v2 files, `observatii/`, `_sync`), `ARCHITECTURE.md` (v2 roots, enrichment, `_sync`,
  CI; 9 Mermaid blocks parse), `CONTRIBUTING.md` (proposal routes as the code supports them; v2 is not editable by contributors yet),
  `README.md`, `CLAUDE.md`/`AGENTS.md` command lists (Haiku), `data/taxonomy-v2/README.md` (detach). `scripts/test_docs.py` fails
  when a column is missing from `DATA-SCHEMA.md`.
- Measured on the merged branch: 269 unit tests pass (34 cutover, 2 docs). `check_preview.py` 98/98. Rehearsal passes
  (269 tests in the copy, 6 skipped as cutover-state tests). `actionlint` 1.7.12 + shellcheck 0.10.0 pass on the four workflows.
  `--plan` lists 4 blockers: 122 unaccepted entries, 27 open high-priority items, `tabs.intrari` null, not detached.
  The v1 build is byte-identical to the build before slice F (timestamps aside).

**Hard**
- Existing tests pinned the draft data and the v1 default root. A simulated owner state (detached, accepted, items closed, vocabulary added)
  exposed 19 failures; the tests now read `PUBLIC_ROOT` and the derived roots, so they hold before and after the cutover.
- Two local preview servers from earlier sessions held ports 8765 and 8766, so the first browser run checked a stale build.
  The final run used port 8791. The servers were left running: they are not from this session.

**Decided**
- Detach before the owner edits, instead of routing every decision through `modificari.csv`. A direct edit and a Sheet pull into
  `v2-intrari` then work. Cost: after detach, CI proves the derivation only at the detach commit, and `--baseline` is skipped for the overlay.
- The rehearsal waives the gate only inside its copy, through a driver script. A flag or environment variable in `build.py` would be
  a way to publish drafts. Cost: the waiver lives in rehearsal code that the tests must keep in step.
- The cutover removes its own rehearsal step from `validate.yml`; `--rehearse` reports "already applied" afterwards.
- Not done: applying the v2 questions to the live Form (`form.py --apply` refuses a v2 root). It is an owner item before the cutover.

## 2026-10-20 — Integration review queue reconciled with the current classifications (slice D)

**Done**
- New code `revizuire_stare:tehnic` ("Închis tehnic"): a closure without an editorial decision. It needs a reason and refuses
  `decizie_editor`. The publication gate counts only `deschis`. Recorded as a draft.2 amendment in `versiuni.json`.
- `integrare/reconciliere.csv` (editable, 103 rows): every R, C, S and V item rewritten against `integrare/intrari.csv`, the sealed
  responses and the C/S items. `integrare.py` applies it and refuses any evidence token that does not resolve (400 tokens, all resolve).
  The base queue and every `intrari.csv` are unchanged; no classification changed.
- Result: 66 open (29 R, 23 C, 3 S, 11 V), 37 `tehnic` (31 premise not applicable, 6 duplicates). Open high priority: 28 → 27.
  Publication gate: 150 → 149 errors (122 unaccepted entries, 27 open high-priority items).
- Every open item has a "Recomandare: …" with its rationale and evidence. The Moldova area recommendation is `tara:MD`
  (ISO style, like `tara:RO`); the area is not added.
- Tests: `scripts/test_taxonomy_v2.py` 56 (16 new). Unit tests overall: 233.

**Hard**
- "The questioned value" is ambiguous when the integration value equals the draft.1 proposal. The agent closed such an item
  only when the old label is absent and the description settles the question; otherwise it stays open.
- The run attaches one excerpt to many facets, so several facet claims are weaker than the response summary. The recommendations say so.

**Decided**
- Opus review changed one rule: the agent had closed three high-priority R items (R004, R015, R030) as duplicates of medium C items,
  which removed 3 gate errors. Now the C items (C001, C008, C015) close as duplicates, and the R items stay open at high priority
  with the C texts. A test checks that a duplicate closure never points to a lower priority.
- One table for all four prefixes, and the evidence goes into `motiv`, so `schema.json` and the Sheet tab layout stay unchanged.
  Cost: the evidence is text, not a column a filter can read.
- The agent's rule for vocabulary proposals ("accept a new concept with two or more evidenced entries") is a recommendation only.
  It is not in the specification; the owner decides.

## 2026-10-20 — Sheets and Form for v2: sync marker, three-way pull, blocking validation (slice B)

**Done**
- `sheets.py --data-dir <v2 root>` works only on new tabs: `v2-intrari` (mirror of `intrari.csv`) and, with `--tabs`, `v2-revizuire`.
  A v2 root refuses `proiecte`, `orgs`, `propuneri` and `_sync`; a v1 root refuses the `v2-` tabs. Every cell is text; multi-value
  `|` cells get at most a suggestion list, never a strict drop-down.
- Sync base: a tab `_sync` (`tab, commit, sha256, time`). `push` writes it last, and only when the pushed bytes equal the CSV at
  `HEAD`. `pull` merges three ways (base = the CSV at the marker's commit) and writes nothing when the Sheet and the repo changed
  the same cell (exit 3). `push` reads by column name and clears stale columns to the right (a latent bug of the old `push_tab`).
- `pull --check` validates the pulled rows with the root's checks (v2: per-token IDs and schemes) and exits 1 on errors.
- `sheets-pull.yml`: a conflict fails the job before any PR change. A failed `validate.py` or `build.py` still opens or updates
  the PR, then sets the commit status `validate / sheets-pull` to failure and fails the job. `sheets-push.yml` uses the marker, not `before`.
- `form.py --data-dir <v2 root>` plans 13 questions in `intrari.csv` order (6 kinds, 13 root subjects and 12 formats as
  checkboxes, 4 coverage levels). `data/form-v2.json` (version 1) maps labels to IDs; it never re-maps a label.
  `--import FILE.csv` turns `propuneri` rows into `intrari.csv` rows and reports unknown labels. `--apply` and `--save` refuse v2.
- `scripts/test_sheets_form.py`: 122 tests with an in-memory Sheet, no Google and no network. Real data round trips byte for byte:
  109 + 13 v1 rows and 122 × 31 v2 cells. The workflow steps run in `bash -e` against stub `uv`, `gh` and `python3`.
- Measured: 217 unit tests pass; `actionlint` passes on the four workflows.

**Hard**
- This worktree also started at `v0.3.1` and was fast-forwarded before work.
- A checkbox cell joins labels with commas, and one subject label contains commas ("Drept, justiție și drepturi").
  The importer splits by known labels, longest first.

**Decided**
- A conflict writes nothing for any tab. Cost: one conflicting cell holds back the other Sheet edits until it is settled.
- An unusable marker (unknown commit, other bytes) is an error, not a silent two-way fallback, which would bring back the
  "revert" defect. Cost: the owner repairs it once (`--since` or `push --force`).
- The importer sets `de-revizuit` with an empty subject when a response ticks no subject or several; the ticked IDs go to
  `nota_clasificare`. Taking the first one would be a guess. This differs from the brief's `propus`; accepted.
- Do not require `validate / sheets-pull` in branch protection: only the `sheets-sync` PR gets it, so it would block the others.
- Not verified against Google: `add_worksheet` by the service account, `batch_clear` with two ranges, an empty new tab's values,
  and `gh api …/statuses` with `GITHUB_TOKEN`.

## 2026-10-20 — Enrichment on explicit roots; profile merge; label hashes; dated last activity (slice A)

**Done**
- `profile.py`, `search.py`, `review.py` take `--data-dir` (default `data/`). A v2 run reads entries from `load_catalogue` and
  reads and writes only the root's `observatii/` files. Images stay in `site/img/`. The three scripts now import under plain
  `python3`; each asks for its libraries only when it needs them.
- `common.merge_profile(old, fresh)`: a refresh (also `--force`) keeps `mentions`, `mention_hosts`, `search_social`, `opr`, and
  the `--extra` signals that the new fetch did not return (`cert_first`, `wiki_refs`, the repo group, …). `wiki_refs()` returns
  None on a failed call instead of a false 0.
- `search.py` on v2: author names from the attribution relations, `autor_original` as fallback; organisation sites only from
  relation targets that are organisation entries. Example: `7-ani-de-acasa` now searches "Funky Citizens", not `funky-citizens`.
- `review.py` on v2: facet IDs with definitions, one array per facet, cited evidence for technologies and typed roles
  (a quote of at least 12 characters from the supplied text), unknown terms to a proposal list. Output in
  `observatii/review/` (gitignored); `intrari.csv` is never written. The v1 prompt, schema and suggestion rows are unchanged
  (compared on all 122 entries).
- Each review answer stores hashes of the entry text, the sent URL set, the vocabulary, the prompt and the model. A changed hash
  makes the entry due again. `build.py` counts a label only for a kept row with the same URL; a partly labelled entry adds its
  unlabelled kept hosts and carries `provisional: true`. `review.py` and `build.py` print the label coverage.
- `last_activity`: a dated update wins; the copyright year is a fallback, as `<year>-01-01`, never after today.
- `scripts/test_enrichment.py`: 55 tests, no network. All 95 unit tests pass (also on Python 3.12).
- Measured: label coverage 0/1408 kept rows (no labels exist yet). Before the fix, 27 profiles had a future
  last activity (`2026-12-31`). v1 build: `stale` changes on 2 of 122 items (`code4ro` 2026 → 2023; `e-cutremur` empty → 2023),
  `score` on 19, all lower (17 by 7–8 points; `code4ro` 73 → 49, `e-cutremur` 57 → 33). Nothing else in the build changed.
- `docs/METODOLOGIE.md` and `docs/DATA-SCHEMA.md` describe the new rules.

**Hard**
- This worktree also started at `v0.3.1`; the agent rebased its empty branch onto the brief's commit.

**Decided**
- The hashes stay in the local, untracked `raw.jsonl`. Cost: a fresh checkout treats every entry as due (a paid re-run).
  A tracked hash file would avoid it, but it adds a file; revisit before the first paid run.
- A failed fetch never blanks a known value. Cost: a feed that a site really removed stays in the profile until `--extra` finds another.
- `review.py --dry-run` no longer fetches the homepage (also v1); `--fetch` restores it. A dry run must work offline.
- The v2 review does not propose `maturitate` or `tip_organizatie`. Maturity needs an explicit declaration (specification).

## 2026-10-19 — v2 browser code: failed load, noscript, head metadata, observed dates, methodology (slice C)

**Done**
- Work moved to branch `taxonomy-v2-migration`; `main` (8 unpushed commits) is unchanged. Slices A–D ran as Sonnet agents in
  separate worktrees from the brief `docs/briefs/v2-migration-completion.md`; Opus reviewed and merged each one.
- CI (`validate.yml`): runs on `site/**`, `site-v2/**` and workflow changes too. Jobs: v1 validation and build, all `scripts/test_*.py`,
  v2 package and overlay baselines, `integrare.py` reproduction, v2 validation and preview build (uploaded as an artifact),
  a non-blocking report of the v2 publication gate, `node --check` of both browser files, the browser checks, and `actionlint`.
  Measured locally: `actionlint` 1.7.12 with shellcheck 0.10.0 passes on all four workflows.
- Slice C, in `site-v2/app.js` (production `site/app.js` is unchanged; the cutover brings the fixes):
  a failed or aborted `data.json` request shows a message, a retry button and the three archive links;
  `canonical`, `og:*` and `twitter:*` follow the open entry and return to the home values on close;
  `since` is called "prima urmă observată" everywhere ("apărut recent", "nu este data lansării"), with tooltips for Z/L/A.
- `site/index.html` (shared): a `<noscript>` block with the archive links, and a footer link to the new `docs/METODOLOGIE.md`
  (Romanian; statuses, dates, score weights, what the score favours, limits; written from the code).
- Measured: `scripts/check_preview.py` 98/98 (35 new; 4 fail as expected with the old head and badge code).
  The v1 build differs from the previous build only in `index.html` and the 122 entry pages (the noscript and the footer link).

**Hard**
- One agent worktree started at `v0.3.1`, not at the branch. The agent fast-forwarded it before working; the others started correctly.
- `entry_pages()` already puts its own `<noscript>` at the top of each entry page, so the template's block sits inside `#results`.

**Decided**
- Fix the audit's browser defects in `site-v2/` only, as in v0.6.1. Cost: production keeps them until the cutover.
- Keep the `nou` URL value; only the wording changes. Old links keep working.
- The footer link and noscript reach production with the next merge to `main`. The methodology page names the v1 wording too.

## 2026-10-19 — One footer line for corrections; draft notices hidden

**Done**
- Owner request: the footer's "Propune un proiect" block has one line with the three ways to correct an entry:
  the Sheet (`tabel`), the Google Form (`formular`), and a GitHub issue. The text is in `site/index.html`.
- Owner request: the preview hides the "classifications are proposals" notices in the toolbar, the detail panel,
  the archives, and `llms.txt`. One `DRAFT_NOTE` switch in `site-v2/app.js` and one in `scripts/build.py` turn them back on.
- Measured: `scripts/check_preview.py` 63/63.

**Decided**
- Hide the notices with a switch instead of deleting them. The preview still sets `draft`, and a build without
  `--allow-draft` still refuses proposed classifications.

## 2026-10-19 — Phone layouts for cards and list; site address under the name

**Done**
- Owner request, in `site/style.css` (production and preview): below 720 px, a card is a row with the picture as a
  75 px square on the left, with type, name, tagline, and status. The list hides the picture and keeps the logo,
  description, badges, and dates. The detail panel puts the site address right under the name.
- The list row's date line started with "·" when the grey line was empty (v2 projects). Both browsers now join the parts.
- Measured: `scripts/check_preview.py` 63/63 (2 new checks for the phone layouts).

**Decided**
- Change the layout with CSS only. The card and row markup stays the same, so the desktop layouts are unchanged.

## 2026-10-19 — v1 details restored in the v2 preview; site link and footer note

**Done**
- Owner request: the detail panel's site link is now the plain address (blue, underlined, with the arrow), not a "Deschide …" button.
  Changed in `site/app.js` and `site-v2/app.js`; style in `site/style.css`. The archive button ("Vezi în arhivă") is unchanged.
- Owner request: the footer's "Propune un proiect" block has a "Corectează în tabel" link to the Sheet, with the panel's note.
  Changed in `site/index.html`, so the production site also gets it at the next push.
- Compared v1 and v2 builds entry by entry (122 detail panels, cards and list rows on three tabs, archives, llms.txt, feed)
  and by free-text search over all 55 v1 keywords. Restored in the v2 preview:
  - "Corectează în tabel" was missing on all 122 entries, because the Sheet has no v2 tab. The build now gives each item the v1 tab and row.
    All 122 rows equal the v1 build's rows.
  - Free-text search lost 133 entry–keyword matches (36 of 55 keywords, for example `date deschise`, `primării`, `alegeri`).
    Now 0: the search also reads the `legacy` words.
  - "Tot din …" was missing on 6 entries, because related entries had to share the primary subject. Now 4 remain:
    3 resources whose subject no other resource has, and `incentru`, which has no subject.
  - Cards lost their type (for example "Bază de date"). The grey line now names the first format.
  - Archive subject groups lost their hint line. Each now shows its four most frequent topics.
- Measured: `scripts/check_preview.py` 61/61 (6 new checks); `scripts/test_taxonomy_v2.py` 40 tests pass; v1 validator 0 errors.

**Hard**
- The comparison also shows intended differences: "Autor" is now "Atribuire · rol neconfirmat", "cod deschis" is "cod public",
  and v1 types and `#keywords` are replaced by the classification groups. These follow the specification and stay.

**Decided**
- Use the v1 Sheet row until the v2 tab exists. A report then reaches a real row; the alternative showed no Sheet option at all.
  The v1 row cannot hold v2 facets, so classification corrections still need GitHub or the review queue.
- Keep v1 words in the search index only. The vocabulary is frozen, so adding alternative labels was not an option.

## 2026-10-19 — Taxonomy v2 preview: missing UI recommendations

**Done**
- Compared `site-v2/app.js` with the specification's "Visible filter design" and "Browser filtering and search" sections,
  and with the audit's dialog defects. Most items were in v0.6.0. These were missing:
  - `Temă` showed all 52 project topics as one tag cloud. It now shows the 12 most used, plus a button for all of them.
  - Result badges had no facet name. Each badge now names its facet in a tooltip and in hidden text.
  - Facet choices had no group name for screen readers. Each facet's choices now form a named group.
  - Ctrl/Cmd+K and `/` moved the focus to the search box behind an open dialog. They now do nothing while a dialog is open.
  - Shift+Tab from Close tried to focus a link inside the closed report panel, so the focus stayed on Close.
    The focus trap now skips controls inside a closed panel.
  - A toggle or the reset button lost the focus after a filter change. The focus selector now uses only the control's own attributes.
    The mobile sheet also keeps its scroll position.
- Removed a dead first definition of `facet()`.
- Measured: `scripts/check_preview.py` 55/55 (8 new checks); `scripts/test_taxonomy_v2.py` 40 tests pass. `site/` is unchanged.

**Hard**
- In Chrome, a link inside a closed `<details>` still has client rectangles. A visibility test alone did not exclude it.

**Decided**
- Show the most used topics instead of grouping all topics under subject headings. Grouping would still show 52 choices.
  The subject filter already gives the hierarchical route.
- Fix the audit's dialog defects in `site-v2/` only. `site/app.js` gets them at the cutover, so the v1 build stays byte-identical.

## 2026-10-19 — Taxonomy v2 core slices 1–4: draft.2 package, integration copy, loaders, build, preview

**Done**
- Upgraded `data/taxonomy-v2/` to `2.0.0-draft.2`. `concepte.csv` equals the frozen run's 128-concept table (content; LF endings).
  New `valori.csv` (16 lists, 65 codes), `roluri-linkuri.csv` (22 roles), `gazde-linkuri.csv` (29 hosts), `versiuni.json`.
  `schema.json` has field rules with list/scheme references and cardinality; `setari.json` keeps only the reporting addresses.
  `manifest.json`, `source/`, `reference/`, `observatii/`, the initial ledger and the base `intrari.csv` are unchanged.
- Moved the checks to `scripts/taxonomy_v2.py`. `data/taxonomy-v2/validate.py` is now a thin wrapper with `--root` and `--publication`.
  Measured: base package `--baseline` 0 errors; integration copy `--baseline` 0 errors.
- Added `data/taxonomy-v2/integrare.py` and the overlay `integrare/`. It verifies the run's seal (258 hashes) and frozen
  files before reading, and refuses a vocabulary that differs from the frozen one. 122 entries: 121 `propus`, `incentru`
  `de-revizuit`; results 105 classified, 16 partial, 1 abstention. Texts, links, contacts, `stare` and `nota` come from
  `source/` by source identity. Queue: 103 items (66 R, 23 C, 3 S, 11 V); 10 vocabulary proposals (8 concepts, 2 areas).
- Addressed the three semantic concerns in `integrare/modificari.csv` (4 rows): M001 keeps `data-expertforum`'s media root
  with an exact excerpt from the stored source's Media section; M002 lowers its confidence and S001 asks for the Moldova
  area; M003 removes `jailando`'s `format:registru`; M004 removes `presspay`'s `scop:sprijin-organizatii` and proposes
  `scop:sustenabilitate-presa`. The sealed run is unchanged.
- `common.py`: `data_schema`, `observation_paths`, `split_ids`, `load_vocabulary`, `load_catalogue`; loaders take a root.
  `validate.py --data-dir [--publication]`. Publication gate on the integration copy: 150 errors (122 unaccepted, 28 open high-priority items).
- `build.py --data-dir --site-dir --allow-draft`; the v2 browser code is in `site-v2/` (`app.js` fork, `v2.css`).
- Verified: v1 validator 0 errors, 28 warnings. An isolated v1 build and a default build in a copy equal the HEAD build
  (all pages, archives, `llms.txt`, `index.html` identical; `data.json` and `feed.xml` differ only in timestamps).
  v2 preview: 122 entry pages, 3 archives, 120 of 128 concepts and 10 areas in the payload, maturity 29 operational,
  1 prototype, 92 null. `scripts/test_taxonomy_v2.py`: 40 tests pass. `scripts/check_preview.py`: 47 browser checks pass
  (desktop 1280×900, mobile 390×844). Technology claims: 6 on 5 entries, each with a non-legacy justification.

**Hard**
- The run's frozen CSVs have CRLF endings and the package has LF. The adapter compares parsed rows, not bytes.
- v1 output had to stay byte-identical: the refactored builder keeps the v1 item key order and the v1 score inputs.
- A facet opened and clicked quickly lost its open state: the `toggle` event fires after the re-render. The v2 code reads
  the open state from the page. The same race exists in `site/app.js` (backlog).
- The AI topic is assigned only to organisations, so the project tab never suggests it. The check tests each tab separately.

**Decided**
- The integration copy is an overlay (`pachet.json`, `local_files`), not a full copy. One vocabulary, one set of lists
  and one source snapshot. Cost: loaders resolve two folders, and an overlay cannot replace a base table silently.
- Fork `site/app.js` into `site-v2/app.js` instead of a dual-mode file. Production JS stays byte-identical until the cutover.
  Cost: two browser files to keep in step until then.
- `schema.json` is the only source of v2 column lists; Python reads it. Cost: no import-time constants for v2.
- The abstention keeps its entry with an empty classification as `de-revizuit`; no subject was invented. Partial results stay `propus`.
- Entry `incredere` is the lowest confidence among the entry's classification claims.
- A build folder must be outside the repository; a v2 build must not target `site/`. Proposals need `--allow-draft`,
  and the preview says that its classifications are proposals.
- Old `d`, `t`, `kw`, `c` bookmarks filter on `legacy` fields with their v1 meaning and show `(v1)` pills; they are not translated.
- Nothing was pushed or deployed; no workflow, Sheet or Form changed. `site/`, `data/*.csv` and `data/taxonomy.json` are unchanged.

## 2026-10-19 — Preserve taxonomy work for implementation

**Done**
- Committed the frozen classification run as `3a1c8fe`, tagged `v0.4.0`.
- Prepared the remaining proposal, snapshots, specification, classifier contract, audit notes, and handoff for a separate commit.
- Added the completed-run pointer to the handoff. The shared package remains draft.1; production remains unchanged.
- Rechecked the package baseline: 122 entries, 125 concepts, and zero errors. Production validation reports zero errors and 28 existing warnings.
- Excluded editor locks and Python caches from the package's Git exception.

**Hard**
- The original handoff described classification as future work. Its continuation update now records the completed experiment.
- Preserved source CSV text includes trailing spaces and CRLF line endings. Those bytes remain unchanged.

**Decided**
- Use the sealed candidate for core slices 1–4. Apply semantic corrections in a separate integration copy.
- Keep an automated inference runner optional for this preview; implementing it first would repeat completed classification work.
- Record this specification and data-package deliverable as `v0.5.0`. This repository has no `Cargo.toml`.

## 2026-10-19 — Consolidated classification input

**Done**
- Added `data/taxonomy-v2/clasificare-input.csv`: 122 unique original entries from the two immutable source CSVs.
- Preserved original descriptions, links, categories, types, keywords, geography, attribution, and source record references.
- Excluded manually proposed v2 assignments, private notes, and contact fields. Verified CSV round-trip equality.

**Hard**
- The consolidated input still has the original evidence gaps. One file does not make missing descriptions available.

**Decided**
- Prepare the agreed schema and vocabulary first, run and evaluate automated classification second, then integrate the build and UI.
- Keep the classification input separate from the controlled vocabulary and output contract.

## 2026-10-19 — Implementation handoff and automated classification prompt

**Done**
- Updated `docs/specs/taxonomy-v2.md` with the owner's agreed draft.2 decisions.
- Specified zero-or-one maturity: experiment, prototype, pilot, or operational. Reliability, adoption, and novelty remain separate dimensions.
- Specified CSV-owned code lists, link roles, and host lookup, with structural JSON rules and no independently edited duplicate enums.
- Added `docs/briefs/handoff-taxonomy-v2.md` as the fresh-session entry point, with core implementation slices and preview acceptance checks.
- Added `docs/prompts/taxonomy-v2-classifier.md` and its machine-readable JSON output schema.
- Defined an initially automated experiment with evidence citations, per-assignment confidence, vocabulary-gap proposals, abstentions, and independent evaluation.
- Checked the output JSON Schema with Draft 2020-12 validation and 12 structural cases. The current draft baseline still passes with 0 errors.
  Citation accuracy, supplied-ID membership, justification coverage, and original-attribution preservation are explicit checks for the future runner.

**Hard**
- The actual package remains draft.1. It has one maturity concept and the earlier JSON-owned lists.
  The handoff makes draft.2 package preparation a prerequisite for the classifier so that prompt and data cannot disagree.

**Decided**
- Treat the new request as preparation for implementation in a fresh session. Production code and source data remain unchanged in this turn.
- Keep the manually proposed assignments out of model input; compare them with automated results only after inference.
- Distinguish a valid model response, a complete candidate, and an editorially accepted entry.
- Preserve incomplete model output and uncertainty instead of manufacturing a primary subject.
- No provider was selected and no model calls were run. The next step for inference is a runner with a no-call dry run.

## 2026-10-19 — Taxonomy diagrams and filter implications

**Done**
- Added a Mermaid model overview and a filter-combination example to `docs/specs/taxonomy-v2.md`.
- Added `data/taxonomy-v2/export_mermaid.py`. It generates `docs/specs/taxonomy-v2-vocabulary.md` from the editable concept table.
- Measured complete coverage: 125 concepts across 13 subject hierarchy diagrams and 7 independent facet diagrams.
- Specified public filter labels, conditional facets, topic ancestry, unique counts, result badges, and detail-panel grouping.
- Verified the diagram export and the draft baseline validator. The draft still has 0 validation errors. `git diff --check` passes.

**Hard**
- One diagram with all 125 concepts would be difficult to read. The complete reference therefore uses smaller diagrams.

**Decided**
- Keep the current tabs, desktop sidebar, mobile filter sheet, list, and detail panel as the proposed interface structure.
- Replace mixed types and keywords with subject, topic, capability, and format filters. Put specialist facets under more filters.
- Use a flat list after subject filtering. An entry matched through a secondary subject should not appear under an unrelated primary heading.
- Distinguish national applicability from the availability of data for a particular locality. These require different evidence.
- This change documents the proposed interface. It does not modify the current frontend or production data.

## 2026-10-19 — Separate taxonomy v2 review copy

**Done**
- Created `data/taxonomy-v2/` and the integration specification `docs/specs/taxonomy-v2.md` at the owner's request.
- Proposed classifications for all 122 entries: 100 projects, 13 organisations, and 9 resources in the existing URL sections.
- Added 125 controlled concepts, including 13 local browsing subjects, with Romanian/English labels and Romanian definitions.
- Preserved the original eight top-level CSV/JSON files byte for byte. Recorded their SHA-256 hashes and copied generated observations separately.
- Added 822 initial assignment records, 86 unresolved source attributions, and 66 specific editorial review items.
- Retrieved 22 EuroVoc identifiers and Romanian/English labels from the official SPARQL endpoint. Stored the exact query and response.
- Kept every external semantic mapping and every entry classification proposed. No individual project site was fetched for this pass.
- `validate.py --baseline --export` passes with 0 errors. Twelve focused integrity checks pass on temporary copies.
  The checks cover unknown IDs, wrong schemes, duplicate slugs, missing roots, hierarchy cycles, retired concepts, external identifiers,
  relation endpoints, review decisions, manual edits, snapshot integrity, and the initial export.
- Production validation still reports 0 errors and the same 28 warnings. An isolated v1 build still produces 122 entries and 3 archives.
  All eight original data files retain their source hashes.
- Added a scoped `.gitignore` exception so that the separate proposal and its snapshots are not silently ignored.

**Hard**
- The first SPARQL query timed out after 40 seconds. A query with directly bound English labels returned the verified subset.
- Sparse descriptions cannot establish precise capabilities or technology use. Such entries retain low confidence and explicit review items.
- The document connector was unavailable. The requested specification is repository Markdown.

**Decided**
- Keep human-readable CSVs authoritative; generate `catalogue.json` from them with the package's standalone stdlib validator.
- Keep the thirteen browsing roots local. Use EuroVoc as a reference and SKOS as a modelling guide, without claiming conformance.
- Distinguish subjects from civic purposes, capabilities, formats, technologies, institution types, and geographic coverage.
- Preserve uncertain author roles as `atribuit_in_sursa`; guessing a maintainer or funder would create unsupported claims.
- Do not adapt production scripts or publish the proposal. The owner will review the copy and carry out the later integration.

## 2026-10-19 — Product, UX, and architecture audit

**Done**
- Reviewed the purpose, data flow, frontend, enrichment scripts, and publishing workflows.
- Ran validation: 0 errors, 28 warnings. Built a temporary copy: 122 entries, comprising 100 projects, 13 organisations, and 9 resources.
- The build has 101 active entries, 1 unconfirmed entry, and 20 inactive entries. Twelve live entries have no descriptive text.
- Checked Chrome at widths 320, 390, 768, 1024, and 1440. No page-level horizontal overflow or normal-load JavaScript errors appeared.
- Reproduced blank results after a failed data request, dialog focus defects, mobile filter focus loss, and stale canonical metadata.
- All eight Python scripts parse. `node --check site/app.js` passes.
- Recorded findings in BACKLOG.md. No implementation or source data changed.

**Hard**
- The configured Playwright browser binary was absent. The audit used installed Chrome.
- The audit did not run paid enrichment, write to Google, trigger workflows, or verify live hosting settings.

**Decided**
- Keep the static architecture. Current size does not justify an application server or a database.
- Prioritise evidence quality, failure handling, and editorial checks before adding ranking signals.
  These are audit recommendations; no product or specification changes were applied.

## 2026-10-19 — llms.txt

**Done**
- `build.py` writes `site/llms.txt` (`llms_txt`), in the llmstxt.org format: an H1, a summary in a blockquote,
  the data links (`data.json`, the two CSVs, `DATA-SCHEMA.md`, `CONTRIBUTING.md`, `feed.xml`), and one
  Markdown link per entry to its own page, with the tagline (else the description, cut at 200 characters), the
  site address, and `(offline)` / `(arhivat)` for a retired entry. Projects are grouped by domain, organisations
  run A-Z, resources are grouped by `fel`. Measured on the current data: 122 entries, about 21 KB.

**Decided**
- The text is in Romanian, like the site. The file is generated on every build, so it cannot drift from the data.
  A hand-written file would be shorter, but it would go out of date with each new entry.
- The links go to the entry pages, not to the projects' sites: the entry page carries the description in
  `<noscript>`, and the line also gives the site address. No `llms-full.txt`: `data.json` holds the full data.

## 2026-10-18 — Stale CSS behind Cloudflare

**Done**
- Symptom: after the push, the public footer showed the old dark palette and overlapping theme buttons, but the
  new HTML (the "Liste simple" line). Measured with `curl -I`: `style.css` and `app.js` answered `cf-cache-status:
  HIT`, `cache-control: max-age=14400`, `last-modified` from the earlier deploy, and their hashes differed from
  the files on GitHub Pages and in the repository. The HTML and `data.json` were `DYNAMIC` and current.
- Cause: Cloudflare caches static files by extension, and its browser TTL (4 hours) replaces the 10 minutes that
  GitHub Pages sends. HTML and JSON are not cached, so the new page ran with the old CSS and JS.
- `build.py` now writes `?v=<sha1 prefix>` on the `style.css` and `app.js` links of `site/index.html`
  (`stamp_assets`, before the page writers copy it). A changed file has a new address, so nothing needs a purge
  and no browser keeps the old file. Browsers that hold the old page's CSS see the new one on their next visit
  to the page (the HTML is cached 10 minutes).

## 2026-10-18 — A manual image for an entry

**Done**
- The owner saved `site/img/og/semnal-razboiul-hibrid.webp` by hand, and it did not show. Cause: the entry
  had no row in `profil.csv` (a new Sheet row, never profiled), and `build.py` takes the image from that row.
- `profile.py` now adopts an image file that it did not write (`manual_image`): it records the size, colour
  and kind with `img_source` = `manual`, and no fetch or screenshot replaces it. A file from an earlier run
  names its source in the old profile row, so it is refreshed as before. Run `uv run scripts/profile.py
  --only <slug>` after saving the file.
- Profiled `semnal-razboiul-hibrid` (status activ, image kept: 34708 bytes before and after, 960 x 557).

**Hard**
- The same gap holds for the other new Sheet rows: they have no profile row yet (see the status `neverificat`
  in `data.json`). `uv run scripts/profile.py` without arguments profiles them.

## 2026-10-18 — Logos, archives, report a problem, Monokai dark theme

**Done**
- The owner ran `form.py --apply` (read back with `form.py`: 13 questions, "Altele" in Domeniu).
- Logos: the 128 px icons are shown as the project's logo: 24 px before the name in list rows (no blank
  when there is none, so a title without a logo starts at the left edge), and 72 px in a new drawer
  header, left of the title, the "Deschide" button and the tagline.
- `acoperire` empty now means `national` in `build.py`; `validate.py` no longer warns about it.
- Archives: `build.py` writes `site/proiect/`, `site/organizatie/` and `site/resursa/` `index.html`: every
  entry of the kind, readable without scripts. The footer links them. All three, not only projects and
  organisations, so that the resources do not lack one.
- "Semnalează o problemă" at the end of the drawer: a `<details>` with three prefilled options (the Sheet
  row, an e-mail, a GitHub issue). `data/site.json` holds the addresses; `build.py` adds `row` to each item
  (row 1 is the header, so the first entry is row 2). The e-mail is empty,
  so that option is hidden until the owner sets it.
- Dark theme is Monokai Pro, filter Classic (bg `#272822`, text `#fdfff1`, pink `#f92672`, blue `#66d9ef`,
  green `#a6e22e`, yellow `#e6db74`, orange `#fd971f`; the hex values come from the theme's preview
  SVG on vscodethemes.com, except orange). Project images in dark get `opacity: .85` so a white page
  blends into the dark background. The accent badge text now uses `--bg`.
- The pending work of the earlier entries was committed by topic (8 commits).

**Hard**
- The e-mail address is not in the repository; I did not guess one.

## 2026-10-18 — Authors, `fel`, kind paths, text size, theme

**Done**
- Pulled the Sheet into the CSVs (`sheets.py pull`): 4 new rows (one is a Sheet edit of `registrul-firmelor`),
  `autor` cells changed to org slugs, the org slug `ethicalmedia` renamed `ethical-media`, and the entry
  `gov2` removed. PR #1 is stale now; the next `sheets-pull` run updates it.
- `taxonomy.json`: new domain `altele`, and a new list `fel` (`proiect`, `resursa`, `articol`, `ghid`,
  `campanie`, `cercetare`), each with the tab it belongs to. `common.FEL_KIND` maps `fel` to the tab, so
  every `fel` but `proiect` lands on "Resurse & liste". `validate.py` and the Sheet's drop-down read
  the list. Data still holds only `proiect` and `resursa`; the owner has not set the new values yet.
- Addresses follow the tab: `/proiect/…`, `/organizatie/…`, `/resursa/…` (`build.py` writes the three
  folders; `app.js` reads any of them).
- Authors: `build.py` turns `autor` into `authors: [{name, org}]` (a name that is an `orgs.csv` slug
  becomes that organisation). The drawer of an entry shows the organisation as a card, and "De același
  autor" lists the other entries with the same author. The drawer of an organisation shows "Proiecte și
  resurse". Names that are not slugs match by their written text.
- Footer: text size S / M / L / XL (0.9 / 1 / 1.15 / 1.3 of the current size; M is the old size) and
  theme Sistem / Luminoasă / Întunecată. Both persist in localStorage and apply before the first paint
  (a `<head>` script). Every `px` font size in `style.css` is now `calc(Npx * var(--fs))`; the dark
  styles exist twice (OS preference, and `data-theme="dark"`).
- Measured in headless Chromium: body font 14.4 / 16 / 18.4 / 20.8 px; OS dark + "Luminoasă" gives a
  white page; reload keeps both choices; no page errors, no 4xx.

**Decided**
- `acoperire` may be empty (a warning, no longer an error). Later the same day the owner chose a default:
  an empty value means `national`, with no warning. The two new Sheet rows had it empty, and an
  article has no reach. Cost of the alternative: CI fails on rows the owner added on purpose.
- An author written as plain text is not matched to an organisation by name, only by slug. Cost of
  name matching: a link nobody asked for. Cost of slugs only: the owner must write the slug.

**Hard**
- The `gov2` entry is gone from the Sheet, and three rows still name `gov2` as author.

## 2026-10-18 — Favicons beside names, first Sheet pull request

**Done**
- `sheets-pull` ran for the first time (by hand). It opened PR #1 with one new row
  (`registrul-firmelor`) and one edit (`ro-api-hub`). The owner swapped the two description cells of
  the new row in the Sheet, and the second run carried the fix. The merge is still open (see **Hard**).
- `site/app.js`, `site/style.css`: the project's favicon (`it.icon`) shows before the name in list rows
  (16 px) and in the detail heading (24 px). Rows keep their og-image thumbnail. An entry without a
  favicon gets a blank of the same width in a row, so the names stay aligned. Cards are unchanged.
- Measured in headless Chromium, light and dark: 65 rows show a favicon, 16 rows show a gap, and
  the page raises no errors. Of the 117 entries in `data.json`, 81 have a favicon.

- List view: a **Links** column (up to 4 icons: curated links first, then those found on the site;
  "+n" for the rest), and **Age** / **Updated** columns, narrower, with compact values: `9Z` days,
  `2L` months, `13A` years, no space. The headers are English at the owner's request; the values in
  the drawer keep the long Romanian form. "Zile" became `Z` by analogy with `L` and `A`.
- Pretty links: `build.py` writes 117 pages to `site/proiect/<slug>/index.html` (git ignores them).
  Each has its own title, description, canonical URL and og/twitter image, a `<base href="../../">`
  and a `<noscript>` summary. `app.js` takes the slug from the path, writes `/proiect/<slug>/` with
  `pushState`, and still opens `?p=<slug>`. An entry opened by address alone shows its own tab
  (organisations, resources). The RSS links point to the new addresses.
- Tested in headless Chromium: static page, close, click in the list, Back, old `?p=`, organisation
  page, filters in the query, `j` step, no trailing slash: no page errors, no 4xx.

- `docs/DATA-SCHEMA.md`: every column of `proiecte.csv`, `orgs.csv`, `profil.csv`, `mentiuni.csv`,
  `mentiuni_etichete.csv`, `taxonomy.json`, `form.json` and `data.json`, with the rules of
  `validate.py`. Written from the scripts; each claim was checked in the code. Linked from the README,
  CONTRIBUTING, ARCHITECTURE and CLAUDE.md.

**Hard**
- A relative image path breaks after `pushState` to `/proiect/<slug>/` on a page without `<base>`
  (`img/og/x.webp` resolves under `/proiect/<slug>/`). Found in the first test run. `app.js` now
  prefixes every data path with `ROOT` at load.
- A fix pushed to the `sheets-sync` branch would make `sheets-push` exit 3 after the merge: the
  Sheet's swapped cells count as edits the repo does not have. The fix went into the Sheet instead.
- The agent's `gh pr merge` was blocked by the permission classifier. The owner merges the PR.

## 2026-10-18 — Form live, Form template, architecture doc

**Done**
- `form.py --apply` wrote the 13 questions to the proposal Form (revision 7). `--save` stores the
  Form, as edited by hand, in `data/form.json`; `--apply` uses it as the template from then on.
- Scripts read the repo's `.env` themselves (`load_env` in `common.py`); exported variables win.
- First real sync: pulled the owner's Sheet edit (`demoanaf`), removed quotes typed into two `tip`
  cells and around one description, pushed back with `--force`; `diff` then showed no differences.
  `sheets-push`, `pages` and `validate` passed on GitHub.
- Footer links the public Form (forms.gle/wswqrm7P4QV25NZx7). `docs/ARCHITECTURE.md` describes the
  data flow, the Sheet ⇄ CSV workflows and the Form, with Mermaid charts; linked from the README.

**Hard**
- The owner saw the Form's file name as "Untitled form". `form.py` sends no `updateFormInfo`; the
  API showed `documentTitle: "Untitled form"` already before the first `--apply`. Now both names are
  "Sugestii listă civtech.gov2.ro".

**Decided**
- Taxonomy-backed choices (Ce propui?, Domeniu, Tip, Acoperire) always come from `taxonomy.json`, even
  with a template, so answers map back to CSV keys. Cost: renaming those four questions breaks that.

## 2026-10-18 — Proposal Form generated from the data model (brief `form-generator.md`)

**Done**
- `scripts/form.py` (PEP 723: `google-auth`, `requests`). It plans 13 questions in the order of the brief (D2).
  The choices of `Domeniu`, `Tip` and `Acoperire` come from `data/taxonomy.json`; the first question has the
  labels of the brief. `TITLES` (top of the file) holds the titles; `ANSWER_KEYS` maps title → choice label →
  CSV key and is printed. Default mode prints the plan and the Form as it is now (read only). `--json` also
  prints the `batchUpdate` body. `--apply` deletes all items and creates the planned ones in one
  `forms.batchUpdate` (D1). **`--apply` was not run**: the owner approves the dry run first.
- README: part "Formular (the proposal Form)" in the Google Sheets section.

**Measured** (2026-10-18; the key was never printed)
- `GET forms/{id}` with scope `forms.body`: HTTP 200. The Form has 1 item (`Untitled Question`, radio),
  revision `00000006`, and a linked Sheet.
- Tab `propuneri`, row 1: `Timestamp`, `Untitled Question`. 0 responses.
- The plan: 13 questions (3 required), 14 requests in the body (1 `deleteItem`, 13 `createItem`). The longest
  help text (Domeniu, with 11 hints) has 772 characters.
- The `batchUpdate` body has 0 errors against the schema of the v1 discovery document (field names, types,
  enums). That is the only check: the API has no dry run.
- Discovery document: `TextQuestion` has only `paragraph`, so a URL validation is not possible.

**Hard**
- No way to test the write. A scratch Form would be a new file in the service account's Drive (outside the
  brief), so the first real test is `--apply` itself. The call is all or nothing, and it carries
  `requiredRevisionId`, so a concurrent edit of the Form makes it fail instead of being overwritten.
- The auto-mode classifier denied a test run of `--apply` without credentials (a guard check). It was not
  retried.

**Decided**
- **Hints in the help text, one `label: hint` line per hint of 60 characters or less.** A drop-down has no text
  per choice, so the hints go into the help text of the question. All 20 hints pass. Alternative: the hint in
  the choice label. The answer text would then differ from the taxonomy label, and a changed hint would break
  `ANSWER_KEYS`.
- **Key `organizatie`** for the third choice of `Ce propui?` (the `kind` of `common.py`); `proiect` and `resursa`
  are the `fel` values.
- **Delete from the last index down**, so every index in the request is the one that was read.
- **`includeFormInResponse`**, then compare the titles of the answer with `TITLES`. A mismatch is an error.
- The Google imports sit inside functions, so `from form import ANSWER_KEYS` works without the Google packages.
- **Open risk:** the Sheet may keep the column `Untitled Question` after the delete. See BACKLOG, *Proposal
  Form*.

## 2026-10-18 — Google Sheets sync (brief `sheets-sync.md`)

**Done**
- `scripts/sheets.py` (PEP 723: `gspread`, `google-auth`): `diff`, `pull`, `push [--since REF] [--force]`.
  Key from `GOOGLE_SA_KEY` (JSON text) or the file in `GOOGLE_APPLICATION_CREDENTIALS`; Sheet from `SHEET_ID`.
  `pull` reads strings, checks that row 1 equals `PROIECTE_COLS` / `ORGS_COLS`, drops empty rows, strips
  trailing spaces and line-ending `\r`, and writes with `write_csv`. `push` writes header and rows in one
  `update` (RAW), clears the rows below, then freezes and bolds row 1, sets every cell of the table to plain
  text, and adds drop-downs for `fel`, `domeniu`, `tip` (suggests only), `acoperire`, `stare`, `civictech`.
  Exit codes: 0 done, 1 error, 3 the Sheet holds edits not yet in the repo (nothing written).
- `.github/workflows/sheets-pull.yml`: every 6 hours and on demand; `diff`, `pull`, `validate.py`,
  `build.py`; one pull request from `sheets-sync` (force-pushed), title and text in Romanian, text = `diff`
  plus `validate.py` output. It commits the two CSVs only. When the Sheet matches `main` again, it closes an
  open `sheets-sync` pull request.
- `.github/workflows/sheets-push.yml`: on push to `main` that touches the two CSVs, and on demand (inputs
  `since`, `force`); `push --since <before>`; exit 3 fails the job with "Tabelul are modificări
  nesincronizate; rulează sheets-pull". `fetch-depth: 0`, so that `--since` can read an older commit.
- Both workflows use `concurrency: group: sheets`, `cancel-in-progress: false`.
- README: the "Editing in Google Sheets" section now says how it works, with the one-time setup.

**Measured** (all on 2026-10-18; the key was never printed)
- Real Sheet, read only (`diff`): `proiecte` 104 rows in the CSV and the Sheet, one cell differs
  (`demoanaf` / `descriere`: the Sheet lacks the sentence "Proiect independent." and the two line breaks).
  `orgs` 13 rows, no cell differs. Because of that cell, the first `push` to the real tabs was **not** run
  (brief: stop and report).
- Real Sheet, `pull` as a test: `proiecte.csv` 1 cell (4 lines in `git diff`), `orgs.csv` 2 lines
  (`descriere_scurta` of `code4ro` and `techsoup` end with a space in the CSV; `pull` strips it). Restored
  with `git checkout`.
- Push, pull and diff on two temporary tabs of the real spreadsheet (`zz-test-proiecte`, `zz-test-orgs`,
  created and deleted in each run; the data tabs were not touched): `push` wrote 104 and 13 rows; `diff`
  then showed no differences; `pull` left `proiecte.csv` byte-identical (empty `git diff`) and `orgs.csv`
  differs in exactly the 2 trailing-space lines. Under `UNFORMATTED_VALUE` the `civictech` cells come back as
  strings (7 of 7 read); A1, A2 and O2 carry `numberFormat TEXT`; row 1 is frozen and bold; 6 drop-downs, 5
  strict and `tip` not.
- Guards on the same tabs: a Sheet edit gives exit 3 for `push` (no ref), for `--since HEAD` and for
  `--since 6aec21c` (only the edited cell is listed, not the rows that changed in the repo since). With the
  Sheet equal to the current CSVs, `--since c2028f3` gives exit 0 (the merged pull request case). A renamed
  header cell gives exit 1 and names "missing 'nume'; unknown 'nume_x'"; an unknown ref gives exit 1;
  trailing spaces are stripped.

**Hard**
- The first test runs failed on two defects, both fixed: an empty tab comes back from `get_all_values()` as
  one empty row (it looked like a wrong header), and a `values.update` with `RAW` resets the number format of
  the cells it writes (the first version formatted before writing, so no cell was plain text). Now
  `push_tab` writes first and formats after.
- The service account cannot create a spreadsheet (HTTP 403), so the tests used temporary tabs in the real
  spreadsheet.
- The tab list of the spreadsheet changed while this ran (`Form Responses 1` became `propuneri`): somebody
  else edits it. `sheets.py` reads and writes only the two named tabs.
- Not run: `validate.py`/`build.py` inside the workflow shell and the `gh` calls (no workflow may run, no
  push). The shell blocks passed `bash -n`, the YAML parsed, and the PR text step ran with stubbed
  `validate.py` and `build.py`.

**Decided**
- **D4 is refined, not changed.** As written, `push --since <before>` fails on the main flow: the editor edits
  the Sheet (Sheet = A + E), `sheets-pull` opens a pull request with A + E, the merge pushes to `main` with
  `before` = A, and the Sheet differs from the CSVs at A, so the job would fail on every merge of a Sheet
  pull request. Now a Sheet change counts as pending only when it is neither in the CSVs at `--since` nor in
  the current CSVs (cell by cell, three-way). A change that a pull request already carried is settled; the
  guard against losing a pending edit holds. Cost of the alternative (D4 as written): a red job after each
  Sheet pull request, and the Sheet is never rewritten from the merged CSVs. To get the literal D4 back,
  compare `changes(base, sheet)` in `cmd_push` instead of `pending(...)`.
- Row order counts as an edit only when the Sheet's order of the common slugs differs from both the old and
  the new CSV. Without `--since`, any order change counts.
- `diff` and the checks compare cells after the same normalisation on both sides (no trailing spaces), so a
  stray space is never a Sheet edit. `diff` adds a line when only the file format would change.
- An empty tab or a tab without data rows holds no edits (push fills it). `pull` refuses to write an empty
  tab over a CSV.
- `sheets-pull` closes the open `sheets-sync` pull request when the Sheet matches `main`; else a stale pull
  request would stay open. `sheets-push` takes the inputs `since` and `force` for manual runs; without them a
  manual run compares with the current CSVs.
- A pull request opened with `GITHUB_TOKEN` does not start `validate.yml`; that is why `sheets-pull` runs
  `validate.py` and `build.py` itself (D5). The job does not fail when they report errors: the errors go into
  the pull request text.

## 2026-10-18 — Network logos, link favicons, GitHub stats (brief `link-icons-github-stats.md`)

**Done**
- Drawer (`site/app.js`, `style.css`): a link to one of the 13 networks shows its logo, 18 px,
  inline SVG from Simple Icons 16.35.0 (CC0), `currentColor`. Each has `aria-label` and `title`
  with the network name; the global focus ring shows on it. Other links show their host's favicon
  (14 px) before the label; in dark mode the favicon sits on a white chip, because dark marks
  (GitHub) vanish on the dark background.
- `profile.py`: `link_icons()` fetches one favicon per non-network link host into
  `site/img/linkicon/<host>.webp` (32 px at most; skipped when the file exists, unless `--force`).
  `build.py` adds `icon` to a link when the file exists. `common.py`: `NETWORK_ROLES`, `ROLES`,
  `link_host()`, `parse_link()` (the role parsing of `build.links()` moved there).
- `profile.py` icon: `icon_candidates()` (declared icons, logo images in `header`/`nav`/`a[rel=home]`,
  root paths, two icon services) and `fetch_icon()` (first square candidate of 64 px or more, else
  the largest; a stored icon is replaced only by a larger one). `extras_one` now owns the icon step
  (`profile_one` no longer fetches it), so `--extra` upgrades small icons.
- GitHub stats in `extras_one`: new `profil.csv` columns `open_issues`, `commits`, `contributors`,
  `last_commit`, `license`, `language`. `build.py` writes `repo: {name, url, stars, forks, issues,
  commits, contributors, last, license, language, archived}` per item that has a repo. The drawer
  shows a "Cod" row under "Cod sursă".

**Measured**
- Full `--extra` run (116 entries): 151 GitHub requests; core limit 5000, 4912 left after it.
  Total for the session about 178 requests; 4895 left at the end. 0 rate-limit stops.
- 19 repos with stats (20 repos in `profil.csv`; the 20th, `rescue-4x4`, is an orphan row of a
  deleted entry). All 19 have stars, forks, open issues, commits, contributors, last commit and
  language; 13 have a licence (the others have none).
- Link favicons: 12 hosts, 12 stored, 0 failed.
- Icons under 64 px: 29 of 104 before, 22 of 106 after. 7 upgraded (crpe 16 to 99, efor 16 to 68,
  harta-firmelor 32 to 128, igov 48 to 128, ro-api-hub 32 to 128, romania-transparenta 48 to 128,
  tech-and-tonic 16 to 115); 2 new (onorata-instanta, calitate-aer-radauti, 128 px). The 22 left
  include 10 orphan files; factual stays at 32 px (its logo is an SVG) and code4ro at 48 px (its
  logo, 376 x 116, is a wordmark).
- Examples: ro-api-hub 2 stars, 1 fork, 0 issues, 27 commits, 1 contributor, last commit
  2026-09-24, MIT; redirectioneaza 26 stars, 27 forks, 20 issues, 1538 commits, 27 contributors,
  2026-10-04, MPL-2.0; sicap-ai 92 stars, 23 forks, 0 issues, 388 commits, 7 contributors,
  2026-09-25.
- `validate.py`: 0 errors. `build.py`: 117 entries.

**Hard**
- `profile.py --only factual,funky-citizens,ro-api-hub,code4ro` (asked in the brief) replaces whole
  rows: it dropped `mentions`, `mention_hosts`, `search_social` (restored by `search.py
  --prune-only`, no requests) and, because crt.sh answered 502, `cert_first` of factual and
  code4ro. A later `--extra --only factual,code4ro` restored it once crt.sh answered again.
- A code4ro-style wordmark (376 x 116) is a poor icon in a square slot, so `fetch_icon` ranks a
  candidate wider than 2:1 below any square one.

**Decided**
- Open issues without pull requests: `open_issues_count` minus the open pull requests (one core
  request with `per_page=1`, the page count from the `Link` header). The brief allowed the search
  API; it allows 30 requests a minute and the profiler already spends them on `github_find`. Cost
  of the alternative: about 2 minutes more per run, and a second source of rate-limit stops.
  With this, the UI says "issues" and never mixes in pull requests. When the pull request call
  fails, `open_issues` stays empty.
- Added to the "Cod" row beyond the brief's example: the language and "arhivat" (an archived repo),
  and the repository's name as a link when it is not the "Cod sursă" link above (code4ro links
  an organisation page; the stats are of `code4romania/code4.ro`). Cost: a longer row. Drop them
  in `repoRow()` if too long.
- The favicon of a host is not removed when a link goes away; files are keyed by host and may be
  shared by several entries.
- A failed GitHub call never writes a zero: the field keeps its old value. A rate limit sets a
  flag, skips every later GitHub call, and ends the run with a non-zero exit after the profile is
  saved.

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
