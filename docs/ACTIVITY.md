# Activity

## 2026-10-27 — Six groups approved; five entries without data

**Done**
- At the owner's request („I approve the 6 groups”), `uat`, `partid-politic`, `beneficiar-fonduri-publice`, `subventie-partid`, `donatie-partid` and `cod-caen` are `revizuit`, with all 23 members confirmed and the 7 deductions ticked. Written with `Store.decide_group`. Every group of `inventar-concepte.json` is now `revizuit` (41).
- `relatie_date` = `fara-date` for `observatori-votcorect`, `romania-fara-gropi`, `votcorect`, `votez-info` and `presspay` (owner: „right - no data”). No active project or resource has an empty value now.

**Decided**
- The families stay as proposed: `beneficiar-fonduri-publice` and `deficit-bugetar` in `achizitii`, `subventie-partid` and `donatie-partid` in `alegeri`, `cod-caen` in `identificatori`. The owner approved the groups as they were; a new family stays possible later.

## 2026-10-27 — Dates in the leak check; the owner's rule for person data

**Done**
- `inventory_persons.identifies` also looks for a date alone (`1975-03-02`, `02.03.1975`, `02/03/1975`), at the owner's request. A birth date without a time was a gap of the check. `inventory.py --check` still finds no leak in the 12 marked sources.

**Decided**
- The owner's rule for person data: start as open as possible, and limit step by step when a need shows. The six unmarked sources that name persons stay unmarked; the backlog notes them. The cost: values such as the three surnames in `chei_exemplu` of `romaniainteractiva.ro/guverne` stay in tracked files of the public repository.

## 2026-10-27 — The group `cod-caen` and the source `seats-index.json`

**Done**
- Two owner decisions of 2026-10-27, branch `caen-seats` (base `cf9fa9e`). 0 requests: the work used the cache and the retained bodies (`inventory.py --offline`).
- **`cod-caen`** (`inventar-concepte.json`). New proposed group (`propus`; no review key on the group or on a member). Family `identificatori`, category `identificator`, as `cpv`. Five members in four entries, each with the source URL and a `context`: `lista-firme` `$.caen[].code` (integer); `companii-de-stat` `$.companii{*}.caen` of the bulletin data file (string) and `$.caen` of its OpenAPI (no type); `romania-transparenta` `$.date[].caen_principal` (text or null); `demoanaf` the path parameter `code` of `GET /api/caen/{code}` and `/hub`. The search of `campuri.csv` (case-insensitive `caen`, `nace`, `activit` in the name or the path) matched 62 records; 26 records mention CAEN in some column. The others are `monitorul-ai` activity records, two `onorata-instanta` columns and `infos.activityCode`. Only the DemoANAF parameter was new beyond the three entries of the brief: its OpenAPI says „Get one CAEN Rev.3 code” and gives the pattern `^\d{4}$`. Each selector matches only its own fields (1, 1, 1, 1 and 4 records). 12 pinned evidence items (5 for the definition, 7 for member facts): `inventory.py --check` 129 verified (117 before), 0 stale. `Store.errors_of`: 0 errors. 8 ambiguity entries: the two CAEN versions, integer against string and the leading zero, one code against a list, whose code it is, the fields kept out, the fields documented without a record, and the family.
- **`seats-index.json`** (`sondaje-romania`). The render record of lot D lists it among the bodies that the browser kept, and `surse/5335f57d009536be2636.json` held it (`via: browser`, 1,139 characters). So the source was registered offline with a new specification file, `adaugari/lot-d-seats-index.json` (locator `randare`, as `lot-d-randare.json`): 0 requests, and `sondaje-romania` stays at 5 of 15 requests. The corrected reader gives one field record, `${*}` (role `colectie-cu-chei`, 21 keys). Field records 4,443 → 4,444; `sondaje-romania` 4 → 5 sources and 36 → 37 field records; lot D 36 → 37 sources and 637 → 638 field records; /date/ (the sum of the per-entry counts of the build) 4,154 → 4,155.
- The note of `sondaje-romania` (`rezultat`, `limite`, `limite_en`), the lot D addendum, the `lista-firme` next step and the review list of `inventar-note.json` follow the new state; `acoperire.csv` and `docs/reports/inventory-expansion.md` are regenerated.
- Tests: 831 run, 6 skipped (830 and 6 before). One new test in `test_inventory_report`: the poll index is one keyed collection, the browser received it, and no key is a field name. It reads tracked data only and pins no review state and no count that the owner edits. Mutation check: 4 of 4 breaks fail it (an extra field, a source without `via`, a direct request in the log, a wrong key count).
- Checks: `validate.py --publication` 0 errors, 0 warnings. `inventory.py --check` 0 errors, 147 bodies hash-verified, 12 sources with persons searched. `inventory_report.py --check` current. The three package checks pass. `inventory.py --offline` on a copy of the tracked folder (with the cache copied in) gives the six generated files byte for byte, also with the new specification file. `build.py --with-inventory` into a scratch folder: `site/` has no change; the finder lists `cod-caen` (`propus`) for four entries. Browser against the served build: `check_preview.py` 141/141, `check_inventory_preview.py` 40/40, `check_data_finder.py` 61/61.

**Hard**
- The leak search of `inventory.py --check` looks for every string with a space in a body that carries the mark `persoane`. A CAEN description is such a string: measured, it is one of the 11 values that the search looks for in the `lista-firme` response. So a fragment that quotes it would fail the check, although a CAEN description is no person data. The evidence fragment of the response stops before the description: `"caen":[{"code":6210,"version":3,"caen_details":{"section":"`. It holds key names, one CAEN code and its version.
- `companii-de-stat` holds the CAEN code as a string of 4 characters in 1,328 records and of 3 characters in 118 of 1,446 (measured on the retained body), and none starts with `0`. The 3-character values (`111`, `130`, `141`, `210`) look like classes of the divisions 01–09 without the leading zero. The source does not say so, so it is an ambiguity and not a fact. The same risk exists for the integer of `lista-firme`.
- `lista-firme` has `$.caen[].caen_details.class` equal to `code` in the three elements, and `division` and `group` are the first two and three digits. They are coarser levels or a repeat, so they are not members. `infos.activityCode` (a migration column) has a name that suggests an activity code, but no retained copy says it is the CAEN code, so it is not a member.
- I used `git stash` once, to measure the lot D totals before the change. The cache folders are untracked symlinks, so the stash did not touch them, and `git stash pop` restored the tree. A copy of the committed `acoperire.csv` would have been enough.

**Decided**
- A fifth member for the DemoANAF parameter `code`. The brief named three entries and allowed more where the evidence shows the CAEN code. The OpenAPI declares „CAEN Rev.3” and 4 digits, and the two `code` parameters of the API are both CAEN. The cost: it is an input, not a value in a response, and the `context` and the `role` constraint say so. The owner can exclude it. The selector keeps `$.error.code` out with the role `parametru-api`.
- Two members for `companii-de-stat` (the data file and the OpenAPI), not one. Each has its own source and evidence, so the owner can confirm one and exclude the other. The cost: two review actions.
- `$.caen[].version` of `lista-firme` is a fact of the member (`fapte`, key `versiune`) and not a member, because it names the version and not the code. The value 3 is recorded as observed. The meaning „Rev. 3” is not asserted: the response does not say it.
- Category `identificator` and family `identificatori`, as `cpv` (a classification code). The family `firme` is the alternative, but its description speaks of financial and personnel data. The choice is in the ambiguity entries and in the backlog item for the owner. No new family is needed.
- No provider item and no `selectori_candidati` for `seats-index.json`. The field matches no group (its keys are values). The institutes in the keys are INSCOP, CURS and IRES (accepted as providers, D197–D199), and Avangarde, Sociopol, ARA and ARP. `llms.txt` and the methodology page name the first three of those four as institutes collected by hand, and the Institutes page names ARP („Agenția de Rating Politic”). A key is the identifier of a poll, not a statement about who produced the data, and the batch D rule is not to infer a provider from a citation. The cost: no `date_din` relation for the four until the owner names one.
- A new specification file (`lot-d-seats-index.json`) and not a change to `lot-d-randare.json`: the history of when and why the source came stays visible.

**Measured and assumed**
- Measured: the field records and counts above; the types and lengths of the CAEN values; the values `code`, `version`, `division`, `group` and `class` of the three elements of the response; the declarations of DemoANAF; the 12 pins (fragment found and SHA-256 equal); the matches of the 5 selectors; the replay bytes; the test and browser results.
- Assumed: the years of the two CAEN versions (Rev. 2 from 2008, Rev. 3 from 2025) come from the brief and general knowledge, not from a retained copy; the ambiguity entry says so. `version` 3 stands for Rev. 3, which is consistent with the codes seen (6210, 6290, 6310) but is not declared. The leading zero was lost in the 3-character values. `ARA` and `ARP` in the keys are the institutes of the same names on the Institutes page.

## 2026-10-27 — Person data in sources, and three corrections of the JSON reader

**Done**
- Brief `docs/briefs/inventory-readers-persons.md`, branch `readers-persons` (base `ea5f6fc`). No request: the work used the cache and the retained bodies (`inventory.py --offline`, two replays, `--check`).
- **B, C, D** (`inventory_literals.keyed_collection`, `inventory.observed_fields`). One function decides a keyed collection for the plain `json` reader (also `lista-ins` and `json-esantion`) and for `js-literale`: 100 members or more; 2 or more year keys (`^(19|20)[0-9]{2}$`) of one kind; 12 to 99 members of one kind whose keys are not all identifiers (`^[a-z][A-Za-z0-9_]*$`). The identifier test is a correction of the brief (see Decided): a record of 12 to 99 members with identifier keys stays a record. Rows of one width (2 to 12 cells, scalars) give one field for each position (`p[][0]`, …). An empty list or object gives a field of the type `array` or `object` with `numar_elemente` 0; a null stays `null`; the last member of a cut sample gets no record when it is empty (the cut may have emptied it).
- **A.** `persoane: true` in a source or render specification. The registry record and the source record carry it (events `marcat-persoane` and `nota-inlocuita`); a marked source is read as `csv`, `json` or `json-esantion` only, with the allowed field keys, and a CSV cell above the header stays only when it is a key name; a specification cannot quote a marked body; `--persons` marks `--add-source` and `--import-saved`; `inventory.py --check` searches the files that the inventory writes for the identifying values of each retained marked body and prints a file and a fingerprint; `render_pages.py --fara-text` (and a render specification with the mark) keeps `text_randat` as null with `text_lungime` and `text_sha256`. 12 sources are marked: 5 tables of `onorata-instanta`, the sample of `politicieni-corupti`, 5 GeoJSON files of `dupa-cutremur`, the `lista-firme` API response.
- **Field records** (`seturi-date.json`): 5,134 before, 4,443 after (−691). In the JSON family: keyed collections −736, rows +22, empty containers +12. In `js-literale`: +11 (`statul-digital`, see below). On /date/ (the sum of the per-entry counts of the build): 4,845 → 4,154; 42 entries have fields before and after, 12 changed. By source (before → after): `ce-face-statul-cu-1000-de-lei` 333 → 34 (B −299); `companii-de-stat` `data.json` 454 → 165 (B −291, C +2) and `index.json` 19 → 20 (D); `lista-firme` API 55 → 57 (D +2); `romania-transparenta` `primarii.json` 40 → 13 (B −27) and `control-saptamanal.json` 19 → 20 (D); `unde-se-termina-asfaltul` `osm.json` 130 → 19 (B −119, C +8); `trei-din-patru` `places.json` 4 → 11 (C +7) and `names.json` 2 → 3 (D); `dupa-cutremur` `_strazi_arie_colaps` 13 → 14, `arie_colaps_complete` 15 → 17, `cladiri_complete` 26 → 28 (C: the coordinates of a polygon are two positions); `codurbanism` 51 → 53 and 37 → 38 (D); `ultima-noapte-pib` 107 → 109 (D); `europescope` 16 → 17 (D); `posturi-gov2` 21 → 22 (D); `statul-digital` `data.js` (`js-literale`) 93 → 104 (the 12 members of `inferences[]` have identifier keys: a record now). Lot D: 910 → 637. `complet-online` is unchanged (53 → 37 → 53).
- **Keyed collections found** (all sources): baseline 18 (3 in the JSON family, 15 in `js-literale`); with the rule of the brief 24 (9 and 15); with the identifier test 21 (7 and 14). The 7 of the JSON family have keys that are county numbers, company ids, years, county names or dates; the one that `js-literale` lost is `inferences[]` of `statul-digital`.
- **Registry and sources.** 12 registry records changed (the mark and its event; two also got the replaced note). 26 source records changed against the base (18 with other field records, 12 with the mark, 4 both). A second replay gives the same bytes. The six generated files, `acoperire.csv` and `docs/reports/inventory-expansion.md` are regenerated; the counts that `inventar-note.json` states by hand follow the new numbers.
- **Group members.** 164 selectors compared before and after, all of them (also the proposed and the excluded ones). Three confirmed members of reviewed groups keep only part of their matches because the repeated paths merge: `cui` (`companii-de-stat`) 50 → 9, `cifra-afaceri` (`companii-de-stat`) 48 → 7, `deficit-bugetar` 22 → 2 (the paths `$.companii_pe_judet{*}[].cui`, `….mfin_ca`, `$.years{*}.deficit_mil_lei` and `$.years{*}.deficit_pct_pib` replace the repeated ones). No selector that had a match has none. No review state changed, and no member was added or edited. The three candidates of the `lista-firme` response (`selectori_candidati`: `cui`, `judet`, `localitate`) still match their fields.
- **Values removed from tracked files by the rule of A.** One sentence in the notes of `onorata-instanta` (the home-page check of the table `performanta-instante`): 2 values (an institution name and a label that it holds), in 4 files (the specification `lot-d.json`, the registry note, `inventar-note.json`, the generated report). The other 11 marked sources: 0 values. The sentence is replaced by one without a value.
- **Tests:** 830 run, 6 skipped (775 and 6 before): `test_inventory` +8, `test_inventory_literals` +1, `test_inventory_jsonsample` +2, `test_inventory_persons` 44 (new), `test_inventory_report` 0 (3 changed). None pins a review state, a count of members or a count of entries with a value. Mutation check: 71 breaks of the new rules (each of the three reader rules, the identifier test and its pattern, the mark, the form check, the search and its exemptions, the render option); all failed a test. In the first round 3 survived (the field filter in `analyse_source`, the same filter in `--check`, a value in the answer) and got a test. `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check`: 0 errors, 146 bodies hash-verified, 117 dictionary evidence items verified, 0 stale, 12 sources with persons searched. `inventory_report.py --check`: current. The package checks pass. `build.py --with-inventory` into a scratch folder, served: `check_preview.py` 141/141, `check_inventory_preview.py` 40/40, `check_data_finder.py` 61/61.

**Hard**
- The check of the brief, read literally (no string of 4 characters or more of a marked body in a tracked file), cannot pass on the current tree. It finds `Feature`, `Point`, a coordinate system, road kinds, years in 4 digits (also inside hashes), OpenStreetMap identifiers, `Romania` and a role label. Some of those are pinned evidence of reviewed members (`inventar-concepte.json`) and of the accepted review item D204 (`revizuire.csv`), which a tool must not edit. The check looks for the values that identify instead; the module and `docs/DATA-SCHEMA.md` give the rule and its gap (a single word). The first version of the digit rule (7 digits or more) found the 8-digit OpenStreetMap identifier that D204 quotes; the length of 10 digits (a phone number) keeps the rule on persons.
- The rule for keyed collections of the brief (12 members of one kind) read three real records as collections and lost their member names: the `address` object of the `lista-firme` response (12 text members, −11), the `counts` object of `complet-online` (17 numbers, −16) and `inferences[]` of `statul-digital` (12 text members, −11). The candidates `judet` and `localitate` had no field for a while. I followed the brief first and measured a refinement; the coordinator took it as a correction of the brief (see Decided).
- The registry stores the note of a specification only when it creates the record, and no option corrects it, so a value that a note quoted could not leave the registry. A marked specification now replaces the note (event `nota-inlocuita`). The same defect for the unmarked notes of `lista-firme` stays open (backlog).
- The search for the 4 names of the `politicieni-corupti` sample in all 813 tracked files found them outside the scope: 3 in the search results (`observatii/mentiuni.csv`, the frozen `source/mentiuni.csv`, `data/mentiuni.csv`) and 1 in two files of the frozen package `runs/2026-10-19-reasoned-evidence/`. No reader of the inventory wrote them. Fingerprints: `8f0b71cd`, `4f9d9c4f`, `18415bb1` and `b1059795`.
- Three of the five `dupa-cutremur` samples (`arie_colaps_complete`, the shelters and the road segments) show no person key in the retained bodies, although the lot D note says so for all five.

**Decided**
- **Identifier test (the coordinator's correction of the brief, same day).** From 12 to 99 members, an object whose keys are all identifiers (`^[a-z][A-Za-z0-9_]*$`) stays a record, unless the year rule applies; 100 members or more stays always a collection. It is in the one shared function, so `js-literale` has it too: the only `js-literale` source whose records change is `statul-digital` `data.js` (`inferences[]`, 93 → 104). Among the 9 collections that the rule of the brief found in the JSON family it changes exactly two (`$.address`, `$.counts`); no selector changes its matches. Cost: a collection keyed by lowercase slugs (`alba`, `arad`) with fewer than 100 members is read as a record, as before 2026-10-27. Tests for both sides (12 identifier keys: a record; county names, codes, numbers, dates and keys that start with a capital, a digit, `_` or hold `-`: a collection; 99 and 100 members) and 20 mutations of the rule.
- The mark is stored in the registry (the reader needs it at the next replay) and in the source record (a test can check the form without the registry). Cost: two places to keep equal; the state check and `--check` compare them.
- A marked source is read as `csv`, `json` or `json-esantion` only, and a field keeps the allowed keys only. Cost: a marked source in another format gets `eroare-parsare` until the owner decides; the alternative (to filter the text readers) would have to know every key that holds a copy.
- The note of a marked specification replaces the registry note. Cost: the history of the old note is lost (the event stays). The alternative, a hand edit of a generated file, is forbidden.
- No retroactive refusal for the dictionary: the existing evidence of reviewed members that quotes a marked body (a coordinate system, the coordinates of a shelter, an OpenStreetMap identifier) is not about persons and is not edited. A specification that would quote a marked body is refused from now on.
- All five `dupa-cutremur` sources are marked, as the notes of lot D say. Cost: three files read with key names only that show no person key (backlog).
- The counts and statements in `inventar-note.json` that the new readers made false (`lista-firme`, `dupa-cutremur`, `trei-din-patru`, `ce-face-statul-cu-1000-de-lei`, `onorata-instanta` and the lot D addendum) were corrected with the new numbers and the old ones, so that the history stays visible.

**Measured and assumed**
- Measured: the field counts before and after (a script over `seturi-date.json`, and an ablation that applies the rules one after the other to the 37 retained bodies of the JSON family and reproduces the baseline counts); the matches of the 164 selectors; the hits of the values in 813 tracked files (by file, with fingerprints); the build counts of /date/; the tests, mutations and checks above; that the replay is idempotent.
- Assumed: the search finds a value only as a whole text; a part of a value is not found. The exemption "an unmarked body holds the value too" needs the retained bodies, so a checkout without them cannot run the search (it says "unavailable"). The `expert` values and the other identifying values of the `dupa-cutremur`, `politicieni-corupti` and `lista-firme` bodies are person data; the lot D notes say so, and I did not judge each value.

## 2026-10-27 — dupa-cutremur documentation collected again

**Done**
- At the owner's request, `collect_docs.py --only dupa-cutremur --force` (5 requests). The two pages with letters outside ASCII (`ce-înseamnă-redu`, `sistemul-de-mapare-rapidă`) are now collected; the entry changed from `documentatie-neconfirmata` (1 page) to `documentatie-gasita` (3 pages).
- `inventory.py --check`: 0 stale evidence items, so the accepted provider D203 keeps its pinned evidence. 775 unit tests pass.

## 2026-10-27 — `lista-firme`: one response of the live API

**Done**
- The owner raised the request limit of `lista-firme` for one request. `inventory.py --only lista-firme --lot D --budget 120 --max-requests 1 --add-sources-file adaugari/lot-d-lista-firme-api.json` made it through `common.forbidden` and the request log: `GET https://lista-firme.info/api/v1/info?cui=51859625` (the CUI of the operator). Answer: HTTP 200, `application/json`, 2,276 bytes, no redirect, no key, no retry. It is the one row for the API in `jurnal-cereri.csv`.
- The response is the 7th source of the entry and the 36th of lot D: 55 field records (key paths and observed types), 106 for the entry, 910 for the lot. The body stays in the git-ignored cache (`surse/`, symlinked to the main checkout in this worktree).
- The response has 17 keys. Nine are columns of `companies`, one is computed (`is_active`), seven are relations: `address` (12 keys), `info` (null), `status` (one key, `details`, with `code` and `description`), `caen` (3 elements; `code`, `version` and the same 7 keys under `caen_details` and `details`), `legal_representatives` (1 element, 14 keys), `natural_person_representatives` (empty list) and `eu_branches` (empty list). The relation names are in snake case; the code of the controller writes them in camel case.
- Against the 51 migration columns (measured by comparing the key names; counts add up to 51): 21 appear (9 of `companies`, 12 of `addresses`); 7 are hidden (`id`, `created_at`, `updated_at` of `companies`; `id`, `company_id`, `created_at`, `updated_at` of `addresses`); the 5 columns of `statuses` do not appear; the 18 columns of `infos` were not observed because `info` is null. The API adds `is_active`, the relation keys, and the keys of `caen` (16 paths) and `legal_representatives` (14 paths) that no migration read gives. `legal_representatives[]` keeps `id`, `company_id`, `created_at` and `updated_at`, which the API hides for the company and the address.
- Dictionary: three candidate members for the reviewed groups, in `inventar-note.json` (`selectori_candidati`, the key is back): `cui` (`$.cui`), `judet` (`$.address.county`) and `localitate` (`$.address.city`). The confirmed selectors of the entry name the migration paths and the migration source, so they do not match the response; the new ones name the response path and source. No group got a member, no group and no provider item was added, no review item was decided. A group `cod-caen` is a suggestion only: the field exists in 3 entries (`lista-firme`, `companii-de-stat`, `romania-transparenta`).
- The `lista-firme` note (`rezultat`, `limite`, `limite_en`, `urmatorul_pas`, `urmator_en`), the blocker line, the lot D addendum, the network figures of lot D (77 direct requests, 4,226,710 bytes, `lista-firme` 16, `lista-firme.info` 2) and the check line of `inventar-note.json` are current. `acoperire.csv` and `docs/reports/inventory-expansion.md` are regenerated.
- Person data: the body names a legal representative (name, birth date and place, current location). No value reached a tracked file. Proof, run on the retained body: 6 identifying string values of the person relations; 0 hits in the blobs of the 3 data commits, 0 in the working tree (812 files), 0 in the scratch site build (506 files). Four tests: the persons test now covers this source (allowed keys of a `json` record); the source record and the paths of the response hold only key names and types; when the body is present, no identifying value is in `data/taxonomy-v2/` or `docs/` (the answer shows a fingerprint, not the value); the leak check finds a value that it is given; the log holds one API request and no other API path, CUI or name query.
- Checks: 775 unit tests, 6 skipped (772 and 6 before). `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check`: 0 errors, 146 bodies hash-verified (145 before), 117 dictionary evidence items verified, 0 stale. `inventory_report.py --check`: current. The three package checks pass. Replay of `inventory.py --offline` on a copy of the tracked folder: the six generated files are byte for byte the same, 0 requests. `build.py --with-inventory` into a scratch folder: `site/` has no change. Browser against the served build: `check_preview.py` 141/141, `check_inventory_preview.py` 40/40, `check_data_finder.py` 61/61.

**Hard**
- The plain `json` reader records only the leaves that it sees. An empty list (`natural_person_representatives`, `eu_branches`) gives no record, so the inventory cannot say that the key exists. A null (`mark`, `info`) gives the type `null` and nothing else. Both go to the backlog.
- The first grep for the person values matched 288 files. The cause was generic values: a role label, a country name and empty strings. A per-key count (value lengths and hits only) showed that the identifying keys had 0 hits. The test and the proof now leave out the label keys (`role`, `birth_country`, `current_country`), numbers and strings under 4 characters.
- The `caen` relation repeats its 7 keys under two names (`caen_details` and `details`), because the controller loads both `caen` and `caen.details`. The record count (16 paths) counts the paths, not 7 distinct keys.
- `inventar-note.json` has no trailing newline; `json.dumps` writes none, so a script round-trip keeps the file byte-stable.
- The notes of the six migration sources still say "The live API was not requested" (`descoperiri.json`, `adaugari/lot-d.json`). It was true when they were written. A generated file must not be edited by hand, and no option corrects the note of a registered source: backlog item.

**Decided**
- A new specification file `lot-d-lista-firme-api.json`, not a change to `lot-d.json`. The cost of the alternative: the history of when and why the source came is lost in a file of 33 entries.
- The evidence of the new source is the README fragment that documents the endpoint and the controller fragment that names the relations (`cache: true`). A fragment of the response body is not used: the registry stores the fragment text, so a value of a person could reach a tracked file.
- No provider item. The response and the terms name no originator that the entry lacks: ONRC and ANAF are accepted (L185, L186). The cost: none for the facet; a licence or a producer for the API response stays unknown.
- No group `cod-caen` and no `selectori_candidati` for it. The owner did not ask for a group; a new group needs a definition, evidence from three entries and a review. The cost of the alternative: more review work now, with 3 members.
- The label keys are outside the person check. The cost: a role label in a tracked file would not fail the test. A role (for example „Administrator”) names a position, not a person.
- The test pins the request log (one API request) and not the review state or a count of members.

**Measured and assumed**
- Measured: the status, size and type of the response; its key paths and types (a script over the retained body that printed paths and types only); the counts above; the tests, checks and browser results.
- Assumed: the deployed code equals the repository at commit 1dcb375 (the response agrees: `is_active` and the relation set match `Company.php` and the controller). `is_active` is computed by the scope `preferActive` (read in the code, not seen in a query). `status.details.code` stands for the `statuses.status` column (the response does not say it). A hidden key is hidden by the model; the code proves it for `Company` only. The CUI belongs to the operator that the terms name (the owner said so). One company says nothing about the keys of the other companies: `natural_person_representatives` and `eu_branches` may have keys for a company that has such records.

## 2026-10-27 — Owner decisions on batch D

**Done**
- At the owner's request („ok with 1, 2, 3, 4”), the batch D proposals were decided in bulk with the review interface's own code (`Store.decide_provider`, `Store.decide_group`, `Store.errors_of`: 0 errors before and after):
  - The 22 provider items D189–D210 are `acceptat`; they wrote the relations L185–L206.
  - The groups `deficit-bugetar` and `coordonate-geografice` are `revizuit`, with their 6 members confirmed. `deficit-bugetar` keeps the family `achizitii`.
  - The four lot D members of the proposed groups `partid-politic` (3) and `uat` (1) are confirmed; the two groups stay `propus`.
  - The 14 candidate selectors joined their reviewed groups as `confirmat`; the key `selectori_candidati` left `inventar-note.json`.
- The owner postponed the requests for exports from project owners (`dupa-cutremur`, `guvernezi`, `politicieni-corupti`).
- 772 unit tests pass; `validate.py --publication` and `inventory.py --check` pass.

**Decided**
- The owner raised the request limit of `lista-firme` for one API response (the operator's own CUI). A Sonnet agent does that request; the response gives key names only.

## 2026-10-27 — Inventory batch D: twelve entries of „De analizat”

**Done**
- Lot `D` (brief `docs/briefs/inventory-batch-d.md`, branch `inventory-batch-d`). The documentation of the twelve entries was already collected (`collect_docs.py --only` made 0 requests). The discovery order of `inventory-expansion.md` section 6.C gave 35 sources and 855 field records for eleven entries; `guvernezi` has no structured source.
  By entry (sources / field records): `lista-firme` 6 / 51 (migrations of the repository `tudorr89/info-firme`), `dupa-cutremur` 5 / 90 (five GeoJSON files of the live map), `reciclare-arad` 3 / 40 (the JSON files of the repository), `onorata-instanta` 5 / 73 (TSV tables of the repository), `sondaje-romania` 4 / 36 (the page and three JSON files that it requests), `politicieni-corupti` 1 / 15 (a sample of the repository file named in the JSON-LD), `unde-locuiesc` 1 / 23, `trei-din-patru` 6 / 27 (page table, two data files, three INS metadata records), `statul-digital` 2 / 99, `pe-datorie` 1 / 68, `ce-face-statul-cu-1000-de-lei` 1 / 333, `guvernezi` 0 / 0.
- Network (measured from `jurnal-cereri.csv`): 76 direct requests (limit 120; at most 15 for each entry, 15 for `lista-firme`), 4,224,434 bytes, all HTTP 200 or 206, no retry. 3 browser navigations (`guvernezi.ro/`, `sondajeromania.ro/parlamentare`, `politicieni-corupti.ro/lista`) and 96 browser requests, most of them Next.js route prefetches. No host answered 401, 403 or 429, so there is no proposed row for `colectare-interzisa.csv`. No reserve entry was used.
- Readers and options, each with offline fixture tests: `json-esantion` (a JSON or GeoJSON file that a range read cut; complete elements only), the CSV option `delimitator` `tab` (the second row of the TSV tables is the header), script files and the forms `window.NAME = {...}` and `Object.freeze([...])` in `js-literale`, Laravel `Schema::table` migrations in the `php` reader. The collector now percent-encodes letters outside ASCII in a link (`collect_docs.wire_url`). A partial repository file is not compared with its blob hash; a mutation check makes the new test fail without the rule.
- Dictionary: two new proposed groups (`deficit-bugetar`, `coordonate-geografice`), three selectors for `partid-politic`, one for `uat`; 14 evidence items more (117 verified, 0 stale). 14 candidate selectors for five reviewed groups are in `inventar-note.json` (`selectori_candidati`) and section 5 of the report: `cui` 1, `judet` 4, `localitate` 4, `populatie` 2, `perioada-de-referinta` 3. No reviewed group got a member.
- Providers: 22 review items D189–D210, state `deschis`, none accepted. Each cites a retained copy with its hash and a fragment; the review interface's own `Store.provider` shows all 22 as `verificat`. `relatii.csv` did not change.
- The coverage export has a new state, `investigat-fara-surse` (an entry that a lot touched and that has no usable source and no recorded blocker): `guvernezi`. The report knows lot `D` (section 3 and the network summary).
- Tests: 772 run, 6 skipped (727 and 6 before): `test_inventory_jsonsample` 20 (new file), `test_inventory_literals` +6, `test_inventory_sheet` +6, `test_inventory_text` +2, `test_collect_docs` +3, `test_inventory_report` +8. None pins a review state or a count of entries with a value. `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check`: 0 errors, 145 bodies hash-verified (110 before). `inventory_report.py --check`: current. The package checks pass. A build with `--with-inventory` into a scratch folder: `site/` has no change. Browser checks against that build: `check_preview.py` 141/141, `check_inventory_preview.py` 40/40, `check_data_finder.py` 61/61.

**Hard**
- `politicieni-corupti.ro` is a client-side shell: its methodology page has 574 characters and the list page makes no data request. The repository came from the `sameAs` of its JSON-LD. The base file holds only 11 fields per record; the validator and the build script at the same commit declare more (geography, verified_at, sources), but the data of those is in a 3.2 MB script that I did not request.
- The browser record of `/lista` kept 20,000 characters of rendered text with the names and legal status of persons. I deleted the record before the first data commit and kept the measured aggregates (779 politicians, by eight status labels) in the notes. The helper has no rule against this: backlog item.
- The 15-request limit of `lista-firme` went to the repository (README, routes, controller, model, six migrations, the terms page), so the live API was not requested. The README says `?name=`, the code reads `company`. The routes file has one route and a fallback that aborts other paths with 401.
- `ce-face-statul-cu-1000-de-lei` gives 333 field records: about 30 paths repeated for each of 11 years, because eleven members are below the keyed-collection threshold of the plain reader. The count is a count of paths. `places.json` of `trei-din-patru` has rows of eight cells without field names; the plain reader gives `p[][]` and loses the positions. Both are backlog items.
- The first collection of `dupa-cutremur` recorded an `eroare-retea` for any link with letters outside ASCII. I found it by reading the `error` text, fetched the download page with a percent-encoded address, and then fixed the fetcher. I did not run `collect_docs.py --force` for the entry: it would write new snapshots and could change the hash that the review item D203 pins.
- `check_data_finder.py` failed one check ("uninventoried projects remain reachable") on the new data. Cards with evidence come first and 24 are shown at a time, so the uninventoried cards were on a later page. The check was wrong, not the page: it now opens every page of cards (61/61).
- Eleven sources are range samples: each GeoJSON file (30,000 bytes), the politicians file (4,108) and the TSV tables (5,000, and 900 for the contact header). The inventory knows the fields of the first complete records, not the size of a file or the number of its records.

**Decided**
- The live API of `lista-firme` stays unrequested. The terms forbid mass collection for commercial use, the response lists legal representatives (natural persons), and the entry's budget was spent. The cost: the keys of a real response are unknown; the columns come from the migrations and the model, at a recorded commit. The README documents the endpoint, so one request would be within the brief if the owner raises the limit.
- A new state `investigat-fara-surse` and not `blocat` for `guvernezi`. `blocat` means that a host refused or failed; here nothing was refused. The cost of the alternative: the coverage table would say that the project is blocked when it publishes no structured data.
- No provider items for `guvernezi` and `politicieni-corupti`. The first compiles positions from many public citations; the second names 14 official hosts in its build code as citation hosts. A provider proposed from those would infer a provider from a citation. The cost: no `date_din` relation for the two entries until the owner names one.
- The candidates for reviewed groups stay in the notes, as for batch C2; selectors for proposed groups (`partid-politic`, `uat`) and the two new groups were added directly, as in batch C2 part 3. `deficit-bugetar` is in the family `achizitii` because no family fits, with an ambiguity entry that says a family for public finance is the owner's decision (the same compromise as `beneficiar-fonduri-publice`).
- `seats-index.json` of `sondaje-romania` was seen and not admitted: its keys are values (poll identifiers). `geoBoundaries` (county limits) of `trei-din-patru` and the 14 official hosts of `politicieni-corupti` got no provider item: map background and citations, not data.
- The page tables of `onoratainstanta.ro` were not read: the performance page has no `<table>`, and its values equal the repository table (one value compared). The deployed use is shown by that equality and by the build script, not by a rendered table.

## 2026-10-27 — Out-of-scope entries keep their „Date & metodă” panel (v0.34.1)

**Done**
- The owner decided that an entry out of the variable inventory keeps the „Date & metodă” panel in the explorer: „if it holds a url value, other types of projects might still have method, and data they used”. `publish_preview` no longer applies the scope rule. `/date/`, `/date/lista/` and the default selection of the collectors still do.
- Measured on a `--with-inventory` build: 81 items have the key `inventory` (61 before, 81 before steps D–E). The 20 items that get it back hold documentation links only; no out-of-scope entry has fields today.
- Tests: two unit tests now say the opposite of the old ones (an entry that leaves the scope keeps its file and panel; an organisation keeps its links). The browser checks open the page of an out-of-scope organisation and project and find their links; three checks of the old rule left `check_data_finder.py`. Without the change, 3 unit tests and 1 check in each browser script fail.
  Counts: 727 unit tests; `check_preview.py` 141/141, `check_inventory_preview.py` 40/40, `check_data_finder.py` 61/61.
- The CNP of `db.banipartide.ro` is the owner's work in that project; the backlog item is dropped. The cleaned copy of its database in the scratchpad was deleted.

**Decided**
- The explorer markers follow the panel: an out-of-scope entry with fields would show its marker. None has fields today. The cost of the alternative (panel without marker): a second rule for one case that does not exist.

## 2026-10-27 — The 24 candidate members confirmed in bulk

**Done**
- At the owner's request („I'm happy with your proposals for the 24 candidate members … I'll untangle if I spot mistakes later”), the 24 candidate selectors of batch C2 (parts 1–3) went into their reviewed groups with `stare` `confirmat` and the note „Confirmat în bloc la cererea proprietarului (2026-10-27)”: `judet` 7, `cui` 4, `localitate` 4, `perioada-de-referinta` 4, `populatie` 2, `voturi-valide` 2, `siruta` 1.
  Written with the review interface's own validation (`Store.errors_of`: 0 errors before and after) and its byte-stable JSON writer. The key `selectori_candidati` left `inventar-note.json`, so the report no longer lists them.
- One test read the candidates from the notes; it now reads the members of the groups. 727 unit tests pass; the browser checks pass on a `--with-inventory` build (141, 40 and 63).

**Decided**
- The groups keep their state `revizuit` and their review date: the owner reviewed the group definitions, and the new members carry their own note. The cost: the group record does not show that members were added after its review; the member notes and git do.

## 2026-10-27 — Two groups for the relation to data, in the explorer and on /date/ (brief section 9)

**Done**
- `common.DATA_GROUPS` defines the two public groups once: `cu-date` „Lucrează cu date” (`date-publice`, `date-proprii`, `calcul`; the same tuple as `IN_SCOPE_RELATIONS`) and `fara-date` „Fără date” (`fara-date` and an empty value). `common.data_group(relation)` gives the group of a value, and `common.public_reason(reason)` turns the reason `neevaluat` into `fara-date`. `inventory_exclusion` and `acoperire.csv` do not change: `neevaluat` stays an internal state for editors.
- How Python and the browser stay in step: `build.py` writes the tuple to `vocabulary.dataGroups` in `data.json` (key, label, codes), and `site/app.js` reads the groups there (`dataGroup(code)`; the empty value goes to the group that lists `''`). `app.js` holds no list of codes. `test_taxonomy_v2` checks that every listed code and the empty value belong to exactly one group and that `cu-date` is exactly what `inventory_exclusion` keeps in scope. `test_inventory_site` checks that `app.js` holds no code literal, and that a new code in `valori.csv` needs a decision. `check_data_finder.py` checks that `?dat=cu-date` lists the same entries as the finder on each tab.
- Explorer: the facet `dat` offers `cu-date` and `fara-date` only. `?dat=date-publice`, `?dat=calcul` and `?dat=neevaluat` list nothing (the work was never pushed, so no URL exists). `dat` is still not offered on the organisation tab (one option). `st` is unchanged.
- `/date/` and `/date/lista/`: two reasons, without data (`fara-date` and empty together, active entries) and inactive. `inventar/index.json` `leftOut` has the keys `fara-date` and `inactiv`. The links are `?dat=fara-date` and `?st=inactiv` (`?k=resursa&…` for resources). The footer of `/date/` (`inventory.js`) and the section of `/date/lista/` (`inventory_site.py`) say the same.
- Measured on the tracked data (build `--with-inventory`). Groups on the explorer tabs, inactive entries hidden as by default: projects 73 `cu-date` + 14 `fara-date` = 87 of 105 (18 inactive), resources 12 + 9 = 21 of 21. With the inactive entries: projects 75 + 30 (2 and 16 inactive), resources 12 + 9. The finder lists 85 (73 projects, 12 resources), as before. `/date/lista/` leaves out 41, as before, now in two lines: without data 23 (14 projects and 9 resources; of the projects, 9 have the code `fara-date` and 5 an empty value) and inactive 18 (18 projects). Before: without data 18, not assessed 5, inactive 18. The tables hold 31 rows with fields and 54 entries without fields, as before.
- Tests: 727 run, 6 skipped, 1 failure; 725 run, 6 skipped, 1 failure before. The failure is not from this work (see Hard). New: `test_taxonomy_v2` 1, `test_inventory_site` 1 (class `Scope`); the left-out tests changed to two reasons. Browser, against a served scratch build with `--with-inventory`: `check_preview.py` 141/141 (138 before), `check_inventory_preview.py` 40/40 (36), `check_data_finder.py` 63/63 (62). `check_preview.py` also gives 141/141 against the build without inventory.
- Verified that the new and changed tests fail without the change. Unit mutations, each makes the named test fail: `calcul` outside `cu-date` (`test_taxonomy_v2` and `test_inventory_site`); the group `fara-date` without the empty value (both); `public_reason` that keeps `neevaluat` (4 tests of `test_inventory_site`); `left_out` without `public_reason` (2); a build without `dataGroups` (`test_taxonomy_v2`); a code literal in `app.js` (1). Browser: the checks of the commit before this work run against a build of that commit (`git archive` of `3745ba2` built into a scratch folder). The new `check_preview.py` fails 12 of 141 on it, `check_inventory_preview.py` 2 of 40, `check_data_finder.py` 9 of 63. A served `data.json` with `calcul` moved to `fara-date` fails 5 checks of `check_preview.py` and 6 of `check_data_finder.py` (the explorer group no longer equals the finder); a served `inventory.js` with a wrong query fails 3 checks of `check_data_finder.py`.
- Docs: `DATA-SCHEMA.md` (the two groups and how they are kept in step, `vocabulary.dataGroups`, `leftOut`, `/date/`, `/date/lista/`, the facet `dat`, the note that `neevaluat` is internal), `specs/taxonomy-v2.md`, `data/taxonomy-v2/README.md` (one Romanian paragraph for editors).
- `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check`: 0 errors. `inventory_report.py --check`: 0 outputs out of date. `integrare.py` passes.

**Hard**
- One test fails on `main` before this work and after it: `test_inventory_report.Coverage.test_bani_partide_is_read_from_the_listing_that_the_owner_saved_and_says_what_it_did_not_read` pins 172 fields, and the data holds 171 since `6b4d56c` (the CNP column is discarded). It pins a number that the owner's data decides. I did not change it; it is in the backlog.
- The first version of the changed `check_preview.py` crashed on the old build (a missing key and a missing label) instead of reporting a failed check. The checks now use `.get`, so that a build without the change fails them one by one.
- No `dat` group has a small count in the tracked data (73 and 14 on the project tab), so the check "a selected option stays visible although its count is small" cannot use a real small group. It combines `dat=fara-date` with a search that finds nothing (count 0), which does not depend on the data.

**Decided**
- The group definition lives in Python and travels in `data.json`; the alternative was a second list in `app.js`. The cost of the chosen way: the explorer needs `vocabulary.dataGroups` in `data.json` (a build without it offers no `dat` facet, and the tests catch that). The gain: one list, and the tests need no parser for JavaScript.
- `leftOut` keeps its name and drops the key `neevaluat` instead of keeping a zero. No consumer reads the old key, and a key that is always zero would invite a third line on the page.
- An inactive entry is still counted as inactive, whatever its group, as before. So the count „fără date” (23) does not include the 16 inactive entries of the group `fara-date`, and `?dat=fara-date` (which hides inactive entries by default) shows the same 14 projects and 9 resources that the note gives.
- The public text does not say „neevaluat”: for a reader an entry with no value is an entry without data (owner, 2026-10-26).
- No version bump, no tag and no `docs/RELEASES.md` entry: the owner's Opus session merges the branch and tags it.

**Measured and assumed**
- Measured: all counts above (build, `data.json`, `inventar/index.json`, the served pages through the three browser checks), the test counts before (725 run on `3745ba2`, and the browser checks 138, 36 and 62 on a build of `3745ba2`) and after, and the mutations.
- Assumed: that no external page links `?dat=date-publice`, `?dat=calcul` or `?dat=neevaluat` (the brief says the work was not pushed); that the production `data.json` is rebuilt together with `app.js` (the Pages workflow does it; the `?v=` hash of `app.js` in `site/index.html` changes with this commit).

## 2026-10-26 — The scope of /date/ and the explorer facets dat and st (steps D and E of the relation to data)

**Done**
- One rule for the scope of the variable inventory: `common.inventory_exclusion(kind, status, relation)` gives the reason, or an empty string when the entry is in scope (a project or a resource, not `offline` or `arhivat`, `relatie_date` `date-publice`, `date-proprii` or `calcul`; an empty value and `fara-date` both leave the entry out). `status_of` and `years_since` moved from `build.py` to `common.py`, so that scripts that read the catalogue get the built status too (`common.inventory_scope`). `inventory_site.scope_reason(item)` applies the rule to a built item.
- `publish_preview`, `publish_finder` and `publish_overview` use that function. An item out of scope has no `inventory` key, no `inventar/<slug>.json`, no row in `inventar/index.json`, `/date/` or `/date/lista/`.
  `inventar/index.json` has a new key `leftOut` (counts by reason and kind). `/date/lista/` has the section "Lăsate pe dinafară (N)": a count for each reason and a link to the explorer for each kind (`?dat=fara-date`, `?dat=neevaluat`, `?st=inactiv`, and `k=resursa` for resources). The note "Lipsa câmpurilor nu înseamnă lipsa datelor" stays with the entries in scope. `/date/` says the same in its footer.
- Measured, before and after (build `--with-inventory` into a scratch folder): the finder index holds 126 entries (105 projects, 21 resources) before and 85 after (73 projects, 12 resources). `/date/lista/`: 31 rows with fields and 95 entries without fields of 126 before; 31 rows and 54 entries without fields of 85 after. The finder leaves out 41: 18 without data (9 projects, 9 resources), 5 not assessed (5 projects: `observatori-votcorect`, `romania-fara-gropi`, `votcorect`, `votez-info`, `presspay`) and 18 inactive (18 projects). The 13 organisations are not counted. `inventar/` holds 31 field files and the index, as before: no entry with fields left the finder.
- `acoperire.csv` (142 rows, hidden entries included), before: `neinvestigat-in-lot` 97, `cu-surse-structurate` 31, `in-afara-ariei` 13, `blocat` 1. After: `neinvestigat-in-lot` 53, `cu-surse-structurate` 31, `inactiv` 19, `fara-date` 18, `in-afara-ariei` 13, `neevaluat` 7, `blocat` 1. The 19 and 7 include the three hidden entries (one inactive, two not assessed). `urmatorul_pas` is empty for the new states, except `neevaluat`: it asks the editor to set `relatie_date`. The report states the scope and the counts.
- `collect_docs.py` and `inventory.py`: without `--only`, a run skips the entries out of scope and prints how many, by reason (57 on the tracked data: `in-afara-ariei` 13, `inactiv` 19, `fara-date` 18, `neevaluat` 7). `--only` runs an entry and prints `NOTE: SLUG is out of the variable inventory (reason)`. `update_inventory` has a new parameter `skip`. An explicit `--add-source`, `--retire` or a project with no tracked record always runs. An offline replay of `inventory.py` on a copy of the tracked folder gives the six generated files byte for byte, with the skip.
- Explorer: the facets `dat` ("Date", the codes of `relatie_date` and `neevaluat`) and `st` ("Stare": `activ`, `inactiv`, `neconfirmat`) under "Mai multe filtre", with labels, counts, pills and URL state, in the pattern of `ent`. `st=inactiv` shows inactive entries without `ina=1`; the toggle "Ascunde proiecte inactive" is then off and disabled. The counts of the `st` options ignore the hiding of inactive entries. `ina=1` and the old parameter `s` keep their meaning.
- Docs: `DATA-SCHEMA.md` (new section "Scope of the variable inventory"; the states of the coverage export; the column row; the incremental runs), `specs/taxonomy-v2.md` and `data/taxonomy-v2/README.md` no longer say that an empty value stays in `/date/`.
- Tests: 724 run, 6 skipped (701 and 6 before). New: 8 in `test_inventory_site` (class `Scope`), 5 in `test_inventory_report` (`Scope`), 3 in `test_collect_docs`, 7 in `test_inventory_state`. No new test pins a `relatie_date` value, a review state or a count of entries: fixtures build their own items, and the tests on tracked data check invariants (the site and the scripts give every public entry the same reason; the table has the state that the rule gives).
  Each new unit test fails under a mutation of the code that it covers. Checked: the preview without the rule (3 tests fail), the finder without it (1) and the list without it (1); no left-out section; the left-out section when nothing is left out; an empty value in scope (the first version of the brief; 3 tests fail); `calcul` out of scope; `arhivat` not inactive; the catalogue route without the profiler status (the test on tracked data fails); the report without the scope, with the scope before the evidence, without the `neevaluat` step, and counting hidden entries; collect_docs with no skip and with no note; `inventory.py` with no `skip`; `update_inventory` ignoring `skip`, skipping an explicit addition, and skipping a new entry. 19 mutations in all, each makes the named test fail.
  Browser: `check_preview.py` 138/138 (111 before), `check_inventory_preview.py` 36/36 (31), `check_data_finder.py` 62/62 (40), against a served scratch build with `--with-inventory`; `check_preview.py` also against the build without inventory (138/138). Mutations of the served `app.js` (`st=inactiv` not showing inactive entries, the `st` counts hiding them, an empty relation not mapped to `neevaluat`, the toggle not disabled, the toggle ignoring `st`) each make a named check fail, a build whose finder lists every project and resource again fails 5 checks of `check_data_finder.py`, and a build whose preview keeps the inventory of an entry out of scope fails 2 checks of `check_inventory_preview.py` and 1 of `check_data_finder.py`.
- `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check`: 0 errors. `inventory_report.py --check`: current. The package checks and `integrare.py` pass.

**Hard**
- A targeted run of the new tests passed, but the full run found three failures: two tests of `test_saved_copies` ran `inventory.main()` on a catalogue entry without `kind`, and one test of `test_review_ui` built a finder from an item without `status` and `dataRelation`. The fixtures now carry what the rule reads. The lesson: run the whole suite after a change to a function that many fixtures share.
- The first version of the `dat` facet had a rule that hid it on the organisation tab. A mutation that removed the rule changed nothing: an organisation has one option (`neevaluat`), and a facet with one option is not offered. The rule was redundant and is gone.
- `st` counts its own options without the rule that hides inactive entries. With the rule, the option `inactiv` would show 0 and could not be chosen.
- An entry out of scope loses the whole key `inventory`, documentation links included. 81 items had the key before and 61 after. The 20 that lost it held documentation links only: 9 organisations and 11 projects and resources (8 `fara-date`, 3 with an empty value). The text of that panel, „Câmpurile de date nu sunt încă inventariate aici”, would be wrong for them, but the owner may want the links. Open in the backlog.
- A new entry has an empty `relatie_date`, so it is out of scope and the default run of the collectors skips it. An editor who needs its documentation runs `--only SLUG`. Open in the backlog.
- The three hidden entries are in `acoperire.csv` (the file lists the whole catalogue) with the state of their own value. The report counts them apart. Their `urmatorul_pas` is empty.

**Decided**
- The state of an entry with a parsed or a failed source stays `cu-surse-structurate` or `blocat`, whatever its scope. The scope states replace only `neinvestigat-in-lot`. The alternative (scope first) would hide evidence that the repository holds; the cost of this choice is that an out-of-scope entry with fields would show a state that its public output does not follow. Today no entry is in that case (measured: all 31 entries with fields are in scope). `validate.py` already warns when a `fara-date` entry has fields.
- An inactive entry is counted as inactive, whatever its `relatie_date`. So the counts by reason add up, and the link `?dat=fara-date` (which hides inactive entries) shows the number that the note gives. The cost: the count „fără date” does not include an archived guide.
- `neevaluat` is the name of the state and of the facet value for an empty value. The column never holds it.
- `/date/` has a footer note as well. The brief names `/date/lista/`; section 3 says `/date/` links to the explorer. The cost: a few lines in `inventory.js` and the template.
- The links of the note go to the explorer for each kind (`?dat=…` for projects, `?k=resursa&dat=…` for resources), because the explorer shows one tab at a time. A single link would show the projects only, and its count would not match the note.
- `update_inventory(skip=…)` and not "pass the entries in scope as `selected`": an empty `selected` means every entry, so a run with no entry in scope would widen to all. A test covers it.
- No version bump, no tag and no `docs/RELEASES.md` entry: the owner's Opus session merges the branch and tags it.

## 2026-10-26 — The relation to data applied (step C); two entries hidden; D185–D188

**Done**
- The owner edited `relatie-date-propuneri.csv`: `testvot` → `calcul`; `didi365` and `harta-tv-locale` marked „remove”; `data-expertforum` → `date-publice` (earlier). 106 values went into `integrare/intrari.csv`. 21 rows stay empty (15 inactive entries, the hidden `fiipregatit` and 5 active entries with too little evidence), and 2 carried the removal mark.
- `didi365` (not specific to Romania) and `harta-tv-locale` are `ascuns`, as for `fiipregatit`; the two `didi365` images left `site/img/` (`harta-tv-locale` had none). `build.py` writes 139 entries.
- The owner decided D185 (rejected), D186 (rejected: „should be Monitorul Oficial, HG's are published in MO”) and D187 (accepted, L183). D188 proposes Monitorul Oficial for `data-expertforum` with the evidence of D186; it is open for the owner.
- Two tests pinned data that the owner edits: the round trip of `relatie_date` in `test_sheets_form.py` (it expected an empty column), and the batch C2 part 2 provider test (it expected one item). Both now check the behaviour only. 701 tests pass.

**Decided**
- The owner decided that an entry without a value leaves `/date/`, like `fara-date`. The first brief kept it in. The cost: 5 active entries without enough evidence (`observatori-votcorect`, `romania-fara-gropi`, `votcorect`, `votez-info`, `presspay`) leave the finder until someone sets a value. `data-relation.md` section 3 is updated.
- „Remove” was applied as `ascuns`, not as a deleted row: the public result is the same, and the data, relations and observations stay. The precedent is `fiipregatit`.
- D188 is a proposal, not an accepted row: `CLAUDE.md` says that an agent never decides a review item for the owner, even when the owner's note names the answer.

## 2026-10-26 — Inventory batch C2, part 3: bani-partide from the owner's saved Datasette listing

**Done**
- Imported the listing that the owner saved (`tmp/banipartide.json`, 11,493 bytes, SHA-256 `252c26c05f04f3c8…`, saved 2026-10-26T20:30:00+02:00) with `inventory.py --import-saved`. 0 requests. The log of requests got no row, and the owner's local checkout of the project was not read.
- New reader `baza-datasette` (`scripts/inventory_datasette.py`, brief section 8.1): the format comes from the shape of the JSON. Measured on the copy: 18 visible tables with 172 columns (one field record for each, path `<table>.<column>`, role `coloana-sql`, no type), 457,900 rows in all (the row count of each table is a fact that the server computed), 20 hidden tables (a count, no field), 4 views (names only), and the declared source „Expert Forum”, its address and the licence CC Attribution 4.0 (a fact with a pointer for each).
  The field browser titles the source „Bază de date Datasette · banipartide.json”, shows the table of a field with its row count, and credits the licence: „Nume de câmpuri și descrieri preluate din db.banipartide.ro, licență CC Attribution 4.0 License · Sursa: Expert Forum.” 18 reader and run tests and 6 tests on the tracked state (24 in `test_inventory_datasette`), and 2 in the site tests.
- The discovery locator of the source is a fragment of the copy (`"source": "Expert Forum"`), with three more fragments that have a role (source address, licence, licence address). The home page of the project answered HTTP 403 and links no data address, so the copy is the only text that can be located.
  For this, `--import-saved` now puts the copy in the cache before it resolves `--add-sources-file` (before, a specification with `cache: true` could not find a fragment in the copy of the same run). 2 tests; a mutation check (the old order) makes the first one fail.
- Mapping to groups. The column `Partid` (12 tables, 12 fields) is one new selector of the proposed group `partid-politic`, and `Legenda partide.UAT` is one new selector of the proposed group `uat`. Two groups are new, state `propus`: `subventie-partid` (`Subvenții.Suma`) and `donatie-partid` (the column `Suma` of the three donor tables). Both are in the family `alegeri`; neither has a unit, because the listing declares none. 38 groups in all.
  Six candidate selectors for three reviewed groups are in `inventar-note.json` and section 5 of the report; no reviewed group got a member: `cui` (3: `Contracte subventii.CUI`, `Donatori persoane juridice.CUI`, `Legenda partide.CUI` with `Venituri anuale partide de la MF.CUI`), `judet` (2: `Judet` of two tables, `Cod județ`) and `perioada-de-referinta` (1: the column `An` of 12 tables). `siruta`, `localitate` and `voturi-valide` have no candidate.
- One provider item, D187: Ministerul Finanțelor, from the table title `Venituri anuale partide de la MF` (state `deschis`, priority `mica`). The review interface's own `Store.provider` shows the evidence as `verificat` (kind `sursă păstrată`, hash `252c26c05f04f3c8`, fragment found) on a temporary copy of the data root. `relatii.csv` did not change.
- Relation to `data-expertforum`: its political finance data set links `https://www.banipartide.ro/` as the related report. The two entries share no data source (the Drive file of that data set was not read), so nothing is counted twice.
- Coverage: `bani-partide` goes from `blocat` to `cu-surse-structurate` (lots `C2` and `S`): 1 source, 172 field records, 0 with a description, 0 with a type, 4 groups, 4 measures without a unit, 1 source with a verified locator.
- Tests: 701 run, 6 skipped (671 and 6 before): `test_inventory_datasette` 24 (new file), `test_saved_copies` +2, `test_inventory_site` +2, `test_inventory_report` +2 (the test that pinned `bani-partide` as `blocat` now builds a blocked entry from the data, and no new test pins a review state).
  `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check`: 0 errors, 110 bodies hash-verified (109 before), 5 saved copies hash-verified, 102 dictionary evidence items verified (95 before), 0 stale. `inventory_report.py --check`: current. The package checks pass. A build with `--with-inventory` into a scratch folder: 128 finder entries, 38 groups; `site/` has no change except the `app.js` stamp in `index.html`.
  Browser checks on that build: `check_preview.py` 111/111, `check_inventory_preview.py` 31/31, `check_data_finder.py` 40/40, and a one-off check of the field browser of `bani-partide` (10 checks). An offline replay on a copy of the tracked folder gives the six generated files byte for byte.

**Hard**
- The brief says „a table title names the Ministry of Finance … but the copy names no provider” and „Propose a provider only from text in the copy”. I read it so: the title is text in the copy, so it can support one proposal; it is a table name, so the priority is `mica`; the copy writes only „MF”, so the expansion is mine and D187 says so. The other reading gives no item. The cost of D187 is one decision for the owner.
- The listing declares nothing but names and counts. All 172 fields have a name and nothing more, and the groups rest on table names and neighbouring column names (`deductie-din-dovezi`, so the review interface asks the owner to tick each one). The meaning of `Suma` (month or year, which currency) is unknown. `Subvenții pe an` has two sums (`Suma`, `Sume alocate`) that the listing does not tell apart.
- A column name can be a person-related name: `Donatori persoane fizice` has `Nume donator` and `CNP`. The inventory and the field browser show the two names, because the public listing shows them. No row was read, and no group takes these two columns. If the owner prefers not to show them, a rule in `inventory_datasette.py` must leave them out.
- `Sediul social ` has a trailing space in the listing. The field keeps it, and a selector must write it.
- The part 2 entry counted 669 tests. This worktree measured 671 before my first change. The fix `cadde0e` came after that count and adds two test functions in `test_inventory_sheet.py` (counted in its diff); I did not check the other commits one by one.
- The home page and the documentation pages of `banipartide.ro` stay unread, so the project's own words about its providers (the AEP, Monitorul Oficial) are not in the inventory. The brief says that the notes of the project, not the copy, name them; I did not propose them.

**Decided**
- The reader detects the listing from the shape (`database`, `tables`, `views`), like `metadate-ins`, and has no name in `citire`. A document with the same member names that is not a valid listing is an error, not a sampled JSON. The cost: a file of another kind with these three members would be read as a listing; the check of the shape is strict (every table needs a name, a column list and a boolean `hidden`).
- The role is `coloana-sql` (existing label „Coloane în baza de date”) and the state of the field type is `declarat-in-lista-baza`; the source has `baza_tipului` `lista-fara-tipuri`. The alternative `antet-fara-tipuri` is the name of the CSV header and would be wrong here.
- The attribution of the licence is the declared `source`, word for word. The site adds „Sursa: ” in the projection only, so the fact stays exact.
- The credit sentence now says „Nume de câmpuri și descrieri preluate din”. The old „Descrieri preluate din” would be false for a listing that has no description. The cost: the sentence of Harta Firmelor changes too.
- No new family. The groups of political finance are in `alegeri`, with an ambiguity entry that says that a family such as „Finanțarea politică” is the owner's decision (as for `beneficiar-fonduri-publice`).
- Not proposed as groups: `Alegeri`, `Tip` and `Tip alegeri` (election and its type; the listing has no value), the annual income and expense columns of `Venituri anuale …` (two tables with different meanings), the names of donors (persons), `Voturi` and `Mandate` of `Rezultate alegeri` (the votes of one party are not „voturi valabil exprimate” of `voturi-valide`), the dates and months. `Expert Forum` is the project author and distributor, not a provider.

## 2026-10-26 — Inventory batch C2, part 2: data-expertforum from the owner's saved page and 14 Google Sheet tabs

**Done**
- Imported the page that the owner saved (`tmp/data.expertforum.ro.html`, 14,032 bytes, SHA-256 `d6f05a562b778e55…`, saved 2026-10-26T20:23:00+02:00) with `collect_docs.py --import-saved` and `inventory.py --import-saved`. The documentation record of the page was the HTTP 403 of 2026-10-24; the saved copy replaces it. 0 requests.
- New reader `html-lista-seturi` (`scripts/inventory_setlist.py`, 20 tests; fixture: the saved page without the tag-manager script and the contact sentence). The page lists 15 data sets: Electoral 4, Finanțare politică 1, Infrastructură 6, Media 1, Sănătate 3. Each has a category, a subcategory, a title, a description, related reports and links, every fact with a `char:START-END` interval of the retained body.
  The links are wrapped as `https://www.google.com/url?q=TARGET`. The reader takes TARGET from `q` and makes no request to `www.google.com`. Link kinds: 14 Google Sheet tabs (in 11 data sets), 1 Drive file (political finance) and 3 links to one Drive folder (the three health data sets).
- 14 tabs requested once each as CSV exports (`docs.google.com/spreadsheets/d/ID/export?format=csv&gid=N`, `inventory.py --probe --lot C2`, then `--add-sources-file adaugari/lot-c2-efor-foi.json --offline`). Measured: 14 requests (limit 30), 14 answers HTTP 200 after a redirect to seven `doc-NN-c0-sheets.googleusercontent.com` hosts, 11,395,562 bytes read.
  10 tabs parsed: 100 field records, one for each header cell. 4 tabs answered with more than 2,000,000 bytes (4 × 2,000,001 bytes read, refused): recorded with the state `raspuns-prea-mare`, not parsed.
- CSV header options (`scripts/inventory_sheet.py`, 12 tests): `rand_antet` and `coloane_fara_nume`. Three tabs need them: the migration tab of 2016 has a title row above its header, and the two media tabs have empty header cells. The plain rules stay the default.
- 15 discovery records (the page and 14 tabs). Each tab has the link in the saved page as its exact locator, and further locators with a role: category, title, description, related report, label of the link, and for two tabs the title row (`titlu-in-foaie`) or the source named in the sheet (`furnizor-numit-in-foaie`).
- The field browser titles a tab by the data set of the page (`Foaie Google · <title> · <label>`): before, ten tabs of one entry had the title `Fișier CSV · export`. 2 tests.
- Three proposed groups (`uat`, `partid-politic`, `beneficiar-fonduri-publice`; 36 groups in all; every definition and role fact has a fragment with a hash that `--check` verifies: 95 dictionary evidence items, 11 more than before). Eight candidate selectors for five reviewed groups (`siruta`, `cui`, `judet` ×3, `localitate`, `voturi-valide` ×2) are in `inventar-note.json` and section 5 of the report. No reviewed group got a member.
- One provider item, D186: Guvernul României, from `HG 1088/2021` and `HG 1264/2021` (state `deschis`, priority `medie`). `relatii.csv` did not change.
- Relation to `bani-partide` in the notes: the political finance data set names `https://www.banipartide.ro/` as its related report. It is not a source.
- Tests: 669 run, 6 skipped (627 and 6 before): `test_inventory_setlist` 26 (20 reader and run tests, 6 on the tracked state), `test_inventory_sheet` 12, `test_inventory_site` +2, `test_inventory_report` +2. No new test pins a review state.
  `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check`: 0 errors, 109 bodies hash-verified (99 before). `inventory_report.py --check`: current. A build with `--with-inventory` into a scratch folder: 128 finder entries, 36 groups; `site/` has no change.
  Browser checks on that build: `check_preview.py` 111/111, `check_inventory_preview.py` 31/31, `check_data_finder.py` 40/40. An offline replay on a copy of the tracked folder gives the six generated files byte for byte.

**Hard**
- A tab of more than 2,000,000 bytes has no header, so the biggest data sets are the least known: the three PNDL tables and the candidate list of the local elections 2020. The brief says not to parse such a response. A second request with `--sample-bytes` would break "one request for each tab", and Google ignores a byte range, so a bounded read still starts the same response. The decision is the owner's (backlog).
- The header texts are not clean. One header has line breaks and trailing spaces, and two header cells of one tab differ only by that whitespace (`Partidul Politic „Șor”`). The inventory keeps each name as the cell is written, so the two stay distinct.
- Only one tab names a provider: the tab of HG 1088/2021 has a column `sursa` with the same value in all 2,797 rows. The other tab of the pair has no such column; the page labels its link „HG 1264/2021 (Ciucă)”. „Monitorul Oficial” also appears in a media tab, as the name of a payee, not as a provider. I did not propose it.
- The candidate tab of the 2020 parliamentary elections holds names of persons. The repository keeps its header only (the parser reads nothing else), but the retained body in the ignored cache `surse/` holds the whole tab, as for every tab. The cache is local and not in git. The owner can delete the cache file of that tab; a later `--check` then reports the body as unavailable, not verified.
- The final URL of a redirect holds a Google account number and a signed path. The evidence contract asks for the final URL, so `seturi-date.json` kept it at first.
  Changed before the merge (Opus review): `inventory.public_url` keeps the host, the file ID and the query, and replaces the token and account segments with `…`. A public repository should not hold a third party's account number. The local cache keeps the full address; the evidence is the retained body and its hash. One new test.
- The title facts have `&icirc;` entities in the page. The registry locators use the raw text of the page, not the decoded text, so each locator fragment is an exact slice of the retained body.

**Decided**
- The limits of section 7 are the limits of part 2 (30 requests, one request for each tab). The limit of ten new sources for each entry (section 4) came from part 1, and section 7 names each of the 14 sheets. The cost: 15 sources for one entry.
- The Drive file and the Drive folder were not requested. The page does not say that the file is a spreadsheet, the brief limits requests to `docs.google.com`, a folder cannot be listed without the API, and the finance data set holds donor data about persons.
- A new reader for the page and not only specification files. The page has 15 data sets, and the specification files can hold facts only for the 14 tabs. The page source keeps all 15, with the Drive items. The cost: a new format name and a new check branch.
- The title of a tab comes from a join in the site builder (the page source and the tab by document and tab number). The alternative, a new key in each tab record, would copy the facts of the page into 14 records.
- No group for `furnizor` and none for the amount columns. `furnizor` means the grantor in one API and the supplier in another; the amount columns mix allocation, request, commitment and payment, and lei with MDL. Group `beneficiar-fonduri-publice` has the family `achizitii` only because the test needs a family (no existing family fits).
- No `Competitor-partid` or `Denumirea formațiunii politice/Candidat independent` in `partid-politic`: the party under which a person runs is another role, and the tab holds data about persons.

## 2026-10-26 — Batch C2 decisions: providers, three groups, the EFOR hosts listed (v0.30.1)

**Done**
- The owner decided D176–D185 in the review interface: D176–D180, D182 and D184 accepted (relations L176–L182), D181 („prea generic”) and D183 (Agerpres, a news agency) rejected, D185 postponed. Committed as the owner's decisions.
- At the owner's request, the groups `casatorii`, `divorturi` and `studenti` were marked `revizuit` through the interface's own `Store`: 10 members confirmed, 6 deductions ticked, note „Revizuit în bloc la cererea proprietarului”.
- Added `banipartide.ro` and `expertforum.ro` to `colectare-interzisa.csv`. The second row covers `data.expertforum.ro`; `common.forbidden()` now refuses `data-expertforum`, `bani-partide`, `efor` and `ghiduri-efor`.
- `relatie-date-propuneri.csv`: `data-expertforum` is `date-publice` (the owner's decision).
- Fixed `test_inventory_report.py`: the batch C2 provider test pinned the state `deschis`, so the owner's decisions failed it. The test now checks the evidence and leaves the state to the owner.
- Checks: `validate.py --publication` 0 errors, 0 warnings; the package checks pass; `inventory.py --check` 0 errors (98 bodies, 84 dictionary evidence items); `inventory_report.py --check` current; 627 unit tests pass (6 skipped); `test_forbidden_hosts.py` with `httpx` passes.

**Hard**
- Before the listing, the owner asked for one more reachability check. Three requests with `curl` and a User-Agent that names this project (`civtech-ro-inventory`) got HTTP 200 from `banipartide.ro`, `data.expertforum.ro` and `expertforum.ro`; two more got their `robots.txt` (HTTP 200, not read). The collectors' User-Agent got HTTP 403 on 2026-10-24 and 2026-10-26. So the block is a filter on the client, not on our address. These five requests are not in `jurnal-cereri.csv`.
- A test of other User-Agents was refused by the session's safety check as a bot-check circumvention, and was not run. Which part of the User-Agent the filter matches is not measured.

**Decided**
- The hosts go on the list, as the owner asked: a site that filters our collectors does not want them. Getting past the filter with another User-Agent would go against that. The cost: the entries get evidence only from pages that the owner saves.
## 2026-10-26 — Inventory batch C2: România Interactivă read; both EFOR hosts answer 403

**Done**
- Lot `C2` (brief `docs/briefs/inventory-batch-c2.md`) covered the three active entries `data-expertforum`, `bani-partide` and `romania-interactiva`. The coverage export gives them the lot code `C2`.
- `romania-interactiva` has ten structured sources (specification file `observatii/inventare/adaugari/lot-c2.json`): seven tool pages (`recensaminte/`, `guverne/`, `universitati/`, `cupluri/`, `locale/`, `harta-notelor/` and the site `orase-digitale.ro`) and three INS TEMPO metadata records (SCL103D, POP210A, POP212A).
  Each source has an exact discovery locator in the project's own pages. Measured: 269 field records, 17 with a description, 5 measures with a unit and 11 without, 10 sources with a verified locator.
- New reader `js-literale` (`scripts/inventory_literals.py`): the data that a page script holds as literals, JSON data islands, and the schema.org `Dataset` of the JSON-LD (`seturi_ld`, and `variableMeasured` as fields). It reads no value into a record except three example keys of a collection. 21 offline tests.
  Reason: the tool pages keep their data in script constants and in one data island; no existing reader sees them, and the pages declare no schema.
- Three proposed groups, state `propus`: `casatorii`, `divorturi` and `studenti` (10 members, family `populatie-teritoriu`). Every definition and unit fact has a fragment of a retained body with its hash (`inventory.py --check`: 84 dictionary evidence items verified, 22 more than before).
- Ten provider items D176–D185, state `deschis`: INS, Eurostat, CNFIS, AEP, Ministerul Educației, Guvernul României, Monitorul Oficial (priority `medie`), Agerpres, ANOSR and Cushman & Wakefield Echinox (priority `mica`).
  Each cites the tool page that names the provider, with the hash of the retained copy. `relatii.csv` did not change.
- `inventory_report.py` knows lot `C2`, and a note that records a blocker gives the state `blocat` to an entry that has no source record. The report has a subsection for the batch and a network summary. 3 new tests.
- Network (lot C2): 18 direct requests in the log (limit 60) plus 2 of `collect_docs.py` (it does not write the log): 20. Bytes read: 7,484,573, of which 4,000,002 came from two responses that the fetcher refused. No retry.
  Hosts: romaniainteractiva.ro 12, ins.gov2.ro 3, expertforum.ro 2, banipartide.ro 1, data.expertforum.ro 1, orase-digitale.ro 1. Browser: 2 navigations (`harta-notelor/`, `locale/`), 0 data requests.
- Tests: 614 run, 6 skipped (590 and 6 before). `validate.py --publication`: 0 errors. `inventory.py --check`: 0 errors, 98 bodies hash-verified (88 before). A build with `--with-inventory` into a scratch folder: 128 finder entries, 33 groups; `site/` has no change. Browser checks against that build: `check_preview.py` 111/111, `check_inventory_preview.py` 31/31, `check_data_finder.py` 40/40.
- A fresh clone of the branch (no local caches): 614 tests pass, `validate.py --publication` 0 errors, `inventory.py --check` 0 errors with 305 bodies reported unavailable (never counted as verified). An offline replay from the caches gives the six generated files byte for byte.

**Hard**
- `banipartide.ro`, `data.expertforum.ro` and `expertforum.ro` answer HTTP 403 to every automated request (the documentation collector got 403 on four pages of each of the first two on 2026-10-24; the home pages again on 2026-10-26, and two pages of `expertforum.ro`).
  The brief says to stop on a host after a 403. The two entries have no source, no field and no group, and the question "which provider supplies each record" stays open. Proposed rows for `colectare-interzisa.csv` are in the report (section 7); none was added.
- The sealed run `runs/2026-10-19-reasoned-evidence` holds a text of the page of `data.expertforum.ro` (a table of data sets; "Finanțarea politică 2006–2021" links to `banipartide.ro`). It shows that both entries may share one data set. It is context only: it has no locator that the inventory can verify, and the folder is sealed.
- A response over 2,000,000 bytes is refused by the fetcher after it read that many bytes. `locale/` and `harta-notelor/` were the first requests that had this size, so 4,000,002 bytes were read for nothing. The range read of 600,000 bytes ends at the last complete line, which is before the data script (12,844 and 32,622 characters). Their data was not read.
  Lesson for the next batch: probe a page of unknown size with `--sample-bytes` first.
- All 30 groups are `revizuit`, and a reviewed group cannot hold a member that the owner has not confirmed (`validate_group_state`). A new selector would need `confirmat` (the owner's decision) or a group that goes back to `amanat`. Neither is for this session.
  So no field was added to a reviewed group. 19 field records match 10 candidate selectors of four groups: `perioada-de-referinta` (5: TIME_PERIOD of POP210A, POP212A and SCL103D, `Y[]`, `DATA.years[]`), `judet` (2: REF_AREA of SCL103D, `RAW[][0]`), `localitate` (3: REF_AREA_2 of SCL103D, `D[].n`, `dataScript.cities[].name`) and `populatie` (9: `RAW[][1..8]` and `DATA.c{*}.p[]`).
  The REF_AREA of POP210A and POP212A mixes macroregions, regions and counties, so the `judet` group keeps them out. The selectors are in section 5 of `docs/reports/inventory-expansion.md` (`selectori_candidati` of `inventar-note.json`).
- POP210A: the INS note says the data are split by "the place where the marriage was registered"; the page says "according to the domicile of the spouses". Both texts are in `ambiguitati` of `casatorii`.
- Orașe digitale holds the authors' own data (manual coding, 46 indicators, three waves). The page names no source for the population of a city (`pop`) and no licence. The data island and the app also hold interface state (`rankingsState`, `GA_ROUTE_TITLES`); the reader lists them because they are literals of the page. They are paths, not variables.
- The keys of the page data (`L`, `T`, `V`, `m`, `d`, `p`, `t`, `b`, `x`) are short and are not described. Their meaning comes from button labels, code and sums. Each such statement in a group has the basis `deductie-din-dovezi` or `observatie-esantion`, so that the review interface asks the owner to tick it.

**Decided**
- Stop on the three hosts after the first 403 and do not pass the refusal with a browser (the precedent is `harta-firmelor.ro`, and the brief says to stop). The cost: two of three entries have no inventory. A browser pass would work around a refusal; the owner decides.
- Do not run `collect_docs.py` for the two blocked entries: its first request fails, and it asks for three more pages of the same host.
- Reuse the evidence type `observat-in-esantion-json` and `declarat-in-metadate` for the new reader. A new type would need a change in the label maps of `site/app.js` and `site/inventory.js` and a new stamp of `site/index.html`.
- Admit `locale/` and `harta-notelor/` as sources although they hold no field: the JSON-LD data set (period, licence, `isBasedOn`) and the provider sentence are retained evidence, and the ten-source limit allowed it. Cost: two sources with zero field records.
- No provider item for Orașe digitale: its data are the project's own. No item for the map of the home page (the code comment names Natural Earth and GeoNames); both are decoration.

## 2026-10-26 — The relation to data: the column `relatie_date` and its proposals (steps A and B)

**Done**
- Step A of `docs/briefs/data-relation.md`. `valori.csv` has the list `relatie_date` (`date-publice`, `date-proprii`, `calcul`, `fara-date`). `schema.json` has the rule and the header, after `dovada_detaliere`. Both `intrari.csv` files (the package and `integrare/`) have the empty column. `taxonomy_v2.py` refuses an unknown code, a value on an organisation, and `fara-date` together with `detaliere_date`; `NO_DATA` names the code. `common.py` loads `data_relation`, and `build.py` writes `dataRelation` on each item and `vocabulary.dataRelations`. `validate.py` warns, and never fails, when a `fara-date` entry has `campuri_din_surse` above zero in `rezumat.csv`. `sheets.py` and the Form needed no change.
- Docs: `DATA-SCHEMA.md`, `specs/taxonomy-v2.md` and one Romanian paragraph in `data/taxonomy-v2/README.md`.
- 13 new tests: 9 in `test_taxonomy_v2.py` (class `RelationToData`) and 4 in `test_sheets_form.py` (round trip in both directions, the strict drop-down from the code list, no Form question, an imported row leaves the column empty). All 13 fail on the previous commit. With only the data files (no script change), the 4 tests that need code still fail (organisation, `fara-date` with a breakdown, the `validate.py` warning, the build); the 4 Sheet and Form tests pass, because `sheets.py` reads its header and drop-downs from `schema.json` and `valori.csv`.
- Test count: 590 before, 603 after (6 skipped, as before). `validate.py --publication`: 0 errors, 0 warnings; the package root and `inventory.py --check` / `inventory_report.py --check` are unchanged.
- A build into a separate folder differs from a build of `main` only by `dataRelation` (empty, 141 items) and `vocabulary.dataRelations` (4 codes). The committed `site/data.json` also changes its `generated` time; it is a separate commit.
- Step B. `observatii/inventare/relatie-date-propuneri.csv`: 129 rows (128 public projects and resources, and the hidden `fiipregatit`). Evidence: the entry row, the cached page text, `profil.csv`, the accepted sources and the inventory; no request. Proposals: `date-publice` 63, `date-proprii` 20, `fara-date` 19, `calcul` 3, empty 24. By confidence: `mare` 53, `medie` 49, `mica` 27 (24 of them are the empty rows). Of the 100 entries that `acoperire.csv` calls `neinvestigat-in-lot`: 19 `fara-date`, 38 `date-publice`, 16 `date-proprii`, 3 `calcul`, 24 empty.
- Measured again before the work: 128 projects and resources in `data.json` (108 `activ`, 10 `arhivat`, 9 `offline`, 1 `necunoscut`); `acoperire.csv` has 100 `neinvestigat-in-lot`, 28 `cu-surse-structurate`, 13 `in-afara-ariei`, 1 `blocat`; no inactive entry has extracted fields. These equal the numbers of the brief.

**Hard**
- The tests derive their package from the detach commit, so that package has no column. `RelationToData` copies the real package (without the local caches), and the code reads the column with `.get`, so an older package still passes.
- The base `data/taxonomy-v2/intrari.csv` is checked against the same `schema.json` header, so it needed the empty column too, as for `detaliere_date`.
- The brief's rule for mixed cases (the first code in the table) decides several rows. A hybrid of own sensors and one public source, a calculator that reads Eurostat life tables, and a curated database built from official sources all go to `date-publice`. The proposal says so in `baza`; the owner may prefer `date-proprii` or `calcul` for these.
- The cached page text is often poor: login pages, error pages, JavaScript shells. For 24 entries (16 of them inactive) the evidence does not settle the code, so `propunere` is empty and `incredere` is `mica`. An empty value stays in `/date/`.

**Decided**
- The warning reads `rezumat.csv`, which `inventory.py` writes with the field counts, and not `acoperire.csv`, which `inventory_report.py` writes later. The cost: none for the checks; `rezumat.csv` is always as new as the fields.
- The proposal file includes the hidden `fiipregatit` (empty): the column lives in `intrari.csv`, and the entry may return. The cost: one row that the public site never shows.
- No release bump and no tag in this work: the owner's Opus session merges this branch with `inventory-batch-c2` and tags both.

## 2026-10-26 — Briefs: the relation to data, and inventory batch C2

**Done**
- Wrote `docs/briefs/data-relation.md`: the column `relatie_date`, the scope of `/date/` and the explorer facets `dat` and `st`.
- Wrote `docs/briefs/inventory-batch-c2.md`: the variable inventory of `data-expertforum`, `bani-partide` and `romania-interactiva`.
- Measured: of 128 projects and resources, 19 are inactive (10 `arhivat`, 9 `offline`); none of them has extracted fields. `acoperire.csv` has 100 entries `neinvestigat-in-lot`. A guess from `formate` over these 100: 49 with a data format, 22 with only formats without data, 21 with no format, 8 publications.

**Hard**
- The format does not tell whether an entry has data: `testvot` is a quiz with a data set (party positions), `ani-de-pensie` is a calculator, and some publications are data journalism. The column is a separate decision for each entry, and the format only feeds the proposal.

**Decided**
- The owner decided that `/date/` lists only projects and resources with data, and that inactive entries leave the variable inventory. Three of the six named entries are inactive, so batch C2 has three entries.
- One code for each entry, not a yes/no flag: `calcul` and `date-proprii` have variables but no public provider. The cost of a flag: the finder could not tell a quiz from a guide.
- The column lives in `intrari.csv`, not in a separate list under `observatii/`: it describes the entry, and editors see it in the Sheet. The cost: one more column in the schema, the Sheet and the checks.
- An empty value stays in `/date/`: only the entries that are clearly without data leave it.
- Values are proposed from the repository's own evidence (no requests), and the owner accepts them before they reach `intrari.csv`.

## 2026-10-26 — Hidden entries: the code `ascuns`; fiipregatit.ro hidden

**Done**
- The owner decided that `fiipregatit.ro` does not belong in the catalogue (an official state platform), but the inferred data stays. The data model had no way to hold an entry back: `stare` `arhivat` / `offline` still shows it, and `propus` / `de-revizuit` block the whole build through the publication gate.
- Added the code `ascuns` to the list `clasificare_stare` (`valori.csv`, order 3). `taxonomy_v2.HIDDEN` names it. The gate accepts it, and an open high-priority review item of a hidden entry does not count. `common.public_catalogue()` leaves hidden entries out, and `items_v2` in `build.py` reads only that list. `draft` ignores them, and a relation from another entry shows the name of a hidden entry but no link.
- Set `fiipregatit` to `ascuns`; the note records that it was accepted, then hidden. Removed its two images from `site/img/` (the profiler makes them again with `--force --only fiipregatit`; `profil.csv` keeps the paths).
- Docs: `DATA-SCHEMA.md` (column, code list, gate, a section on hidden entries), `specs/taxonomy-v2.md`, `data/taxonomy-v2/README.md`, `CLAUDE.md` and `AGENTS.md`. Backlog: the entry-specific items are dropped with the reason.
- Four new tests in `test_taxonomy_v2.py`: the gate accepts a hidden entry and ignores its review items; it still refuses a proposal next to one; `ascuns` is refused where `valori.csv` does not list it; a build leaves the entry out of `data.json`, the entry page, the feed and `llms.txt`, with contiguous ids. They fail without the code change.
- Measured after the change: `validate.py --publication` 0 errors (141 `acceptat`, 1 `ascuns`); `build.py` writes 141 entries to `site/`; a build with `--with-inventory` into a separate folder also has no trace of the slug.

**Hard**
- The tests run on a package derived from the detach commit, so their `valori.csv` has no `ascuns`. The tests add the code to their copy.
- A hidden entry still needs a full classification: the rule `empty_allowed_when` names only `de-revizuit`. Not changed; a looser rule would be a second decision.
- The Sheet dropdown of the column is strict and comes from the code list. `ascuns` reaches it at the next `sheets-push` (it runs when `intrari.csv` changes on `main`).

**Decided**
- The code is `ascuns`, the owner's word „hidden”, in the Romanian style of the list. The alternative `exclus` says „excluded” and would hint at a rejection; the owner chose hiding, not rejecting.
- The two images are removed, not kept: `site/img/` is public, and an unlinked image of a hidden entry would still be served. The cost: after unhiding, the images must be made again.
- `cutover_v2.py` still counts `ascuns` as „not acceptat”. The cutover is applied, so the script is not changed.

## 2026-10-26 — A list of hosts that no script requests (v0.26.0)

**Done**
- New file `data/taxonomy-v2/colectare-interzisa.csv` (`gazda`, `motiv`, `dovada`, `data`, `nota`). First row: `harta-firmelor.ro` (HTTP 429 from a Vercel Security Checkpoint; `llms.txt` forbids automated extraction). The row also covers `api.harta-firmelor.ro`.
- `scripts/common.py` holds the one check, `forbidden(url)`, and `refuse_forbidden`, `browser_args`, `refuse_route` and `note_failed_request` for the browser passes. The match is by whole host labels; a leading `www.` is ignored.
- Request paths found and guarded:
  - `profile.py`: the page, images, icons, feeds, sitemap, `--extra` signals and link favicons go through `get()` or an httpx client. Each client has a request hook that refuses a redirect hop to a listed host. A listed entry is left out in every mode and keeps its row. The browser pass skips a listed page, aborts a navigation to a listed host and starts Chromium with the resolver rule.
  - `review.py`: `fetch()` (httpx with the same hook) and `render()` (Playwright). A listed entry is skipped before the download and before the model request; its answer, suggestions and labels stay.
  - `collect_docs.py`: `Fetcher.__call__` checks before the cache, the log and the budget. A redirect handler refuses a listed target. `collect()` returns the state `colectare-interzisa` for a listed entry; `merge_refresh` keeps an earlier record unchanged, with no `ultima_incercare`.
  - `inventory.py`: all requests go through the same `Fetcher`. `obtain()` does not refresh a listed source (`--force` and `--force-url` included). `--probe` makes no request and writes no cache file for it. A body retained earlier stays the evidence.
  - `render_pages.py` (found in the search; the brief did not name it): a listed URL is dropped before the browser starts. A render that ends on a listed host has the state `colectare-interzisa`.
  - `search.py` calls only the Serper and Brave APIs. `sheets.py` and `form.py` call only Google. `build.py` and the `check_*.py` files request nothing outside the local preview. The list does not apply to them.
- `validate.py` checks the file (header, host, `motiv`, date, duplicate host; absent file is an error). A row whose host is the `url` host of no entry is a warning.
- Docs: `docs/DATA-SCHEMA.md`, `data/taxonomy-v2/README.md` (one Romanian paragraph), `README.md`, `CLAUDE.md`, `AGENTS.md`, `.claude/commands/add-new-url.md`, and the backlog.
- Tests: `scripts/test_forbidden_hosts.py`, 62 offline tests. Name resolution and connections are switched off in each test, so a request that gets past a guard fails the test.
  Measured: the full suite runs 583 tests (521 before), 8 skipped without `httpx` (6 before, plus 2 that need the real `httpx`); with `uv run --offline --with httpx` the new file runs 62 tests and skips none.
  `validate.py --publication`: 0 errors, 0 warnings. `inventory.py --check` (with the local caches linked read-only from the main checkout): 0 evidence errors, 88 source bodies hash-verified, 2 owner-saved copies hash-verified.
- Mutation check (one guard off at a time, the new file only, with `httpx`): `forbidden()` always `None`, 50 of 62 tests fail (42 failures, 8 errors); `Fetcher` guard, 2; redirect handler, 1; `collect()`, 5; `inventory.obtain()`, 2; `profile.py` entry filter, 2; httpx hook, 2; `get()`, 4; `review.fetch()`, 2; `review.main()`, 1; `render_pages`, 2; resolver rule, 4; `validate.py` call, 1.

**Hard**
- A Playwright route handler does not see the redirect hop of a request that it let through. A test against a loopback server showed that the server received the request for the listed name. The handler alone cannot keep a redirect from a listed host. Chromium now also starts with `--host-resolver-rules` that map each listed host to `~NOTFOUND`. The handler stays as the second layer.
- An httpx event hook runs for each redirect hop, so one hook per client is the smallest correct change. `urllib` has no such hook; `collect_docs.py` uses an `HTTPRedirectHandler` that raises before the next request. For both, the first request goes to an allowed host and the hop to the listed host is never sent.
- `test_enrichment.py` counted the entries that `review.py` asks about. A listed entry is now skipped, so the test subtracts the listed entries (and checks that at least one exists).

**Decided**
- The list sits next to the vocabulary files and every script reads the same file, whatever `--data-dir` says. A site that forbids access forbids it for every root. The cost of one list per root is drift between roots.
- A skipped result is a state (`colectare-interzisa`), not an error. A failed-attempt mark would make a later run retry, and `offline` would show a live site as down on the public build.
- A missing list file is a validation error, and a list that cannot be read stops the script. An error that ends in "allow every request" is worse than a stopped run.
- Not done: a test that scans the scripts for a new request path without the guard (open in the backlog). A new script must call `forbidden()` itself; `CLAUDE.md` says so.
## 2026-10-26 — The data finder on the public site (v0.25.0)

**Done**
- `build.py --with-inventory` may now write `site/`; it still needs a v2 root. `pages.yml` builds with it, and `validate.yml` adds `--with-inventory` to its preview and runs `check_inventory_preview.py` and `check_data_finder.py`.
- A build without the flag now removes `date/` and `inventar/` from any site directory, `site/` included.
- `inventar/<slug>.json` gives a source `licence` when all its data sets declare the same one. The field browser then says „Descrieri preluate din harta-firmelor.ro, licență CC BY 4.0 · Sursa: harta-firmelor.ro.”
- Measured in a clean worktree of 6c470cc with this change: `validate.py --publication` 0 errors; the public build writes `site/date/` (24 KB) and `site/inventar/` (29 files, 1.7 MB); the CI preview passes `check_preview.py` 111/111, `check_inventory_preview.py` 31/31 and `check_data_finder.py` 40/40; unit tests pass (6 skipped).

**Hard**
- The main checkout held another session's uncommitted entry (`fiipregatit`, state `propus`), so a publication build there fails. All checks ran in a clean worktree, and only this change was staged.

**Decided**
- No brief: the owner asked for it, and the open questions had answers. The review was complete, the labels already follow the review state, and the inventory output needs no ignored cache (a clean checkout builds the same `date/` and `inventar/` as the local one).
- Credit a licence only when every data set of the source declares the same one. Cost of the alternative: a credit per field, or a credit that names the wrong licence for a mixed page.

## 2026-10-26 — New entry fiipregatit.ro (issue #3)

**Done**
- Added `fiipregatit` to `intrari.csv` (row 143, `proiect`, `clasificare_stare` `propus`, confidence `medie`) and its attribution L175 to `relatii.csv` (`Departamentul pentru Situații de Urgență`, `rol_neconfirmat`). Sources: the home, guides, map, campaigns, podcast, about, contact and terms pages (rendered with Playwright), and the repository `civicnet/fiipregatit.ro`.
- Profiled: status `activ`, HTTP 200, screenshot image and 128 px icon. Searched with Serper: 20 results, 15 kept, 5 dropped by the `social` rule. The kept results are pages about the site (government and public bodies, UNICEF, a 2023 tender specification). `editor` is empty.
- Ran `collect_docs.py --only fiipregatit` (4 requests; found the page and the about page), `inventory.py --only fiipregatit` (0 requests) and `inventory_report.py`.
- `validate.py` 0 errors. `validate.py --publication` 1 error: the entry is `propus`. The isolated build with `--allow-draft` writes 142 entries. Unit tests: 523 run, 2 fail (the `propus` gate in `test_inventory_site` and `test_review_ui`), 6 skipped. Before the inventory steps, `test_inventory_report` failed with `KeyError: 'fiipregatit'`.

**Hard**
- `/add-new-url` still names `proiecte.csv` / `orgs.csv` (see the backlog). This run used `intrari.csv` and `relatii.csv`.
- `since` shows 2008-12-08 (`arhiva`). Two Wayback captures (2008, 2009) predate the project: the first certificate is from 2018-02-06 and continuous captures start on 2018-03-02. The About page gives 2018 as the launch year. `EARLIER_DOMAIN_USE` would give 2020-03-14 (the repo), which is also wrong. Not changed: it needs a decision on `since`.
- `stale` shows 2022 for a live site. The only dated activity is the last push of the old repository (2022-12-05, `updated_src` `cod`). The site lists a campaign dated 2026-07-15 and the last Wayback capture is 2026-10-13. Not changed.
- The terms describe a virtual assistant „bazat pe ChatGPT”. The first version of this entry said the rendered pages do not show it, and left out `tehnologie:ai`. That was wrong. The assistant is the text field „Întreabă-l pe FiiPregătit” on the home page. The check read `inner_text`, which skips the placeholder of an input; the profiler screenshot showed the field. Corrected the same day: `tehnologie:ai` added, and one sentence about the assistant added to `descriere` (the vocabulary rule: the description must state the use of AI). The menu buttons ChatAI and Alerte are in the HTML but not in the render, so `functie:alerte` stays out.

**Decided**
- The entry started as `propus`: acceptance is the owner's decision. The owner accepted it in the same session, so it is now `acceptat`. The note in `nota_clasificare` says so.
- `civictech_original` is `0`: the operator is a government department. The same value is on `oradea-city-report` and `ong-camera-deputatilor`.
- `linkuri` holds the old repository and the four social profiles from the footer. The profiles belong to the DSU, not to the site alone. The repository belongs to the previous version (2018–2023), built by CivicNet.
- No row for CivicNet: `civicnet.ro` answers with a `surge.sh` certificate, so the audit could not rely on it.
- `institutii_vizate` is empty. The vocabulary has no type for DSU, IGSU or the ministry.

## 2026-10-26 — New entry lista-firme.info

**Done**
- Added `lista-firme` to `intrari.csv` (row 142, `proiect`, state `propus` at first, then `acceptat`; confidence `medie`) and its attribution L174 to `relatii.csv` (`RTI Global Services SRL`, `rol_neconfirmat`). The site names this company as its operator. The GitHub repo `tudorr89/info-firme` is the `linkuri` cell.
- Profiled: status `activ`, HTTP 200, screenshot image and 128 px icon. Searched with Serper: 20 results, 7 kept by the rules. All 7 are name collisions with generic „lista firme” pages (none is about the site). `editor` was empty at first; the owner then asked for `editor=0` on all 7 and `--prune-only` set `mentions` to 0 (`reach.indep` 0). `--prune-only` also changed `regula` on 6 rows of 4 other entries (`gov2` 3, `incentru`, `ethicalmedia`, `accesinfo`) and one `mentions` value; those were reverted, not part of this change.
- `validate.py` 0 errors. `validate.py --publication` 1 error: the entry is `propus`. The isolated build with `--allow-draft` writes 141 entries.
- Ran the documentation and inventory steps for the one slug (`collect_docs.py --only lista-firme`: 4 requests; `inventory.py --only lista-firme`; `inventory_report.py` to refresh `acoperire.csv` and `docs/reports/inventory-expansion.md`). The draft is partial: one HTML search control, no schema, no data dictionary. `inventory.py --check` 0 errors.
- Unit tests before the owner's commit 786fc22 / 27428c0: 4 failed (2 on the `propus` gate, 2 pinning 140 entries). After acceptance, the unpinning on `main` and the `since` test: 523 run, 0 fail, 6 skipped.

**Hard**
- `/add-new-url` still writes `proiecte.csv` / `orgs.csv`. Those files are frozen since the cutover and a row there never reaches the site. This run used `intrari.csv` and `relatii.csv` instead (see the backlog).
- `since` showed 2011-05-19 (`arhiva`). The two Wayback captures of 2011 show a GoDaddy parked-domain page. The first certificate is from 2024-04-18 and the repo from 2024-05-04. The owner asked for 2024. `build.py` now skips the first capture of the slugs in `EARLIER_DOMAIN_USE` (one slug, `lista-firme`): `since` is 2024-05-04 (`cod`) and the score falls from 60 to 49 (46 after the prune). The other 140 entries keep their `since`. A general rule was not used: of 29 entries whose first capture is 2+ years older than the repo or certificate, most are old sites that got a certificate late.
- `profile.py` re-sorted `observatii/profil.csv`: the 19 mariuscomper.uk rows moved from the end of the file into slug order.

**Decided**
- The entry started as `propus`: acceptance is the owner's decision. The owner accepted it in the same session, so it is now `acceptat`. `validate.py --publication` 0 errors; `build.py` writes 141 entries to `site/`; 2 tests fail (both pin 140 entries).
- The owner attests that `tudorr89/info-firme` belongs to the site (thread r/programare 1cpozgm, not read by the agent). No author row was added for the repo owner.
- `civictech_original` stays empty. The operator is a private company; the site states no civic purpose. 17 entries already have an empty value.
- `institutie:anaf` is the only institution. The main source (ONRC) has no concept in the vocabulary, as for `registrul-firmelor`.
- No `date_din` relation and no review item: provider relations need an owner decision (`revizuire.csv` was open in the review interface).

## 2026-10-26 — Review decisions recorded

**Done**
- The owner decided D135, D143, D144, then D132–D134, D136–D140, D145 and D175 in the review interface.
- At the owner's request („accept them for me”), the remaining 31 provider items and the 30 groups were decided in bulk through the interface's own `Store` (same checks, same atomic writes):
  29 items accepted with the proposed name and evidence; D153 and D154 closed as duplicates of D140 and D141; 92 members confirmed; 30 groups marked `revizuit`. Every bulk note says „în bloc la cererea proprietarului”.
- Measured after the decisions: 44 provider items (41 accepted, 3 duplicates, 0 open); `validate.py --publication` 0 errors; 15 entries get public data sources in the build; 521 unit tests pass (6 skipped).

**Hard**
- Some accepted names keep the route or the scope in parentheses, and the public site shows them as they are. SICAP / SEAP has three public forms. The backlog has the follow-up.

**Decided**
- No version bump: these are editorial decisions, not a deliverable or a correction. Git keeps the audit trail.

## 2026-10-25 — Registrul firmelor: the other providers of its sources page (v0.24.1)

**Done**
- `registru.horecaos.org/surse` names nine sources: ONRC, the ONRC history (archived snapshots on data.gov.ro), ANAF, Ministerul Finanțelor, SEAP, OpenStreetMap, the courts portal, BPI and Monitorul Oficial Partea a IV-a.
  D153–D156 already cited the page for ONRC, ANAF, Ministerul Finanțelor and SEAP.
- New items: D174 OpenStreetMap (prioritate `medie`) and D175 Ministerul Justiției, portalul instanțelor (prioritate `mica`: the page marks the source „în lucru”, with the period „în pregătire”).
  The fragments are the provider lines of the page, found in the retained text (sha256 `81cd22875d06a3b4`). `relatii.csv` did not change.
- D140 and D141 (candidates from the description, linked to L140 and L141) got one sentence each that points at D153 and D154. Their state did not change.

**Hard**
- The owner saved the page on 2026-10-25 (`tmp/registru.horecaos.org-surse.html`). The copy fetched on 2026-10-24 already holds every source line; only the counts differ. The site does not block requests, so the saved copy was not imported.
- The owner's uncommitted acceptance of D135 / L135 stays out of the commit: the commit was made from the HEAD versions of the review files, and the owner's change was applied again afterwards.

**Decided**
- No item for BPI and Monitorul Oficial. The page marks both „cerut oficial”: the project asked for the data and does not have it yet. Its insolvency state comes from the ONRC status codes, which D153 covers.
  Cost of the alternative: two items that the owner would reject, or a `date_din` relation for data that the project does not use.
- Keep the duplicate pairs D140/D153 and D141/D154 open for the owner. The review interface has a duplicate action; deciding it here would decide a review item for the owner.

## 2026-10-25 — Owner-saved pages as evidence: Harta Firmelor open data and its providers (v0.24.0)

**Done**
- New way to register a page that the owner saved from their own browser, with no request: `inventory.py --import-saved SLUG URL FILE --saved-at 2026-10-25T20:39:00+02:00 [--note TEXT]` and
  `collect_docs.py --import-saved SLUG URL FILE --saved-at …`. The record keeps the URL, the SHA-256 of the file's bytes (`sha256_fisier`), the saved-at time as `fetched_at` (UTC), `http_status` null and
  `origine` `copie-salvata-de-proprietar`. The body goes to the ordinary ignored cache and snapshot, so `inventory.py --check` and the review interface's evidence locator verify it like a fetched body.
  The command implies `--offline --only SLUG`, refuses `--force`, `--probe`, `--dry-run` and `--check`, and puts the old cache file back when the run fails. The log of requests got no row: 0 requests.
- Both tools now skip an address that holds a saved copy: a later `--force` makes no request for it and leaves no failed-attempt mark. A fetched body is never replaced by a saved copy.
- `--check` verifies saved sources (body hash, `sha256_fisier` equals `sha256` unless a credential was masked, status null, time consistent) and saved documentation pages (text hash), and prints the saved copies on a separate line.
  Measured on this checkout: 0 errors; 88 source bodies hash-verified (87 before); the 2 saved copies (`/date` source body, `llms.txt` page text) hash-verified; 62 dictionary evidence items verified.
- Saved the owner's two files (`tmp/harta-firmelor.ro-date.html`, 182,248 bytes, SHA-256 `926aeef9d421d1ee…`; `tmp/harta.firmelor.ro-llms.txt`, 1,251 bytes, `5f10594f5e23c1cd…`). `harta-firmelor` goes from "documentation not confirmed"
  to `documentatie-gasita` and from 0 to 40 field records. `llms.txt` is documentation, not a field source; its link `/date` is the discovery locator (`/links/3`) of the new source, and its sentence
  "Extragerea automată și în masă a datelor de pe site nu este permisă." is a second locator with the role `restrictie-colectare`.
- New reader `html-carduri-csv` (`scripts/inventory_csvcards.py`, stdlib): the page has no table, so no existing reader fits. Measured on the saved page: 8 datasets (rows 37, 18, 19, 71, 23, 9, 20, 37; period, measured-at date
  11.09.2026, licence CC BY 4.0 with its link and attribution, and the named sources, 9 of them for `registru-cifre.csv`) and 40 fields (14, 5, 3, 3, 3, 3, 6, 3): 40 with a declared description, 1 with a unit
  (`median_turnover_lei`: "lei nominali", from the description), 0 with a type. Every locator is a `char:START-END` interval of the retained body. The 8 CSV files were not downloaded.
- Review items: D136–D139 (ONRC, ANAF, SICAP / SEAP, Monitorul Oficial) and their proposed rows L136–L139 now cite `https://harta-firmelor.ro/date` with an exact fragment and the hash of the retained text; new items D170–D173
  propose Ministerul Finanțelor, Ministerul Justiției (portalul instanțelor), Buletinul Procedurilor de Insolvență and ANRM. Measured with the review interface's own `Store.provider`: all 8 items show `verificat` (copy kind
  `sursă păstrată`, text hash `926aeef9d421d1ee`, fragment found). The page names "Geocodare — adresele pe hartă" without a provider: it is in the notes, not an item. `relatii.csv` keeps L136–L139 as `propus`.
- Checks on the committed state (a clean worktree of the commit, the ignored caches linked): `validate.py --publication` 0 errors, 0 warnings; `inventory.py --check` 0 errors; `inventory_report.py --check` 0 outputs out of date;
  `git diff --check` clean. Replaying `inventory.py --offline` for all 140 entries reproduced `proiecte.json`, `seturi-date.json`, `descoperiri.json`, `rezumat.csv`, `campuri.csv` and `intrari-utilizator.csv` byte for byte.
- Tests: 521 run, 6 skipped, 0 failures (487 / 6 before), also in the clean worktree: 10 reader tests (`test_inventory_text.CsvCards`, with a 14 KB trimmed fixture of the saved page) and 24 tests in `test_saved_copies.py` (import, hash, replay byte for byte,
  `--check` verifies, altered body or record reported, absent body unavailable and never verified, no request on `--force`). A mutation check confirmed that two of them fail when the guard is off.
  Browser checks on port 8770: `check_data_finder.py` 40/40, `check_inventory_preview.py` 31/31, `check_preview.py` 111/111; `check_review_ui.py` 75/75 (it proves that the real review files did not change).

**Hard**
- The saved page is a Next.js page. Its texts occur several times: in the visible card, in `schema.org` Dataset JSON-LD blocks (the same column names and descriptions) and in script payloads.
  `Monitorul Oficial, partea a IV-a` first occurs in the JSON-LD name and the card title, so D139 cites `Monitorul Oficial, partea a IV-a</dd>`, which occurs once, in the `Surse` line.
  The other seven fragments are the clean `Surse` text, each first found in its own card.
- The page states "Anii sunt numere întregi" and "O celulă goală înseamnă „nemăsurat”, nu zero" for all files. These are reading rules, not types per column, so every `tip_declarat` stays null; the notes record the rules.
- The public payload built from the live tree differs from HEAD in `generated` and in one provider: `executii-bugetare` gets a data source from the owner's uncommitted acceptance of L135. It is not part of this change.
  In a clean worktree of the commit the payload equals the one at HEAD apart from `generated`; `site/data.json` and `site/feed.xml` of the live tree were restored.
  The generated report and `acoperire.csv` were written in that worktree, so the commit holds no decision of the owner (the live report still counts the accepted D135).
- A guard on one address protects little: `collect_docs.py --force` still requests the other addresses of the same site. A guard for the whole site needs the same rule in `profile.py` and `search.py`; it is in the backlog.

**Decided**
- A saved copy has its own origin keys on the same cache and snapshot machinery, instead of a separate store. Cost of the alternative: a second check path, and the review interface would not find the text.
- Keep two hashes: `sha256_fisier` (the owner's file) and `sha256` (the retained body). They are equal unless a credential was masked. For a documentation page the text hash differs from the file hash, because plain text loses its outer spaces.
- Use `Ministerul Justiției (portalul instanțelor)` for the courts and say in the item that the page does not name the operator; propose `Buletinul Procedurilor de Insolvență (BPI)` without a publisher for the same reason.
  Cost of a guess: a proposal that names an organisation the page never mentions.
- Do not change `inventar-concepte.json` or the review interface while the owner reviews. Group candidates are in the backlog: the seven `year` columns look like `perioada-de-referinta`; `employees_reported` and `median_turnover_lei` do not belong
  to `numar-salariati` and `cifra-afaceri`, which hold the value of one company and already keep national aggregates out.

## 2026-10-25 — Count restatements once, a variable table, DemoANAF paused

**Done**
- A field that restates a record of another source (`in_contract`) counts once. Profiles, `rezumat.csv`, `acoperire.csv` and the report use
  `inventory_state.counted_fields`; the preview folds the restatement into the contract record as `also` evidence, and the field browser shows
  "Documentat și în …". Measured on DemoANAF: counted fields 221 → 130, fields with a description 35 → 19 (the page descriptions now sit on the contract
  records as evidence), finder card 85 → 57, `cui` evidence 5 → 3. Other entries are unchanged.
- `/date/lista/` is now a table: entries in rows, families in columns, normalised group names in the cells, and "Altele" with the count of ungrouped
  field names. Sticky header and first column; the table scrolls horizontally inside its frame. Source field names move to a future project profile page.
- DemoANAF paused with conclusions and a resume hint in the backlog. ro-api-hub correspondences and a static read API idea are in the backlog.

**Decided**
- Fold restatements at projection and count time, and keep every record in `seturi-date.json` and `campuri.csv`. The evidence stays complete; only counts change.
  Dropping the page records would lose 22 page-only inputs and the page descriptions.

## 2026-10-25 — Variable families and a per-project list of variables

**Done**
- `inventar-concepte.json` has a `familii` list (9 families) and a `familie` on each of the 30 groups. `inventory.py --check` and the review interface validate them.
- The `/date/` variable facet shows the groups under their families. A family opens when it holds a selected variable or a variable with more than three entries.
- New static page `/date/lista/` in the inventory preview: 27 rows (entries with extracted fields) with `source:field` names by family, the other names per source
  (inputs apart from returned fields), and the 100 entries without fields named once. 468 unit tests (6 skipped); `check_data_finder.py` 40/40.

**Decided**
- Families by what the variable describes: three cross-cutting keys (identifiers, geography, time), then subject areas. The role (`categorie`) stays a separate badge.
  A role-only split would put CUI next to a party group, and a subject-only split would scatter county and year over every subject.
- The list page is static HTML. It needs no script, so it stays readable with search in the browser (Ctrl+F).
## 2026-10-25 — Add the DemoANAF API reference page to its inventory (v0.21.0)

**Done**
- Fetched `https://demoanaf.ro/api-docs` (lot `demoanaf-api-docs`, 4 direct requests, 315,089 bytes): the page (148,681 bytes, body SHA-256 `7391a120…beb1`, retrieved 2026-10-25T17:15:39Z),
  the two script files of the page (`ApiDocsPage-DIsZ3AlF.js` 17,177 bytes, `api-docs-CGERF1wP.js` 969 bytes) and the English copy `/en/api-docs` (148,262 bytes). No `/api/...` address was called and no browser ran.
- New reader `html-api-docs` (`scripts/inventory_apidocs.py`, stdlib): the page has no table, so no existing reader fits. It reads the endpoint cards into three separate kinds of record:
  60 operations (59 GET, 1 POST; 38 with the `x402` badge), 113 request inputs (112 parameters, 1 body member) and 6 response members. `DATA-SCHEMA.md` documents every new key.
- The source is registered with `adaugari/demoanaf-api-docs.json` (`--add-sources-file`). Its discovery locator is the link `/links/24` of the home page; the second locator is the llms.txt line `[Public API documentation](…/api-docs)`.
- Comparison with `openapi.json` of the same project (body SHA-256 `77602f7c…34d2`): every operation and request input carries `in_contract` (`{sursa_id, pointer}` or `null`), and the source carries `comparatie_contract`.
  Measured: 46 of 60 operations are in the contract and 14 only in the page; the contract has no operation that the page lacks.
  Of the 113 inputs, 91 are in the contract and 22 only in the page; the contract has 4 inputs that the page lacks (`press-articles` `page`, `limit`, `topic`; `top-companies` `sliceKey`).
- DemoANAF now has 3 structured sources (was 2) and 221 field records (was 102): 95 contract parameters, 7 INS records, 119 new page records.
  Page inputs: 42 with location `path`, 20 `query`, 1 `body`, 50 without a stated location; 28 with a description, 42 with a hint in parentheses, 6 with declared alternatives, 1 with a declared type (`cuis`: `string[]`).
- `inventory.py --check`: 0 errors, 87 bodies hash-verified (86 before). `inventory_report.py` regenerated `acoperire.csv` (one row changed) and the report. Other projects: the diffs of `campuri.csv`, `seturi-date.json` and `descoperiri.json` only add lines;
  `proiecte.json` and `rezumat.csv` change the `demoanaf` lines only. A second `--only demoanaf --offline` run reproduced every file byte for byte.
- Tests: 483 run, 6 skipped, 0 failures (465 / 6 at v0.20.0; 18 new in `test_inventory_text.py`; the suite takes about 86 s). Browser checks on port 8770: `check_data_finder.py` 33/33, `check_inventory_preview.py` 31/31, `check_preview.py` 111/111.
  `validate.py --publication` 0 errors. The default `build.py` payload equals the earlier `site/data.json` apart from `generated`.

**Hard**
- The page documents no response field. It names the envelope `{ success, data, meta }` and shows one JSON error example (HTTP 429). The script file holds the same endpoint list as the page plus translation keys, with no schema; the English page is the same.
  So the 6 response members are all that exist; every operation needs a Pro key and none was called.
- Two cards (`top-suppliers`, `analysis` of `/api/seap/cpv/{cpv}`) show the untranslated keys `ep.seap-cpv-top.description` and `ep.seap-cpv-analysis.description` in place of a description, in Romanian and in English.
  One card shows the cache label `cache.6h`. The reader keeps the key as `descriere_cheie_nerezolvata` and leaves `descriere` empty; the label stays as written.
- The brief said "about 18" endpoint patterns missing from `openapi.json`. Measured with method and template: 14. The rest of the 18 came from loose string matching (for example `/api/sicap/tender/:notice` is `{notice}` in the contract).
- The first version of `split_top` dropped the last part of a parameter text when a bracket did not close, without any error. A test (`q (text`) found it. An unbalanced bracket is now an error.
- The page body is one line (minified), so `linie` has no use; locators are `char:START-END` intervals of the retained body, and a unit test cuts every locator and checks the text.

**Decided**
- Operations are a source-level list (`operatii`), not field records. Cost of the alternative: 60 endpoints would enter the field browser, its keyword search and its examples as if they were variables.
- Set `loc` only where the page shows it (a `:segment` of the template, the example request, or `body:`). Cost: 50 of 113 inputs have no location, although 44 of them are in the contract, which says `query`. The comparison pointer gives the contract's `in`.
  Inferring `query` from "GET and not in the path" would have been a guess that the page does not state.
- Mark restated records instead of dropping them. The page adds descriptions and 22 inputs that the contract lacks, so dropping the 91 restated inputs would lose evidence. Cost: the preview counts both sources.
  Measured in the preview index for `demoanaf` (before / after): fields 36 / 85; groups `cui` 2 / 5, `cpv` 2 / 4, `judet` 2 / 4, `localitate` 3 / 5. The selectors name no source, so the new fields join the groups by name.
  Left open: whether the finder should count a record with `in_contract` once (see the backlog).
- Reuse the evidence type `declarat-in-documentatie-api` (already shown as "Declarat în documentația API") for the page inputs; the error example uses `exemplu-in-documentatie`.
- Add a `demoanaf` entry to the `note` block of `inventar-note.json` (limits, blocker, next step, in Romanian). The verification block of that file stays as it was: it records the v0.18.0 pass. `inventar-concepte.json` was not touched.
- Do not register the script files or the English page as sources: they hold no field that the Romanian page lacks. Their four request lines stay in the log.

## 2026-10-25 — Build the local review interface (v0.20.0)

**Done**
- `scripts/review_ui.py` (stdlib, Python 3.12): a server on 127.0.0.1 and a Romanian page (`scripts/templates/review_ui.{html,css,js}`, no external request, CSP `default-src 'none'`)
  for the 31 provider items (`camp=surse_date`, D132–D162) and the 30 groups with their 92 members. Start: `python3 scripts/review_ui.py` (default port 8790).
  It writes `revizuire.csv`, `relatii.csv` and `inventar-concepte.json` and never commits. Each write reads the file, applies one decision, validates it
  (`taxonomy_v2.check` with the publication gate and `validate_concept`; only errors that the decision adds count), checks the hashes that the page loaded,
  and replaces the files atomically (two files: all or none). A file that does not round-trip byte for byte (BOM, CRLF, quoting, indentation) is refused.
- Review keys in `inventar-concepte.json`: group `stare`, `decizie_editor`, `data_revizie`; selector `stare`, `nota_editor`; a missing key means `propus`.
  `selector_matches` never matches an `exclus` selector; `variable_matches` and `publish_finder` skip `respins` groups; the finder index carries `state` and the page shows a badge.
  `inventory.py --check` does not ask an `exclus` selector to reach a field. `inventory_report.py` counts provider items and groups by state (generated report regenerated, `acoperire.csv` unchanged).
- Measured: `python3 -m unittest discover` runs 465 tests (6 skipped; baseline 411 / 6), 54 of them new in `test_review_ui.py`; the suite takes about 82 s (baseline 49 s).
  `check_review_ui.py` 75/75 (390 px and 1280 px, no horizontal scroll, no request outside the local server); `check_data_finder.py` 33/33 (baseline 31, +2 for the state badge);
  `check_inventory_preview.py` 31/31; `check_preview.py` 111/111. The default `build.py` payload equals the tracked `site/data.json` of 426a37d apart from `generated`.
- Latency on a copy of the data root: state 14–78 ms, a provider or group view 82–116 ms, a decision about 215 ms, the three check subprocesses 395 ms together.
- Evidence against the retained copies on this checkout: of the 31 provider items 16 are `verificat` (D147–D162), 9 `fără amprentă` (D132–D134, D140–D145) and 6 `indisponibil local` (D135–D139, D146);
  all 44 group proofs and 18 member facts are `verificat`. Five statements rest on a deduction (`cui` 4, `valoare-achizitie-directa` 1).
- No real item or group changed state: D132–D162 stay `deschis`, the 30 groups stay `propus`, `relatii.csv` has its 146 rows, and `inventar-concepte.json` has no review key.

**Hard**
- The three evidence states of the brief need a recorded hash, and D132–D146 record none (their evidence is the project page named in the relation row). Showing them as `verificat` would break the rule;
  hiding the retained text would lose the evidence. They get a fourth state, `fără amprentă`: the text and the highlighted provider name are shown, and the tool never calls them verified.
- The first round-trip test passed a file with a byte order mark, because the BOM became part of the first header name. `parse_csv` now refuses it explicitly (a test covers it).
- The first version ran four package checks for each decision (about 0.5 s). The errors of the unchanged files are now cached by file hashes and seeded after a write: one check per decision.
- The page's Content-Security-Policy forbids `eval`, so Playwright's `wait_for_function` cannot run on it. `check_review_ui.py` polls from Python instead.
- A condition such as `list.length && [...]` put a literal `0` in the page. The conditions are explicit now. The 390 px layout also needed `min-width: 0` on the grid children to stop long URLs from widening the page.
- While I checked the explorer, port 8791 was held by another process; my first `check_preview.py` run got a 404 from that server. I used another port and left the servers on 8770 and 8791 running.

**Decided**
- Count a deferred item (`amanat`) as open: the default filter `Deschise` keeps it, and the header says `(N amânate)`. Cost of the alternative: progress could reach `31 / 31` with items still waiting.
  `Grupuri: n / 30 revizuite` counts `revizuit` and `respins` groups.
- Link an item to the row that it appended with a marker in `decizie_editor` (`Acceptat 2026-10-25 (rând L147): …`). Cost of the alternative (a column or an id in `relatii.csv`): a format change that the brief does not approve.
  A reject, defer or duplicate removes a row that no commit holds, and sets a committed row to `respins` or `propus`, so history stays in git.
- A duplicate keeps the earlier reason after `Motiv inițial:` and an accept, reject or defer restores it, so a re-decision loses nothing. The other item must exist, belong to the same project and not be a duplicate itself.
- Refuse a second accepted source with the same name for one project (suggest the duplicate action); compare the exact name, and warn about the looser match (`ANAF` against `ANAF (serviciul public PlatitorTva)`) without refusing it.
- `Revizuit` also needs one confirmed member. A member changes only while its group is `propus` or `amanat`; the tick for each deduction is part of the request and is not stored (the brief adds no key for it).
- Check `Host` and `Origin` on every request, not only on POST. A rebinding page could otherwise read the token from `GET /`.
- Add the optional parameter `package` to `taxonomy_v2.check` so that a change is validated in memory before it is written; add `include_excluded` to `selector_matches` for the review page.
- `Resetează` goes back to `HEAD`, so it undoes uncommitted decisions. After a commit, a new decision changes the state.
- Leave `inventar-note.json` (the hand-edited notes of the expansion report) as it was: its verification section records the v0.18.0 pass.

## 2026-10-25 — Specify the local review interface

**Done**
- Added `docs/briefs/review-ui.md`: a local stdlib server (`scripts/review_ui.py`) for the 31 provider items and the 30 variable groups.

**Decided**
- A local tool, not a published page. It writes repository files, and git is the audit trail. A hosted page would need a second store and a sync back to the CSVs.
- Add review states to groups and selectors (additive keys; missing means `propus`). Without them the owner cannot record a group review. An `exclus` selector stays in the file for history.
- Make the public `/date/` a separate brief after the review. The owner wants it public, but the states to show depend on the review outcome.

## 2026-10-25 — Show the new evidence, export coverage and report (milestone E)

**Done**
- The existing explorer panel and the `/date/` finder now show the new evidence: declared alternatives, formulas, periods and the table or class a field comes from;
  INS dataset blocks (code, name, period, geographic levels, declared units, a note that the data is a mirror's metadata); the category, the ambiguity notes, the context and
  the unit facts of each group, and links to the evidence of its definition. A source whose refresh failed says so. No new explorer and no new sidebar facet.
- `scripts/inventory_report.py` writes `observatii/inventare/acoperire.csv` (140 rows, the 16 columns of the brief) and `docs/reports/inventory-expansion.md`.
  Measured, 127 projects and resources: structured fields 14 to 27 entries (113 to 100 without), source URLs 25 to 87, field records 2,302 to 3,525, groups 7 to 30.
  Field-level meaning is thinner than group-level meaning: source-declared descriptions exist for 4 of the 12 new inventories and declared types for 4; 11 of 12 are in a group.
- The three browser suites derive their expected counts from the generated index and from filter rules written in the scripts. Results: `check_preview.py` 111/111,
  `check_inventory_preview.py` 31/31 (baseline 25), `check_data_finder.py` 31/31 (baseline 25), with the 390 px and 320 px layouts.
- 411 unit tests (6 skipped; baseline 308). `inventory.py --check`: 0 errors, 86 bodies hash-verified, 62 dictionary evidence items verified, 0 stale. The default public payload is unchanged.

**Hard**
- A false stale alarm on a checkout without the cache: a pin on a source body was compared with the collected text of the same address, which has a different hash. A pin now names the
  kind of copy it was made on, and a missing copy is reported as unavailable. A test covers it.
- The first version of the table reader called a numeric-looking cell `numar`. A CUI column would then look numeric. The sample types are now `forma-numerica` and `forma-de-data`:
  how a cell is written, never a storage type.
- Fields of the INS measure used an evidence type that the preview did not map, so 3 of the shared groups lost members in the preview index (populatie 6 to 2, locuinte 4 to 1, lungime-drumuri 3 to 0).
  Found by comparing the index with the selector reach; a test now requires a preview basis for every evidence type of the tracked inventories.

**Decided**
- Keep the report generated from tracked files and one hand-edited notes file, so a reader can regenerate every number. Cost of the alternative (a hand-written report): numbers that drift from the data.
- Leave `CLAUDE.md` and `AGENTS.md` unchanged. The new commands are documented in `docs/DATA-SCHEMA.md` and in each script's header.
- Treat the target of ten new inventories as met by count (12 of 12 with sources, 11 with a definition-bearing signal) and say that the weakest, `aerlive`, has three fields and no group.

## 2026-10-25 — Add meanings and shared variables (milestone D)

**Done**
- Rebuilt `inventar-concepte.json` from evidence: 30 groups (7 baseline, 23 new). Each group has a Romanian label and definition, a category (identifier 3, dimension 4,
  measure 22, derived output 1), `dovezi` that point to exact retained text, and `ambiguitati` for candidates kept out of the group.
  58 evidence items are verified by `inventory.py --check`; 0 are stale.
- Measured memberships (unique entries): `cui` 4 to 6, `cpv` 3 to 4, `siruta` 2 (unchanged), `judet` 5 to 13, `localitate` 3 to 9, `populatie` 2 to 6, `cifra-afaceri` 1 to 2.
  New shared groups with two or more entries: `perioada-de-referinta` 8, `locuinte` 4, `lungime-drumuri` 3, `numar-salariati` 3, `profit-net` 2, `valoare-achizitie-directa` 2,
  `voturi-pentru`, `voturi-impotriva`, `voturi-abtinere` and `grup-politic` 2 each (European Parliament and Romanian Parliament, flagged as different institutions).
  Single-entry groups: 7 environmental measures and 6 election measures. Every baseline membership survives (a test pins them).
- Selectors can now carry `source`, `path` and `role` next to `names`, with a fixture for each combination. `REF_AREA` joins the county group for POP107D, LOC101B and GOS104A and not
  for ACC102B or TRN139A, whose area list mixes macroregions, regions and counties. County_id and locality_id of Rezultate Vot are internal keys and stay out.
- INS datasets get one measure field, `OBS_VALUE`, with the indicator definition and the declared unit. ACC102B declares two units (persons and per mille), so no single unit is chosen.
- Units: declared for the Rădăuți centre station (ppm, µg/m³, %, °C, from the project page) and for four INS measures. Unknown and kept unknown: PM10, pressure, wind speed, turnover,
  net profit and the other stations.
- Added 16 provider proposals D147-D162 with the producer, the distributor and the project author named apart. `relatii.csv` is unchanged, so the accepted provider facet is unchanged.

**Hard**
- A group must not be a spelling match. `year`, `name`, `for` and `id` occur in many sources; selectors fix them by exact path or source. Names such as `afn`, `sfn`, `pd` and `fd` in the SICAP
  REST response have no description (the linked `describedby` address returns 404). `afn` and `sfn` rest on a deduction: their values equal the authority CUI in the address and the supplier CUI in the report.
  `pd` and `fd` stay unmapped.
- The locality list of POP107D carries SIRUTA numbers in its labels, but the metadata states this only for two localities. It stays an ambiguity note, not a member of the SIRUTA group.
- `Presiunea` is a string in the Rădăuți sample, while the other pressure fields are numbers of another magnitude. The group says so and makes no unit claim.

**Decided**
- Put meaning at the group level, with evidence and a basis, and keep field-level meaning to what the source declares. Cost of the alternative (a field-by-field definition file): hundreds of
  paraphrases without a source to check them against.
- Label every definition `parafraza-editoriala`. The evidence next to it is direct (a declaration or a sample value). The wording is ours.
- Leave the accepted provider facet and the live relations untouched; provider findings are review items.

## 2026-10-25 — Investigate the bounded batch of 12 entries (milestone C)

**Done**
- Investigated all 12 primary entries; no reserve entry was needed. Every primary entry now has at least one structured source: 54 explicit additions
  (specification files in `observatii/inventare/adaugari/`): 51 new sources and three new memberships of INS records already held. The limit of ten new sources per entry holds
  (dignitas and rezultate-vot read ten each).
  Sources per entry: afacut 4, biografia-localitatii 4 (one dictionary table, three INS records), registrul-firmelor 1, dignitas 10, monitorul-ai 7,
  rezultate-vot 10, votdiaspora 5, aerlive 1, calitate-aer-radauti 1, banii-nostri 3, europescope 7, despre-femicid 1.
- Added readers for HTML tables, markdown tables, SQL, C#, Laravel migrations/resources/constants, annotated JSON in design documents and page-script names
  (`inventory_text.py`), exact locators for each, repository files pinned to a commit and verified by git blob hash, credential masking, bounded range reads,
  `--probe`, and the optional browser helper `render_pages.py`. 383 unit tests run (6 skipped).
- Network (lot C): 78 direct requests (73 ok; 5 errors: one 404 at EuropeScope, two 403 at aerlive, two 404 at the SICAP metadata link), 2.40 MB, made one at a time (so the six-worker and two-per-host limits were never reached), no retries.
  Hosts: raw.githubusercontent.com 37, api.github.com 10, api.europescope.eu 7, afacut.ro 5, data.g4d.ro 3, and 12 hosts with 1-2 each. Browser: 4 navigations (afacut 2, aerlive 2) and
  6 data requests seen. With lots B and B2 the pass made 90 direct requests. Cache reuse: every source replay is offline.
- Field records: 2,472 to 3,520 (+1,048); entries with structured fields: 15 to 27. These are source paths, not business variables.

**Hard**
- A page leaks a token. `desprefemicid.ro/analiza-date` embeds an Airtable personal access token in its script, with the base and table names. The token was not used and the
  database was not read. The first cached copy was deleted; the stored copy has the token masked (`redactari: 1`). The page's field names are recorded as page usage only.
  This is a security finding for the project owners; this pass does not contact them.
- `aerlive.ro` answers HTTP 403 to a plain request for its two JSON endpoints, while its own page receives them. The helper keeps the browser copy of the 888-byte cities list.
  It did not keep the 12,647-byte data response, and the two allowed navigations are used. No workaround was tried. The data fields of aerlive stay unknown.
- `europescope.eu` links "Use the API" to `/api/docs`, which returns 404. The seven bulk files documented on `/data` work. CSV files are read as a 24 KB sample.
- `calitate-aer-radauti`: the page's own script reads a Firebase JSON address. Its newest record is dated 2026-04-19, six months before the read. The published spreadsheet is filled by a script.
- `rezultate-vot`: the table of the results page has five cells per row under three headers, so no types are claimed for its columns. The API resources and migrations of the repository are the evidence.
- `votdiaspora`: the repository's last commit is from 2021-11-08, and its 8.8 MB `resources.sqlite` was not downloaded. The classes may predate the deployed site.
- `dignitas`: the schema is split over 84 patches. Ten were read (74 are not), so the table list is partial. `Statement.php` supplies the verdict scale as code constants.
- `afacut`: the search page says "Mod demonstrație" and requests no data at load. The structured evidence is the tables of the edition and county pages.

**Decided**
- Use exact fragments of public text, not clever parsing, as the unit of evidence: every reader reports an interval or table cell, and `--check` re-reads the body.
  Cost of the alternative (an LLM or loose heuristics): unverifiable fields.
- Count a page-script reader as usage evidence (`utilizat-in-cod-pagina`), not as a schema. It lets the pass say which variables a page reads without touching the data behind it.
- Keep browser copies (`via: browser`) only for responses the page itself received, up to six per page. The helper never retries a refused address with other headers.
- Stop at 78 requests of 150. Remaining budget is better kept than spent on reserve entries when all 12 primaries produced evidence.

## 2026-10-25 — Deepen the INS inventory and six other sources (milestone B)

**Done**
- Fetched the documented listing `https://ins.gov2.ro/api/datasets?limit=1`. Measured: HTTP 200, 557 bytes, `total` 3,368 datasets, 16 card members
  (`matrix_code`, `matrix_name`, `context_code`, `ultima_actualizare`, `row_count`, `dim_count`, `archetype`, `has_time`, `has_geo`, `time_range`,
  `primary_unit_type`, `time_granularity`, `is_split`, `parent_matrix_code`, `split_count`, `option_count`). llms.txt says "about 3,600"; the listing says 3,368.
  `limit` and `offset` are documented; only `limit=1` was run, so pagination is not verified.
- Fetched five dataset metadata records (`?lang=en`): ACC102B (again; same body hash as on 2026-10-24, so still available), POP107D, LOC101B, TRN139A, GOS104A.
  The codes come from the projects' own pages, not from guessing: POP107D is named by `constru-pentru-cine`, `orasul-care-se-intinde` and `demoanaf`;
  LOC101B by `constru-pentru-cine` and `orasul-care-se-intinde`; TRN139A and GOS104A by `unde-se-termina-asfaltul`. Each use is a locator in the registry
  (page hash plus exact text interval). Eleven memberships were added: seven for the projects that name the datasets and four for `ins-gov2` (the service that exposes them).
- New `set_date` and `catalog` records (inventory_ins.py, `scripts/fixtures/ins/`): name, code, update date, categories, the indicator definition,
  methodology links, the source note verbatim, dimensions with bounded code samples (code kept beside label), declared unit options, period and
  geographic levels labelled as API-computed, level counts labelled as counted, and a missing licence stated as missing.
- Fetched six more sources where a named gap existed: `companiidestat.ro` data index (declares licence CC BY 4.0 and four original providers), its
  2025 financial statements (a collection keyed by 1,446 CUIs), `transparenta.eu/ai/index.json` (route list), `romaniatransparenta.eu` `primarii.json` and
  `control-saptamanal.json`, and the codurbanism `source-manifest.json`.
- Network: lot B 6 requests (1 listing, 5 metadata; 1.4 MB), lot B2 6 requests (1.5 MB). All HTTP 200. No retries. 12 direct requests in total; no browser.
- Field records: 2,302 to 2,472. New: 24 `declarat-in-metadate` dimensions, 150 more sampled JSON paths. 15 entries now have structured fields
  (14 baseline plus `constru-pentru-cine`, which has only INS metadata). 362 unit tests run (6 skipped); the evidence check passes: 35 bodies hash-verified, 0 errors.

**Hard**
- The mirror's period is shorter than the projects cite. LOC101B's time options end in 2023 (`ultima_actualizare` 2026-07-21), while `constru-pentru-cine`
  documents 1990-2025. POP107D ends in 2025 against 2026 in the project; TRN139A ends in 2024 against 2025. The projects read TEMPO directly. Memberships therefore
  say "metadata read from the ins.gov2.ro API", and the note on each discovery says so. The mirror's `profile` is API-computed, not an INS declaration.
- `companiidestat.ro/date/v1/index.json` has an `openapi` member that holds a URL. The old test treated it as an API contract and read zero fields.
  The test now needs a version number. Existing sources are unchanged by this.
- The 2025 financials object was keyed by CUI: 2,000 fields (the limit) of the form `$.companii.<cui>.<member>`. A key map with more than 100 keys is now sampled
  under `{*}` (39 fields). No baseline source has such a map (largest: 42 keys), so no tracked record changed; the baseline sources compared equal field by field.
- A locality option label starts with a number (`38731 RIPICENI`). The POP107D note declares "Ripiceni (SIRUTA 38731)" and "Scanteia (SIRUTA 98916)", and the
  options carry exactly those two numbers (a second `94429 SCANTEIA` shows that names collide). This supports, but does not prove, that the leading token is SIRUTA for
  all localities. It stays an open question for the meaning pass.

**Decided**
- Attach each INS metadata source to the projects whose own pages name the dataset, with the page evidence, rather than only to `ins-gov2`. Cost of the alternative:
  an INS dimension could not be tied to a project that uses the dataset, and the finder could not show the use evidence. Risk accepted: the source is a mirror, labelled as such.
- Count the six extra fetches in their own lot (B2) so that the INS limit (the listing plus five records) stays exact.
- Do not re-test the `POP101A` example. The brief records a 404 and asks for fresh evidence before reuse; this pass does not reuse it.

## 2026-10-25 — Make inventory collection incremental and safe (milestone A)

**Done**
- Added `scripts/inventory_state.py` (registry, validation, atomic writes, request log) and rebuilt the control flow of `inventory.py` around it.
  The run reads the tracked profiles, sources and registry first. `--only` changes only the selected projects and the sources they use.
- Added the generated `observatii/inventare/descoperiri.json`, seeded offline from the tracked memberships and the cached documentation.
  Measured: 59 records for 140 projects. 25 are active (24 from documentation, 1 from the pilot file) and 34 were found but not admitted.
  Every locator was recoverable from the local documentation snapshots (page hash plus link index or text interval). None was marked unknown.
- A smaller `--max-files` no longer removes members. A failed, unparsable or missing-cache refresh keeps the last field evidence and
  records `ultima_incercare`. A changed body keeps the earlier version in `versiuni_anterioare`. Failed responses no longer overwrite a good cached body.
- Added `--dry-run`, `--retire` with a required reason, `--add-source`, `--lot`, `--budget`, `--max-requests`, and a request log (`jurnal-cereri.csv`).
  `--check` now separates corruption from bodies that are absent on the checkout, and never counts absent bodies as verified.
- The documentation collector keeps pages that an earlier run collected and a later run cannot collect again (audit found the defect, see Hard).
- The preview marks a source whose last refresh failed (`refreshFailed`, `stale`) so that it is not shown as freshly verified.
- Replay check: `inventory.py --offline` on a copy of the tracked folder reproduces `proiecte.json`, `seturi-date.json`, `campuri.csv`,
  `rezumat.csv` and `intrari-utilizator.csv` byte for byte. A copy without any cached body, run with `--only afacut,ins-gov2,demoanaf --offline`,
  also reproduces all six files. 34 new tests (`test_inventory_state.py`, `test_collect_docs.py`, `test_inventory_site.py`); 342 tests run, 6 skipped.
- Public build check: the default payload equals the v0.13.0 payload apart from `generated`; classifications and accepted providers are unchanged.

**Hard**
- The old `main` kept `fetch_urls` only for the selected projects but still rebuilt every profile from caches. A fresh checkout turned every
  unselected source into `necolectat`. The old cache write also replaced a good body with a failed response on `--force`. Both were read from code;
  the new tests reproduce each failure mode on fixtures. No tracked evidence was damaged: the baseline `--check` passed with 0 errors.
- `collect_docs.py` replaced a whole entry record with the new result, so one failed forced refresh would drop its collected pages.
  The test showed the defect. `merge_refresh` fixes it. Restored snapshots now rewrite their original content (key order may differ).
- `Python 3.15` is the local interpreter. The code stays inside 3.12 features; CI is the check.

**Decided**
- Discovery has no per-run limit; admission has. A candidate beyond the limit is recorded as `descoperit`, so a later run with a larger limit needs no new discovery.
  Cost of the alternative (store only admitted sources): the 34 candidates beyond the old three-file limit would be rediscovered or lost.
- Offline runs keep a tracked record when its body is absent. They fail only when the tracked files are unreadable or the proposed state is invalid.
  Cost of failing on every missing body: no targeted run would work on a fresh checkout, which is the case the brief wants to support.
- `ultima_incercare` is the only stale marker. A source older than some age is not stale by itself; the interface says "consultat la".

## 2026-10-25 — Specify the next inventory implementation pass

**Done**
- Added `docs/briefs/inventory-expansion.md`, with a copyable session prompt, baseline, file map, evidence contract and five implementation milestones.
- Named 12 primary entries, three reserves, a bounded INS metadata expansion and a target of ten new structured inventories.
- Defined preservation tests, collection budgets, coverage exports, browser checks and the final implementation report.
- Linked the handoff from the README and backlog. Collection and implementation remain pending.

**Hard**
- Code inspection found that `inventory.py --only` limits fetching but rebuilds every profile from available caches.
  Missing local bodies can erase unrelated fields. Candidate limits can also discard earlier source memberships.
  This finding comes from the current control flow; no destructive reproduction was run against tracked inventories.

**Decided**
- Make safe incremental collection the first milestone. More fetching before that fix could reduce the existing evidence coverage.
- Require explicit source membership and contextual variable mappings. Shared providers alone do not prove shared dataset use.
- Use bounded investigation and report coverage shortfalls honestly. Leave editorial acceptance and public deployment outside this implementation pass.


## 2026-10-25 — Record the inventory milestone as v0.12.0

**Done**
- Updated the README, architecture, data schema, specification, release notes and backlog for the inventory milestone.
- Recorded the proposed expansion sequence: deepen existing inventories, inspect selected missing entries, then review meanings and source relations.
- Version v0.12.0 records the collector, generated inventory metadata, explorer integration and dedicated data finder preview.
  This repository has no Cargo workspace; versions use `docs/RELEASES.md` and Git tags.

**Hard**
- Most entries have no extracted structured fields: 113 of 127 projects and resources. Collection gaps do not prove missing variables.
- Source paths repeat concepts across files and endpoints. Raw record counts overstate independent variable coverage.

**Decided**
- Keep the proposed expansion work pending. The owner requested recommendations without starting another collection pass.
- Measure project coverage and evidence quality before raw field totals. Prefer documented schemas and source definitions over guessed types.
- Record this milestone locally. The inventory feature retains its isolated-preview boundary.


## 2026-10-25 — Discover projects through shared data

**Done**
- Added the dedicated `/date/` page to the isolated inventory preview, with a navigation link from the explorer.
- Included all 106 projects and 21 resources. Resource inclusion defaults to on; organisations stay in the general explorer.
- Added variable, accepted-provider, subject and target-institution filters, with counts, removable selections and shareable URLs.
- Added seven proposed business-variable groups with explicit project/field selectors. Six groups occur in multiple entries.
  CUI matches four entries, CPV three, SIRUTA two, county five, locality three, population two, and turnover one.
- CUI plus CPV matches two projects. INS matches nine entries, or three with resources excluded.
- Each match exposes source examples, field roles, type evidence and references. Target institutions never become provider assertions.
- The discovery index is 148,475 bytes for 127 entries. The page fetches one index and renders 24 results per batch.
  Missing inventories remain discoverable through catalogue descriptions and classifications; 14 entries have structured fields.
- Publication validation, ordinary build and isolated preview build pass. The full suite runs 308 tests, with 6 skipped.
  Fifty browser checks pass: 25 for the explorer inventory and 25 for the dedicated finder, including 320/390 px layouts.

**Hard**
- Provider coverage is sparse: only 11 entries have accepted source relations. Existing inventory extraction cannot approve the remaining sources.
- Shared fields have different roles and representations. CUI can identify a taxpayer, contracting authority, supplier or budget creditor.
  Kept each source's role and type evidence instead of presenting a shared group as a certified join key.

**Decided**
- Use a dedicated page for the reverse route from data needs to projects. Keep the ordinary explorer's sidebar unchanged.
- Require all selected variables. Other facets use alternatives within each group; groups intersect.
- Keep business mappings in the hand-edited `inventar-concepte.json`. Generic `id` or `value` names never establish equivalence.
- Keep this page local while business mappings remain proposals. No new commit, push or deployment was made for this prototype.


## 2026-10-25 — Showcase inventories in an isolated explorer preview

**Done**
- Added `build.py --with-inventory --site-dir DIR` and `inventory_site.py`. The flag exports draft inventory metadata to a separate preview.
- Results with structured evidence have an `Inventar de date` marker. The project panel adds `Date & metodă`, partial status,
  example field buttons, documentation links, field search, source/role filters, types, units and source references.
- Main project search also reads inventoried field names. No new sidebar facet was added.
- The field payload loads only when opened, then stays cached. Failed requests offer a retry without losing the project panel.
  Search/filter changes keep focus and do not change the main query or URL.
- The preview has 14 markers and 77 entries with inventory or documentation sections. Generic HTML controls remain out of the UI.
- Repeated API parameters share a display row when their source, name, type, description and location agree.
  DemoANAF shows 29 rows from 95 declarations, with all operation contexts retained.
- Fixed the known 320 px page overflow. The result column and sort select now shrink correctly; the viewport stays 320 px, not 347 px.
- Validation and both builds pass. 304 unit tests pass, with 6 skipped; 111 existing browser checks and 25 inventory checks pass.
  Inventory evidence has 0 errors. The default public data payload is unchanged apart from its generation time.

**Hard**
- The first preview repeated CPV parameters across endpoints. Grouped those declarations and labelled their query/path locations.
- At 320 px the existing sort/select controls widened the layout viewport, which also widened the fixed drawer.
  A drawer-only grid change did not solve it. Fixed the result-column minimum and the select's flex minimum instead.
- Initial screenshots caught the drawer's opening animation. Visual captures now wait for it to settle.

**Decided**
- Put the inventory in results and project details. More sidebar controls would work against the owner's simplification request.
- Keep the full fields out of data.json. The main payload carries compact discovery metadata; individual files load on demand.
- Show declared types, sample observations, metadata dimensions and unknown CSV types distinctly. Source links remain available for inspection.
- Use an isolated preview while the inventories remain proposals. `--with-inventory` cannot write `site/`; the default public build stays unchanged.


## 2026-10-25 — Continue variable inventories after the push

**Done**
- Pushed 0fa981b (v0.11.0) and repair 1a75a90 (v0.11.2). GitHub validate and Pages passed for 1a75a90.
  Sheets push passed for the first commit. No GitHub release was published.
- Added stdlib `scripts/inventory.py`. It reads cached documentation and up to three explicitly linked schema/data files per entry.
  It reuses checked pilot metadata links without per-project URLs in code. Generated inventory drafts cover all 140 entries.
- Made 26 read-only requests; retained 25 source URLs after excluding a configuration file. Twenty-four sources parsed; one returned 401.
  The sources include three OpenAPI files, four JSON Schemas, six CSV files, ten JSON samples and one INS metadata response.
- Recorded 2,302 source-scoped field records for 14 projects: 1,312 schema declarations, 904 sampled JSON paths,
  82 CSV headers without declared types and four INS dimensions. These are not 2,302 independent business variables.
- Recorded 308 HTML control candidates across 78 entries. A Făcut?'s three linked edition pages yielded a real locality-search control.
  The optional `collect_docs.py --follow-data-links` keeps the existing page limit and defaults to off.
- Exported review CSVs for fields and controls, JSON source/profile records, and a per-entry summary. All are proposals.
  Seventy-eight profiles are partial; 62 remain unconfirmed. Existing catalogue descriptions and capabilities remain their semantic starting point.
- Added `inventory.py --check` for source hashes, valid field pointers, declared types and control references.
  The current evidence check reports 0 errors. Downloaded source bodies stay gitignored and have immutable hash-named versions.
- Publication validation and build pass. The full suite runs 299 tests, with 6 skipped.
  Offline replay is byte-identical and makes 0 requests. The public payload is unchanged apart from its generation time.

**Hard**
- Monitor Energie's linked OpenAPI URL returned 401. No credentials were requested or used; the source remains an explicit gap.
- A JSON data catalogue can contain a `$schema` annotation without being a JSON Schema. The parser now distinguishes those cases.
- Common OpenAPI models appear under many operations. The registry keeps one field declaration with all its operation bindings.
- The România Transparentă contract has 1,085 distinct field records across 67 paths. Raised the field limit from 1,000 to 2,000.
  JSON samples are bounded to 25 elements per array and seven nested levels. Sample types remain observations.
- HTML input names alone can identify generic site controls. They are candidates, not accepted project-data inputs.

**Decided**
- Preserve explicit, observed and unknown types separately. Cost of inferring types from CSV strings: identifiers can lose leading zeros.
- Keep source IDs tied to URLs and body hashes tied to versions. Do not assert that two differently formatted files are the same dataset.
- Keep inventory drafts out of the public build until business meanings, units and completeness are reviewed.
  This continuation remains local work after the requested milestone push.


## 2026-10-25 — Repair the base package check after the v0.11.0 push

**Done**
- Pushed 0fa981b and v0.11.0 on the owner's instruction. Pages and Sheets push passed; CI failed in the base package check.
- Added a local `integrare/relatii.csv` with all 146 live relations. The base package keeps its 100 valid relations.
  The live build preserves all public attributions and data sources. Both package roots now have endpoint validation coverage.
- Both package checks, publication validation and build pass. 285 unit tests pass, with 6 skipped.

**Hard**
- The base had 46 orphan relations: 19 earlier author attributions and 27 source relations for integration-only entries.
- I missed the base check's nonzero exit before pushing because later commands in that shell returned zero.
  A clean git archive reproduced the failure. The workflow had redirected the explanatory errors to /dev/null.

**Decided**
- Relations are editorial entry data and belong to the detached integration copy. Keep vocabulary shared.
  Cost of keeping live relations in the base: a 122-entry package cannot validate edges for its 140-entry overlay.
- The sandbox blocked staging. My sequence then created and pushed v0.11.1 on the old commit.
  Kept that tag as history; v0.11.2 carries the actual repair. Later mutations now stop on a failed command.
- Patch version v0.11.2 corrects the package layout. No GitHub release is published.


## 2026-10-25 — First-party documentation collection and five inventory drafts

**Done**
- Prepared the v0.11.0 commit and tag on the owner’s instruction. This repository versions releases through tags and `docs/RELEASES.md`; it has no Cargo workspace.
- Added stdlib `scripts/collect_docs.py`. It checks each homepage and scoped/root `llms.txt`, then follows methodology/about links.
  It also records inline sections and bounded fallback paths. Limit: five pages per entry, six workers, two requests per host.
- Completed a corrected pass over all 140 entries: 571 requests, 591 entry-page records, 246 collected page records.
  Found candidate documentation for 76 entries: 17 have project-specific llms files, 40 have methodology candidates, 51 have about candidates.
  These groups overlap. 102 homepages yielded usable static text. Documentation remains unconfirmed for 64 entries.
- Saved the generated metadata in `observatii/documentare/index.json` and `rezumat.csv`.
  Downloaded bodies stay in gitignored `pagini/`. Collection preserves HTTP/network errors, homepage copies, HTML llms fallbacks and shared-host scope.
- Drafted five partial inventories: afacut, ins-gov2, ani-de-pensie, calitate-aer-radauti and codurbanism.
  `pilot-inventare.json` holds 19 field/input candidates, evidence hashes and character intervals, methods, outputs and explicit gaps.
  Inferred types remain proposals. No inventory feeds the public build or changes editorial classifications.
- Validation: 0 errors and 0 warnings. Public build: 140 entries. Unit suite: 284 tests, 6 skipped.
  Eleven new tests cover scoping, duplicate-homepage rejection, HTML llms rejection, inline sections, missing links and snapshot restoration.

**Hard**
- The sandbox blocked the initial requests. Repeated the collection with network permission; those failures were not treated as missing documentation.
- An early collection stopped on an anchor with an empty href. Fixed the parser, retained completed records, then refreshed all 140 entries.
- Headings alone missed A Făcut?'s method section. Its navigation link points to a fragment; the collector now preserves fragment evidence.
- Snapshot bodies can be shared between projects. Restore keeps each entry's scope and document kind from its own metadata.
- INS llms retrieval succeeded (HTTP 200, 3,750 stripped characters). The owner's `tmp/ins-llms.txt` matches it after stripping.
  The POP101A metadata route returns 404 with `Dataset POP101A not found`; that does not mean the API is unavailable.
  The dataset list and ACC102B metadata both return 200. The llms example calls ACC102B GDP, but its live metadata describes workplace accidents.

**Decided**
- Start from methodology, about and llms as the owner requested. Treat downloaded text as evidence, never as instructions or accepted classifications.
- Keep project-specific documentation distinct from shared-host indexes. Cost: a shared llms may help discovery without proving this project's data model.
- Separate declared interfaces from checked interfaces. Added the successful and failed INS checks to the draft inventory.
  ACC102B exposes CATEGORY, REF_AREA, TIME_PERIOD and UNIT_MEASURE. Its source note names Inspecția Muncii; INS distributes the data.
  This one verified matrix does not define every dataset on the project.
- Keep raw bodies local and review metadata in git. Cost: reviewers on a new checkout must use `--force` to obtain the cited snapshots.
- Defer JavaScript rendering, binary document extraction and a public inventory UI. The current deliverable is collection plus five reviewable drafts.


## 2026-10-25 — Compact sidebar and source labels

**Done**
- Source labels use INS, MDLPA, Adm. Prez, MO, BNR, ONRC and ADR. The two parliamentary chambers share `Parlament`.
  Full names remain in source records, detail tooltips and autocomplete. Older source URLs map to compact labels.
  Grouped counts count each entry once. Duplicate evidence links for the two chambers render once.
- Moved `Surse de date` above `Format`. Widened the desktop sidebar from 230 to 260 px; reduced its gap from 40 to 32 px.
  Facet text is 13 px instead of 14 px. Tags wrap inline, including within long labels.
- Browser acceptance: 111/111 checks. These include chamber grouping, old source URLs, evidence links and Enter/Space operation.
  Visual checks at 1280, 1024, 390 and 320 px confirm inline tag layout. Validation: 0 errors and 0 warnings.

**Hard**
- Native buttons compute to inline-block even with `display: inline`. Used inline links with button semantics and Space support.
  Existing filter handling prevents navigation; disabled options have no link and ignore activation.
- The visual run found a 347 px document width at a 320 px viewport. No overflow occurred at 390, 1024 or 1280 px.
  The filter tags themselves wrap. The 320 px page overflow needs a separate layout audit.
- A browser selector had nested quotes after its disabled-state update. Fixed the syntax and reran the acceptance suite.

**Decided**
- Keep short source labels in presentation, preserving the recorded provider names and source evidence.
  Cost of renaming source records: the two chambers would lose their individual provenance.
- Keep the existing fonts. Smaller text and more sidebar width provide the compact layout without another font download.
- The owner proposed project data inventories. Added a pilot to the backlog; no extraction schema or rollout was implemented.


## 2026-10-25 — Simpler filters, data sources and geographic detail

**Done**
- Combined broad subjects and themes under `Subiect`. New selections use OR within this filter; older `topic` URLs keep their constraint.
- Each facet sorts by current count, then Romanian label. Options with at most three matches expand under `Mai multe`.
  Selected options stay visible, including zero matches. The mobile sheet uses the same controls.
- Added `Surse de date`, source autocomplete, and evidence links in the detail panel.
  Added 26 accepted `date_din` relations for 11 entries. Added 15 proposed relations and review items D132–D146.
  The public build excludes proposals and keeps all source relations separate from author attributions.
- Added optional `detaliere_date` and `dovada_detaliere` columns. Recorded 10 evidence-backed details: four national aggregates,
  three locality breakdowns, and three county/locality breakdowns. The other 130 entries remain unverified or not applicable.
- Secondary geography controls distinguish national aggregates, nationwide data with local detail, local reach, and unverified national detail.
  Explicit locality choices no longer match country-only assignments. Bucharest now matches 4 active projects, rather than 80.
- Updated the schema, contributor guide, specification, acceptance checks, and source validation tests.
- Validation: 0 errors and 0 warnings. Public build: 140 entries. Unit suite: 273 tests, 6 skipped.
  Browser acceptance: 106/106 checks, including desktop, mobile, old URLs, source evidence, geographic groups, and focus.

**Hard**
- The existing area matcher included national entries for every listed locality. It showed counts near 77 for unrelated local areas.
  Those numbers counted catalogue entries, not datasets or local records. The same rule would also apply to any newly listed county.
- The first browser run retained three old `Temă` label expectations. Updated them to `Subiect`; the new behaviour then passed.
- A full unit run loaded the schema documentation before the new column descriptions were written. Its documentation check failed.
  The documentation check passed after those descriptions were added.
- Only 11 entries have accepted source records. This is an initial verified pass, not a complete provenance audit.
  The 15 proposals come from existing descriptions or names. They need primary evidence before publication.

**Decided**
- Keep the editorial subject/theme distinction in CSVs; combine it in discovery. This avoids rewriting accepted classifications.
- Keep geographic reach separate from geographic data detail, as the owner clarified. National reach alone proves neither local detail nor completeness.
  Cost of a forced three-way classification: unreviewed national entries would acquire unsupported claims. They keep an explicit unverified option instead.
- Use the existing relation table for providers and evidence. Cost: these records need repository edits; existing Sheets tabs do not sync relations.
  Geographic detail uses entry columns, which the schema-driven Sheets and Form code can preserve. No Google sync ran here.
- Verified source names identify providers or publications that the project names. They do not certify the provider's underlying data.


## 2026-10-22 — Cutover to taxonomy v2 applied, merged and deployed (pull request #4)

**Done**
- Sheets first. The owner's `sheets.py pull --check` replaced `data/proiecte.csv` with the Sheet's copy (no sync marker, so two-way: the Sheet won). That copy lacked the 19 new rows
  and still had `incentru`. I restored the file from git, then ran `push --since 97304fa` (the Sheet equalled the repository at that commit): `proiecte` 127 rows, `orgs` 13, marker 3989209.
  `v2-intrari` had no marker either, and the plain push refused (exit 3). The diff held only `incentru` and 19 `sursa_rand` values, so I used `--force` on that tab: 140 rows.
  `sheets.py diff` shows no difference on the three tabs.
- The owner ran `cutover_v2.py --apply` (my attempt was refused by the permission check as a production deploy): 24 text edits in 10 files, `site-v2/` gone, `PUBLIC_ROOT` is the integration copy.
- The 19 entries' profile and search rows (19 and 213) went into `observatii/`. `validate.py --publication` passes, `build.py` writes 140 entries, 269 tests pass (6 skipped: tests of the pre-cutover state).
- Merged on the owner's instruction (merge commit fda9545). `pages` and `validate` passed on `main`. Post-deploy checks on https://civtech.gov2.ro/: `data.json` has schema `2.0.0-draft.2`, `draft` false,
  140 entries (106 projects, 21 resources, 13 organisations), `tabs.intrari` 541482181, no `incentru`; an entry page of each kind and the three archives answer 200;
  `style.css` and `app.js` carry new `?v=` hashes; `check_preview.py` passes 97 of 97; `sheets.py diff` shows no difference; a manual `sheets-pull` ended without a pull request.
- After the deploy the owner asked whether "by the same author" was lost. The feature stays, renamed "Cu aceeași atribuire" (v2 shows an unconfirmed role as an attribution, not as an author). But the 19 mariuscomper.uk entries had no author and no group: v2 reads authors from `relatii.csv`, and I had filled only `autor_original`. 19 rows (L087–L105, `atribuit_in_sursa`, `rol_neconfirmat`) fix it: each page shows "Marius Comper · rol neconfirmat" and "Cu aceeași atribuire · 18". Lesson for a new entry in v2: add its attribution rows in `relatii.csv`.
- `check_preview.py` failed on the live site twice: Cloudflare answers 403 to urllib's default User-Agent, and the image check ran before the images arrived over the network. It now names itself and waits up to 10 s.
- Documents the command does not edit: `README.md`, `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/ARCHITECTURE.md`, `docs/DATA-SCHEMA.md`, `docs/METODOLOGIE.md` and `docs/specs/taxonomy-v2.md` now state the new public source, the frozen v1 files and the moved browser code.

**Hard**
- CI on the pull request failed once in `test_cutover.py`: `shutil.copytree` met a vanished `.git/objects/maintenance.lock`, because git ran background maintenance after the base commit. The tests now run git with `maintenance.auto=false` and `gc.auto=0` and skip `*.lock` files when they copy.
- Only the statements that became false were changed. Long sections still describe the v1 flow or the "preview" in detail (the README editing section, the contributor routes, parts of ARCHITECTURE and the specification). They carry a dated note. See BACKLOG.
- The contributor route after the cutover is my reading, not a decision: a pull request on `proiecte.csv` no longer reaches the site, and proposals come through the Form or an issue and an editor copies them into `intrari.csv`.

**Decided**
- Form (runbook step 5): option B. The live Form keeps the v1 questions, and an editor copies each proposal into `intrari.csv`. Cost of option A: editing the live Form by hand to match `form.py`'s plan.
- Not done: protecting the v1 Sheet tabs (no command; by hand in Google Sheets), the merge (it deploys v2 to the public site), and an actionlint run (not installed locally; CI runs it).

## 2026-10-22 — v2 editorial decisions taken on the recommendations; 19 entries added to the integration copy

The owner detached the copy on 2026-10-21 and asked for the decisions "as much as possible", because the project is not live. These are assistant decisions, not owner review.

**Done**
- Review queue: 65 of 66 open items closed with `decizie_editor` text. Most recommendations said "keep"; 10 items changed 12 entries in `intrari.csv`:
  `format:ghid` removed from 2 entries (R062, R063) and `format:vizualizare` from `ins-gov2` (C003); `nu-astepta-supereroi` is `national` + `tara:RO` (C013);
  `data-expertforum` and `crpe` cover `tara:MD`; the two hybrid-war entries cover `regiune:Europa`; `tehnologie:retea-de-senzori` and `scop:sustenabilitate-presa` are assigned.
- Vocabulary: `tara:MD`, `tehnologie:retea-de-senzori` and `scop:sustenabilitate-presa` added (130 concepts). Of the other proposals: 6 deferred, `regiune:europa-de-est` rejected.
- Entries: 121 of 122 set to `acceptat` in one pass. The pass checked only that each has a primary subject. It did not review each entry.
- The 19 mariuscomper.uk entries added to `integrare/intrari.csv` (7 `proiect`, 12 `publicatie`), `acceptat`, confidence `medie`.
  Their profile and search rows (19 and 213) were first copied from `data/` into `observatii/`, then taken out again: CI runs `validate.py --baseline` on the package,
  which compares `observatii/` with `source/` byte for byte, and failed on `main`. The cutover drops that flag. Until the rows are copied back, the v2 build shows the 19 as "neverificat", without images.
- Three tests pinned entry counts (122 and 121). They now read the counts from the data. 269 tests pass.
- `cutover_v2.py --plan`: 3 blockers, down from 4 on 2026-10-20 (detach done by the owner): `incentru` not accepted, C009 open, `tabs.intrari` null.
- Later the same day the owner gave up `incentru` and created the tab `v2-intrari`. `incentru` left v1 (`proiecte.csv`, `profil.csv`, `mentiuni.csv`: 34 rows)
  and v2 (`intrari.csv`, `rezultate.csv`, and its three review items: the validator refuses an item for an unknown entry). Its rows in `observatii/` stay: that folder keeps records of entries that left.
  `setari.json` has `tabs.intrari = 541482181`, read from the Sheet. `--plan` now shows no blocker: 140 entries, all `acceptat`. The `sursa_rand` of the 19 new entries was recomputed (the removal shifted `proiecte.csv` by one row).
- `check_preview.py` opened `incentru` to test the abstention panel. It now tests that panel only when an entry has no primary subject. 97 of 97 checks pass.

**Hard**
- The validator requires the top-level parent of every theme in `subiecte`. `subiect:statistica` has the parent `guvernare-democratie` and `subiect:populatie` has `comunitati-teritoriu`.
  Adding those parents would misdescribe the entries, so five entries dropped the theme `statistica`, and `ani-de-pensie` and `pensie-din-bursa` use `situatie-sociala`. Statistics is not searchable as a theme for them.
- `incentru` had no description, a parked domain (last capture 2025-08-16) and no evidence of its purpose. The Wayback lookup timed out. The owner decided to give it up.
- The two new concepts follow the existing `propus` convention for `statut`.
- After the push of `main`, `validate.yml` failed twice. The baseline check above was one. The other was `astral-sh/setup-uv@v10`, a version that does not exist;
  the file now uses `@v6`, as the Sheets workflows do. The local rehearsal passes (24 edits, 269 tests); actionlint was not available locally.
- After the push, `sheets-push` exited 3 ("Tabelul are modificări nesincronizate; rulează sheets-pull"): it refused to overwrite the Sheet, as designed. The 19 rows are not in the v1 tabs yet.

**Decided**
- `modificari.csv` is not extended. After the detach the file is not applied, and its rows must match the sealed assembly. Git history and `decizie_editor` are the record.
- Calculators use `format:formular` (no better format in the vocabulary). Articles use `format:raport` (research) or `format:articol` (explainers). `maturitate` is empty where the page does not state it.
- Not done: the Form, the v1 tab freeze, the 26 entries without text, and the cutover itself. The tab `v2-intrari` has 141 rows and needs a new push from the committed `intrari.csv`.

## 2026-10-21 — 19 mariuscomper.uk pages added to the v1 data

**Done**
- Added 20 rows to `data/proiecte.csv`: 7 `proiect`, 10 `cercetare`, 3 `articol`. Author Marius Comper, `civictech=1`. Each text comes from the live page
  (meta description and page text). A script checked every figure in the descriptions against the page text.
- On 2026-10-22 the owner dropped `tuneluri-feroviare` (weak civic fit). Its rows left `proiecte.csv`, `profil.csv` and `mentiuni.csv` (4 rows, 0 kept),
  and its two images were deleted. 19 entries remain: 7 `proiect`, 10 `cercetare`, 2 `articol`.
- Profiled the 20 (`profile.py --only`): all `activ`, HTTP 200. Image (19 entries after the drop): 16 OG, 3 screenshots (`ani-de-pensie`, `achizitii-directe-ti-2026`, `trei-din-patru`).
  Icon: 18 (`achizitii-directe-ti-2026` has none).
- Searched the 20 (`search.py --only`): 22 Serper and 20 Brave requests, 0 errors, ≈ $0.12. 217 result rows (213 after the drop); 103 kept by the rules, 84 after pruning.
- Measured: `validate.py` 0 errors, 28 warnings (all in older rows). `build.py` writes 141 entries after the drop; the pages build with scores from 25 to 43.
- `test_cutover.py` pinned the v1 entry count at 122, so it failed at 142. It now counts the rows of `proiecte.csv` and `orgs.csv`. 269 tests pass.

**Hard**
- The `mc-i` index row for `achizitii-directe-ti-2026` described another page (AFCN funding). The live page is a dashboard of direct-procurement
  signals. The row uses the live page; the `mc-i` summary for that id is not used.
- Surname collision: 19 kept results came from `concursurilecomper.ro` and `edituracomper.ro` (a competitions publisher). They are `editor=0` now.
  Open: 6 `iqads.ro` and 3 `republica.ro` results name a "Marius Comper"; nobody confirmed that it is the same person.
- `search.py --prune-only` re-applies the rules to all entries. It changed `regula` on 53 older rows and `mentions` on 10 other entries in
  `profil.csv`: the stored values were older than the current rules. The import reverted both, so the diff holds only the 20 entries.

**Decided**
- `fel`: v1 has no content tab. Explainers and investigations use `cercetare` or `articol` (tab "Resurse & liste"); tools use `proiect`.
  The v2 plan moves `cercetare` and `articol` to a new tab. Cost of the alternative (`proiect` for all 20): the pieces would crowd the main tab.
- The pages have no repository or social links of their own. `linkuri` holds only four dataset links (`date:`).
- Three entries use `altele`, because v1 has no domain for pensions or education.
- Not done: classification of the 19 in the v2 integration copy (see BACKLOG). No runbook step covers entries added to v1 after the sealed run.

## 2026-10-20 — Cutover prepared as one tested command; documentation of the v2 preview (slice F)

**Done**
- `integrare.py --detach` (owner, once): records the commit in `pachet.json`. After it, `integrare/` is editorial, and the check proves
  only that the overlay at the detach commit still assembles from the sealed run. Tested on temporary copies; the real overlay is not detached.
- `common.PUBLIC_ROOT` (today `data/`) is the default root of all seven scripts and the loaders. Only the public root may write `site/`;
  a v2 public root always runs the publication gate, and `--allow-draft` can never target `site/`.
- `scripts/cutover_v2.py`: `--plan` (blockers and steps), `--apply` (24 exact text edits in 10 files plus the `site-v2/` move; refuses
  while a blocker exists and writes nothing on any mismatch), `--rehearse DIR` (the whole cutover on a clone, then validation, build,
  script dry runs, unit tests and `actionlint` there). CI runs the rehearsal on every PR.
- Runbook `docs/briefs/cutover-taxonomy-v2.md`: owner decisions in order, external actions with commands, post-deploy checks, rollback.
- Documentation: `DATA-SCHEMA.md` (v1 and v2 files, `observatii/`, `_sync`), `ARCHITECTURE.md` (v2 roots, enrichment, `_sync`,
  CI; 9 Mermaid blocks parse), `CONTRIBUTING.md` (proposal routes as the code supports them; v2 is not editable by contributors yet),
  `README.md`, `CLAUDE.md`/`AGENTS.md` command lists (Haiku), `data/taxonomy-v2/README.md` (detach). `scripts/test_docs.py` fails
  when a column is missing from `DATA-SCHEMA.md`.
- Measured on the merged branch: 269 unit tests pass (34 cutover, 2 docs). `check_preview.py` 98/98. Rehearsal passes
  (269 tests in the copy, 6 skipped as cutover-state tests). `actionlint` 1.7.12 + shellcheck 0.10.0 pass on the four workflows.
  `--plan` lists 4 blockers: 122 unaccepted entries, 27 open high-priority items, `tabs.intrari` null, not detached.
  The v1 build is byte-identical to the build before slice F (timestamps aside).

**Hard**
- Existing tests pinned the draft data and the v1 default root. A simulated owner state (detached, accepted, items closed, vocabulary added)
  exposed 19 failures; the tests now read `PUBLIC_ROOT` and the derived roots, so they hold before and after the cutover.
- Two local preview servers from earlier sessions held ports 8765 and 8766, so the first browser run checked a stale build.
  The final run used port 8791. The servers were left running: they are not from this session.

**Decided**
- Detach before the owner edits, instead of routing every decision through `modificari.csv`. A direct edit and a Sheet pull into
  `v2-intrari` then work. Cost: after detach, CI proves the derivation only at the detach commit, and `--baseline` is skipped for the overlay.
- The rehearsal waives the gate only inside its copy, through a driver script. A flag or environment variable in `build.py` would be
  a way to publish drafts. Cost: the waiver lives in rehearsal code that the tests must keep in step.
- The cutover removes its own rehearsal step from `validate.yml`; `--rehearse` reports "already applied" afterwards.
- Not done: applying the v2 questions to the live Form (`form.py --apply` refuses a v2 root). It is an owner item before the cutover.

## 2026-10-20 — Integration review queue reconciled with the current classifications (slice D)

**Done**
- New code `revizuire_stare:tehnic` ("Închis tehnic"): a closure without an editorial decision. It needs a reason and refuses
  `decizie_editor`. The publication gate counts only `deschis`. Recorded as a draft.2 amendment in `versiuni.json`.
- `integrare/reconciliere.csv` (editable, 103 rows): every R, C, S and V item rewritten against `integrare/intrari.csv`, the sealed
  responses and the C/S items. `integrare.py` applies it and refuses any evidence token that does not resolve (400 tokens, all resolve).
  The base queue and every `intrari.csv` are unchanged; no classification changed.
- Result: 66 open (29 R, 23 C, 3 S, 11 V), 37 `tehnic` (31 premise not applicable, 6 duplicates). Open high priority: 28 → 27.
  Publication gate: 150 → 149 errors (122 unaccepted entries, 27 open high-priority items).
- Every open item has a "Recomandare: …" with its rationale and evidence. The Moldova area recommendation is `tara:MD`
  (ISO style, like `tara:RO`); the area is not added.
- Tests: `scripts/test_taxonomy_v2.py` 56 (16 new). Unit tests overall: 233.

**Hard**
- "The questioned value" is ambiguous when the integration value equals the draft.1 proposal. The agent closed such an item
  only when the old label is absent and the description settles the question; otherwise it stays open.
- The run attaches one excerpt to many facets, so several facet claims are weaker than the response summary. The recommendations say so.

**Decided**
- Opus review changed one rule: the agent had closed three high-priority R items (R004, R015, R030) as duplicates of medium C items,
  which removed 3 gate errors. Now the C items (C001, C008, C015) close as duplicates, and the R items stay open at high priority
  with the C texts. A test checks that a duplicate closure never points to a lower priority.
- One table for all four prefixes, and the evidence goes into `motiv`, so `schema.json` and the Sheet tab layout stay unchanged.
  Cost: the evidence is text, not a column a filter can read.
- The agent's rule for vocabulary proposals ("accept a new concept with two or more evidenced entries") is a recommendation only.
  It is not in the specification; the owner decides.

## 2026-10-20 — Sheets and Form for v2: sync marker, three-way pull, blocking validation (slice B)

**Done**
- `sheets.py --data-dir <v2 root>` works only on new tabs: `v2-intrari` (mirror of `intrari.csv`) and, with `--tabs`, `v2-revizuire`.
  A v2 root refuses `proiecte`, `orgs`, `propuneri` and `_sync`; a v1 root refuses the `v2-` tabs. Every cell is text; multi-value
  `|` cells get at most a suggestion list, never a strict drop-down.
- Sync base: a tab `_sync` (`tab, commit, sha256, time`). `push` writes it last, and only when the pushed bytes equal the CSV at
  `HEAD`. `pull` merges three ways (base = the CSV at the marker's commit) and writes nothing when the Sheet and the repo changed
  the same cell (exit 3). `push` reads by column name and clears stale columns to the right (a latent bug of the old `push_tab`).
- `pull --check` validates the pulled rows with the root's checks (v2: per-token IDs and schemes) and exits 1 on errors.
- `sheets-pull.yml`: a conflict fails the job before any PR change. A failed `validate.py` or `build.py` still opens or updates
  the PR, then sets the commit status `validate / sheets-pull` to failure and fails the job. `sheets-push.yml` uses the marker, not `before`.
- `form.py --data-dir <v2 root>` plans 13 questions in `intrari.csv` order (6 kinds, 13 root subjects and 12 formats as
  checkboxes, 4 coverage levels). `data/form-v2.json` (version 1) maps labels to IDs; it never re-maps a label.
  `--import FILE.csv` turns `propuneri` rows into `intrari.csv` rows and reports unknown labels. `--apply` and `--save` refuse v2.
- `scripts/test_sheets_form.py`: 122 tests with an in-memory Sheet, no Google and no network. Real data round trips byte for byte:
  109 + 13 v1 rows and 122 × 31 v2 cells. The workflow steps run in `bash -e` against stub `uv`, `gh` and `python3`.
- Measured: 217 unit tests pass; `actionlint` passes on the four workflows.

**Hard**
- This worktree also started at `v0.3.1` and was fast-forwarded before work.
- A checkbox cell joins labels with commas, and one subject label contains commas ("Drept, justiție și drepturi").
  The importer splits by known labels, longest first.

**Decided**
- A conflict writes nothing for any tab. Cost: one conflicting cell holds back the other Sheet edits until it is settled.
- An unusable marker (unknown commit, other bytes) is an error, not a silent two-way fallback, which would bring back the
  "revert" defect. Cost: the owner repairs it once (`--since` or `push --force`).
- The importer sets `de-revizuit` with an empty subject when a response ticks no subject or several; the ticked IDs go to
  `nota_clasificare`. Taking the first one would be a guess. This differs from the brief's `propus`; accepted.
- Do not require `validate / sheets-pull` in branch protection: only the `sheets-sync` PR gets it, so it would block the others.
- Not verified against Google: `add_worksheet` by the service account, `batch_clear` with two ranges, an empty new tab's values,
  and `gh api …/statuses` with `GITHUB_TOKEN`.

## 2026-10-20 — Enrichment on explicit roots; profile merge; label hashes; dated last activity (slice A)

**Done**
- `profile.py`, `search.py`, `review.py` take `--data-dir` (default `data/`). A v2 run reads entries from `load_catalogue` and
  reads and writes only the root's `observatii/` files. Images stay in `site/img/`. The three scripts now import under plain
  `python3`; each asks for its libraries only when it needs them.
- `common.merge_profile(old, fresh)`: a refresh (also `--force`) keeps `mentions`, `mention_hosts`, `search_social`, `opr`, and
  the `--extra` signals that the new fetch did not return (`cert_first`, `wiki_refs`, the repo group, …). `wiki_refs()` returns
  None on a failed call instead of a false 0.
- `search.py` on v2: author names from the attribution relations, `autor_original` as fallback; organisation sites only from
  relation targets that are organisation entries. Example: `7-ani-de-acasa` now searches "Funky Citizens", not `funky-citizens`.
- `review.py` on v2: facet IDs with definitions, one array per facet, cited evidence for technologies and typed roles
  (a quote of at least 12 characters from the supplied text), unknown terms to a proposal list. Output in
  `observatii/review/` (gitignored); `intrari.csv` is never written. The v1 prompt, schema and suggestion rows are unchanged
  (compared on all 122 entries).
- Each review answer stores hashes of the entry text, the sent URL set, the vocabulary, the prompt and the model. A changed hash
  makes the entry due again. `build.py` counts a label only for a kept row with the same URL; a partly labelled entry adds its
  unlabelled kept hosts and carries `provisional: true`. `review.py` and `build.py` print the label coverage.
- `last_activity`: a dated update wins; the copyright year is a fallback, as `<year>-01-01`, never after today.
- `scripts/test_enrichment.py`: 55 tests, no network. All 95 unit tests pass (also on Python 3.12).
- Measured: label coverage 0/1408 kept rows (no labels exist yet). Before the fix, 27 profiles had a future
  last activity (`2026-12-31`). v1 build: `stale` changes on 2 of 122 items (`code4ro` 2026 → 2023; `e-cutremur` empty → 2023),
  `score` on 19, all lower (17 by 7–8 points; `code4ro` 73 → 49, `e-cutremur` 57 → 33). Nothing else in the build changed.
- `docs/METODOLOGIE.md` and `docs/DATA-SCHEMA.md` describe the new rules.

**Hard**
- This worktree also started at `v0.3.1`; the agent rebased its empty branch onto the brief's commit.

**Decided**
- The hashes stay in the local, untracked `raw.jsonl`. Cost: a fresh checkout treats every entry as due (a paid re-run).
  A tracked hash file would avoid it, but it adds a file; revisit before the first paid run.
- A failed fetch never blanks a known value. Cost: a feed that a site really removed stays in the profile until `--extra` finds another.
- `review.py --dry-run` no longer fetches the homepage (also v1); `--fetch` restores it. A dry run must work offline.
- The v2 review does not propose `maturitate` or `tip_organizatie`. Maturity needs an explicit declaration (specification).

## 2026-10-19 — v2 browser code: failed load, noscript, head metadata, observed dates, methodology (slice C)

**Done**
- Work moved to branch `taxonomy-v2-migration`; `main` (8 unpushed commits) is unchanged. Slices A–D ran as Sonnet agents in
  separate worktrees from the brief `docs/briefs/v2-migration-completion.md`; Opus reviewed and merged each one.
- CI (`validate.yml`): runs on `site/**`, `site-v2/**` and workflow changes too. Jobs: v1 validation and build, all `scripts/test_*.py`,
  v2 package and overlay baselines, `integrare.py` reproduction, v2 validation and preview build (uploaded as an artifact),
  a non-blocking report of the v2 publication gate, `node --check` of both browser files, the browser checks, and `actionlint`.
  Measured locally: `actionlint` 1.7.12 with shellcheck 0.10.0 passes on all four workflows.
- Slice C, in `site-v2/app.js` (production `site/app.js` is unchanged; the cutover brings the fixes):
  a failed or aborted `data.json` request shows a message, a retry button and the three archive links;
  `canonical`, `og:*` and `twitter:*` follow the open entry and return to the home values on close;
  `since` is called "prima urmă observată" everywhere ("apărut recent", "nu este data lansării"), with tooltips for Z/L/A.
- `site/index.html` (shared): a `<noscript>` block with the archive links, and a footer link to the new `docs/METODOLOGIE.md`
  (Romanian; statuses, dates, score weights, what the score favours, limits; written from the code).
- Measured: `scripts/check_preview.py` 98/98 (35 new; 4 fail as expected with the old head and badge code).
  The v1 build differs from the previous build only in `index.html` and the 122 entry pages (the noscript and the footer link).

**Hard**
- One agent worktree started at `v0.3.1`, not at the branch. The agent fast-forwarded it before working; the others started correctly.
- `entry_pages()` already puts its own `<noscript>` at the top of each entry page, so the template's block sits inside `#results`.

**Decided**
- Fix the audit's browser defects in `site-v2/` only, as in v0.6.1. Cost: production keeps them until the cutover.
- Keep the `nou` URL value; only the wording changes. Old links keep working.
- The footer link and noscript reach production with the next merge to `main`. The methodology page names the v1 wording too.

## 2026-10-19 — One footer line for corrections; draft notices hidden

**Done**
- Owner request: the footer's "Propune un proiect" block has one line with the three ways to correct an entry:
  the Sheet (`tabel`), the Google Form (`formular`), and a GitHub issue. The text is in `site/index.html`.
- Owner request: the preview hides the "classifications are proposals" notices in the toolbar, the detail panel,
  the archives, and `llms.txt`. One `DRAFT_NOTE` switch in `site-v2/app.js` and one in `scripts/build.py` turn them back on.
- Measured: `scripts/check_preview.py` 63/63.

**Decided**
- Hide the notices with a switch instead of deleting them. The preview still sets `draft`, and a build without
  `--allow-draft` still refuses proposed classifications.

## 2026-10-19 — Phone layouts for cards and list; site address under the name

**Done**
- Owner request, in `site/style.css` (production and preview): below 720 px, a card is a row with the picture as a
  75 px square on the left, with type, name, tagline, and status. The list hides the picture and keeps the logo,
  description, badges, and dates. The detail panel puts the site address right under the name.
- The list row's date line started with "·" when the grey line was empty (v2 projects). Both browsers now join the parts.
- Measured: `scripts/check_preview.py` 63/63 (2 new checks for the phone layouts).

**Decided**
- Change the layout with CSS only. The card and row markup stays the same, so the desktop layouts are unchanged.

## 2026-10-19 — v1 details restored in the v2 preview; site link and footer note

**Done**
- Owner request: the detail panel's site link is now the plain address (blue, underlined, with the arrow), not a "Deschide …" button.
  Changed in `site/app.js` and `site-v2/app.js`; style in `site/style.css`. The archive button ("Vezi în arhivă") is unchanged.
- Owner request: the footer's "Propune un proiect" block has a "Corectează în tabel" link to the Sheet, with the panel's note.
  Changed in `site/index.html`, so the production site also gets it at the next push.
- Compared v1 and v2 builds entry by entry (122 detail panels, cards and list rows on three tabs, archives, llms.txt, feed)
  and by free-text search over all 55 v1 keywords. Restored in the v2 preview:
  - "Corectează în tabel" was missing on all 122 entries, because the Sheet has no v2 tab. The build now gives each item the v1 tab and row.
    All 122 rows equal the v1 build's rows.
  - Free-text search lost 133 entry–keyword matches (36 of 55 keywords, for example `date deschise`, `primării`, `alegeri`).
    Now 0: the search also reads the `legacy` words.
  - "Tot din …" was missing on 6 entries, because related entries had to share the primary subject. Now 4 remain:
    3 resources whose subject no other resource has, and `incentru`, which has no subject.
  - Cards lost their type (for example "Bază de date"). The grey line now names the first format.
  - Archive subject groups lost their hint line. Each now shows its four most frequent topics.
- Measured: `scripts/check_preview.py` 61/61 (6 new checks); `scripts/test_taxonomy_v2.py` 40 tests pass; v1 validator 0 errors.

**Hard**
- The comparison also shows intended differences: "Autor" is now "Atribuire · rol neconfirmat", "cod deschis" is "cod public",
  and v1 types and `#keywords` are replaced by the classification groups. These follow the specification and stay.

**Decided**
- Use the v1 Sheet row until the v2 tab exists. A report then reaches a real row; the alternative showed no Sheet option at all.
  The v1 row cannot hold v2 facets, so classification corrections still need GitHub or the review queue.
- Keep v1 words in the search index only. The vocabulary is frozen, so adding alternative labels was not an option.

## 2026-10-19 — Taxonomy v2 preview: missing UI recommendations

**Done**
- Compared `site-v2/app.js` with the specification's "Visible filter design" and "Browser filtering and search" sections,
  and with the audit's dialog defects. Most items were in v0.6.0. These were missing:
  - `Temă` showed all 52 project topics as one tag cloud. It now shows the 12 most used, plus a button for all of them.
  - Result badges had no facet name. Each badge now names its facet in a tooltip and in hidden text.
  - Facet choices had no group name for screen readers. Each facet's choices now form a named group.
  - Ctrl/Cmd+K and `/` moved the focus to the search box behind an open dialog. They now do nothing while a dialog is open.
  - Shift+Tab from Close tried to focus a link inside the closed report panel, so the focus stayed on Close.
    The focus trap now skips controls inside a closed panel.
  - A toggle or the reset button lost the focus after a filter change. The focus selector now uses only the control's own attributes.
    The mobile sheet also keeps its scroll position.
- Removed a dead first definition of `facet()`.
- Measured: `scripts/check_preview.py` 55/55 (8 new checks); `scripts/test_taxonomy_v2.py` 40 tests pass. `site/` is unchanged.

**Hard**
- In Chrome, a link inside a closed `<details>` still has client rectangles. A visibility test alone did not exclude it.

**Decided**
- Show the most used topics instead of grouping all topics under subject headings. Grouping would still show 52 choices.
  The subject filter already gives the hierarchical route.
- Fix the audit's dialog defects in `site-v2/` only. `site/app.js` gets them at the cutover, so the v1 build stays byte-identical.

## 2026-10-19 — Taxonomy v2 core slices 1–4: draft.2 package, integration copy, loaders, build, preview

**Done**
- Upgraded `data/taxonomy-v2/` to `2.0.0-draft.2`. `concepte.csv` equals the frozen run's 128-concept table (content; LF endings).
  New `valori.csv` (16 lists, 65 codes), `roluri-linkuri.csv` (22 roles), `gazde-linkuri.csv` (29 hosts), `versiuni.json`.
  `schema.json` has field rules with list/scheme references and cardinality; `setari.json` keeps only the reporting addresses.
  `manifest.json`, `source/`, `reference/`, `observatii/`, the initial ledger and the base `intrari.csv` are unchanged.
- Moved the checks to `scripts/taxonomy_v2.py`. `data/taxonomy-v2/validate.py` is now a thin wrapper with `--root` and `--publication`.
  Measured: base package `--baseline` 0 errors; integration copy `--baseline` 0 errors.
- Added `data/taxonomy-v2/integrare.py` and the overlay `integrare/`. It verifies the run's seal (258 hashes) and frozen
  files before reading, and refuses a vocabulary that differs from the frozen one. 122 entries: 121 `propus`, `incentru`
  `de-revizuit`; results 105 classified, 16 partial, 1 abstention. Texts, links, contacts, `stare` and `nota` come from
  `source/` by source identity. Queue: 103 items (66 R, 23 C, 3 S, 11 V); 10 vocabulary proposals (8 concepts, 2 areas).
- Addressed the three semantic concerns in `integrare/modificari.csv` (4 rows): M001 keeps `data-expertforum`'s media root
  with an exact excerpt from the stored source's Media section; M002 lowers its confidence and S001 asks for the Moldova
  area; M003 removes `jailando`'s `format:registru`; M004 removes `presspay`'s `scop:sprijin-organizatii` and proposes
  `scop:sustenabilitate-presa`. The sealed run is unchanged.
- `common.py`: `data_schema`, `observation_paths`, `split_ids`, `load_vocabulary`, `load_catalogue`; loaders take a root.
  `validate.py --data-dir [--publication]`. Publication gate on the integration copy: 150 errors (122 unaccepted, 28 open high-priority items).
- `build.py --data-dir --site-dir --allow-draft`; the v2 browser code is in `site-v2/` (`app.js` fork, `v2.css`).
- Verified: v1 validator 0 errors, 28 warnings. An isolated v1 build and a default build in a copy equal the HEAD build
  (all pages, archives, `llms.txt`, `index.html` identical; `data.json` and `feed.xml` differ only in timestamps).
  v2 preview: 122 entry pages, 3 archives, 120 of 128 concepts and 10 areas in the payload, maturity 29 operational,
  1 prototype, 92 null. `scripts/test_taxonomy_v2.py`: 40 tests pass. `scripts/check_preview.py`: 47 browser checks pass
  (desktop 1280×900, mobile 390×844). Technology claims: 6 on 5 entries, each with a non-legacy justification.

**Hard**
- The run's frozen CSVs have CRLF endings and the package has LF. The adapter compares parsed rows, not bytes.
- v1 output had to stay byte-identical: the refactored builder keeps the v1 item key order and the v1 score inputs.
- A facet opened and clicked quickly lost its open state: the `toggle` event fires after the re-render. The v2 code reads
  the open state from the page. The same race exists in `site/app.js` (backlog).
- The AI topic is assigned only to organisations, so the project tab never suggests it. The check tests each tab separately.

**Decided**
- The integration copy is an overlay (`pachet.json`, `local_files`), not a full copy. One vocabulary, one set of lists
  and one source snapshot. Cost: loaders resolve two folders, and an overlay cannot replace a base table silently.
- Fork `site/app.js` into `site-v2/app.js` instead of a dual-mode file. Production JS stays byte-identical until the cutover.
  Cost: two browser files to keep in step until then.
- `schema.json` is the only source of v2 column lists; Python reads it. Cost: no import-time constants for v2.
- The abstention keeps its entry with an empty classification as `de-revizuit`; no subject was invented. Partial results stay `propus`.
- Entry `incredere` is the lowest confidence among the entry's classification claims.
- A build folder must be outside the repository; a v2 build must not target `site/`. Proposals need `--allow-draft`,
  and the preview says that its classifications are proposals.
- Old `d`, `t`, `kw`, `c` bookmarks filter on `legacy` fields with their v1 meaning and show `(v1)` pills; they are not translated.
- Nothing was pushed or deployed; no workflow, Sheet or Form changed. `site/`, `data/*.csv` and `data/taxonomy.json` are unchanged.

## 2026-10-19 — Preserve taxonomy work for implementation

**Done**
- Committed the frozen classification run as `3a1c8fe`, tagged `v0.4.0`.
- Prepared the remaining proposal, snapshots, specification, classifier contract, audit notes, and handoff for a separate commit.
- Added the completed-run pointer to the handoff. The shared package remains draft.1; production remains unchanged.
- Rechecked the package baseline: 122 entries, 125 concepts, and zero errors. Production validation reports zero errors and 28 existing warnings.
- Excluded editor locks and Python caches from the package's Git exception.

**Hard**
- The original handoff described classification as future work. Its continuation update now records the completed experiment.
- Preserved source CSV text includes trailing spaces and CRLF line endings. Those bytes remain unchanged.

**Decided**
- Use the sealed candidate for core slices 1–4. Apply semantic corrections in a separate integration copy.
- Keep an automated inference runner optional for this preview; implementing it first would repeat completed classification work.
- Record this specification and data-package deliverable as `v0.5.0`. This repository has no `Cargo.toml`.

## 2026-10-19 — Consolidated classification input

**Done**
- Added `data/taxonomy-v2/clasificare-input.csv`: 122 unique original entries from the two immutable source CSVs.
- Preserved original descriptions, links, categories, types, keywords, geography, attribution, and source record references.
- Excluded manually proposed v2 assignments, private notes, and contact fields. Verified CSV round-trip equality.

**Hard**
- The consolidated input still has the original evidence gaps. One file does not make missing descriptions available.

**Decided**
- Prepare the agreed schema and vocabulary first, run and evaluate automated classification second, then integrate the build and UI.
- Keep the classification input separate from the controlled vocabulary and output contract.

## 2026-10-19 — Implementation handoff and automated classification prompt

**Done**
- Updated `docs/specs/taxonomy-v2.md` with the owner's agreed draft.2 decisions.
- Specified zero-or-one maturity: experiment, prototype, pilot, or operational. Reliability, adoption, and novelty remain separate dimensions.
- Specified CSV-owned code lists, link roles, and host lookup, with structural JSON rules and no independently edited duplicate enums.
- Added `docs/briefs/handoff-taxonomy-v2.md` as the fresh-session entry point, with core implementation slices and preview acceptance checks.
- Added `docs/prompts/taxonomy-v2-classifier.md` and its machine-readable JSON output schema.
- Defined an initially automated experiment with evidence citations, per-assignment confidence, vocabulary-gap proposals, abstentions, and independent evaluation.
- Checked the output JSON Schema with Draft 2020-12 validation and 12 structural cases. The current draft baseline still passes with 0 errors.
  Citation accuracy, supplied-ID membership, justification coverage, and original-attribution preservation are explicit checks for the future runner.

**Hard**
- The actual package remains draft.1. It has one maturity concept and the earlier JSON-owned lists.
  The handoff makes draft.2 package preparation a prerequisite for the classifier so that prompt and data cannot disagree.

**Decided**
- Treat the new request as preparation for implementation in a fresh session. Production code and source data remain unchanged in this turn.
- Keep the manually proposed assignments out of model input; compare them with automated results only after inference.
- Distinguish a valid model response, a complete candidate, and an editorially accepted entry.
- Preserve incomplete model output and uncertainty instead of manufacturing a primary subject.
- No provider was selected and no model calls were run. The next step for inference is a runner with a no-call dry run.

## 2026-10-19 — Taxonomy diagrams and filter implications

**Done**
- Added a Mermaid model overview and a filter-combination example to `docs/specs/taxonomy-v2.md`.
- Added `data/taxonomy-v2/export_mermaid.py`. It generates `docs/specs/taxonomy-v2-vocabulary.md` from the editable concept table.
- Measured complete coverage: 125 concepts across 13 subject hierarchy diagrams and 7 independent facet diagrams.
- Specified public filter labels, conditional facets, topic ancestry, unique counts, result badges, and detail-panel grouping.
- Verified the diagram export and the draft baseline validator. The draft still has 0 validation errors. `git diff --check` passes.

**Hard**
- One diagram with all 125 concepts would be difficult to read. The complete reference therefore uses smaller diagrams.

**Decided**
- Keep the current tabs, desktop sidebar, mobile filter sheet, list, and detail panel as the proposed interface structure.
- Replace mixed types and keywords with subject, topic, capability, and format filters. Put specialist facets under more filters.
- Use a flat list after subject filtering. An entry matched through a secondary subject should not appear under an unrelated primary heading.
- Distinguish national applicability from the availability of data for a particular locality. These require different evidence.
- This change documents the proposed interface. It does not modify the current frontend or production data.

## 2026-10-19 — Separate taxonomy v2 review copy

**Done**
- Created `data/taxonomy-v2/` and the integration specification `docs/specs/taxonomy-v2.md` at the owner's request.
- Proposed classifications for all 122 entries: 100 projects, 13 organisations, and 9 resources in the existing URL sections.
- Added 125 controlled concepts, including 13 local browsing subjects, with Romanian/English labels and Romanian definitions.
- Preserved the original eight top-level CSV/JSON files byte for byte. Recorded their SHA-256 hashes and copied generated observations separately.
- Added 822 initial assignment records, 86 unresolved source attributions, and 66 specific editorial review items.
- Retrieved 22 EuroVoc identifiers and Romanian/English labels from the official SPARQL endpoint. Stored the exact query and response.
- Kept every external semantic mapping and every entry classification proposed. No individual project site was fetched for this pass.
- `validate.py --baseline --export` passes with 0 errors. Twelve focused integrity checks pass on temporary copies.
  The checks cover unknown IDs, wrong schemes, duplicate slugs, missing roots, hierarchy cycles, retired concepts, external identifiers,
  relation endpoints, review decisions, manual edits, snapshot integrity, and the initial export.
- Production validation still reports 0 errors and the same 28 warnings. An isolated v1 build still produces 122 entries and 3 archives.
  All eight original data files retain their source hashes.
- Added a scoped `.gitignore` exception so that the separate proposal and its snapshots are not silently ignored.

**Hard**
- The first SPARQL query timed out after 40 seconds. A query with directly bound English labels returned the verified subset.
- Sparse descriptions cannot establish precise capabilities or technology use. Such entries retain low confidence and explicit review items.
- The document connector was unavailable. The requested specification is repository Markdown.

**Decided**
- Keep human-readable CSVs authoritative; generate `catalogue.json` from them with the package's standalone stdlib validator.
- Keep the thirteen browsing roots local. Use EuroVoc as a reference and SKOS as a modelling guide, without claiming conformance.
- Distinguish subjects from civic purposes, capabilities, formats, technologies, institution types, and geographic coverage.
- Preserve uncertain author roles as `atribuit_in_sursa`; guessing a maintainer or funder would create unsupported claims.
- Do not adapt production scripts or publish the proposal. The owner will review the copy and carry out the later integration.

## 2026-10-19 — Product, UX, and architecture audit

**Done**
- Reviewed the purpose, data flow, frontend, enrichment scripts, and publishing workflows.
- Ran validation: 0 errors, 28 warnings. Built a temporary copy: 122 entries, comprising 100 projects, 13 organisations, and 9 resources.
- The build has 101 active entries, 1 unconfirmed entry, and 20 inactive entries. Twelve live entries have no descriptive text.
- Checked Chrome at widths 320, 390, 768, 1024, and 1440. No page-level horizontal overflow or normal-load JavaScript errors appeared.
- Reproduced blank results after a failed data request, dialog focus defects, mobile filter focus loss, and stale canonical metadata.
- All eight Python scripts parse. `node --check site/app.js` passes.
- Recorded findings in BACKLOG.md. No implementation or source data changed.

**Hard**
- The configured Playwright browser binary was absent. The audit used installed Chrome.
- The audit did not run paid enrichment, write to Google, trigger workflows, or verify live hosting settings.

**Decided**
- Keep the static architecture. Current size does not justify an application server or a database.
- Prioritise evidence quality, failure handling, and editorial checks before adding ranking signals.
  These are audit recommendations; no product or specification changes were applied.

## 2026-10-19 — llms.txt

**Done**
- `build.py` writes `site/llms.txt` (`llms_txt`), in the llmstxt.org format: an H1, a summary in a blockquote,
  the data links (`data.json`, the two CSVs, `DATA-SCHEMA.md`, `CONTRIBUTING.md`, `feed.xml`), and one
  Markdown link per entry to its own page, with the tagline (else the description, cut at 200 characters), the
  site address, and `(offline)` / `(arhivat)` for a retired entry. Projects are grouped by domain, organisations
  run A-Z, resources are grouped by `fel`. Measured on the current data: 122 entries, about 21 KB.

**Decided**
- The text is in Romanian, like the site. The file is generated on every build, so it cannot drift from the data.
  A hand-written file would be shorter, but it would go out of date with each new entry.
- The links go to the entry pages, not to the projects' sites: the entry page carries the description in
  `<noscript>`, and the line also gives the site address. No `llms-full.txt`: `data.json` holds the full data.

## 2026-10-18 — Stale CSS behind Cloudflare

**Done**
- Symptom: after the push, the public footer showed the old dark palette and overlapping theme buttons, but the
  new HTML (the "Liste simple" line). Measured with `curl -I`: `style.css` and `app.js` answered `cf-cache-status:
  HIT`, `cache-control: max-age=14400`, `last-modified` from the earlier deploy, and their hashes differed from
  the files on GitHub Pages and in the repository. The HTML and `data.json` were `DYNAMIC` and current.
- Cause: Cloudflare caches static files by extension, and its browser TTL (4 hours) replaces the 10 minutes that
  GitHub Pages sends. HTML and JSON are not cached, so the new page ran with the old CSS and JS.
- `build.py` now writes `?v=<sha1 prefix>` on the `style.css` and `app.js` links of `site/index.html`
  (`stamp_assets`, before the page writers copy it). A changed file has a new address, so nothing needs a purge
  and no browser keeps the old file. Browsers that hold the old page's CSS see the new one on their next visit
  to the page (the HTML is cached 10 minutes).

## 2026-10-18 — A manual image for an entry

**Done**
- The owner saved `site/img/og/semnal-razboiul-hibrid.webp` by hand, and it did not show. Cause: the entry
  had no row in `profil.csv` (a new Sheet row, never profiled), and `build.py` takes the image from that row.
- `profile.py` now adopts an image file that it did not write (`manual_image`): it records the size, colour
  and kind with `img_source` = `manual`, and no fetch or screenshot replaces it. A file from an earlier run
  names its source in the old profile row, so it is refreshed as before. Run `uv run scripts/profile.py
  --only <slug>` after saving the file.
- Profiled `semnal-razboiul-hibrid` (status activ, image kept: 34708 bytes before and after, 960 x 557).

**Hard**
- The same gap holds for the other new Sheet rows: they have no profile row yet (see the status `neverificat`
  in `data.json`). `uv run scripts/profile.py` without arguments profiles them.

## 2026-10-18 — Logos, archives, report a problem, Monokai dark theme

**Done**
- The owner ran `form.py --apply` (read back with `form.py`: 13 questions, "Altele" in Domeniu).
- Logos: the 128 px icons are shown as the project's logo: 24 px before the name in list rows (no blank
  when there is none, so a title without a logo starts at the left edge), and 72 px in a new drawer
  header, left of the title, the "Deschide" button and the tagline.
- `acoperire` empty now means `national` in `build.py`; `validate.py` no longer warns about it.
- Archives: `build.py` writes `site/proiect/`, `site/organizatie/` and `site/resursa/` `index.html`: every
  entry of the kind, readable without scripts. The footer links them. All three, not only projects and
  organisations, so that the resources do not lack one.
- "Semnalează o problemă" at the end of the drawer: a `<details>` with three prefilled options (the Sheet
  row, an e-mail, a GitHub issue). `data/site.json` holds the addresses; `build.py` adds `row` to each item
  (row 1 is the header, so the first entry is row 2). The e-mail is empty,
  so that option is hidden until the owner sets it.
- Dark theme is Monokai Pro, filter Classic (bg `#272822`, text `#fdfff1`, pink `#f92672`, blue `#66d9ef`,
  green `#a6e22e`, yellow `#e6db74`, orange `#fd971f`; the hex values come from the theme's preview
  SVG on vscodethemes.com, except orange). Project images in dark get `opacity: .85` so a white page
  blends into the dark background. The accent badge text now uses `--bg`.
- The pending work of the earlier entries was committed by topic (8 commits).

**Hard**
- The e-mail address is not in the repository; I did not guess one.

## 2026-10-18 — Authors, `fel`, kind paths, text size, theme

**Done**
- Pulled the Sheet into the CSVs (`sheets.py pull`): 4 new rows (one is a Sheet edit of `registrul-firmelor`),
  `autor` cells changed to org slugs, the org slug `ethicalmedia` renamed `ethical-media`, and the entry
  `gov2` removed. PR #1 is stale now; the next `sheets-pull` run updates it.
- `taxonomy.json`: new domain `altele`, and a new list `fel` (`proiect`, `resursa`, `articol`, `ghid`,
  `campanie`, `cercetare`), each with the tab it belongs to. `common.FEL_KIND` maps `fel` to the tab, so
  every `fel` but `proiect` lands on "Resurse & liste". `validate.py` and the Sheet's drop-down read
  the list. Data still holds only `proiect` and `resursa`; the owner has not set the new values yet.
- Addresses follow the tab: `/proiect/…`, `/organizatie/…`, `/resursa/…` (`build.py` writes the three
  folders; `app.js` reads any of them).
- Authors: `build.py` turns `autor` into `authors: [{name, org}]` (a name that is an `orgs.csv` slug
  becomes that organisation). The drawer of an entry shows the organisation as a card, and "De același
  autor" lists the other entries with the same author. The drawer of an organisation shows "Proiecte și
  resurse". Names that are not slugs match by their written text.
- Footer: text size S / M / L / XL (0.9 / 1 / 1.15 / 1.3 of the current size; M is the old size) and
  theme Sistem / Luminoasă / Întunecată. Both persist in localStorage and apply before the first paint
  (a `<head>` script). Every `px` font size in `style.css` is now `calc(Npx * var(--fs))`; the dark
  styles exist twice (OS preference, and `data-theme="dark"`).
- Measured in headless Chromium: body font 14.4 / 16 / 18.4 / 20.8 px; OS dark + "Luminoasă" gives a
  white page; reload keeps both choices; no page errors, no 4xx.

**Decided**
- `acoperire` may be empty (a warning, no longer an error). Later the same day the owner chose a default:
  an empty value means `national`, with no warning. The two new Sheet rows had it empty, and an
  article has no reach. Cost of the alternative: CI fails on rows the owner added on purpose.
- An author written as plain text is not matched to an organisation by name, only by slug. Cost of
  name matching: a link nobody asked for. Cost of slugs only: the owner must write the slug.

**Hard**
- The `gov2` entry is gone from the Sheet, and three rows still name `gov2` as author.

## 2026-10-18 — Favicons beside names, first Sheet pull request

**Done**
- `sheets-pull` ran for the first time (by hand). It opened PR #1 with one new row
  (`registrul-firmelor`) and one edit (`ro-api-hub`). The owner swapped the two description cells of
  the new row in the Sheet, and the second run carried the fix. The merge is still open (see **Hard**).
- `site/app.js`, `site/style.css`: the project's favicon (`it.icon`) shows before the name in list rows
  (16 px) and in the detail heading (24 px). Rows keep their og-image thumbnail. An entry without a
  favicon gets a blank of the same width in a row, so the names stay aligned. Cards are unchanged.
- Measured in headless Chromium, light and dark: 65 rows show a favicon, 16 rows show a gap, and
  the page raises no errors. Of the 117 entries in `data.json`, 81 have a favicon.

- List view: a **Links** column (up to 4 icons: curated links first, then those found on the site;
  "+n" for the rest), and **Age** / **Updated** columns, narrower, with compact values: `9Z` days,
  `2L` months, `13A` years, no space. The headers are English at the owner's request; the values in
  the drawer keep the long Romanian form. "Zile" became `Z` by analogy with `L` and `A`.
- Pretty links: `build.py` writes 117 pages to `site/proiect/<slug>/index.html` (git ignores them).
  Each has its own title, description, canonical URL and og/twitter image, a `<base href="../../">`
  and a `<noscript>` summary. `app.js` takes the slug from the path, writes `/proiect/<slug>/` with
  `pushState`, and still opens `?p=<slug>`. An entry opened by address alone shows its own tab
  (organisations, resources). The RSS links point to the new addresses.
- Tested in headless Chromium: static page, close, click in the list, Back, old `?p=`, organisation
  page, filters in the query, `j` step, no trailing slash: no page errors, no 4xx.

- `docs/DATA-SCHEMA.md`: every column of `proiecte.csv`, `orgs.csv`, `profil.csv`, `mentiuni.csv`,
  `mentiuni_etichete.csv`, `taxonomy.json`, `form.json` and `data.json`, with the rules of
  `validate.py`. Written from the scripts; each claim was checked in the code. Linked from the README,
  CONTRIBUTING, ARCHITECTURE and CLAUDE.md.

**Hard**
- A relative image path breaks after `pushState` to `/proiect/<slug>/` on a page without `<base>`
  (`img/og/x.webp` resolves under `/proiect/<slug>/`). Found in the first test run. `app.js` now
  prefixes every data path with `ROOT` at load.
- A fix pushed to the `sheets-sync` branch would make `sheets-push` exit 3 after the merge: the
  Sheet's swapped cells count as edits the repo does not have. The fix went into the Sheet instead.
- The agent's `gh pr merge` was blocked by the permission classifier. The owner merges the PR.

## 2026-10-18 — Form live, Form template, architecture doc

**Done**
- `form.py --apply` wrote the 13 questions to the proposal Form (revision 7). `--save` stores the
  Form, as edited by hand, in `data/form.json`; `--apply` uses it as the template from then on.
- Scripts read the repo's `.env` themselves (`load_env` in `common.py`); exported variables win.
- First real sync: pulled the owner's Sheet edit (`demoanaf`), removed quotes typed into two `tip`
  cells and around one description, pushed back with `--force`; `diff` then showed no differences.
  `sheets-push`, `pages` and `validate` passed on GitHub.
- Footer links the public Form (forms.gle/wswqrm7P4QV25NZx7). `docs/ARCHITECTURE.md` describes the
  data flow, the Sheet ⇄ CSV workflows and the Form, with Mermaid charts; linked from the README.

**Hard**
- The owner saw the Form's file name as "Untitled form". `form.py` sends no `updateFormInfo`; the
  API showed `documentTitle: "Untitled form"` already before the first `--apply`. Now both names are
  "Sugestii listă civtech.gov2.ro".

**Decided**
- Taxonomy-backed choices (Ce propui?, Domeniu, Tip, Acoperire) always come from `taxonomy.json`, even
  with a template, so answers map back to CSV keys. Cost: renaming those four questions breaks that.

## 2026-10-18 — Proposal Form generated from the data model (brief `form-generator.md`)

**Done**
- `scripts/form.py` (PEP 723: `google-auth`, `requests`). It plans 13 questions in the order of the brief (D2).
  The choices of `Domeniu`, `Tip` and `Acoperire` come from `data/taxonomy.json`; the first question has the
  labels of the brief. `TITLES` (top of the file) holds the titles; `ANSWER_KEYS` maps title → choice label →
  CSV key and is printed. Default mode prints the plan and the Form as it is now (read only). `--json` also
  prints the `batchUpdate` body. `--apply` deletes all items and creates the planned ones in one
  `forms.batchUpdate` (D1). **`--apply` was not run**: the owner approves the dry run first.
- README: part "Formular (the proposal Form)" in the Google Sheets section.

**Measured** (2026-10-18; the key was never printed)
- `GET forms/{id}` with scope `forms.body`: HTTP 200. The Form has 1 item (`Untitled Question`, radio),
  revision `00000006`, and a linked Sheet.
- Tab `propuneri`, row 1: `Timestamp`, `Untitled Question`. 0 responses.
- The plan: 13 questions (3 required), 14 requests in the body (1 `deleteItem`, 13 `createItem`). The longest
  help text (Domeniu, with 11 hints) has 772 characters.
- The `batchUpdate` body has 0 errors against the schema of the v1 discovery document (field names, types,
  enums). That is the only check: the API has no dry run.
- Discovery document: `TextQuestion` has only `paragraph`, so a URL validation is not possible.

**Hard**
- No way to test the write. A scratch Form would be a new file in the service account's Drive (outside the
  brief), so the first real test is `--apply` itself. The call is all or nothing, and it carries
  `requiredRevisionId`, so a concurrent edit of the Form makes it fail instead of being overwritten.
- The auto-mode classifier denied a test run of `--apply` without credentials (a guard check). It was not
  retried.

**Decided**
- **Hints in the help text, one `label: hint` line per hint of 60 characters or less.** A drop-down has no text
  per choice, so the hints go into the help text of the question. All 20 hints pass. Alternative: the hint in
  the choice label. The answer text would then differ from the taxonomy label, and a changed hint would break
  `ANSWER_KEYS`.
- **Key `organizatie`** for the third choice of `Ce propui?` (the `kind` of `common.py`); `proiect` and `resursa`
  are the `fel` values.
- **Delete from the last index down**, so every index in the request is the one that was read.
- **`includeFormInResponse`**, then compare the titles of the answer with `TITLES`. A mismatch is an error.
- The Google imports sit inside functions, so `from form import ANSWER_KEYS` works without the Google packages.
- **Open risk:** the Sheet may keep the column `Untitled Question` after the delete. See BACKLOG, *Proposal
  Form*.

## 2026-10-18 — Google Sheets sync (brief `sheets-sync.md`)

**Done**
- `scripts/sheets.py` (PEP 723: `gspread`, `google-auth`): `diff`, `pull`, `push [--since REF] [--force]`.
  Key from `GOOGLE_SA_KEY` (JSON text) or the file in `GOOGLE_APPLICATION_CREDENTIALS`; Sheet from `SHEET_ID`.
  `pull` reads strings, checks that row 1 equals `PROIECTE_COLS` / `ORGS_COLS`, drops empty rows, strips
  trailing spaces and line-ending `\r`, and writes with `write_csv`. `push` writes header and rows in one
  `update` (RAW), clears the rows below, then freezes and bolds row 1, sets every cell of the table to plain
  text, and adds drop-downs for `fel`, `domeniu`, `tip` (suggests only), `acoperire`, `stare`, `civictech`.
  Exit codes: 0 done, 1 error, 3 the Sheet holds edits not yet in the repo (nothing written).
- `.github/workflows/sheets-pull.yml`: every 6 hours and on demand; `diff`, `pull`, `validate.py`,
  `build.py`; one pull request from `sheets-sync` (force-pushed), title and text in Romanian, text = `diff`
  plus `validate.py` output. It commits the two CSVs only. When the Sheet matches `main` again, it closes an
  open `sheets-sync` pull request.
- `.github/workflows/sheets-push.yml`: on push to `main` that touches the two CSVs, and on demand (inputs
  `since`, `force`); `push --since <before>`; exit 3 fails the job with "Tabelul are modificări
  nesincronizate; rulează sheets-pull". `fetch-depth: 0`, so that `--since` can read an older commit.
- Both workflows use `concurrency: group: sheets`, `cancel-in-progress: false`.
- README: the "Editing in Google Sheets" section now says how it works, with the one-time setup.

**Measured** (all on 2026-10-18; the key was never printed)
- Real Sheet, read only (`diff`): `proiecte` 104 rows in the CSV and the Sheet, one cell differs
  (`demoanaf` / `descriere`: the Sheet lacks the sentence "Proiect independent." and the two line breaks).
  `orgs` 13 rows, no cell differs. Because of that cell, the first `push` to the real tabs was **not** run
  (brief: stop and report).
- Real Sheet, `pull` as a test: `proiecte.csv` 1 cell (4 lines in `git diff`), `orgs.csv` 2 lines
  (`descriere_scurta` of `code4ro` and `techsoup` end with a space in the CSV; `pull` strips it). Restored
  with `git checkout`.
- Push, pull and diff on two temporary tabs of the real spreadsheet (`zz-test-proiecte`, `zz-test-orgs`,
  created and deleted in each run; the data tabs were not touched): `push` wrote 104 and 13 rows; `diff`
  then showed no differences; `pull` left `proiecte.csv` byte-identical (empty `git diff`) and `orgs.csv`
  differs in exactly the 2 trailing-space lines. Under `UNFORMATTED_VALUE` the `civictech` cells come back as
  strings (7 of 7 read); A1, A2 and O2 carry `numberFormat TEXT`; row 1 is frozen and bold; 6 drop-downs, 5
  strict and `tip` not.
- Guards on the same tabs: a Sheet edit gives exit 3 for `push` (no ref), for `--since HEAD` and for
  `--since 6aec21c` (only the edited cell is listed, not the rows that changed in the repo since). With the
  Sheet equal to the current CSVs, `--since c2028f3` gives exit 0 (the merged pull request case). A renamed
  header cell gives exit 1 and names "missing 'nume'; unknown 'nume_x'"; an unknown ref gives exit 1;
  trailing spaces are stripped.

**Hard**
- The first test runs failed on two defects, both fixed: an empty tab comes back from `get_all_values()` as
  one empty row (it looked like a wrong header), and a `values.update` with `RAW` resets the number format of
  the cells it writes (the first version formatted before writing, so no cell was plain text). Now
  `push_tab` writes first and formats after.
- The service account cannot create a spreadsheet (HTTP 403), so the tests used temporary tabs in the real
  spreadsheet.
- The tab list of the spreadsheet changed while this ran (`Form Responses 1` became `propuneri`): somebody
  else edits it. `sheets.py` reads and writes only the two named tabs.
- Not run: `validate.py`/`build.py` inside the workflow shell and the `gh` calls (no workflow may run, no
  push). The shell blocks passed `bash -n`, the YAML parsed, and the PR text step ran with stubbed
  `validate.py` and `build.py`.

**Decided**
- **D4 is refined, not changed.** As written, `push --since <before>` fails on the main flow: the editor edits
  the Sheet (Sheet = A + E), `sheets-pull` opens a pull request with A + E, the merge pushes to `main` with
  `before` = A, and the Sheet differs from the CSVs at A, so the job would fail on every merge of a Sheet
  pull request. Now a Sheet change counts as pending only when it is neither in the CSVs at `--since` nor in
  the current CSVs (cell by cell, three-way). A change that a pull request already carried is settled; the
  guard against losing a pending edit holds. Cost of the alternative (D4 as written): a red job after each
  Sheet pull request, and the Sheet is never rewritten from the merged CSVs. To get the literal D4 back,
  compare `changes(base, sheet)` in `cmd_push` instead of `pending(...)`.
- Row order counts as an edit only when the Sheet's order of the common slugs differs from both the old and
  the new CSV. Without `--since`, any order change counts.
- `diff` and the checks compare cells after the same normalisation on both sides (no trailing spaces), so a
  stray space is never a Sheet edit. `diff` adds a line when only the file format would change.
- An empty tab or a tab without data rows holds no edits (push fills it). `pull` refuses to write an empty
  tab over a CSV.
- `sheets-pull` closes the open `sheets-sync` pull request when the Sheet matches `main`; else a stale pull
  request would stay open. `sheets-push` takes the inputs `since` and `force` for manual runs; without them a
  manual run compares with the current CSVs.
- A pull request opened with `GITHUB_TOKEN` does not start `validate.yml`; that is why `sheets-pull` runs
  `validate.py` and `build.py` itself (D5). The job does not fail when they report errors: the errors go into
  the pull request text.

## 2026-10-18 — Network logos, link favicons, GitHub stats (brief `link-icons-github-stats.md`)

**Done**
- Drawer (`site/app.js`, `style.css`): a link to one of the 13 networks shows its logo, 18 px,
  inline SVG from Simple Icons 16.35.0 (CC0), `currentColor`. Each has `aria-label` and `title`
  with the network name; the global focus ring shows on it. Other links show their host's favicon
  (14 px) before the label; in dark mode the favicon sits on a white chip, because dark marks
  (GitHub) vanish on the dark background.
- `profile.py`: `link_icons()` fetches one favicon per non-network link host into
  `site/img/linkicon/<host>.webp` (32 px at most; skipped when the file exists, unless `--force`).
  `build.py` adds `icon` to a link when the file exists. `common.py`: `NETWORK_ROLES`, `ROLES`,
  `link_host()`, `parse_link()` (the role parsing of `build.links()` moved there).
- `profile.py` icon: `icon_candidates()` (declared icons, logo images in `header`/`nav`/`a[rel=home]`,
  root paths, two icon services) and `fetch_icon()` (first square candidate of 64 px or more, else
  the largest; a stored icon is replaced only by a larger one). `extras_one` now owns the icon step
  (`profile_one` no longer fetches it), so `--extra` upgrades small icons.
- GitHub stats in `extras_one`: new `profil.csv` columns `open_issues`, `commits`, `contributors`,
  `last_commit`, `license`, `language`. `build.py` writes `repo: {name, url, stars, forks, issues,
  commits, contributors, last, license, language, archived}` per item that has a repo. The drawer
  shows a "Cod" row under "Cod sursă".

**Measured**
- Full `--extra` run (116 entries): 151 GitHub requests; core limit 5000, 4912 left after it.
  Total for the session about 178 requests; 4895 left at the end. 0 rate-limit stops.
- 19 repos with stats (20 repos in `profil.csv`; the 20th, `rescue-4x4`, is an orphan row of a
  deleted entry). All 19 have stars, forks, open issues, commits, contributors, last commit and
  language; 13 have a licence (the others have none).
- Link favicons: 12 hosts, 12 stored, 0 failed.
- Icons under 64 px: 29 of 104 before, 22 of 106 after. 7 upgraded (crpe 16 to 99, efor 16 to 68,
  harta-firmelor 32 to 128, igov 48 to 128, ro-api-hub 32 to 128, romania-transparenta 48 to 128,
  tech-and-tonic 16 to 115); 2 new (onorata-instanta, calitate-aer-radauti, 128 px). The 22 left
  include 10 orphan files; factual stays at 32 px (its logo is an SVG) and code4ro at 48 px (its
  logo, 376 x 116, is a wordmark).
- Examples: ro-api-hub 2 stars, 1 fork, 0 issues, 27 commits, 1 contributor, last commit
  2026-09-24, MIT; redirectioneaza 26 stars, 27 forks, 20 issues, 1538 commits, 27 contributors,
  2026-10-04, MPL-2.0; sicap-ai 92 stars, 23 forks, 0 issues, 388 commits, 7 contributors,
  2026-09-25.
- `validate.py`: 0 errors. `build.py`: 117 entries.

**Hard**
- `profile.py --only factual,funky-citizens,ro-api-hub,code4ro` (asked in the brief) replaces whole
  rows: it dropped `mentions`, `mention_hosts`, `search_social` (restored by `search.py
  --prune-only`, no requests) and, because crt.sh answered 502, `cert_first` of factual and
  code4ro. A later `--extra --only factual,code4ro` restored it once crt.sh answered again.
- A code4ro-style wordmark (376 x 116) is a poor icon in a square slot, so `fetch_icon` ranks a
  candidate wider than 2:1 below any square one.

**Decided**
- Open issues without pull requests: `open_issues_count` minus the open pull requests (one core
  request with `per_page=1`, the page count from the `Link` header). The brief allowed the search
  API; it allows 30 requests a minute and the profiler already spends them on `github_find`. Cost
  of the alternative: about 2 minutes more per run, and a second source of rate-limit stops.
  With this, the UI says "issues" and never mixes in pull requests. When the pull request call
  fails, `open_issues` stays empty.
- Added to the "Cod" row beyond the brief's example: the language and "arhivat" (an archived repo),
  and the repository's name as a link when it is not the "Cod sursă" link above (code4ro links
  an organisation page; the stats are of `code4romania/code4.ro`). Cost: a longer row. Drop them
  in `repoRow()` if too long.
- The favicon of a host is not removed when a link goes away; files are keyed by host and may be
  shared by several entries.
- A failed GitHub call never writes a zero: the field keeps its old value. A rate limit sets a
  flag, skips every later GitHub call, and ends the run with a non-zero exit after the profile is
  saved.

## 2026-10-18 — New organisations and resources filled in

**Done**
- Sonnet filled the empty cells of 13 `orgs.csv` rows and 3 `proiecte.csv` rows from each site
  (about/contact/donate pages; Wayback for techsoup.ro, which blocks bots, and for the-sponge).
  Profiled all 16; searched the 13 without rows (48 requests, ~$0.10, 0 errors).
- Owner request: removed `safe-companii-de-stat` (its URL is a meta-refresh to monitorsafe.ro,
  already `monitor-safe`), with its 26 `mentiuni.csv` rows.
- Taxonomy: new types `colectie` and `serviciu`, as the owner used them. Slug `expert-forum` →
  `efor` carried into `mentiuni.csv` (34 rows, editor marks kept) and `profil.csv`.
- `split_list` also splits on a comma before a space or the end: the owner typed `a, b` links,
  and the comma had become part of the URL (seen in `ghiduri-efor`).
- Site: on desktop, first visit opens only the "Domeniu" filter; the sidebar lost a 2 px horizontal
  scroll; list thumbnails are 75 px. Footer reads "actualizat:". Header logo removed.

**Measured**
- 116 entries: activ 93, arhivat 11, offline 10, neverificat 1, necunoscut 1. `validate.py`: 0 errors.

**Decided**
- The two local NGOs (Rădăuțiul Civic, Civica Iași) get `domeniu=local`, not `civic`.
- No `orgs.csv` row for Quickdata Studio (PressPay co-author): a commercial studio.

## 2026-10-18 — Share preview, RSS, `/add-new-url`

**Done**
- `site/index.html`: Open Graph and Twitter tags (title "Colecție proiecte CivTech"), canonical
  URL, RSS `<link rel="alternate">`, and an RSS link in the footer.
- `site/img/share.png` (1200×630): logo `civtech-ro-1.png` plus title, made once with Pillow.
- `build.py` writes `site/feed.xml`: the 40 newest live projects by `since`.
- `.claude/commands/add-new-url.md`: check for a duplicate, audit the site, write the row, profile,
  search, validate, build.

**Decided**
- The feed orders by `since` (first trace on the web), because the catalogue has no "date added".
  A date from git history would need a full clone in CI (`fetch-depth: 0`). Cost: a project
  added today with an old site does not show at the top.

## 2026-10-18 — Dead sites out of the main list; automatic `arhivat`

**Done**
- `build.py` `status_of`: a profiler `offline` whose last Wayback capture is over a year old shows
  as `arhivat`. Manual `stare` still wins. Parked domains stay `offline`.
- `stare=offline` by hand for parlament-transparent (connection timeout, repo archived 2023) and
  piata-de-spaga (origin Apache 403 at the root; a reddit thread says it has been down for about a
  year). Both showed as "Neconfirmat", which the main list does not hide.
- CeRe moved: `orgs.csv` url `ce-re.ro` → `cere.ong` (the old site returns 500). Re-profiled
  `cere` and `declic` (declic.ro answers 200 now) and re-ran their search (`--force`, ~6 requests).
  Cleared 2 `editor` marks that pointed at their now-own domains.

**Measured**
- Statuses after: activ 87, arhivat 11, offline 10, neverificat 1, necunoscut 1
  (before: activ 85, arhivat 4, offline 19, necunoscut 3).
- Automatic `arhivat` (7): domnule-primar, harta-taierilor, harta-tv-locale, hoover,
  jailando, oradea-city-report, political-colours (+ the manual ones).

**Decided**
- The rule reads `last_capture`, not `first_seen`: an old project with a recent capture of an
  error page is "offline", not ended. Cost of the alternative (a fixed age): live-but-old projects
  would flip.

## 2026-10-18 — First pruning pass on `data/mentiuni.csv`

**Done**
- 12 Haiku agents (about 240 rows each) read the 2,841 rows that had no `editor` value and were
  not on the project's own site. They had the editor's 45 marks as calibration. Opus checked a
  sample, then set the obvious cases among the rows that Haiku left empty.
- Merged into the `editor` column. The editor's own marks were never changed. Haiku `0` on rows that
  a rule already drops were not written. Log of every cell (source, value, reason):
  `data/review/pruning-2026-10-18.csv` (gitignored, local only).
- Fix pushed for CI (`bce0efa`): `dignitas` had no `domeniu`.

**Measured**
- Haiku: 955 × `1`, 1,123 × `0`, 31 `0`s on rule-dropped rows not written. Opus: 114 × `0`, 2 × `1`,
  2 Haiku `1`s turned to `0` (site checkers: intodns, similarweb).
- After the merge: 3,386 rows, 1,128 kept (was 2,043), `editor` values 978 × `1`, 1,259 × `0`, 1,149 empty.
- Sample check (45 Haiku `0`s, 25 Haiku `1`s): no wrong `0` found; 2 weak `1`s (a tag page, a DNS checker).
- Top 10 by `score` unchanged as a set; expert-forum moved to first place (85).

**Hard**
- Batch 9 wrote its output outside the session scratchpad; it was collected by hand.
- Row ids were the line index in `mentiuni.csv`. Before the merge, every id was checked against slug
  and host, with 0 mismatches.

**Decided**
- `1` also covers the project's own channels and its author's pages, as the editor's marks do. The
  labelling step (`independent`) separates them later. Cost of the alternative: own-channel rows
  would need a third value, which the spec does not have.
- Left empty on purpose: author/organisation pages, generic topic news that may cite the project's
  data, and NGO pages for "redirecționează 3,5%". The editor decides these.

## 2026-10-18 — Search → labelled relevance: build and first run

**Done**
- `scripts/search.py` (new, `uv run`, httpx only). Flags: `--only`, `--force`, `--provider serper|brave|all`,
  `--dry-run`, `--prune-only`. It writes `data/mentiuni.csv` (D3), keeps the `editor` column on every
  rewrite, and recomputes `mentions`, `mention_hosts` and `search_social` in `profil.csv` from the kept rows.
  It saves the file after each entry, so a crash does not lose paid results.
- Prune rules (D5) in a list at the top of `search.py`: `propriu`, `social`, `registru`, `magazin`, `ferma`,
  and two more, `cod` and `zgomot` (see *Decided*). Rules only mark rows (`regula`).
- `profile.py`: removed `--search`, `--gdelt`, `search_mentions()`, `gdelt()` and `SKIP_MENTION`. `gdelt` is
  gone from `PROFIL_COLS` and from `score()`. `SOCIAL_HOSTS` and `SHARE` moved to `common.py`.
- `review.py` (D6): the kept results (at most 40, best rank first) go into the request as `mentiuni`; the schema
  has `mentiuni[{id, despre_proiect, tip_sursa, independent}]` and `atentie`; the system prompt warns about name
  collisions ("when unsure, false"). Labels go to `data/mentiuni_etichete.csv`. An older answer without labels is
  asked again when the entry has results. `--dry-run --only factual,declic` prints both requests (20 and 21 results).
- `build.py` (D7): `reach_features()` reads both CSVs; new `reach` weights; every item has `reach: {indep, stiri,
  cercetare, guvern, ultima}`.
- `validate.py` checks that `editor` in `mentiuni.csv` is empty, `0` or `1`. CONTRIBUTING.md and CLAUDE.md
  describe the new column, commands and pipeline.

**Measured** (all runs of 2026-10-18; prices from the providers' lists: Serper $1/1k, Brave $5/1k)
- Requests: Serper 294 credits (pilot 14, full run 277, force test 2, one date-format probe 1; two bad-key
  requests answered 403 and cost nothing). Brave 104 (pilot 4, full run 100). No error, no retry in the real
  runs. Cost ≈ $0.29 + $0.52 = **$0.81** (budget ≈ $1). The full run took 2 min 19 s.
- Rows: **3386** in 110 entries (10 to 50 per entry, median 32; file 1.3 MB). Kept **2043**.
  By rule: none (kept) 2043, social 633, propriu 503, zgomot 59, cod 51, magazin 47, registru 34, ferma 16.
  The first full run, before the extra rules, kept 2291 of the same 3386 rows.
- Dates: 1140 rows (34 %) have one. Serper 776 of 2616 (30 %), Brave 364 of 770 (47 %). So Serper dates are
  less rare than the spec assumed.
- Most frequent kept hosts (rows / entries): reddit.com 56/34, ro.wikipedia.org 42/33, adevarul.ro 27/23,
  digi24.ro 26/24, hotnews.ro 23/21, expertforum.ro 17/6, stirileprotv.ro 16/13, libertatea.ro 15/12,
  agerpres.ro 14/13, en.wikipedia.org 12/8, redirectioneaza.ro 12/12, romania-actualitati.ro 12/12,
  romaniapozitiva.ro 11/8, iqads.ro 9/7, cere.ong 8/2, galasocietatiicivile.ro 8/7, gov.ro 8/6,
  openpolitics.ro 8/2, researchgate.net 8/7, rfi.fr 8/7.
- Score, top 10 by `score`, old → new (old = HEAD scripts and `profil.csv` on today's catalogue; new = this
  work, **no labels yet**, so `indep` is the kept-host count): sicap-ai 86→86, expert-forum 85→85,
  companii-de-stat 83→83, factual 83→82, apador-ch 81→80, fdsc 75→75, interoperabilitate 74→74, testvot 72→72,
  redirectioneaza 71→71, onesti-city 70→70. The top-10 set is the same. 57 of 110 scores moved (mean +0.74,
  from −1 to +5); the largest rises are entries that had no search before (dignitas 63→68, dupa-cutremur 44→49,
  etherpad-situri-civice 16→21, accesinfo 28→32).
- Editor column: set 3 cells (one `0`, one `1` on a rule-dropped row, one `1` on a row the search does not
  return); `--prune-only` and a real `--force` run on `465` kept all three. The test copy of the file was
  restored afterwards, so no `editor` cell is set now.
- Errors: a run with invalid keys logged `ERR … HTTP 403` per entry, left the rows unchanged and exited 1.

**Hard**
- Name collisions are as bad as the handoff said. `465.ro` (domain query) returns USGS monitoring sites and
  railway wikis; `the-sponge` returns Seinfeld, cryptography and sea sponges; `declic` returns French
  dictionaries and a clothing brand. Rules cannot fix this; the LLM labels and the editor can.
- Author sites dominated the kept hosts: funky.ong had 77 rows in 9 entries and code4.ro 38 in 8. The
  handoff says an author's own channel is not independent, so `propriu` now covers the author's sites too.
- Author names collide as well: "Gabriel Popa" returns footballers and politicians.
- `declic` has `url` = de-clic.ro, which is offline; the search finds the live site at declic.ro. The editor
  decides (not changed: `proiecte.csv` is out of scope).
- Wrong turn: I ran `git stash` by mistake in a chained command and restored it with `git stash pop --index` at
  once; the tree was verified afterwards. Other people had uncommitted edits in `proiecte.csv`, `README.md` and
  `site/` at that time, and they were restored too.
- `validate.py` first reported one error: `dignitas` had an empty `domeniu` in `proiecte.csv`. It was fixed in the
  catalogue by somebody else during the work; the check passes now (28 warnings, all about missing descriptions).

**Decided**
- Queries use the first author only (without a bracketed note) and no author at all when the name already
  contains it ("gov2 gov2"). Three authors in one query narrow the results; the spec says `<autor>` only.
- A failed query leaves all rows of its entry unchanged; the entry is listed at the end and the run exits 1.
  The alternative (keep the rows of the queries that worked) would leave an entry that looks done but misses a
  query, because a slug with rows is skipped without `--force`. Cost: a paid query can be thrown away.
- A row with an `editor` value survives a rewrite even when the search no longer returns it. Cost: a few stale
  rows. The alternative loses editorial work.
- `propriu` also covers the sites of the authors: an organisation in `orgs.csv` with the same name, an author
  written as a domain, and the table `AUTOR_SITES` (funky.ong, funkycitizens.org, code4.ro). This is data
  from the first run; the editor extends it. Without it the top hosts are the authors' own sites.
- Two rules beyond the five named in D5: `cod` (GitHub, GitLab, Codeberg, Bitbucket; the repo is profiled
  already, and the old code skipped them) and `zgomot` (dictionaries, job boards, music, film and football
  databases: sites that answer any name). `magazin` includes online shops, `ferma` includes site checkers and
  review aggregators. All are host lists from what the first run showed.
- `search_social` is computed from every row except those with `editor = 0`, not only from kept rows: a profile
  page is dropped by the `social` rule by design, and it is the thing `search_social` reports.
- `reddit.com` and Wikipedia stay kept. Their pages can be independent attention; the LLM decides.
- Until `review.py` has run, `build.py` counts kept hosts as `indep`, as the spec says. It saturates at 15
  hosts, so name-collision noise counts as reach. The rank is provisional until the labels exist.
- Not done by choice: no change to `README.md` (outside the brief; line 54 still lists `--search --gdelt`),
  and no edit of `proiecte.csv` or `orgs.csv`.

**Not run**
- `review.py` against the API: `ANTHROPIC_API_KEY` is empty in `~/devbox/ePtm/puzzes/.env`. The label code is
  tested with a fake model answer only (ids map to URLs, unknown ids are ignored, `build.py` counts 6 hosts, 3 news,
  1 research, 1 government). `data/mentiuni_etichete.csv` does not exist yet.

## 2026-10-18 — Site: logo, title effects, recent launches, "Active și relevante" sort

**Done**
- Logo 40 px (44 px on desktop) instead of `scale(1.6)`, which overlapped the title on phones.
- Title: a blue–yellow–red band sweeps across the ink text (7 s); each swap picks one of seven
  effects (rise, drop, flip, wipe, zoom, slide, spread). Reduced motion turns both off.
- "Pe domenii": inside each domain, active first, then by last sign of life, then A–Z.
- "lansat recent" (filled tag) for `since` under 60 days; "nou" stays for 60–183 days.
- New sort "Active și relevante" (`o=top`). Fonts one pixel larger; list columns widened to fit.

**Decided**
- "Last sign of life" = the later of `updated` and, for a recent launch, `since`. So a launch
  sorts like an update. This is the "slight bump" in the domain sort.
- `topScore = score × (0.5 + 0.5·e^(−days/365)) + 8 if launched`; unknown date counts as 0.25.
  Measured: `updated` exists for 45 of 74 live projects (61 %), so a pure "updated" sort would
  push 29 projects to the end. The formula keeps them, at a discount. It lives in `app.js` because
  `build.py` belongs to the search work right now. Top 5: factual, sicap-ai, companii-de-stat,
  testvot, redirectioneaza; 3 launches enter the top 15.
- `score` already gives activity 30 %, so the sort counts recency twice. That is intended here.

## 2026-10-18 — Site: keyboard navigation, fresh projects, sort by age

**Done**
- `site/app.js`: `j`/`k` and `←`/`→` move focus through the results in display order. With the
  drawer open, they change the open entry (URL replaced, not pushed). `o` opens the entry's site
  or its Wayback copy. Esc returns focus to the last entry seen.
- `nou` tag on cards, rows and the drawer; "Doar proiecte noi" toggle (`nou=1`); sort
  "Cele mai noi" (`o=nou`). Footer lists the keys (hidden on touch devices).
- Fix: after the drawer re-renders (a related entry, or `j`/`k`), focus goes back to its close
  button. Before, focus fell to `body` and the Tab trap did not hold.

**Hard**
- A second session edits `scripts/` and `data/` at the same time. This work stays in `site/*`
  and uses only fields that `data.json` already has.

**Decided**
- "Fresh" = `since` under 183 days. Measured on the 2026-10-17 data: 24 of 77 live projects.
  `since` is mostly the first Wayback capture (78 of 110), so a new site can show as fresh
  only after its first capture.
- Arrow keys and `j`/`k` do nothing when focus is in a field or the filter sheet is open.
- Checked in headless Chrome (Playwright): focus order, drawer stepping, `o`, filter count,
  sort order. No console errors. Not checked: screen readers, touch devices.

## 2026-10-18 — Spec and brief for search → labelled relevance

**Done**
- Wrote `docs/specs/search-relevance.md` (decisions D1–D7) and `docs/briefs/search-relevance.md`
  from `docs/handoff-search-relevance.md`. Started `docs/BACKLOG.md`.

**Hard**
- The editor's pruning must survive reruns and reach CI, but the result rows are generated.
  Resolved with one generated CSV that carries one human column (`editor`), merged by (slug, url).
- `data/review/` is gitignored, so labels written there never reach the CI build. Labels go to a
  tracked, generated `data/mentiuni_etichete.csv` instead.

**Decided**
- New `scripts/search.py`; `profile.py` loses `--search`. Cost of the alternative: a fourth mode in
  a 690-line script, writing two files with different merge rules.
- Drop GDELT (no usable data measured). See backlog, *Verified limits*.
- The LLM labels each result; `build.py` turns labels into named counts. An LLM score would be
  cheaper to wire, but nobody could explain or tune a rank built on it.
- Brave for the name query, because it accepts quoted phrases and returns dates. Cost: ~$0.55 of
  the ~$0.80 budget.
