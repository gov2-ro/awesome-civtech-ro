# Spec: search mentions → labelled relevance

Status: accepted 2026-10-18. Source: `docs/handoff-search-relevance.md`.
Brief for the build: `docs/briefs/search-relevance.md`.

## Goal

The "Relevanță" sort must rank by independent attention (news, research,
government references), not by a raw count of hosts that contain the domain.
Every number in `reach` must trace back to rows that a person can inspect.

## Flow

```
proiecte.csv + orgs.csv
   │ scripts/search.py      → data/mentiuni.csv  (results + rule verdict + editor column)
   │                        → profil.csv: mentions, mention_hosts, search_social
   │ (editor prunes in data/mentiuni.csv, column `editor`)
   │ scripts/review.py      → data/review/*            (suggestions, as today)
   │                        → data/mentiuni_etichete.csv (labels, generated)
   ▼
scripts/build.py → reads both CSVs → reach features → score
```

## Decisions

**D1. A new script, `scripts/search.py`, owns all search queries.**
`profile.py` loses `--search` and `--gdelt`. Rationale: `profile.py` is
already 690 lines, and search now has its own output file and rerun rules.
Cost of the alternative: one more mode in `profile.py` that writes two files
with different merge rules.

**D2. Drop GDELT.** It rate-limited at 12 s spacing and returned 0 for
factual.ro. Remove the `gdelt` column from `PROFIL_COLS` and from `score()`.
Cost: none measured; no row has a non-zero value.

**D3. Results go to `data/mentiuni.csv`, tracked in git.** One row per
(slug, url). The file is generated, except for the column `editor`, which a
person edits. `search.py` keeps the `editor` value when it rewrites a row
with the same (slug, url). Rationale: the pruning decisions are editorial
work and must survive reruns and reach CI. A CSV at `data/` top level is
tracked by the current `.gitignore`. Cost of the alternative (JSONL under
`data/search/`): a `.gitignore` exception, and the file does not open in
Sheets.

Columns: `slug, provider, query, rank, url, host, title, snippet, date,
regula, editor, fetched_at`.
- `regula`: the name of the rule that drops the row (`propriu`, `social`,
  `registru`, `magazin`, `ferma`, …), or empty when the row passes.
- `editor`: empty, `1` (keep, overrides `regula`) or `0` (drop).
- A row is **kept** when `editor == "1"`, or when `editor` is empty and
  `regula` is empty.

**D4. Queries per entry (at most 4 requests).**
1. Serper `dom -site:dom`, 2 pages. Domain-rooted entries only (as today).
2. Serper `<nume> <autor>`, unquoted, 1 page. All entries.
3. Brave `"<nume>"` plus `<autor>` when present, 20 results. All entries.
   Brave gives result dates; Serper often does not.
Skip query 2 and 3 when `nume` is the domain itself (e.g. `465.ro`): query
1 covers it. An error response (`message` key in Serper, non-200 in Brave)
is an error, never zero results. A failed query leaves the slug's earlier
rows untouched.
Budget: ~110 entries → ~220 Serper + ~110 Brave requests ≈ $0.80.

**D5. Rule-based pruning only marks rows; it never deletes them.** The
editor sees every result and the reason.

**D6. The LLM labels; it does not score.** `review.py` adds the kept rows
(at most 40 per entry, highest rank first) to the existing request. Per
result it returns `id`, `despre_proiect` (bool), `tip_sursa` (enum: `stire`,
`cercetare`, `guvern`, `raport_ong`, `director`, `social`, `altul`),
`independent` (bool). Per entry it returns `atentie`: one Romanian sentence
on how much attention the project gets. Labels go to
`data/mentiuni_etichete.csv` (`slug, url, despre_proiect, tip_sursa,
independent, model, labelled_at`), generated, tracked, never hand-edited.
`atentie` stays in `raw.jsonl` only.

**D7. `build.py` aggregates labels into named features.** For each slug,
counting distinct hosts among kept rows where `despre_proiect` and
`independent` are true:
- `indep`: all such hosts
- `stiri`: `tip_sursa == stire`
- `cercetare`: `tip_sursa == cercetare`
- `guvern`: `tip_sursa == guvern`
- `ultima`: newest `date` of such a row

New `reach` (weights sum to 1.0):
`.30 archive_months/120 + .20 indep/15 + .10 stiri/10 + .05 (cercetare+guvern)/5 + .15 opr/6 + .10 wiki_refs/20 + .10 stars/200`
(log-scaled as today, except `opr`). A slug without labels falls back to
the kept-host count from `mentiuni.csv` in place of `indep`, and 0 for the
others. `data.json` gets `reach: {indep, stiri, cercetare, guvern, ultima}`
per item, so the UI can explain the score later.

## Accepted at review (2026-10-18)

The build added these; Opus accepted them against D3–D5:
- Extra rules `cod` (code hosts) and `zgomot` (dictionaries, job boards, media databases).
- `propriu` also covers the author's own sites (`orgs.csv` match, author written as a domain,
  `AUTOR_SITES`). The first run showed funky.ong (77 rows) and code4.ro (38) as top hosts.
- A failed query leaves all rows of that entry unchanged, and the run exits 1.
- Rows with an `editor` value survive a rewrite, even when the search no longer returns them.
- `search_social` reads every row except `editor = 0`, because the `social` rule drops the
  profile pages it looks for.
- Until labels exist, `indep` is the kept-host count. Noise from name collisions counts as
  reach, so the ranking stays provisional until the first labelled run.

## Out of scope

- UI changes in `site/app.js` (see backlog).
- Open PageRank run (needs `OPR_API_KEY`).
- The editor's own pruning pass and acceptance of review suggestions.
