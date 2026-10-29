# Shared structure engine — 2026-10-30

Status: implemented. Guide: [STRUCTURE-PROFILER.md](../STRUCTURE-PROFILER.md).
Spec: [site-structure-profiler.md](../specs/site-structure-profiler.md).
The [version-1 pilot](site-structure-pilot/README.md) remains unchanged.

## Delivered

The stdlib entry point is `scripts/profile_structure.py`.
`structure_discovery.py` owns bounded HTTP, robots handling and structural signal extraction.
`structure_state.py` owns the separate store, evidence, imports and offline validation.
No dependency or public-build implementation changed.

Version 2 resolves the pilot's schema gaps:

- Operations have a list of collection uses and separate declared/observed security fields.
- Identifier rules distinguish declarations from sampled mappings.
- Collections have record grain and identity components, with explicit unknown values.
- Relationships retain their meanings instead of becoming identity assertions.
- Namespace bindings remain unknown when only a field name or numeric shape is available.
- A changed API security declaration keeps its prior declaration history.

The first engine discovers structural candidates. It does not harvest entity records or produce new identity matches.
Pilot import retains all seven record samples and both proposed correspondences.
It does not copy editorial decisions from the pilot.

## Measurements

The isolated store is `/tmp/civtech-structure-engine`; it is not a committed data root.
The commands in the guide reproduce imports and discovery with new observation times.
The existing documentation cache is optional, so fresh-checkout discovery counts can differ.

| Pass | Charged requests | Result |
| --- | ---: | --- |
| Pilot import | 0 | Four projects, 47 evidence records; seven records and two proposed correspondences retained. |
| Offline documentation replay | 0 | Eleven additional evidence records; missing bodies remain explicit gaps. |
| Initial sandbox live pass | 3 | Robots requests failed DNS. Other paths remained unrequested. SICAP remained blocked. |
| Approved bounded live pass | 20 | Transparenta.eu 6, Registrul firmelor 7, România Transparentă 7, SICAP 0. All dispatched responses were HTTP 200. |
| Linked-document discovery and explicit probe plan | 10 | România Transparentă methodology and data pages were read. The API host's robots rules excluded both contract retrieval and the company probe. |

Totals: 33 charged requests, 30 HTTP 200 responses and three DNS failures.
There were zero requests to forbidden hosts, zero redirects, zero browser requests and zero paid-search calls.
The live pass's large Registrul firmelor sitemap hit the 2 MiB cap.
The engine retained that truncation as a reason for partial coverage.
It did not infer patterns from the truncated document.

The last measured store held four projects, 84 evidence records, 34 patterns and 16 API operations.
It also held 18 collection declarations or path-group candidates, and 19 identifier-rule declarations.
These counts combine imported interpretations and newly discovered candidates. They are not accepted business classifications.
The second approved pass read a linked contract lead but made no request to its disallowed target.
No live API probe succeeded in this engine measurement; the response-shape probe has offline fixture coverage.
The pilot's earlier live API results remain historical observations.

## Verification

Run these checks from the repository root:

```sh
python3 -m unittest discover -s scripts -p 'test_profile_structure.py'
python3 scripts/check_structure_pilot.py
python3 scripts/profile_structure.py --out /tmp/civtech-structure-engine --check
python3 scripts/validate.py
python3 scripts/build.py
```

The final focused suite has 53 tests and passes on Python 3.12 and 3.15.
The final full-suite run passed 1,193 tests with eight skips.
Two additional query/fragment-location cases then passed in the final focused suite on both Python versions.
It covers cross-host redirects, robots failure, disallowed paths, host stops, budgets, pacing, body caps and Unicode URLs.
It also covers missing security declarations, changed security requirements, probe argument checks, HTTP shells and value-free response shapes.
Python 3.12 chooses the first matching robots rule, unlike Python 3.15.
The engine uses a version-independent matcher for longest rules, allow ties, wildcard paths and merged named-agent groups.
State checks cover immutable evidence, unchanged owner decisions, idempotent imports and stale/historical findings.
The first adapter left 17 optional evidence pointers in the old namespace.
The adapter now remaps those pointers, and fresh imports pass the integrity check.
Only the development store needed a one-off reference repair; the pilot and owner decisions stayed unchanged.
An unseeded fixture follows a linked data page to a contract and discovers its operations.

The version-1 pilot checker still passes.
Repository validation reports zero errors and warnings. The public build succeeds with 141 entries.
The public build's generated timestamp and score drift are excluded from this engine deliverable.

## Remaining boundaries

Browser diagnosis, repository discovery, domain search and automatic GraphQL execution remain future work.
The OpenAPI reader does not resolve referenced parameter definitions. Probes with unresolved parameters are skipped.
It records parameter locations and requirements, rather than implementing every schema constraint.
Document paths can group unrelated subjects. Such collections stay explicitly unverified.
The engine's identifier namespaces come from imported evidence; new business bindings require curation.
There is no new real local-ID-to-shared-ID sample. SICAP's local-ID declarations remain declarations.

The next workflow is the curation skill: investigate the uncertain candidates and record reusable bindings with evidence.
A correspondence review interface and public links remain separate work.
