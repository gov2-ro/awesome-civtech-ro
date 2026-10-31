# Brief — data inventories, batch F

Date: 2026-10-31. Status: profiles collected; privacy check blocked.

## Goal

Add evidence-based data profiles for ten active entries still listed under „De analizat” at `/date/lista/`.
Prioritize public information with clear value for civic oversight. Follow sections 5, 6.C and 7 of
[inventory-expansion.md](inventory-expansion.md). Keep source findings and interpretations as proposals.

## Entries

| Slug | Reason for selection |
| --- | --- |
| `antibunk` | Its public graph exposes a manifest and a node index. |
| `barometrul-digital` | Its catalog API returns institution scores and categories. |
| `imobile-rapps` | Its public files describe state properties and boundaries. |
| `monitor-cetatenie` | Its tables report yearly application counts and processing times. |
| `onesti-city` | Its API serves municipal notices, local news and air quality. |
| `vichub-data` | Its public files expose census and historical population data. |
| `monitorul-ai-integritate` | Its statistics pages expose aggregate public integrity data. |
| `bucuresti-verde` | Its API lists tree-related permits and complaints. |
| `bucuresti-help` | Its API exposes aggregate and citizen-report fields. |
| `unde-locuiesc-romanii` | Its public registry describes a geographic data store and live indicators. |

The first candidate set was provisional. The source audit replaced stale, blocked or non-structured pages with these ten data-bearing entries.
`hotarari.ro` returned HTTP 403 and is now listed in `colectare-interzisa.csv`. The map URL for `harta-digitalizarii-primariilor` resolved to an unrelated article.
The public API endpoints of `ce-fac-politicienii` returned HTTP 401; no more requests went to that host. The Camera Deputaților page timed out.
The Monitor Energie contract remains excluded because an earlier pass returned HTTP 401.

## Limits and method

- Refresh the selected project documentation with `collect_docs.py`; cap the pass at six pages per entry and one worker.
- Check the forbidden-host list before every request. Do not bypass HTTP errors, authentication, or terms.
- Use at most 120 direct inventory requests for lot F, at most ten new sources per entry, and bounded source samples.
- Use existing readers. Record person-data sources under the existing inventory rule and copy no individual values into tracked outputs.
- Add provider relations and new variable members as review proposals only. Do not change accepted decisions or the catalogue.
- Mark sources with person records and retain field names only. Do not keep individual values in tracked outputs.
- Preserve prior evidence for projects outside this batch.

## Completion report

Record sources found and parsed, field records, candidate members, proposed providers, blockers, requests, and remaining
owner decisions. Update the inventory report, activity log and backlog. Check inventory evidence, publication validation,
and build the inventory preview in a separate directory. Do not publish or push.

## Implementation status

The ten profiles contain 785 field records: Antibunk 93; Barometrul Digital 12; Imobilele RA-APPS 78; Monitor cetățenie 40;
Onești City 40; VicHub Data 19; Pe propria răspundere 324; București Verde 29; bucuresti.help 33; Unde locuiesc românii 117.
The project inventory grew from 54 to 64 entries with fields. Publication validation passed. The isolated build completed.
`inventory.py --check` did not pass: it reported personal-value overlaps in tracked evidence. Resolve them before completion,
then rerun the check and the required preview checks. The publication queue is expected to shrink from 33 to 23 entries.

The provisional alternatives were rejected after source checks: `hotarari.ro` returned 403 and is now forbidden;
`ce-fac-politicienii` returned 401; the Harta digitalizării URL resolved to an unrelated article; the CDEP page timed out.
