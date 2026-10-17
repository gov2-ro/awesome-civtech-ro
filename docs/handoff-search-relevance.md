# Hand-off: search results → LLM-labelled relevance

Status as of 2026-10-18 (commit `5970e20`). Next step after this: run `scripts/review.py` (Claude Haiku) with search results folded in.

## Where things stand

Pipeline: `data/proiecte.csv` + `data/orgs.csv` (human-edited) → `scripts/profile.py` → `data/profil.csv` (generated) → `scripts/build.py` → `site/data.json`.

`profile.py` passes:
- default: liveness, metadata, og image, icon, screenshot; then the `--extra` signals for new entries
- `--extra` (free): Wayback first capture + months archived, last update (repo push, feed, WordPress, sitemap lastmod, Last-Modified), sitemap URL count, © year, Wikipedia links, GitHub repo (stars, forks, created, archived; found by homepage + name match when not linked), first TLS certificate (crt.sh), favicon fallbacks
- `--search` (Serper, paid): **only partly done**, see below
- `--opr`: Open PageRank, code ready, never run (needs `OPR_API_KEY`, free signup at openpagerank.com)
- `--gdelt`: code ready, no usable data. GDELT answered "please limit requests" even at 12 s spacing, and the queries that went through returned 0 even for factual.ro. Suggest dropping it.
- ROTLD WHOIS: deliberately not used. Their terms forbid automated queries.

`build.py` computes `since`, `stale` and `score` (0–100: activity 30, reach 25, volume 15, longevity 15, documentation 15). Reach already reads `mentions`, `opr` and `gdelt` from `profil.csv`.

`scripts/review.py`: one Haiku call per entry (current row + profiler data + homepage text/links + about/contact pages, JS pages rendered with Playwright). Structured JSON output, shared system prompt cached. Writes `data/review/raw.jsonl` and `data/review/sugestii.csv` (one row per changed field, for manual accept/reject). It never edits `proiecte.csv`. `--dry-run` prints the request. **Not yet run against the API**, because no Anthropic key was available (the one in `~/devbox/ePtm/puzzes/.env` is empty).

## What the search pass does today

`search_mentions()` in `scripts/profile.py`:
- Serper (Google), query `domain.ro -site:domain.ro`, unquoted (the free Serper tier rejects quoted phrases with a 400), 2 pages, `gl=ro hl=ro`
- keeps in `profil.csv`: `mentions` (distinct other hosts, minus social networks), `mention_hosts` (first 12), `search_social` (JSON: social profiles whose handle contains the domain label, length > 3)
- **throws away** result URLs, titles, snippets and dates, so nothing is left to prune or give to an LLM
- domain-rooted entries only (projects on a subpage of a bigger site are skipped)
- the mention count is noisy: company registries (listafirme, firmejust, listamarci), unrelated pages for generic names (the-sponge → calamitymod.wiki.gg)

API keys live in `~/devbox/ePtm/puzzes/.env`: `SERPER_API_KEY`, `BRAVE_API_KEY`, `CERAMIC_API_KEY`, `SERPAPI_API_KEY`. Load them with `set -a; source ~/devbox/ePtm/puzzes/.env; set +a`. Reference adapters: `~/devbox/ePtm/puzzes/puz/search_providers.py`. Prices from its `config.py`: Serper ~$1/1k, Brave ~$5/1k, Ceramic ~$0.25/1k, SerpApi ~$25/1k.

## Proposed next step

1. **Store full results** in a separate file, e.g. `data/search.jsonl`: one line per result with slug, provider, query, rank, url, title, snippet, date. Keep only the derived counts in `profil.csv`.
2. **Query by name as well as domain.** Many articles name a project without its URL ("Factual, proiectul Funky Citizens"). Name queries are ambiguous, which is exactly what the LLM step resolves. Something like `"<nume>" <autor>` or `<nume> <domeniu label>`; quotes need a paid Serper tier, or use Brave, which supports them.
3. **Providers:** Serper for the bulk; add Brave as a second index for its result dates (needed for "latest mention"). Skip SerpApi (price). Budget: ~110 entries × ~4 queries ≈ 440 queries, under $1.
4. **Rule-based pruning before any LLM:** drop the project's own host, social networks, company registries, app stores, link farms. Leave a manual pruning pass to the editor (they want to review results before the LLM sees them).
5. **The LLM labels each result; it doesn't score.** Fold the pruned results into the existing `review.py` call (~20–40 snippets, ~2k tokens extra). Per result, it returns:
   - `despre_proiect`: true/false
   - `tip_sursa`: news, research, government, NGO report, directory, social post, other
   - `independent`: true/false (not the project's or its authors' own channels)

   plus a one-line summary of how much attention the project gets. Extend the JSON schema in `review.py` accordingly.
6. **`build.py` aggregates the labels into features**, not an opaque LLM score: independent news mentions, research citations, government references, date of latest mention. Then reweight `reach` in `score()`. That keeps the ranking explainable and tunable.

## Watch out for

- Name collisions (Declic, Factual, the-sponge, Rescue 4x4): the LLM will confidently match unrelated results. Keep the manual pruning step.
- Serper free tier: no quoted phrases. Check the response for `"message"` (an error) and don't treat an error as zero results. The first full run made exactly that mistake.
- Path-based entries (`oradea.ro/subpagina/...`): domain-level queries describe the host, not the project. Skip them or query by URL/name.
- Some GitHub matches found by search are doubtful and need checking: `rescue-4x4` → `mihaituhari/rescue4x4-language`, `harta-banilor-publici` → `initiativaromania/HBP-Android`, `harta-tv-locale` → `geospatialorg/geospatialorg.github.io`.
- Up but showing no edit in 3+ years (candidates for `stare=arhivat`, the editor's call): pmb-plus, monitor-social, median-research-centre, calitate-aer-radauti, data-expertforum, onorata-instanta, parlament-transparent (archived repo).
