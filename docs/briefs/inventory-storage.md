# Brief — inventory evidence storage

Date: 2026-10-31. Status: ready for implementation.

## Goal and decision

Keep raw browser captures outside Git. Preserve compact discovery evidence and committed profiles needed for offline builds.
Define how original captures are retained, retrieved, and verified. Report unavailable evidence explicitly.

The owner approved this direction. This brief authorizes an implementation session; it does not implement the migration.

## Current state

- Baseline commit: `1310bd9` (`v0.55.0`). The two recent batches changed inventory profiles and collection evidence.
- Git tracks 25 browser records under `data/taxonomy-v2/observatii/inventare/randare/`, totaling 130,486 bytes at that baseline.
- These records mix rendered page text with request metadata. Actual JSON/CSV response bodies already live in ignored `surse/`.
- The seven structured artifacts total 7,399,013 bytes: `campuri.csv`, `seturi-date.json`, `proiecte.json`, `descoperiri.json`,
  `rezumat.csv`, `intrari-utilizator.csv`, and `acoperire.csv`. Keep them tracked in this work.
- `inventory.py` resolves browser discovery through `locate_render()`. `check_locator()` checks `/cereri_date/N` in the referenced record.
- `descoperiri.json` contains 42 references to render paths. Preserve their meaning during migration.
- `inventory.py --check` reports unavailable local evidence. `--strict-snapshots` also fails when evidence is unavailable.
- Offline extraction is deterministic with the same code and cached inputs. A later browser navigation cannot reproduce a historical observation.
- Source selection, notes, and classifications can be assistant-authored. The extraction and report scripts do not call an LLM.

## Scope and implementation constraints

1. Separate raw captures from compact tracked discovery records. Keeping current record paths as compact manifests is acceptable.
2. Keep page and data URLs, observation time, outcome, and the request details needed by discovery locators.
   Keep credential redaction. Use an explicit allowlist for tracked fields; do not copy arbitrary page text or response values.
3. Inspect consumers before removing titles, text, controls, or other fields. Preserve referenced structural facts without copying personal values.
4. Give each retained raw capture a full SHA-256 and an immutable local name. Record the hash algorithm and exact byte representation.
   A repeat capture must not overwrite the original evidence. A hash verifies available bytes; it does not reconstruct them.
5. Use an ignored local capture directory by default. Document local retention and an explicit restore/import procedure.
   Do not introduce a remote archive, credentials, a dependency, or automatic network retrieval in this work.
   Document that another machine cannot verify an original capture until its owner supplies those exact bytes.
6. Update discovery resolution and verification for the split. Distinguish a valid manifest from a verified original capture.
   A present file with the wrong hash is an error. An absent capture is unavailable, never verified.
   Preserve ordinary offline checks and make strict snapshot checking require the referenced originals.
7. Migrate existing tracked records from local copies without requests. Preserve raw copies before replacing or untracking them.
   Preserve discovery URLs and pointers, or migrate every reference atomically with the record format.
8. Leave unrelated untracked exploration records alone. The worktree has such records from the recent audits.
9. Keep profiles, fields, source registrations, review decisions, person-data marks, and publication behavior unchanged.
   Preserve the reviewed false-positive ledger; never fabricate owner decisions to make a check pass.
10. Update `.gitignore`, the schema documentation, and relevant command help. Record the migration and verification limits in activity and release notes.

Changing the working tree does not erase captures from Git history. History rewriting is outside this task.
Batch G still has eight unresolved profiles; this storage migration does not complete that audit.

## Files and consumers to inspect

- `scripts/render_pages.py`: capture output, response cache, credential masking, and person-page text suppression.
- `scripts/inventory.py`: `locate_render`, `resolve_spec`, `check_locator`, and `--strict-snapshots` reporting.
- `scripts/inventory_persons.py`: scan scope and reviewed false-positive matching.
- `scripts/inventory_state.py`: persistence and request log; `scripts/inventory_report.py`: deterministic coverage projection.
- `scripts/test_inventory*.py`: existing extraction, state, report, person-data, and site behavior.
- `docs/DATA-SCHEMA.md`: inventory artifacts, discovery locators, and browser helper contract.
- `.gitignore`: broad taxonomy exception and the existing ignored response-body directory.

## Acceptance evidence

- Use temporary copies for migration tests. Make no source-site request and no browser navigation.
- Migrate a legacy record. Its discovery locator still resolves, and its retained raw bytes match the recorded hash.
- Repeat migration without changing output bytes or destroying a prior capture.
- Exercise missing and altered captures. Report missing originals as unavailable; reject altered originals.
- Verify ordinary checks on a checkout without local captures. Verify strict checks fail for unavailable referenced originals.
- Verify tracked manifests exclude page text, credentials, and personal values, including records collected with `--fara-text`.
- Compare fields, profiles, source membership, and review decisions before and after migration. They must be unchanged.
- Run the affected inventory tests, publication validation, and the report freshness check.
- Build into a separate directory with `--with-inventory --with-structure`. Confirm public inventory content and entity links remain equivalent.
- Update the backlog only when these checks pass. Report capture, manifest, and unavailable-evidence counts separately.

## Prompt for the implementation session

Implement `docs/briefs/inventory-storage.md`. Read AGENTS.md, docs/BACKLOG.md, and docs/ACTIVITY.md first.
Use existing local evidence and temporary migration fixtures. Preserve public profiles and owner decisions.
Complete the acceptance checks and document measured results and any remaining verification limits.
