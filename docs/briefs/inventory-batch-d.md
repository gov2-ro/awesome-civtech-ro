# Brief — variable inventory, batch D

Date: 2026-10-27. Baseline: commit `e1e8e1c`.
Status: ready for implementation.

## 1. Start here

Read `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md` (the batch C2 entries show the current practice).
Read `docs/briefs/inventory-batch-c2.md` (sections 4–8.1) and `docs/briefs/inventory-expansion.md` (section 5, the evidence contract; section 6.C, the discovery order). This brief reuses both.
Read the inventory sections of `docs/DATA-SCHEMA.md` and `data/taxonomy-v2/colectare-interzisa.csv`.

Copy this prompt into the implementation session:

> Implement `docs/briefs/inventory-batch-d.md`.
> Investigate the twelve entries with the discovery order of `inventory-expansion.md` section 6.C, inside the limits of section 4 of this brief.
> Keep the evidence contract. Propose variable groups, members and providers; do not decide them.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 6.

## 2. Goal

Twelve entries of `/date/lista/` „De analizat” get a field inventory. They were chosen for the strongest signals: an API, a data download, a linked repository, or a methodology or `llms.txt` page that the documentation pass found.

## 3. The batch

| Slug | URL | Signal |
| --- | --- | --- |
| `lista-firme` | https://lista-firme.info | An API (`format:api`) and the repository `tudorr89/info-firme`. |
| `dupa-cutremur` | https://sites.google.com/rerise.org/dupacutremur | A data set offered (`format:set-date`). |
| `reciclare-arad` | https://baditaflorin.github.io/calendar-ridicare-gunoi-arad/ | The repository `baditaflorin/calendar-ridicare-gunoi-arad`. |
| `onorata-instanta` | https://www.onoratainstanta.ro | The repository `funkycitizens/onoratainstanta`. |
| `sondaje-romania` | https://sondajeromania.ro/ | `llms.txt` and a methodology page. |
| `guvernezi` | https://www.guvernezi.ro/ | `llms.txt` and a methodology page. |
| `politicieni-corupti` | https://politicieni-corupti.ro/ | A methodology page. |
| `unde-locuiesc` | https://mariuscomper.uk/unde-locuiesc/ | `llms.txt`. |
| `trei-din-patru` | https://mariuscomper.uk/trei-din-patru/ | `llms.txt`. |
| `statul-digital` | https://mariuscomper.uk/statul-digital/ | `llms.txt`. |
| `pe-datorie` | https://mariuscomper.uk/pe-datorie/ | `llms.txt`. |
| `ce-face-statul-cu-1000-de-lei` | https://mariuscomper.uk/ce-face-statul-cu-1000-de-lei/ | `llms.txt`. |

Reserve entries, at most three, used only when a primary entry is blocked: `monitor-safe`, `igov`, `ce-fac-politicienii`. Record the reason before a replacement; a blocked entry stays in the report.
Five entries are on `mariuscomper.uk`. A source that two of them share is one source with two project uses.

Lot code: `D`.

## 4. Limits

- At most 120 direct HTTP requests in all, retries included, and at most 15 for each entry. At most two browser pages for each entry; report them separately.
- At most two concurrent requests for each host. At most ten new structured sources for each entry. Read bounded samples; do not download a full archive.
- A repository: read files at a recorded commit, through the existing readers. Do not clone a whole account.
- `lista-firme`: its API may need a key. Do not request a key and do not guess protected endpoints; record what the public documentation states.
- `onorata-instanta` and `politicieni-corupti` hold case data about persons. Record schemas, column names and aggregates; copy no individual record.
- Check `common.forbidden(url)` before each request (the tools do). If a host answers 401, 403 or 429, or its terms forbid automated access: stop on that host and record it. Propose a row for `colectare-interzisa.csv` in the report; do not add it.
- No paid search, no `review.py`, no message to project owners.

## 5. Work

1. `collect_docs.py --only <the twelve>` for documentation not yet collected.
2. Add the sources with `inventory.py --only …` and the existing readers. Write a new reader only when a source needs one, with an offline fixture test.
3. Map fields to the existing groups of `data/taxonomy-v2/inventar-concepte.json`. A reviewed group needs the owner's confirmation for a new member: list candidates in `inventar-note.json` (`selectori_candidati`) and the report. A new group is `propus`.
4. A new provider is a review item in `integrare/revizuire.csv` (`camp=surse_date`, the next free D number, after D188). Do not accept it.
5. Run `inventory_report.py`, `inventory.py --check`, `validate.py --publication`, the unit tests, the package checks, and a `--with-inventory` build into a separate `--site-dir` with the three browser checks.
6. Add the activity entry and the backlog items. No test may pin data that the owner edits (review states, counts of entries with a value).

## 6. Report

For each entry: sources found, sources parsed, field records, candidate members, proposed groups, proposed providers, blockers.
Also: requests made (from `jurnal-cereri.csv`), browser navigations, test counts before and after, commits, and what was measured and what was assumed.
