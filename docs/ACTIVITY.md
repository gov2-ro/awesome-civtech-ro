# Activity

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
