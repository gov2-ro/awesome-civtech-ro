# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

CivTech România: a curated directory of Romanian civic-tech projects, resources and organisations, published as a static site. No framework, no package.json; stdlib `unittest` files in `scripts/`. User-facing text (site UI, CONTRIBUTING.md, column names, taxonomy keys) is in Romanian; code and comments are in English.

## Commands

```sh
python3 scripts/validate.py                 # check the public root, the v2 integration copy (CI on every PR); --publication adds the gate; --data-dir data checks the frozen v1 CSVs
python3 scripts/build.py                    # merge everything into site/data.json (public root; applies the publication gate)
python3 -m http.server -d site 8000         # preview at http://localhost:8000

python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare      # taxonomy v2 root (draft rules; --publication adds the public gate)
python3 scripts/build.py --data-dir data/taxonomy-v2/integrare --site-dir /tmp/civtech-v2 --allow-draft   # isolated v2 preview
python3 scripts/test_taxonomy_v2.py         # v2 package, root selection and isolated-build tests (stdlib)
python3 scripts/test_enrichment.py          # enrichment stages on explicit data roots (offline)
python3 scripts/test_sheets_form.py         # sheets.py and form.py, offline (no Google, no credentials)
python3 scripts/review_ui.py [--port 8790]   # local review interface for provider items D132+ and the variable groups (127.0.0.1 only; writes revizuire.csv, relatii.csv, inventar-concepte.json; never commits)
python3 scripts/test_review_ui.py           # review_ui.py on temporary git copies of the data root (offline); uv run scripts/check_review_ui.py is its browser check
python3 scripts/test_forbidden_hosts.py     # the list of hosts that no script requests, and every request path that checks it (offline; 2 tests skip without httpx: uv run --offline --with httpx ...)
python3 -m unittest discover -s scripts -p "test_*.py" -v   # all unit tests (CI runs this)
uv run scripts/check_preview.py http://localhost:8765/   # browser checks of a served v2 preview (Playwright)
python3 data/taxonomy-v2/integrare.py       # check integrare/ against a fresh assembly; --write writes it
python3 data/taxonomy-v2/integrare.py --detach   # owner only, once: integrare/ becomes editable (CI then proves the detach commit) (done on 2026-10-21)
python3 scripts/cutover_v2.py --plan|--rehearse DIR   # applied on 2026-10-22: --plan now says so; --rehearse DIR reports "already applied"

uv run scripts/profile.py                   # profile entries missing from profil.csv (--force all, --only slug,slug, --no-shots)
uv run scripts/profile.py --extra           # age / activity / repo / Wayback / cert / Wikipedia signals (free)
uv run scripts/profile.py --opr             # Open PageRank (OPR_API_KEY)
uv run scripts/search.py --dry-run --only slug,slug   # print the search queries; no requests
uv run scripts/search.py                    # Serper + Brave (SERPER_API_KEY, BRAVE_API_KEY, paid): entries without rows in data/mentiuni.csv (--only, --force, --provider serper|brave|all)
uv run scripts/search.py --prune-only       # apply the prune rules to the stored rows and recompute mentions in profil.csv; no requests (profile.py keeps these columns since v0.7.0)
uv run scripts/profile.py --data-dir data/taxonomy-v2/integrare --only slug,slug   # v2 root; profile and search files in observatii/ (also search.py, review.py)
uv run scripts/review.py --only slug,slug   # Claude Haiku review + labels for the kept search results (ANTHROPIC_API_KEY); --dry-run prints the request, no API call
uv run scripts/sheets.py diff|pull|push   # Google Sheet <-> the public root (tab v2-intrari); --data-dir data for the frozen tabs proiecte/orgs (GOOGLE_APPLICATION_CREDENTIALS, SHEET_ID in .env); push refuses to overwrite unsynced Sheet edits
uv run scripts/sheets.py pull --check       # pull, then validate.py; exit 1 on errors
uv run scripts/sheets.py diff|pull|push --data-dir data/taxonomy-v2/integrare   # v2 tabs: v2-intrari, v2-revizuire
uv run scripts/form.py [--apply]            # the Form plan for the public root (v2: plan only, --apply refuses); --data-dir data for the v1 Form (FORM_ID)
uv run scripts/form.py --data-dir data/taxonomy-v2/integrare   # v2 questions; offline, no Google call
uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --import propuneri.csv   # v2: tab `propuneri` export -> intrari.csv rows (--out FILE)
```

`validate.py` and `build.py` are stdlib-only and run with plain `python3` (CI uses 3.12). `profile.py`, `search.py` and `review.py` declare their dependencies inline (PEP 723 `# /// script` header) and must be run with `uv run`; `profile.py` and `review.py` use Playwright for JS-rendered pages. After changing scripts, run `validate.py` then `build.py` (that is exactly what CI does). Three test files cover the scripts: `scripts/test_taxonomy_v2.py`, `scripts/test_enrichment.py` and `scripts/test_sheets_form.py`. `validate.yml` runs all of them, then the v2 package checks, the v2 preview build, the browser checks (`scripts/check_preview.py`) and actionlint.

## Data pipeline

```
Google Sheet (tab v2-intrari) ⇄ scripts/sheets.py (pull / push)
        │
data/taxonomy-v2/integrare/intrari.csv  (human-edited; v1: data/proiecte.csv + data/orgs.csv, frozen)
        │  scripts/profile.py  → data/taxonomy-v2/observatii/profil.csv (generated) + site/img/{og,icon,linkicon}/
        │  scripts/search.py   → observatii/mentiuni.csv (generated; the editor prunes in column `editor`)
        │                      → profil.csv: mentions, mention_hosts, search_social
        │  scripts/review.py   → observatii/review/{raw.jsonl,sugestii.csv} (suggestions only, gitignored)
        │                      → observatii/mentiuni_etichete.csv (labels of the kept results, generated)
        ▼
scripts/build.py → site/data.json  →  site/app.js (vanilla JS, fetches data.json)
```

- **Human-edited source of truth** (since the cutover of 2026-10-22): `data/taxonomy-v2/integrare/intrari.csv` (one row per entry: `tip_entitate`, `sectiune_url`, the facets `subiect_principal`, `subiecte`, `teme`, `scopuri`, `functionalitati`, `formate`, `tehnologii`, `institutii_vizate`, `maturitate`, `nivel_acoperire`, `arii_acoperite`, and `clasificare_stare`), the vocabulary files in `data/taxonomy-v2/` (`concepte.csv`, `arii.csv`, `valori.csv`, `roluri-linkuri.csv`, `gazde-linkuri.csv`) and the review queue `integrare/revizuire.csv`. Columns: `docs/DATA-SCHEMA.md`; the editor guide is `data/taxonomy-v2/README.md` (Romanian). The v1 files in `data/` (`proiecte.csv`, `orgs.csv`, `taxonomy.json`, `profil.csv`, `mentiuni.csv`) are frozen: no script reads them by default, and they stay for the rollback and for `--data-dir data`. Frozen v1 rules: `proiecte.csv` (`fel` = `proiect` | `resursa` | `articol` | `ghid` | `campanie` | `cercetare`; every `fel` but `proiect` lands on the "Resurse & liste" tab, mapped by `fel` in `taxonomy.json` → `common.FEL_KIND`), `orgs.csv`, and `taxonomy.json` (domenii, tipuri, acoperire, keyword `ignora`/`alias` rules, link roles with host lists). Columns are documented in `docs/DATA-SCHEMA.md` (all files) and CONTRIBUTING.md (for contributors, in Romanian). CSVs must stay round-trippable through Google Sheets/Excel: UTF-8, comma-separated, list cells (`linkuri`) space/newline/`|`-separated or a JSON array, `tip` comma-separated with the main type first.
- **Never hand-edit generated files**: `site/feed.xml`, `site/llms.txt`, `data/taxonomy-v2/observatii/profil.csv`, `observatii/mentiuni_etichete.csv`, `site/data.json`, `site/proiect/`, `site/organizatie/`, `site/resursa/` (entry pages and the three archive `index.html` files), `site/img/`. The one exception is the column `editor` in `observatii/mentiuni.csv` (empty, `1` keep, `0` drop); `search.py` keeps it on every rewrite. `review.py` never writes `intrari.csv` — a person accepts suggestions manually.
- **Hosts that forbid automated access**: `data/taxonomy-v2/colectare-interzisa.csv` (hand-edited: `gazda`, `motiv`, `dovada`, `data`, `nota`; a host covers its subdomains). `common.forbidden(url)` is the one check. `profile.py`, `review.py`, `collect_docs.py`, `inventory.py` and `render_pages.py` call it before every request and for each redirect. A listed host gets no request. The state is `colectare-interzisa` with the `motiv`; it is never an error, a failed attempt or `offline`. `validate.py` checks the file. A new request path in a script must call the check too. Details: `docs/DATA-SCHEMA.md` (colectare-interzisa.csv).
- **Review interface** (`scripts/review_ui.py`, local, never published): the provider items (`revizuire.csv` `camp=surse_date`, D132+) and the 30 groups of `data/taxonomy-v2/inventar-concepte.json`. It writes `revizuire.csv`, `relatii.csv` and the review keys of the dictionary (`stare`, `decizie_editor`, `data_revizie` on a group; `stare`, `nota_editor` on a selector; a missing key means `propus`), atomically and byte-stable, and never commits: git is the audit trail. Never decide a review item for the owner; use temporary copies of the data root for tests and demonstrations. Details: `docs/DATA-SCHEMA.md` (Local review interface).
- `scripts/common.py` holds the shared loaders and the canonical column lists (`PROIECTE_COLS`, `ORGS_COLS`, `PROFIL_COLS`). Adding a column means updating it there (and in `validate.py` / `build.py` / `docs/DATA-SCHEMA.md` / CONTRIBUTING.md as relevant). `profil.csv` is flat except `social` (a JSON cell).
- `build.py` decides what the site shows: curated description vs. the site's meta description (`pick_desc`, filtering `BOILERPLATE`), link roles from `linkuri` + profiler-found socials, `status` (manual `stare` = `arhivat`/`offline` overrides the profiler; a profiler `offline` with no Wayback capture for over a year shows as `arhivat`; and a retired entry ignores what is live at its old URL), `since` / `stale`, and `score` (0–100: activity 30, reach 25, volume 15, longevity 15, documentation 15) used by the "Relevanță" sort.
- `site/app.js` keeps all UI state in URL query params (`DEFAULTS` / `FILTERS`), with a few per-browser prefs in localStorage. An open entry lives in the path, `/<kind>/<slug>/` with kind `proiect`, `organizatie` or `resursa` (the old `?p=<slug>` still works). `build.py` writes one page per entry to `site/<kind>/<slug>/` from `site/index.html` (git ignores them; the Pages workflow builds them), so preview with `build.py` first. A new `href`, `src` or `fetch` in `site/index.html` or `app.js` must resolve from that path: the pages carry `<base href="../../">`, and `app.js` prefixes data paths with `ROOT`. `build.py` rewrites the `?v=<hash>` on the `style.css` and `app.js` links in `site/index.html` (Cloudflare caches those two files for hours), so commit `index.html` after a CSS or JS change. `data/taxonomy-v2/setari.json` (report-a-problem addresses and the gid of the Sheet tab) is hand-edited.
- `data/curation.csv`, `data/international.csv`, `data/_OBSOLETE/` aren't read by any script; `international.csv` is the seed for a planned international mirror.
- **Taxonomy v2 (the public model since the cutover of 2026-10-22)**: `data/taxonomy-v2/` is the draft.2 package; `integrare/` is the editable integration copy (detached from the sealed run on 2026-10-21). `scripts/taxonomy_v2.py` loads and checks it. `common.PUBLIC_ROOT` is `data/taxonomy-v2/integrare`: the default root of every script, and the only root that may write `site/`. `site/app.js` is the v2 browser code (`site-v2/` is gone). `--data-dir data` selects the frozen v1 root; `--site-dir` keeps a build out of `site/`. All 140 entries are `acceptat`, in bulk and not one by one. Never write into `data/taxonomy-v2/source/`, `reference/` or `runs/`.

## Deployment

`.github/workflows/pages.yml` runs `validate.py --publication` + `build.py --with-inventory` (the data finder `/date/` is public since 2026-10-26) on push to `main` and publishes `site/` to GitHub Pages. `sheets-pull.yml` (every 6 h) opens or updates a PR from branch `sheets-sync` with the Sheet's edits. If `validate.py` or `build.py` fails, it still opens the PR, sets the commit status `validate / sheets-pull` to failure, and then fails. `sheets-push.yml` rewrites the tab `v2-intrari` after a push to `main` that touches `intrari.csv`; `sheets.py push` compares the Sheet with the commit in its `_sync` tab (the last successful push) and writes that marker last. `validate.yml` runs on PRs and pushes to `main` that touch `data/`, `scripts/`, `site/` or `.github/workflows/`; `validate.py` emits GitHub annotations when `GITHUB_ACTIONS=true`.

## Notes

- `.gitignore` ignores `/data/*` except `*.csv` and a few listed subfolders; a new non-CSV file under `data/` (e.g. a `.jsonl`) needs a `.gitignore` exception or `git add -f`.
- API keys for the search/review passes are kept outside the repo; `docs/handoff-search-relevance.md` (if present) records where, plus the current state of the search → LLM-relevance work and known pitfalls (Serper free tier rejects quoted queries and returns errors that must not be counted as zero results; ROTLD WHOIS terms forbid automated queries; name collisions in search results).

## Tone of voice

Follow Simplified Technical English (ASD-STE100) for docs, error messages and agent-facing
text:

- One instruction per sentence; at most ~20 words (procedures), ~25 (descriptive).
- Active voice; name the actor.
- Simple tenses.
- One word, one meaning; the same term every time.
- No noun clusters over three words; keep the articles.
- Keep every condition and qualifier.

## Process notes

Two files carry the project's memory between sessions. Create each one with the first work
that needs it, and read both before starting.

**`docs/BACKLOG.md`** — roadmap, tasks, bugs. Statuses: `[ ]` open, `[~]` in progress, `[x]`
done, `[-]` dropped.
- Flip an item to `[x]` in the same change that finishes it.
- Add a defect or deferred work when you find it.
- Mark a dead end `[-]` **with the reason**, under *Verified limits*, so that nobody
  investigates it again.

**`docs/ACTIVITY.md`** — dated entries, newest first, each with **Done / Hard / Decided**.
- Add an entry when a chunk of work lands.
- A decision carries its rationale and the cost of the alternative.
- Record wrong turns, and say what was measured and what was assumed. Keep the measured
  numbers: they are the baseline for regressions.

**Versions follow the work.** The project is spec-driven, so a spec, an ADR, a decision that
changes a spec, a set of named tests, and a measured spike are deliverables, as much as a
user capability is. After each committed chunk, check what changed since the last tag. For a
relevant deliverable, bump the minor version; for a correction only, bump the patch. Set the
workspace version in `Cargo.toml`, add a line to `docs/RELEASES.md`, commit, and tag the
commit. Do this without asking, and say when you did. **Publishing a release is separate,
and happens only when asked.**


## Opus designs, Sonnet builds

The work splits by model. **When you are Opus**, defer implementation and well-defined
future work to Sonnet by default:

- **Opus** writes specs, ADRs and briefs; makes and records decisions; and reviews Sonnet's
  results against the brief before they are accepted.
- **Sonnet** carries out a brief: code, spikes, measurements, fixture changes, and the
  activity and backlog entries for that work.
- **Opus does the work itself** when the task is a few lines, or when the design is still
  moving and the doing is part of the deciding.

**Sonnet stops and asks** when a step would change a spec, an ADR, an invariant or a
dependency outside the brief's folder. It reports what it measured and what it assumed.

To hand over, Opus tells the owner that the brief is ready. The owner runs it in a Sonnet
session, or asks Opus to start a Sonnet agent on it.