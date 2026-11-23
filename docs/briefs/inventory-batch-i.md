# Brief — data inventories, batch I

Date: 2026-11-23. Owner: pax. Writer: Opus. Builder: Sonnet. Branch: `inventory-batch-i`.

## Goal

Twelve in-scope entries have an inventory row with no field, no structured source and no control (`completitudine` `neconfirmat`
in `observatii/inventare/rezumat.csv`). No earlier batch audited them. Find their public structured sources and add field
records where the evidence supports them. A result of "no structured source" is a valid result when the report gives the evidence.

## Entries

| Slug | URL | Note |
| --- | --- | --- |
| `satul-care-se-stinge` | https://satulcaresestinge.ro/ | Lookup map with a data story. No page collected yet. |
| `guverneaza-daca-poti` | https://guverneazadacapoti.ro/ | Game or simulation; may hold data literals. |
| `cat-costa-un-vot` | https://1vot.ro/ | Publication. Earlier persons check: a false positive on its note (see ACTIVITY.md). |
| `sondajele-romaniei` | https://sondajeleromaniei.ro/ | Poll data; author Adrian Hudrea. |
| `ghiceste-bugetul` | https://nicolaeurs.ro/ghicestebugetul/ | Tool by Nicolae Urs. |
| `cate-voturi-aduce-un-primar` | https://nicolaeurs.ro/catevoturiaduceunprimar/ | Publication by Nicolae Urs. |
| `mortalitate-evitabila` | https://romaniainteractiva.ro/mortalitate-evitabila/ | Publication on romaniainteractiva.ro. |
| `lipseste` | https://lipseste.ro/ | No page collected yet. |
| `statul-meu` | https://statulmeu.ro/ | Three pages collected. |
| `context-politic` | https://contextpolitic.ro/ | Four pages collected. Political data: check for persons. |
| `cotele-dunarii` | https://coteledunarii.ro/ | Four pages collected. Danube water levels. |
| `civiti` | https://civiti.ro/ | Civic reports, Bucharest. Source code on GitHub (see `linkuri`). Reports may hold persons. |

## Out of scope (do not touch)

- Settled in earlier batches; no request: `465`, `amscapat`, `tipizatul`, `radar-digital`, `econtractauto`, `evermed`,
  `open-budget`, `portal-just-modern`, `testvot`, `hotarari`, `gio`, `accesinfo`, `ong-camera-deputatilor`.
- `harta-notelor` and `romania-in-puncte`: the owner postponed the decision on responses over 2,000,000 bytes (BACKLOG).
- `didi365` and `fiipregatit`: the owner keeps them out (`relatie_date` stays empty).

## Method

- Follow `docs/briefs/inventory-expansion.md` sections 5, 6.C (discovery order) and 7. Use the lot-C2 to lot-H specification
  files in `observatii/inventare/adaugari/` as the model: one file `lot-i.json` (more files only if one source needs its own).
- Read the local caches first (`observatii/documentare/`, `inventare/surse/`, `randare/`). Run `collect_docs.py --only SLUG`
  for an entry with no collected page.
- Use the existing readers (`js-literale`, `html-tabele`, `rsc-json`, `json`, `csv`, `html-carduri-csv`, and the others in
  DATA-SCHEMA.md). Do not write a new reader. If an entry needs one, record it as a backlog item and stop on that entry.
- `common.forbidden(url)` before every request; the scripts already call it. Stop on HTTP 401, 403 or 429 for that host. Do not retry it.
- Never use a key, token or credential that a page or a script bundle contains. A source behind one is "no source".
- A source with records about natural persons gets `persoane: true`; keep schema only. `inventory.py --check` must report no value leak.
- Limits: at most 100 direct HTTP requests in all, two browser pages per entry, ten new structured sources per entry, bounded samples.

## Stop and ask

Stop and ask the owner (through Opus) before you: change `intrari.csv`, `relatii.csv`, `furnizori.csv`, a vocabulary file or
`colectare-interzisa.csv`; accept a provider, group or candidate; add a reader; or change a spec in `docs/`.
Propose providers and candidates only in the report.

## Verification

1. `python3 scripts/inventory.py --check` — no evidence error and no persons leak.
2. `python3 scripts/validate.py` and `python3 -m unittest discover -s scripts -p "test_*.py"`.
3. `python3 scripts/build.py --with-inventory --site-dir <scratch dir>`; do not write `site/`.
4. `python3 scripts/inventory_report.py --check` if the report file changes.

## Completion report

For each entry: the sources found, the reader, the number of field records, the persons mark, and the blockers with evidence.
Give the request counts (direct, browser) and the totals before and after (sources, field records). Add an entry to
`docs/ACTIVITY.md` (Done / Hard / Decided, with the measured numbers) and update `docs/BACKLOG.md`: flip the batch item, and
add a `[-]` under *Verified limits* for each dead end with its reason. Commit on branch `inventory-batch-i`. Do not merge, push or tag.
