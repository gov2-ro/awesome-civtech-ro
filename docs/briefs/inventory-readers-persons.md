# Brief — person data in sources, and three corrections of the JSON reader

Date: 2026-10-27. Baseline: commit `5739a73` (the brief itself is in the next commit).
Status: done on 2026-10-27 (merged from branch `readers-persons`, v0.37.0).

## 1. Start here

Read `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md` (the batch D entries and the `lista-firme` API entry).
Read the inventory sections of `docs/DATA-SCHEMA.md`, `scripts/render_pages.py`, `observed_fields` in `scripts/inventory.py`, and `keyed` and the positional rows in `scripts/inventory_literals.py`.
Read the person-data tests that lot D added in `scripts/test_inventory_report.py`.

Copy this prompt into the implementation session:

> Implement `docs/briefs/inventory-readers-persons.md`.
> Make no network request. Keep the evidence contract.
> Stop and report if a reviewed or confirmed group member stops matching a field. Finish with the report in section 6.

## 2. Goal

The owner approved these backlog items on 2026-10-27:

- **A.** A tracked file must not keep values about persons. Today `render_pages.py` keeps up to 20,000 characters of rendered text, and only a hand-written test protects the `lista-firme` API response.
- **B.** The plain `json` reader turns a year-keyed object into one set of paths for each year. It also turns an object whose keys are values into field names.
- **C.** The plain `json` reader gives one field `p[][]` for rows of equal width without names. The positions are lost.
- **D.** The plain `json` reader records nothing for an empty list or an empty object.

## 3. Decisions

### A. The mark `persoane`

1. A source specification (`observatii/inventare/adaugari/*.json`) and a render specification (`*-randare.json`) accept the key `persoane: true`. It means: the body holds records about natural persons.
2. Add `persoane: true` to these existing specifications:
   - the `onorata-instanta` and `politicieni-corupti` sources;
   - the `dupa-cutremur` sources that lot D marked as person data;
   - the `lista-firme` API response (`lot-d-lista-firme-api.json`).

   Do not mark other sources. If you think that another source holds persons, list it in the report.
3. For a marked source, the readers keep key names, paths, observed types and counts only. They keep no value: no `valori_enum`, no example, and no description taken from a value. Find every place where a reader copies a value into a tracked file, and apply the rule there.
4. `render_pages.py` gets the option `--fara-text`. A render with `persoane: true` in its specification always uses it. With this option, the record keeps `text_randat` as `null`, plus `text_lungime` and `text_sha256`. The controls and the data requests stay. Without the mark and without the option, the behaviour does not change.
5. `inventory.py --check` gets a check: for each marked source with a body in the cache, no string value of the body (4 characters or more, without the key names) occurs in a tracked file under `data/taxonomy-v2/` or `docs/`. Use the method of the lot D test: a failure prints a hash fingerprint, never the value. Keep the lot D tests, or make them call the new check.
6. `validate.py` or the inventory check refuses an unknown value for the key `persoane` (only `true` is allowed).

### B. Keyed collections in the plain `json` reader

1. Use the rule of `inventory_literals.keyed`: 100 members or more is always a keyed collection. From 12 members, it is a keyed collection when the values are of one kind.
2. Add one rule to both readers: an object of 2 members or more whose keys are all years (`^(19|20)[0-9]{2}$`) and whose values are of one kind is a keyed collection.
3. A keyed collection gives the path `…{*}` with the role `colectie-cu-chei` and `numar_chei`, as today for 100 members.
4. Put the rule in one function that both readers use. Do not keep two copies.

### C. Positional rows

1. Rows of equal width without names give one field for each position (`p[][0]`, `p[][1]`, …), as `js-literale` does. Use the same width limit (`POSITIONAL_WIDTH`).
2. Do not guess a name for a position. A candidate member for `siruta` or for the coordinates needs a declared name; if none exists, list the position in the report only.

### D. Empty containers

1. An empty list or an empty object gives a field record with the type `array` or `object` and `numar_elemente: 0`.
2. A `null` keeps the type `null`, as today.

### Common

- Document A, B, C and D in `docs/DATA-SCHEMA.md` (the reader table and the `persoane` key).
- The readers change the field records of earlier sources. Do not edit a confirmed or reviewed member of `inventar-concepte.json` to keep a match. If a member loses its match, stop and report.

## 4. Limits

- No network request. Work from the cache and the retained bodies (`inventory.py --offline`, the replay).
- Do not write into `data/taxonomy-v2/source/`, `reference/` or `runs/`.
- Do not decide a review item. A new candidate member goes to `inventar-note.json` (`selectori_candidati`) and to the report.
- No test may pin data that the owner edits (review states, counts of members, counts of entries with a value).

## 5. Work

1. Before you change code, record the baseline: the field records for each source (`campuri.csv`), and the matches of each group member.
2. Implement A to D, each with offline fixture tests. Run a mutation check on each new rule: break the rule, and see that a test fails.
3. Replay the inventory offline and regenerate the outputs (`inventory.py`, `inventory_report.py`).
4. Compare with the baseline. For each source with changed field records, give the counts before and after and the reason (B, C or D). For each group member, compare the matches before and after.
5. Run all checks:
   - `inventory_report.py --check` and `inventory.py --check`;
   - `validate.py --publication`;
   - the full unit suite (775 tests and 6 skipped before);
   - the three package checks;
   - a `--with-inventory` build into a separate `--site-dir`, with `check_preview.py`, `check_inventory_preview.py` and `check_data_finder.py`.
6. Add the activity entry. Flip the backlog items to `[x]`: the `render_pages.py` defect, the two `json` reader defects (year keys and positional rows), the empty-list defect, and the defect "no tool marks a source whose body holds persons".

## 6. Report

Give these items:

- Which tracked values the rule of A removed, by source. Give counts only, not the values.
- The sources whose field records changed, with the counts before and after and the reason.
- The total of field records before and after, and the change on `/date/`.
- The group members that gained or lost matches, and any new candidate members.
- The test counts before and after, the commits, and what you measured and what you assumed.
