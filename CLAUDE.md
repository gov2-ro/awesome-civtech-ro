# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

CivTech România: a curated directory of Romanian civic-tech projects, resources and organisations, published as a static site. No framework, no package.json, no test suite. User-facing text (site UI, CONTRIBUTING.md, column names, taxonomy keys) is in Romanian; code and comments are in English.

## Commands

```sh
python3 scripts/validate.py                 # check proiecte.csv / orgs.csv (CI on every PR); extra args: more CSVs in proiecte format
python3 scripts/build.py                    # merge everything into site/data.json
python3 -m http.server -d site 8000         # preview at http://localhost:8000

uv run scripts/profile.py                   # profile entries missing from profil.csv (--force all, --only slug,slug, --no-shots)
uv run scripts/profile.py --extra           # age / activity / repo / Wayback / cert / Wikipedia signals (free)
uv run scripts/profile.py --search --opr --gdelt   # paid / keyed reach passes (SERPER_API_KEY, OPR_API_KEY)
uv run scripts/review.py --only slug,slug   # Claude Haiku review (ANTHROPIC_API_KEY); --dry-run prints the request, no API call
```

`validate.py` and `build.py` are stdlib-only and run with plain `python3` (CI uses 3.12). `profile.py` and `review.py` declare their dependencies inline (PEP 723 `# /// script` header) and must be run with `uv run`; both use Playwright for JS-rendered pages. There are no tests: after changing scripts, run `validate.py` then `build.py` (that is exactly what CI does).

## Data pipeline

```
data/proiecte.csv + data/orgs.csv  (human-edited)
        │  scripts/profile.py  → data/profil.csv (generated) + site/img/{og,icon}/
        │  scripts/review.py   → data/review/{raw.jsonl,sugestii.csv} (suggestions only, gitignored)
        ▼
scripts/build.py → site/data.json  →  site/app.js (vanilla JS, fetches data.json)
```

- **Human-edited source of truth**: `proiecte.csv` (`fel` = `proiect` | `resursa`), `orgs.csv`, and `taxonomy.json` (domenii, tipuri, acoperire, keyword `ignora`/`alias` rules, link roles with host lists). Columns are documented in CONTRIBUTING.md. CSVs must stay round-trippable through Google Sheets/Excel: UTF-8, comma-separated, list cells (`linkuri`) space/newline/`|`-separated or a JSON array, `tip` comma-separated with the main type first.
- **Never hand-edit generated files**: `data/profil.csv`, `site/data.json`, `site/img/`. `review.py` never writes `proiecte.csv` — a person accepts suggestions manually.
- `scripts/common.py` holds the shared loaders and the canonical column lists (`PROIECTE_COLS`, `ORGS_COLS`, `PROFIL_COLS`). Adding a column means updating it there (and in `validate.py` / `build.py` / CONTRIBUTING.md as relevant). `profil.csv` is flat except `social` (a JSON cell).
- `build.py` decides what the site shows: curated description vs. the site's meta description (`pick_desc`, filtering `BOILERPLATE`), link roles from `linkuri` + profiler-found socials, `status` (manual `stare` = `arhivat`/`offline` overrides the profiler, and a retired entry ignores what is live at its old URL), `since` / `stale`, and `score` (0–100: activity 30, reach 25, volume 15, longevity 15, documentation 15) used by the "Relevanță" sort.
- `site/app.js` keeps all UI state in URL query params (`DEFAULTS` / `FILTERS`; `p=<slug>` opens an entry), with a few per-browser prefs in localStorage.
- `data/curation.csv`, `data/international.csv`, `data/_OBSOLETE/` aren't read by any script; `international.csv` is the seed for a planned international mirror.

## Deployment

`.github/workflows/pages.yml` runs `validate.py` + `build.py` on push to `main` and publishes `site/` to GitHub Pages. `validate.yml` runs the same two steps on PRs touching `data/` or `scripts/`; `validate.py` emits GitHub annotations when `GITHUB_ACTIONS=true`.

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