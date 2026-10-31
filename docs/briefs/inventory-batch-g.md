# Brief — data inventories, batch G

Date: 2026-10-31. Status: source audit in progress.

## Goal

Add evidence-based data profiles for ten more entries from `/date/lista/` „De analizat”. Prefer public datasets, registries,
and APIs that support civic oversight or public services. Keep all findings and interpretations as proposals.

## Entries

| Slug | Reason for selection |
| --- | --- |
| `ai-aflat` | Fact-checking and public claims may expose a structured archive. |
| `destraja` | Anti-discrimination reporting may expose public findings or resources. |
| `econtractauto` | Consumer contracts may expose terms and structured vehicle data. |
| `monarh-ai` | Public political content may expose a searchable evidence base. |
| `monitor-energie` | Energy monitoring has high value for public oversight. |
| `radar-digital` | Digital services and infrastructure are public-interest topics. |
| `redirectioneaza` | Public-interest organizations and tax redirection may expose registries. |
| `semnal-razboiul-hibrid` | The project monitors public disinformation and security claims. |
| `testvot` | Election guidance may expose structured party or policy comparisons. |
| `tipizatul` | Public-service forms may expose document schemas and requirements. |

This is a prioritized source audit, not an assumption that each entry has machine-readable data. If a site is stale, blocked,
or has no structured source, record the evidence and report the gap. Do not replace an entry without documenting why.

## Limits and method

- Follow `inventory-expansion.md` sections 5, 6.C and 7.
- Use the forbidden-host list before every request. Stop on 401, 403 or 429; do not guess protected endpoints.
- Limit direct HTTP requests to 120 for lot G and ten structured sources per entry. Use bounded samples.
- Do not copy individual values into tracked files. Mark sources with person records and keep schemas only.
- Do not accept provider or variable proposals. Preserve all evidence outside this batch.

## Completion report

Report source findings and parsed fields for each entry, person-data marks, candidate members and providers, blockers, request
counts, validation results, and owner decisions. Update the activity log and backlog. Build only in a separate preview directory.
