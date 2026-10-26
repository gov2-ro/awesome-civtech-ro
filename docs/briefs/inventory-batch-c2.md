# Brief — variable inventory, batch C2

Date: 2026-10-26. Baseline: commit `7bbfef2` (tag `v0.27.0`).
Status: ready for implementation.

## 1. Start here

Read `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md`.
Read `docs/briefs/inventory-expansion.md`, sections 5 (evidence contract) and 6.C (batch method). This brief reuses both.
Read the inventory sections of `docs/DATA-SCHEMA.md` and the list of forbidden hosts (`data/taxonomy-v2/colectare-interzisa.csv`).

Copy this prompt into the implementation session:

> Implement `docs/briefs/inventory-batch-c2.md`.
> Investigate the three entries with the method of `inventory-expansion.md` section 6.C, inside the limits of section 4 of this brief.
> Keep the evidence contract of `inventory-expansion.md` section 5.
> Propose variable groups and providers for the owner; do not decide them.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 6.

## 2. Goal

Three active projects that publish public-sector data get a field inventory.
Each inventory says which datasets the project uses or exposes, which fields they have, and where the evidence comes from.

## 3. The batch

The owner named six entries. Three are inactive in the public build (`status` `offline` or `arhivat`), and the owner removed every inactive entry from the variable inventory. They are not in this batch.

| Slug | URL | Starting question |
| --- | --- | --- |
| `data-expertforum` | https://data.expertforum.ro/ | Which data sets does the portal publish (format, period, geographic level), and which fields do they have? |
| `bani-partide` | https://banipartide.ro/ | Which records of party finance (donations, expenses, subsidies, loans) does the site show, and which provider supplies each one (AEP, the parties' reports in Monitorul Oficial)? |
| `romania-interactiva` | https://romaniainteractiva.ro/ | Which indicators do the charts show, with which unit, period and geographic level, and which provider is named for each one? |

Removed from the batch: `harta-banilor-publici`, `parlament-transparent`, `bani-pierduti`. Do not request their hosts.
`data-expertforum` and `bani-partide` belong to Expert Forum (`efor`). A data set that both use is one source with two project uses; do not count it twice.

Lot code: `C2` (column `investigat_in_lot` of `acoperire.csv`).

## 4. Limits

- At most 60 direct HTTP fetches in all, retries included. Report browser navigations separately: at most two pages for each entry.
- At most ten new structured sources for each entry. Read bounded samples; do not download a full archive.
- Check `common.forbidden(url)` before each request. The scripts already do this; a new request path must do it too.
- No paid search, no `review.py`, no message to the project owners.
- Party-finance records name private donors. Record the schema and the aggregates; do not copy individual donor records into the repository.
- If a source answers 401, 403 or 429, or its terms forbid automated access: stop on that host and record it. Propose a row for `colectare-interzisa.csv` in the report; do not add it yourself.

## 5. Work

1. Run `collect_docs.py --only data-expertforum,bani-partide,romania-interactiva` to find documentation, methodology and data pages.
2. Add the sources that you find with `inventory.py --only …`. Use the existing readers. Write a new reader only if a source needs one, and test it offline with a fixture.
3. Map the fields to the existing groups in `data/taxonomy-v2/inventar-concepte.json` (families: identifiers, geography, time, subject areas).
   Add a selector to an existing group only when the evidence supports the same meaning. A new group is a proposal with the state `propus`.
4. Put each new provider as a review item in `integrare/revizuire.csv` (`camp=surse_date`, the next free D number). Do not accept it.
5. Run `inventory_report.py`, `inventory.py --check`, `validate.py --publication`, the unit tests and a build with `--with-inventory` into a separate `--site-dir`.
6. Add the activity entry and flip the backlog items.

## 6. Report

For each entry: sources found, sources parsed, field records, fields in existing groups, proposed groups, proposed providers, blockers.
Also: requests made (from `jurnal-cereri.csv`), browser navigations, test counts before and after, and what was assumed and not measured.
