# Brief — variable inventory, batch E

Date: 2026-10-27. Baseline: commit `f8d2546`.
Status: ready for implementation.

## 1. Start here

Read these files first:

- `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md`. The batch D entries and the entries after them show the current practice.
- `docs/briefs/inventory-batch-d.md`. This brief keeps its rules unless it says otherwise.
- `docs/briefs/inventory-expansion.md`: section 5 (the evidence contract) and section 6.C (the discovery order).
- `docs/briefs/inventory-readers-persons.md` (the mark `persoane`).
- The inventory sections of `docs/DATA-SCHEMA.md`, and `data/taxonomy-v2/colectare-interzisa.csv`.

Copy this prompt into the implementation session:

> Implement `docs/briefs/inventory-batch-e.md`.
> Investigate the twelve entries with the discovery order of `inventory-expansion.md` section 6.C, inside the limits of section 4 of this brief.
> Keep the evidence contract. Propose variable groups, members and providers; do not decide them.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 6.

## 2. Goal

Twelve more entries of `/date/lista/` „De analizat” get a field inventory. Each has the relation `date-publice`, `date-proprii` or `calcul`.
The choice prefers these signals, in this order:

1. A methodology or `llms.txt` page that the documentation pass found.
2. A public repository or a static host (GitHub Pages, Vercel) whose data files a page loads.
3. A registry or a visualisation of public data (budgets, procurement).

## 3. The batch

| Slug | URL | Signal |
| --- | --- | --- |
| `monitor-safe` | https://monitorsafe.ro/ | `llms.txt` and a methodology page; the SAFE programme funds. |
| `igov` | https://igov.ro/ | A methodology page; reports from public sources. |
| `companii-publice-ro` | https://cosettechichirau.github.io/companiipublice/ | A GitHub Pages site. The repository is probably `cosettechichirau/companiipublice`. |
| `executii-bugetare` | https://executii-bugetare.g4d.ro/ | The budget execution of local authorities. |
| `ce-cumpara-primaria` | https://cecumparaprimaria.vercel.app/ | A Vercel site; the procurement of town halls. |
| `sicap-ai` | https://sicap.ai/ | A search engine for tenders and direct awards. |
| `open-budget` | https://www.openbudget.ro | A budget visualisation. |
| `monitor-social` | http://monitorsocial.ro/ | Social data about Romania. |
| `verifica-psiholog` | https://www.verificapsiholog.ro/ | A methodology page; a register of psychologists. |
| `portal-just-modern` | https://portaljustmodern.ro/ | `llms.txt`; a search of court files and hearings. |
| `cat-de-tare` | https://mariuscomper.uk/cat-de-tare/ | A methodology page; seismic hazard values for 3,181 localities. |
| `recontorizarea` | https://mariuscomper.uk/recontorizarea/ | A methodology page; the consumer basket. |

Use a reserve entry only when a primary entry is blocked. The reserves, in order, are `de-unde-vine-apa`, `ani-de-pensie` and `ai-aflat`. You may use at most three. Record the reason before a replacement, and keep the blocked entry in the report.

Two entries are on `mariuscomper.uk`, as are five entries of lot D. A source that entries share is one source with several project uses.

The lot code is `E`.

## 4. Limits

- **Requests:** at most 120 direct HTTP requests in all, retries included, and at most 15 for each entry. At most two browser pages for each entry; report them separately.
- **Hosts:** at most two concurrent requests for each host.
- **Sources:** at most ten new structured sources for each entry. Read bounded samples; do not download a full archive.
- **Repositories:** read files at a recorded commit, through the existing readers. Do not clone a whole account.
- **Keys:** do not request a key. Do not guess protected endpoints. Record what the public documentation states.
- **Blocked hosts:** check `common.forbidden(url)` before each request (the tools do).
  - If a host answers 401, 403 or 429, stop on that host and record it.
  - If its terms forbid automated access, stop on that host and record it.
  - Propose a row for `colectare-interzisa.csv` in the report. Do not add it.
- **Person data:** `portal-just-modern` holds court files about persons, and `verifica-psiholog` lists named professionals.
  - Record schemas, column names and aggregates only. Copy no individual record.
  - The owner's rule is „start open, limit when a need shows”. So mark a source `persoane` only when its body holds records about private persons, and a value would otherwise reach a tracked file.
  - Render a page that lists persons with `render_pages.py --fara-text`.
  - Report each mark that you set.
- **Out of scope:** no paid search, no `review.py`, and no message to project owners.

## 5. Work

1. Run `collect_docs.py --only <the twelve>` for documentation that is not collected yet.
2. Add the sources with `inventory.py --only …` and the existing readers. Put the specifications in `observatii/inventare/adaugari/lot-e*.json`. Write a new reader only when a source needs one, with an offline fixture test.
3. Map fields to the groups of `data/taxonomy-v2/inventar-concepte.json`. Every group there is `revizuit`:
   - A new member is a candidate. List it in `inventar-note.json` (`selectori_candidati`) and in the report.
   - A new group is `propus`.
4. A new provider is a review item in `integrare/revizuire.csv`, with `camp=surse_date` and the next free D number, after D210. Do not accept it.
5. Run these checks:
   - `inventory_report.py`, `inventory.py --check` (with the persons check) and `validate.py --publication`;
   - the full unit suite (927 tests and 6 skipped before);
   - the three package checks;
   - a `--with-inventory` build into a separate `--site-dir`, with the three browser checks. The new `/date/<slug>/` pages of the twelve entries must exist.
6. Add the activity entry and the backlog items. No test may pin data that the owner edits, such as review states or counts of entries with a value.

## 6. Report

For each entry, give these items:

- sources found and sources parsed;
- field records;
- candidate members, proposed groups and proposed providers;
- `persoane` marks;
- blockers.

Also give these items:

- requests made (from `jurnal-cereri.csv`) and browser navigations;
- test counts before and after, and the commits;
- what you measured and what you assumed;
- the decisions that the owner must make.
