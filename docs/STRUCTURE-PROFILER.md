# Site structure profiler

The structure profiler discovers page patterns, API declarations and identifier candidates.
It runs separately from the site-health profiler and never changes the public catalogue.
The [spec](specs/site-structure-profiler.md#8-engine-contract-version-2--2026-10-30) defines the version-2 contract.
The [engine report](reports/site-structure-engine.md) records the first delivery and its measurements.

## Start with retained evidence

Use an isolated output directory. Every run requires an explicit selection or import.
There is no implicit whole-catalogue pass.

```sh
# Import the checked pilot observations, without making requests.
python3 scripts/profile_structure.py --out /tmp/structure --seed-pilot docs/reports/site-structure-pilot

# Replay existing documentation snapshots. This also makes no requests.
python3 scripts/profile_structure.py --out /tmp/structure --only transparenta-eu,sicap-ai --offline

# Check artifacts, references, accounting and the generated request export offline.
python3 scripts/profile_structure.py --out /tmp/structure --check
```

A fresh checkout may lack the ignored documentation snapshots.
An offline pass then records that gap and keeps earlier findings.
It does not refetch missing snapshots or erase their earlier interpretations.
Repeated pilot imports preserve existing live findings and do not copy the pilot's editorial decisions.

## Run bounded discovery

```sh
python3 scripts/profile_structure.py --out /tmp/structure \
  --only transparenta-eu,romania-transparenta \
  --max-requests 20 --total-requests 40
```

The default limits are 20 requests per project and 100 per invocation.
Robots requests, redirects and failed dispatches count toward those limits.
The engine waits at least one second per host and uses a 20-second request timeout.
Responses have a 2 MiB cap. A truncated document cannot establish complete structure.
The runner fetches at most three sitemap documents per project and samples at most 200 URLs per document.
It retains at most three examples per inferred numeric path pattern.
An inferred `{id}` has no shared identifier namespace.

Discovery uses the project page, scoped/root `llms.txt`, linked methodology/data pages, sitemap declarations and linked API contracts.
The parser reads OpenAPI JSON and the existing strict YAML subset.
It records all declared HTTP methods but never invokes mutating operations.
The first engine does not launch browsers, run paid search, crawl repositories or execute GraphQL requests.
Its checks retain those limits. A successful bounded pass can therefore remain partial.

`common.forbidden` protects each request and redirect.
Robots rules protect the target host's paths, including a separate API host.
A robots transport failure does not grant access to other paths.
401, 403, 429 and challenge pages stop that host across projects in the same invocation.
No retry or client switch bypasses a host stop.

## Import saved documentation

```sh
python3 scripts/profile_structure.py --out /tmp/structure \
  --import-saved sicap-ai https://api.sicap.ai/v1/openapi /path/to/saved-contract.yaml \
  --saved-at 2026-10-27T21:24:00+02:00
```

The import reads a UTF-8 file of at most 2 MiB and makes no request.
The save time must have a timezone and cannot be in the future.
The evidence keeps the original save time and a separate import time.
Use this path for blocked hosts. Importing a document does not authorize live collection.

## Probe a known GET operation

```sh
python3 scripts/profile_structure.py --out /tmp/structure \
  --only romania-transparenta --max-requests 14 --total-requests 14 \
  --probe romania-transparenta 'https://api.romaniatransparenta.eu/v1/companii?limit=1'
```

The probe URL must match a previously imported or discovered GET operation.
Required query arguments must be present. Declared authentication requirements cause a skip.
The engine supplies no API keys, cookies or authentication headers.
The probe still obeys robots rules and the remaining request budget.
At delivery, this example records a robots exclusion on the API host; it does not request the company endpoint.
Do not combine a probe with `--offline`.

A successful JSON probe stores field shapes and scalar types, not record values.
HTTP 200 HTML is an invalid API response.
Probe results record observed anonymous access separately from declared authentication.
A change in the security declaration replaces the current declaration and preserves its prior history.

## Inspect the output

| Artifact | Purpose |
| --- | --- |
| `store.json` | Version 2: projects, findings, immutable evidence references, attempts, request accounting, imported records and proposed assertions. |
| `evidence/<sha256>.txt` | Content-addressed structural extracts. Existing bytes are verified before reuse. |
| `requests.jsonl` | Generated export of dispatches, skips, statuses, limits and policy snapshots from the store. |
| `decisions.json` | Owner decisions. The engine creates an empty file only when absent and never replaces it. |
| `.structure.lock` | Exclusive writer lock, present only during a normal writer invocation. |

Collections inferred from paths have unknown business meaning and unknown record grain.
Named template variables preserve their source names; they do not establish CUI, SIRUTA or another namespace.
Pilot imports preserve the existing typed rules and seven sampled records.
The engine does not generate new entity correspondences from names, numbers or document declarations.
Adding curated bindings for new projects is a later curation step.

A refresh keeps prior findings, evidence and owner decisions.
It marks unsupported earlier findings stale. Retained documentation supports historical findings, not a new live observation.
Attempt outcomes and the last live API test remain separate from editorial acceptance.
If a process stops during a dispatch, its persisted attempt remains partial with an unfinished dispatch record.
Inspect that attempt before another run; do not label it a completed verification.
