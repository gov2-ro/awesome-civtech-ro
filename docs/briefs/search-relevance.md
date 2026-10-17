# Brief: search mentions → labelled relevance

Owner model: Sonnet. Spec: `docs/specs/search-relevance.md` (read it first;
decisions D1–D7 are fixed). Background: `docs/handoff-search-relevance.md`.

## Rules

- Stay inside `scripts/`, `data/` (generated files only), `CONTRIBUTING.md`,
  `CLAUDE.md` (commands section), `docs/BACKLOG.md`, `docs/ACTIVITY.md`.
- Never edit `proiecte.csv` or `orgs.csv`.
- Stop and ask when a step would change a decision in the spec, or add a
  dependency beyond `httpx`, `selectolax`, `anthropic`.
- Match the existing code style: compact, type hints, short comments that
  say why.
- Do not commit. Report what changed.

## Tasks

1. **`scripts/search.py`** (PEP 723 header, `uv run`). Flags: `--only`,
   `--force` (requery slugs that already have rows), `--provider serper|brave|all`,
   `--dry-run` (print the queries, no requests), `--prune-only` (reapply rules
   to existing rows, no requests). Move `search_mentions()` logic, `SKIP_MENTION`
   and the `search_social` extraction out of `profile.py`. Reuse the Brave
   adapter shape from `~/devbox/ePtm/puzzes/puz/search_providers.py`.
   Write `data/mentiuni.csv` per D3 (keep `editor` on rewrite). After the
   write, recompute `mentions`, `mention_hosts`, `search_social` in
   `profil.csv` from kept rows.
2. **Prune rules** (D5), a list of `(name, regex on host or url)` near the
   top of `search.py`: `propriu` (entry's own domain and its `linkuri`
   hosts), `social`, `registru` (listafirme, firmejust, listamarci, termene,
   risco, …), `magazin` (app stores), `ferma` (link farms; start with what the
   first run shows). Then `--prune-only` and list the 20 most frequent kept
   hosts in the report, so the editor can extend the rules.
3. **`profile.py`**: remove `--search`, `--gdelt`, `gdelt()`; remove `gdelt`
   from `PROFIL_COLS` (`common.py`) and from `score()`.
4. **`review.py`** (D6): add kept results to `entry_message` as
   `mentiuni: [{id, url, titlu, fragment, data}]`; extend `schema()` and
   `SYSTEM` (keep the tone of the existing prompt; warn about name
   collisions: when unsure, `despre_proiect: false`). Write
   `data/mentiuni_etichete.csv`. Check with `--dry-run --only factual,declic`.
5. **`build.py`** (D7): load both CSVs, compute features, new `reach`, add
   `reach` object to each item.
6. **Docs**: CONTRIBUTING.md (the `editor` column: what `1` / `0` mean),
   CLAUDE.md command list and pipeline diagram.
7. **Run**, in this order:
   - `uv run scripts/search.py --dry-run --only factual,declic,465`
   - A pilot: `--only factual,declic,465,the-sponge,rescue-4x4`. Load keys
     with `set -a; source ~/devbox/ePtm/puzzes/.env; set +a`. If the keys
     are not reachable, stop here and report.
   - Inspect the pilot rows. Then the full run.
   - `python3 scripts/validate.py && python3 scripts/build.py`.
   - `review.py` against the API only if `ANTHROPIC_API_KEY` is set;
     otherwise the dry run is the end of task 4.
8. **Record**: `docs/ACTIVITY.md` entry (Done / Hard / Decided), with the
   measured numbers: requests per provider, cost, rows total, rows kept,
   rows per rule, top-score changes (old vs new top 10 by `score`). Flip
   the backlog items you finish.

## Acceptance (Opus checks these)

- `validate.py` and `build.py` pass; `data.json` items carry `reach`.
- Rerunning `search.py --prune-only` after setting some `editor` cells keeps
  those cells.
- No Serper/Brave error counted as zero results (the log shows errors).
- Path-based entries get name queries only.
- Score diff for the top 10 is in the activity entry.
