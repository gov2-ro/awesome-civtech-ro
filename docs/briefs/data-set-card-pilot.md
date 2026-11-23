# Brief — the data-set card: pilot cards for procurement and companies

Date: 2026-11-23. Status: ready (both conditions met on 2026-11-23: v0.86.0 and v0.86.1). The two conditions were:

1. [`data-set-card-build.md`](data-set-card-build.md) is merged (the file, the checks and the pages exist).
2. The owner has decided the `propus` `date_din` rows of the pilot entries (spec section 9, decision 3), or says to start without them.

Spec: [`docs/specs/data-set-card.md`](../specs/data-set-card.md) (accepted 2026-11-23). The spec wins over this brief.

## 1. Start here

Read these files first:

- `CLAUDE.md`, the spec (sections 2, 3, 4 and Appendix A) and the top entries of `docs/ACTIVITY.md`.
- `data/taxonomy-v2/integrare/fise-date.csv`, `relatii.csv` (rows `date_din`), `data/taxonomy-v2/furnizori.csv`.
- For each pilot entry: `data/taxonomy-v2/structura/recipes/<slug>.json` (when it exists), its sources in `observatii/inventare/seturi-date.json` and `descoperiri.json`, its fields in `campuri.csv`, the identifier groups of `inventar-concepte.json` (`selectors[].context`), and its documentation in `observatii/documentare/`.
- A built preview: `python3 scripts/build.py --with-inventory --site-dir <tmp>/site`, then `<tmp>/site/inventar/<slug>.json` and `/date/<slug>/`.

Copy this prompt into the implementation session:

> Implement `docs/briefs/data-set-card-pilot.md` on a branch `data-set-card-pilot`.
> Make no network request. Every row you write is `propus`. Never set `acceptat`.
> Stop and report if the evidence of an entry does not settle a data set. Finish with the report in section 4.

## 2. Goal

Write the first cards, all `propus`, so that the owner can accept them and the three usability tasks of the review can run on real cards.
The pilot also measures the cost of a card, which decides whether a proposal script is worth building (spec section 7, step 4).

Pilot entries, in this order (spec section 3):

1. With a structure recipe (10): `sicap-ai`, `achizitii-directe-ti-2026`, `banii-nostri`, `ce-cumpara-primaria`, `companii-de-stat`, `data-expertforum`, `igov`, `monitor-safe`, `registrul-firmelor`, `romania-transparenta`.
2. Without a recipe (5): `ce-face-statul-cu-1000-de-lei`, `harta-firmelor`, `pe-datorie`, `prima-cifra`, `statul-digital`.

## 3. Rules

1. One row for each data set that the entry's own evidence names. A document citit is not a data set (spec section 2): SICAP.ai's four folders under `es/` are data sets; its six files are not six cards.
2. Fill a column only from retained evidence. Leave it empty when the evidence does not say it. Never guess a period from field names or sample values.
3. `furnizor`: a provider with an accepted `date_din` relation of the entry. If the entry names a provider that has no relation, add a `date_din` row to `relatii.csv` (`propus`, `camp_sursa=surse_date`, the evidence URL in `valoare_sursa`) and, for a new name, a `furnizori.csv` row (`propus`). Report each one. The card row stays `propus` and `validate.py` warns until the owner accepts.
4. `romania-transparenta` has no `date_din` relation today. Propose its providers from its own documentation as in rule 3 (owner's decision 4, 2026-11-23).
5. `identificatori`: a role only when the evidence says it (a selector `context`, a recipe relationship, an API route such as `/v1/ac/{cif}` vs `/v1/supplier/{cif}`). A shared namespace without a role in the evidence: leave the identifier out and report it.
6. `variabile_cheie`: at most six, the ones that a visitor of that entry needs (the review: `Cod CPV` yes, `source_row` no). A derived value (`risk_score` of `achizitii-directe-ti-2026`) needs `nota_metoda` from the entry's own text; with no such text, leave the variable out and report it.
7. `baza`: `declarat` when the project or the provider states the card's content; `observat` when it comes from a recipe or a document citit; `editorial` when you combine several pieces of evidence. `dovada`: the URLs that a person opens to check the row.
8. `verificat_la`: the date of your reading. The owner sets it again when the owner accepts the row.
9. Do not decide any review item. Do not change `intrari.csv`.

## 4. Report

- A table: entry, cards written, and for each card the columns left empty.
- Totals: cards, entries with at least one card, the fill rate of each column. Compare with spec section 3.
- The time for each entry (start and end of its reading), and the median per card.
- The `date_din` and `furnizori.csv` rows that you added (rule 3 and 4).
- The cases that you could not settle (rules 1, 5, 6), with the evidence that you read.
- `validate.py --publication`: errors (expected 0) and warnings (list them).
- A `docs/ACTIVITY.md` entry; in `docs/BACKLOG.md`, the pilot line under review item 1, and an open item for the owner: accept the pilot cards.
- What you assumed and what you measured.
