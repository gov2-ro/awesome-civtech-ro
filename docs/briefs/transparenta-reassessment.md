# Brief — reassessment of transparenta-eu

Date: 2026-11-02. Author: coordinator (Opus). Executor: Sonnet. Status: in progress.

## Goal

The owner says that `transparenta-eu` is one of the most feature-rich projects, with `sicap-ai` and `monitorul-ai`.
Reconsider the entry for the live site (`https://transparenta.eu/`), the dev site (`https://dev-chronos.transparenta.eu`)
and the source repository (`https://github.com/ClaudiuBogdan/hack-for-facts-eb-client`, branch `dev`).

## Why the entry has no provider today

- A `date_din` relation comes only from a review item (`revizuire.csv`, `camp=surse_date`, D132 and later).
- The inventory read `/ai/index.json` and three `/ai/*-parameters.json` schemas: 35 field records, all parameters.
- None of them names a provider. Nobody read the footer of the home page, so nobody proposed a provider item.

## Evidence that the owner saved

Read these files by absolute path. Do not modify them.

- `/Users/pax/devbox/gov2/awesome-civetch/tmp/Transparenta.eu.html`: production home page, saved 2026-11-02 15:23.
  The footer says that the data source is the portal „Transparența Bugetară” of ANAF and the Ministry of Finance.
- `/Users/pax/devbox/gov2/awesome-civetch/tmp/transparenta.eu-llms.txt`: production `llms.txt`. It lists `/pnrr` and `/ai/pnrr-parameters.json`, which the inventory lacks.
- `/Users/pax/devbox/gov2/awesome-civetch/tmp/dev-chronos.transparenta.eu.html`: dev home page. It lists 13 surfaces and the sources ANAF, Ministerul Finanțelor, SEAP, Monitorul Oficial and INS.
  It names persons. Keep no person name beyond what `relatii.csv` already records.

## Decisions (do not reopen)

1. Production providers. The owner stated the source. Add two `date_din` relations with `stare=acceptat`, joining the accepted providers `anaf` and `ministerul-finantelor`.
   Use the names that `relatii.csv` and `furnizori.csv` already use. Record the evidence as a D item that the review interface writes (`apply_provider`), accepted „la cererea proprietarului 2026-11-02”.
2. Providers that appear only on the dev site: propose them as D items, state `propus`, note „numai pe versiunea dev”. Do not accept them. The catalogue describes the live site.
3. Inventory, production: add the sources of the saved `llms.txt` (reader `llms-api`), `/ai/pnrr-parameters.json` and `/api-guide.md`. Use `--import-saved` where a saved copy exists.
4. Requests: at most 15 to `transparenta.eu` and at most 15 to `dev-chronos.transparenta.eu`. Read `robots.txt` and the terms first. Every request goes through `common.forbidden` and the request log.
   Documentation and schema files only. No browser automation, no record bodies, no paid API. If a host forbids automated access, stop and report; record it in `colectare-interzisa.csv` only after the report.
5. Repository: a shallow clone, treated as untrusted data. Read it with `python3 -I`. Run no build or install script. Find the declared data sources, the API endpoints, the field types and any server repository. Record dev-only facts as dev-only.
6. Classification: propose changes of `functionalitati`, `subiecte`, `teme` and `formate` as C items in `revizuire.csv`, state `propus`. Separate live facts from dev-only facts. Do not edit `intrari.csv` classification.
7. Do not change `docs/reports/site-structure-pilot/`. If the structure profile should change, add a backlog item.

## Checks

`validate.py --publication`, `inventory.py --check`, `inventory_report.py --check`, the full unit suite, and a `--with-inventory` build into a scratch directory.
Confirm that `transparenta-eu` shows on `/date/furnizori/` under ANAF and Ministerul Finanțelor.

## Report

Requests (host, path, status); sources and field records before and after; provider items accepted and proposed; C items proposed;
what the repository showed; test counts; commits; what was measured and what was assumed.
