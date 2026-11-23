# Brief — data inventories, batch I-2

Date: 2026-11-23. Owner: pax. Writer: Opus. Builder: Sonnet. Branch: `inventory-batch-i` (continue on it; batch I is commit `c2c2228`).

## Goal

Batch I left three gaps. The owner decided them on 2026-11-23:

1. Script data that names persons gets a persons mode. In that mode, a tracked file holds no value and no real key of the data.
2. A source may exceed the 2,000,000-byte response limit when its specification says so, up to a hard cap of 10,000,000 bytes.
3. `lipseste` gets one per-measure file as a sample, only if it adds fields.

## Part A — persons mode for script literals (`js-literale`)

- Today `js-literale` refuses the mark `persoane: true` (see `inventory_persons.READERS` and DATA-SCHEMA.md "Sources with persons").
  Allow the mark for `js-literale`. Use the rules of the other persons-safe readers: keep names, paths, observed types and counts; keep no value.
- A keyed collection (`colectie-cu-chei`) in a marked source writes `chei_exemplu` as placeholders: `‹nume 1›`, `‹nume 2›`, `‹nume 3›`
  (as many as the real keys, at most three). Keep `numar_chei`. Do not use realistic fake names.
- `--check` must search the marked body for values as it does for the other readers. The placeholders must not trigger it.
- Apply the mark to these sources:
  - `sondajele-romaniei` `data/date.js` (owner: the candidate names are public, but the tracked files must not copy them).
  - `cat-costa-un-vot` (the constant `E`): add the source with the mark.
  - `cate-voturi-aduce-un-primar` (the `date-uat` island): add the source with the mark and the Part B exception.
  - `guverneaza-daca-poti`: if the mark lets the reader keep `PMS` safely, drop `PMS` from `omise`. Otherwise leave it.
- After the change, no tracked file may contain the three candidate names that the coordinator named in the first version of this brief (the names are left out here so that the brief holds no value of the source). Grep to prove it with the three names.

## Part B — size exception per source

- Add a source-specification key `max_octeti` (integer). Without it, the limit stays `collect_docs.MAX_BYTES` (2,000,000).
  With it, the limit for that one source is its value. A value over 10,000,000 is a specification error; the run stops before it writes.
- The exception applies to the request of that source only, not to the documentation collector or other sources.
- Apply it to: `romaniainteractiva.ro/locale/` (`romania-in-puncte`, about 2.12 MB), `romaniainteractiva.ro/harta-notelor/`
  (`harta-notelor`, about 8.15 MB) and `nicolaeurs.ro/catevoturiaduceunprimar/` (about 2.16 MB). Choose the reader for the two
  romaniainteractiva pages the way lot C2 did for its other tool pages (`js-literale`, `tabele` where useful). Check the persons rule for each.
- The three CSV files of `satul-care-se-stinge` (`uat_activitati_2021.csv` 4.36 MB, `uat_etnie.csv` 6.27 MB, `uat_religie.csv` 7.26 MB)
  do not use the exception. Read each with a bounded range read (about 200,000 bytes): the header and the first rows are enough.
  First confirm that the `csv` reader accepts a body that ends in the middle of a line (drop the last partial line). If it does not,
  make the smallest change that drops it, with a test. Record the read as partial (`limita_atinsa` or the range-read marks that exist).

## Part C — `lipseste`

Request one file of `lipseste.ro/data/masuri/` (take the first id of `masuri/index.json`). Compare its fields with `analiza-370.json`.
Add it as a source only if it has fields that `analiza-370.json` lacks; otherwise record the result in the notes. Do not add
`solicitari-544.csv` (the owner agreed: same data as `solicitari-544.json`).

## Spec and tests

- Update `docs/DATA-SCHEMA.md`: "Sources with persons" (js-literale allowed, placeholders), the specification-file keys (`max_octeti`
  and its cap), and the CSV range read. This brief authorizes these three spec changes and no other.
- Add unit tests: persons mode of `js-literale` (no value, placeholders, the check still finds a leak), `max_octeti` (accepted, over cap
  refused, default unchanged), a cut CSV body.

## Limits

- At most 40 direct HTTP requests. Log every request in `jurnal-cereri.csv` under lot `I2`, including first looks; do not use plain `curl`.
- `common.forbidden(url)` before every request (the scripts do it). Stop on 401, 403 or 429 for that host.
- Never use a key or credential from a page or a bundle. Run `inventory.py` only with `--only`.

## Stop and ask

Stop and report before you change `intrari.csv`, `relatii.csv`, `furnizori.csv`, a vocabulary file or `colectare-interzisa.csv`;
before you accept a provider or a candidate; or before a change to a spec beyond the three above.
Add a row to `persoane-false-positives.csv` only for a clear false positive, and list each new row in the report.
Keep the CRLF line endings of that file.

## Verification

1. `python3 scripts/inventory.py --check`: 0 evidence errors, 0 leaks.
2. `python3 scripts/validate.py` and `python3 -m unittest discover -s scripts -p "test_*.py"`.
3. `python3 scripts/build.py --with-inventory --site-dir <scratch dir>`; do not write `site/`.
4. `python3 scripts/inventory_report.py --check`.
5. The grep of Part A.

## Completion report

Per source: reader, field records, persons mark, bytes read. Request counts. Totals before and after. Tests added. The DATA-SCHEMA
sections changed. Update `docs/ACTIVITY.md` and `docs/BACKLOG.md` (close the batch I open decisions that this work answers; flip the
postponed decision on large responses with the owner's answer of 2026-11-23). Commit on `inventory-batch-i`. Do not merge, push or tag.
