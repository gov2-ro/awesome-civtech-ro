# Data schema

This file explains every column of every data file, and the rules that check them.
[ARCHITECTURE.md](ARCHITECTURE.md) shows how the files connect.
[CONTRIBUTING.md](../CONTRIBUTING.md) tells a contributor (in Romanian) how to fill in a row.

The file has two parts:

- **Production files (taxonomy v1).** The public site uses them today. They are the first table below and the
  sections up to [data.json](#datajson).
- **Taxonomy v2 files (preview).** They are the migration target. No editor has accepted a v2 classification yet.
  The public site does not read them. A script reads them only when it gets `--data-dir`. They start at
  [Taxonomy v2 package](#taxonomy-v2-package).

The v1 column lists are in `scripts/common.py` (`PROIECTE_COLS`, `ORGS_COLS`, `PROFIL_COLS`,
`MENTIUNI_COLS`, `ETICHETE_COLS`). When a v1 column changes, change that file, `validate.py`,
`build.py` and this file together. The v2 column lists are in `data/taxonomy-v2/schema.json` (`headers`)
and in the `pachet.json` of an overlay (`headers`). No Python constant repeats them.
[Keeping this file complete](#keeping-this-file-complete) shows how to check that every column is described.

## Production files (v1)

| File | Written by | Section |
| --- | --- | --- |
| `data/proiecte.csv` | a person | [proiecte.csv](#proiectecsv) |
| `data/orgs.csv` | a person | [orgs.csv](#orgscsv) |
| `data/taxonomy.json` | a person | [taxonomy.json](#taxonomyjson) |
| `data/profil.csv` | `profile.py` and `search.py` | [profil.csv](#profilcsv) |
| `data/mentiuni.csv` | `search.py`; a person sets `editor` | [mentiuni.csv](#mentiunicsv) |
| `data/mentiuni_etichete.csv` | `review.py` | [mentiuni_etichete.csv](#mentiuni_etichetecsv) |
| `data/review/raw.jsonl`, `data/review/sugestii.csv` | `review.py` (the repository ignores them) | [mentiuni_etichete.csv](#mentiuni_etichetecsv) |
| `data/form.json` | `form.py --save` | [form.json](#formjson) |
| `data/site.json` | a person | [site.json](#sitejson) |
| `site/data.json` | `build.py` | [data.json](#datajson) |
| Sheet tabs `proiecte`, `orgs`, `propuneri`, `_sync` | `sheets.py`, a person, the Form | [Google Sheet tabs](#google-sheet-tabs-and-the-sync-marker) |

## Taxonomy v2 files (preview)

| File or folder | Written by | Section |
| --- | --- | --- |
| `data/taxonomy-v2/intrari.csv` | a person | [intrari.csv (v2)](#intraricsv-v2) |
| `data/taxonomy-v2/concepte.csv` | a person | [concepte.csv](#conceptecsv) |
| `data/taxonomy-v2/valori.csv` | a person | [valori.csv](#valoricsv) |
| `data/taxonomy-v2/roluri-linkuri.csv`, `gazde-linkuri.csv` | a person | [Link roles and hosts](#link-roles-and-hosts) |
| `data/taxonomy-v2/integrare/relatii.csv` | a person | [relatii.csv](#relatiicsv) |
| `data/taxonomy-v2/arii.csv` | a person | [arii.csv](#ariicsv) |
| `data/taxonomy-v2/revizuire.csv` | a person | [revizuire.csv (v2)](#revizuirecsv-v2) |
| `data/taxonomy-v2/mapari-externe.csv` | a person | [mapari-externe.csv](#mapari-externecsv) |
| `data/taxonomy-v2/setari.json`, `schema.json`, `versiuni.json`, `manifest.json`, `catalogue.json` and the history files | a person, or `validate.py --export` | [Settings, contract and history](#settings-contract-and-history) |
| `data/taxonomy-v2/integrare/` | `integrare.py` and a person | [Integration overlay](#integration-overlay-integrare) |
| `data/taxonomy-v2/observatii/` | `profile.py`, `search.py`, `review.py` | [Observations](#observations-observatii) |
| `data/form-v2.json` | `form.py --write-map` | [form-v2.json](#form-v2json) |
| Sheet tabs `v2-intrari`, `v2-revizuire` | `sheets.py` | [Google Sheet tabs](#google-sheet-tabs-and-the-sync-marker) |

The model is in `docs/specs/taxonomy-v2.md`. The editing guide (in Romanian) is `data/taxonomy-v2/README.md`.
[Taxonomy v2 package](#taxonomy-v2-package) says which parts are draft.

## Rules for every CSV

These rules are for the v1 files. A v2 table follows the [conventions of the v2 files](#conventions-of-the-v2-files).

- Encoding is UTF-8. The separator is a comma. A cell that holds a comma, a quote or a new line
  has quotes around it. Google Sheets and Excel do this on their own.
- A **list cell** (`linkuri`, `repos`, `mention_hosts`) holds values separated by a space, a new
  line or `|`. It can also hold a JSON array. A comma at the end of a value is ignored, because
  people type lists that way.
- The cell `tip` is different: it is comma-separated, and the main type comes first.
- A generated file never gets a hand edit. The exception is the column `editor` in `mentiuni.csv`.
- An empty cell means "unknown" or "not applicable". The scripts never write the text `null` or `n/a`.

## proiecte.csv

One row for each **project** (`fel` = `proiect`) or **resource** (every other `fel`: a list, an article, a
guide, a campaign, research). Order of columns: as in the table.

| Column | Meaning | Format and rules |
| --- | --- | --- |
| `slug` | Unique name of the entry. It is also the address, `/<kind>/<slug>/`. | Lower-case letters, digits and single hyphens. **Unique across `proiecte.csv` and `orgs.csv`.** Error if wrong or repeated. |
| `fel` | What the entry is. | One key from `taxonomy.json` → `fel`: `proiect`, `resursa`, `articol`, `ghid`, `campanie` or `cercetare`. Error if anything else. Every value but `proiect` puts the entry on the "Resurse & liste" tab; the site shows the label ("Articol", "Ghid", …) next to the entry. |
| `nume` | Name, as the project writes it. | Required. |
| `descriere_scurta` | One sentence for cards and lists. | About 90 characters at most. Free text. |
| `descriere` | What it does, for whom, from which data. | Free text. `build.py` ignores a description that is only boilerplate, and then uses the site's own meta description. |
| `url` | Main address. | A full address; `https://` is added when missing. Warning if empty. Error if invalid. Warning if another entry has the same address. |
| `linkuri` | **All other links**, in one cell. | List cell. Write `role:URL` to name the role (`donatii:`, `despre:`, `contact:`, `termeni:`, `date:`, `api:`, `mcp:`, `cod:`). Without a role, the host decides (Facebook, GitHub, …); the rest are `web`. The first GitHub, GitLab or `cod:` link is the source code. The roles and hosts are in `taxonomy.json`. Error for an unknown role or an invalid link. |
| `domeniu` | Subject area. | One key from `taxonomy.json` → `domenii`. Required. |
| `tip` | Kind of tool. | One or more keys from `tipuri`, comma-separated, main type first. Error for an unknown key. Warning for a project with no type. |
| `cuvinte` | Keywords. | Comma-separated. `build.py` drops the ones in `cuvinte.ignora` and rewrites the ones in `cuvinte.alias`. It drops `local:*` keywords, because `oras` holds the city. |
| `acoperire` | Geographic reach. | One key from `acoperire`: `national`, `local` or `international`. Empty means `national` (the site shows it so); error for an unknown key. |
| `oras` | City, for local entries. | Free text. Warning if `acoperire` is `local` and this is empty. |
| `autor` | People or organisations behind it. | Separate names with ` / ` (a comma or ` & ` also works). **A name that is the `slug` of a row in `orgs.csv` links the entry to that organisation**: the entry page shows the organisation, and the organisation page lists its entries. Any other name stays plain text; the site shows other entries with the same name under "De același autor". Warning when a name looks like a slug but is not in `orgs.csv`. |
| `contact` | A contact point. | Optional. Free text. |
| `civictech` | The entry is civic tech: made by civil society, volunteers, journalists or researchers. | `1`, `0` or empty. Error for any other value. |
| `stare` | Manual state. | Empty (the profiler decides), `arhivat` or `offline`. A manual value wins over the profiler, and the site then ignores what is live at the old address. |
| `nota` | Internal note. | Never shown on the site. |

A row with no `descriere_scurta` and no `descriere` gives a warning.

## orgs.csv

One row for each **organisation**. It has the same columns as `proiecte.csv`, **minus** `fel`,
`tip`, `autor`, `contact` and `civictech`. An organisation has no kind (`build.py` sets it to
`organizatie`), no type, and no author. The rules for the shared columns are the same. A slug
cannot repeat a slug of `proiecte.csv`.

Order of columns: `slug`, `nume`, `descriere_scurta`, `descriere`, `url`, `linkuri`, `domeniu`,
`cuvinte`, `acoperire`, `oras`, `stare`, `nota`.

## taxonomy.json

The lists of allowed values. `validate.py` checks the CSVs against it. `app.js` builds its filters
from it. `form.py --apply` copies it into the Google Form's choices.

| Key | Holds | Fields |
| --- | --- | --- |
| `domenii` | Subject areas. The order is the order on the site. | `key`, `label`, `short` (a short label), `hint` (a line under the area, listing its topics) |
| `tipuri` | Kinds of tool. | `key`, `label`, `hint` |
| `acoperire` | Geographic reach. | `key`, `label` |
| `fel` | The values of the column `fel`. | `key`, `label`, `kind` (the tab the entry goes to: `proiect` or `resursa`) |
| `kinds` | The three tabs: `proiect`, `organizatie`, `resursa`. The key is also the folder of the entry's page. | `key`, `label` |
| `cuvinte` | Keyword clean-up. | `ignora` (a list of keywords to drop), `alias` (a map: variant → canonical form) |
| `linkuri.roluri` | Link roles. | `key`, `label`, `hosts` (hosts that give the role without a prefix) |

A new `key` in `domenii`, `tipuri` or `acoperire` works at once in `validate.py` and on the site.
Run `uv run scripts/form.py --apply` to refresh the Form's choices. A role in `linkuri.roluri` that shows
a network logo must also be in `NETWORK` in `site/app.js` and in `NETWORK_ROLES` in
`scripts/common.py`.

## profil.csv

What `profile.py` saw on the entry's site, one row for each slug. **Generated.** It holds the
column names of `PROFIL_COLS`. A site that is offline keeps the fields that did not need the site.
`build.py` reads this file, applies the entry's manual `stare`, and writes `data.json`.

**Liveness**

| Column | Meaning |
| --- | --- |
| `slug` | Key; the same as in `proiecte.csv` / `orgs.csv`. |
| `url` | The address that was fetched (from the CSV). |
| `final_url` | The address after redirects. |
| `http_status` | Last HTTP status code; `0` when no answer came. |
| `status` | `activ`, `mutat` (it redirects to another registered domain), `offline` (an error, an HTTP error, or a subpage that now redirects to the home page), `parcat` (a parked domain) or `blocat` (bot protection or a timeout, which the browser pass then decides). |
| `error` | Text of the network error, if there was one. |
| `ssl_error` | `1` when the certificate check failed and the profiler fetched the page without it. |
| `parked` | `1` when the page looks like a parked domain. |
| `fetched_at` | UTC time of the fetch, ISO 8601. |

**Page metadata**

| Column | Meaning |
| --- | --- |
| `title` | The page's `<title>`. |
| `og_title` | `og:title` or `twitter:title`. |
| `site_name` | `og:site_name`. |
| `description` | The meta description. `build.py` uses it when the curated description is missing or boilerplate, and the site is `activ` or `mutat`. |
| `lang` | The language the page declares (`ro`, `ro-RO`, …). |
| `generator` | The `<meta name="generator">`, up to 60 characters (`WordPress 6.5`). |
| `words` | Number of words in the home page body. |
| `copyright_year` | The newest year in a © notice. |
| `feed` | Address of the RSS or Atom feed. |
| `sitemap_urls` | Number of addresses in the sitemap. |

**Links and images**

| Column | Meaning |
| --- | --- |
| `repos` | GitHub addresses found for the entry, space-separated, at most 5. |
| `social` | JSON: social-network links found on the home page, `{"facebook": "https://…"}`. Keys are link roles. |
| `img_src` | Path of the entry's image, `img/og/<slug>.webp` (under `site/`). |
| `img_kind` | `og` (the page's share image), `logo` (an image with a width under 1.3 times its height: a logo or a square image), or `screenshot` (taken in a browser when no usable image exists). |
| `img_w`, `img_h` | Size of the image in pixels. |
| `img_color` | Dominant colour, `#rrggbb`. |
| `img_source` | Where the image came from: the image address, the page address for a screenshot, or `manual` for a file that a person put in `site/img/og/<slug>.webp`. The profiler keeps a `manual` image and never fetches over it. |
| `icon` | Path of the favicon, `img/icon/<slug>.webp`. The profiler replaces it while it is under 64 px and a bigger one exists. |

The favicons of the entry's *other* links are in `site/img/linkicon/<host>.webp`. No column holds them.

**Age and activity**

| Column | Meaning |
| --- | --- |
| `wayback` | Address of the Wayback Machine capture. Only filled for `offline` and `parcat` entries. |
| `first_seen` | Date of the first Wayback capture, `YYYY-MM-DD`. |
| `last_capture` | Date of the last Wayback capture. |
| `archive_months` | Number of months with a Wayback capture. |
| `cert_first` | Date of the first TLS certificate issued for the host (crt.sh). Only for entries on their own domain. |
| `updated` | The newest date among the signals below. It must be older than yesterday: a page that reports today's date is not a real edit. |
| `updated_src` | Where `updated` came from: `cod` (last push to the repository), `feed`, `wordpress`, `sitemap`, `server` (the `Last-Modified` header) or `arhiva` (the last Wayback capture, for a site that is down). |

`build.py` shows the older of `first_seen` and `repo_created` as the entry's age (`since`). It uses `cert_first` only when both are empty, because a domain can be older than the project that now lives on it.

**GitHub**

Filled from the first repository in `repos`. All are empty when there is no repository.

| Column | Meaning |
| --- | --- |
| `repo` | `owner/name`. |
| `repo_created` | Date the repository was created. |
| `repo_archived` | `1` when the repository is archived. |
| `stars`, `forks` | Counts. |
| `open_issues` | Open issues, **without** pull requests. |
| `commits` | Number of commits on the default branch. |
| `contributors` | Number of contributors, anonymous ones included. |
| `last_commit` | Date of the last commit. |
| `license` | SPDX identifier (`MIT`). Empty when GitHub reports no licence. |
| `language` | The main language of the repository. |

**Reach**

| Column | Meaning | Written by |
| --- | --- | --- |
| `wiki_refs` | Number of Romanian and English Wikipedia articles that link to the site's domain. | `profile.py --extra` |
| `opr` | Open PageRank score of the domain. | `profile.py --opr` |
| `mentions` | Number of different hosts (`host`) among the **kept** rows of `mentiuni.csv`. | `search.py` |
| `mention_hosts` | Those hosts, space-separated, at most 12, in the order of the file. | `search.py` |
| `search_social` | JSON: social profiles and a GitHub profile that the search found, `{"instagram": "https://…"}`. Only handles that carry the entry's name count. | `search.py` |

A refresh of a profile row (`profile.py`, also with `--force`) keeps the columns that other stages wrote:
`mentions`, `mention_hosts` and `search_social` (`search.py`), `opr` (`--opr`), and each `--extra` signal for which
the new fetch found nothing (`cert_first`, `wiki_refs`, the repository columns, and so on). A failed call never turns a
known value into a blank. A row for a changed `url` keeps only the three `search.py` columns. The rule is
`merge_profile` in `scripts/common.py`.

## mentiuni.csv

Every search result for every entry, **kept or not**. One row for each (`slug`, `url`). `search.py`
writes it. A person reads it and sets `editor`.

| Column | Meaning |
| --- | --- |
| `slug` | The entry the search was for. |
| `provider` | `serper` (Google) or `brave`. |
| `query` | The query that returned the result. |
| `rank` | Position in that query's results; `1` is first. |
| `url` | Address of the result, without `#fragment`. |
| `host` | Host of the address, without `www.`. |
| `title` | Title the engine showed. |
| `snippet` | Text the engine showed, at most 300 characters. |
| `date` | Date the engine showed, when it showed one. |
| `regula` | The first rule that would drop the row. Empty when no rule drops it. Values: `magazin` (app stores, online shops), `social` (social networks), `cod` (code hosts; the repository is profiled already), `registru` (company registries), `ferma` (sites that build a page for any domain), `zgomot` (sites that answer any name: dictionaries, job boards, databases), `propriu` (the entry's own site, its linked sites, its author's sites). The regexes are in `RULES` in `scripts/search.py`. |
| `editor` | The editor's verdict. `1` keeps the row even if a rule dropped it. `0` drops it even if no rule did. Empty: the rule decides. Error for any other value. `search.py` keeps this column on every rewrite. |
| `fetched_at` | UTC time of the request. |

A row is **kept** when `editor` is `1`, or when `editor` is empty and `regula` is empty
(`is_kept` in `scripts/common.py`).

## mentiuni_etichete.csv

Claude Haiku's labels for the kept results. **Generated** by `review.py`; the file does not exist
until the first run. One row for each (`slug`, `url`). `build.py` turns the labels into the reach
counts that feed the relevance score.

| Column | Meaning |
| --- | --- |
| `slug`, `url` | The row of `mentiuni.csv` that was labelled. |
| `despre_proiect` | `1` only when the page is about this project or organisation. `0` for a page that only mentions the name by chance. |
| `tip_sursa` | `stire` (news), `cercetare`, `guvern`, `raport_ong`, `director` (a directory or listing), `social` or `altul`. |
| `independent` | `1` when the page is not run by the project itself, by its author, or by a partner. |
| `model` | The model that wrote the label. |
| `labelled_at` | UTC time of the label. |

`review.py` also writes `data/review/raw.jsonl` and `data/review/sugestii.csv`. Those files are
suggestions for corrections to `proiecte.csv`. A person accepts them by hand. Git ignores them.
Each answer in `raw.jsonl` carries `inputs`: five hashes (the entry text, the set of result URLs sent, the vocabulary,
the prompt with its answer schema, and the model). `review.py` reviews an entry again when one of them changes.
A v2 root keeps these files in its `observatii/review/` folder, with `propuneri-vocabular.csv` for terms that no
concept covers.

`build.py` counts a label only for a kept row of the same `slug` and `url`. It reports the label coverage (labelled
kept rows over all kept rows) in its last line, and `review.py` reports it after every run.

## form.json

The template of the proposal Google Form: a list of questions. `form.py --save` reads it from the
Form; `form.py --apply` writes it to the Form. The Form's answers go to the tab `propuneri` of the
Google Sheet, and **the title of a question is the column name there**. Rename a question with care.

| Field | Meaning |
| --- | --- |
| `title` | The question, and the column name in `propuneri`. |
| `required` | `true` when the visitor must answer. |
| `kind` | The question type (`radio`, text, …). |
| `choices` | The answers to pick from. `form.py --apply` refreshes the choices of "Domeniu", "Tip", "Acoperire" and "Ce propui?" from `taxonomy.json`. |

The columns of `propuneri` do not match the columns of `proiecte.csv`: a person copies each
accepted row by hand and adds `slug`, `fel` and the other missing cells. See `docs/BACKLOG.md`
for the plan to order the questions like the CSV. The planned v2 Form does not use this file: see [form-v2.json](#form-v2json).

## site.json

Where a visitor can report a problem with an entry: the drawer's "Semnalează o problemă". `build.py`
copies the file into `data.json` as `site`. An empty value hides that option.

| Key | Meaning |
| --- | --- |
| `issues` | Address of GitHub's "new issue" page. The site adds a title and a body that name the entry. |
| `sheet` | Address of the Google Sheet, ending in `/edit`. The site adds the tab and the entry's row. |
| `tabs` | The Sheet's tab ids, `proiecte` and `orgs`: the number after `gid=` in the Sheet's address. |
| `email` | An address for the "send an e-mail" option. Empty by default, so that option is hidden. |

A v2 root keeps the same keys in `setari.json`, under `site`. There `tabs` holds `intrari` instead.

## data.json

What the browser loads: `generated` (time), `checked` (the newest `fetched_at`), `taxonomy`
(`taxonomy.json` without `cuvinte`), `site` (`site.json`) and `items`. **Generated** by `build.py`; the field list is in
`main()` of `scripts/build.py`. Some fields do not copy a column:

- `status`: `activ`, `offline`, `arhivat`, `necunoscut` or `neverificat`. A manual `stare` wins over
  the profiler. The profiler's `mutat` becomes `activ` (the entry then gets `movedFrom` and the new
  address), `parcat` becomes `offline`, and `blocat` becomes `necunoscut`. `neverificat` means no
  profile row exists. An `offline` site with no Wayback capture for over a year becomes `arhivat`.
- `row`: the entry's row in its Sheet tab (`proiecte` or `orgs`): the CSV order plus the header row.
- `fel`: the column `fel` (empty for an organisation). `kind` is the tab, from `fel`.
- `authors`: the `autor` cell as a list of `{name, org}`. `org` is the slug of an organisation when the cell
  named one (then `name` is that organisation's name), else empty.
- `score`: 0 to 100 for the "Relevanță" sort. Activity counts 30, reach 25, volume 15, longevity 15
  and documentation 15.
- `stale`: the year of the last sign of life, when an active site shows no sign of an edit for three
  years, or its repository is archived. A dated update (`updated`) is the last sign of life. Only without one, the
  `copyright_year` stands in, as `<year>-01-01`, and never after today.
- `reach`: `indep`, `stiri`, `cercetare`, `guvern` and `ultima` (see `search.py` and `review.py`). With labels for only some
  of the kept rows of an entry, `indep` also counts the hosts of the unlabelled kept rows, the other counts come from the
  labels alone, and the entry has `provisional: true`. Without any label, the kept hosts stand in for `indep`.

## Google Sheet tabs and the sync marker

The Google Sheet `civtech.gov2.ro` mirrors CSVs. [ARCHITECTURE.md](ARCHITECTURE.md#editing-in-google-sheets) shows the workflows.
`scripts/sheets.py` writes the tabs. Every cell is plain text. Row 1 holds the column names, in the order of the CSV.

| Tab | Root | Holds | Written by |
| --- | --- | --- | --- |
| `proiecte` | v1 | `data/proiecte.csv`; row 1 is `PROIECTE_COLS` | `sheets.py` (push and pull), a person |
| `orgs` | v1 | `data/orgs.csv`; row 1 is `ORGS_COLS` | `sheets.py`, a person |
| `propuneri` | none | The answers of the proposal Form. The title of a question is the column name. | the Form |
| `v2-intrari` | v2 | `intrari.csv`; row 1 is `headers["intrari.csv"]` of `schema.json` | `sheets.py --data-dir` |
| `v2-revizuire` | v2 | `revizuire.csv`; only with `--tabs v2-intrari,v2-revizuire` | `sheets.py --data-dir` |
| `_sync` | both | The sync marker, below. | `sheets.py push` |

- A root accepts only its own tabs: `proiecte` and `orgs` for v1, `v2-intrari` and `v2-revizuire` for v2. `sheets.py` refuses
  every other name in `--tabs`, `propuneri` and `_sync` included. Only `push` creates a `v2-` tab.
- The sync never reads or writes `propuneri`.
- A row is found by its key: `slug` in `proiecte`, `orgs` and `v2-intrari`; `id` in `v2-revizuire`.
- Drop-downs. A column with one code or one concept gets a strict drop-down. A v2 column that takes several IDs gets a list
  that only suggests, and only when the list has at most 40 values. A pick from a suggestion list may replace the whole cell with
  that one value (not tried in Google Sheets). The v1 columns `fel`, `domeniu`, `acoperire`, `stare` and `civictech` are strict; `tip` only suggests.

**The tab `_sync`.** The marker has one row for each synced tab. `push` creates the tab and writes it last. The base of a
three-way comparison is the CSV that the marker names.

| Column | Meaning |
| --- | --- |
| `tab` | The name of the synced tab (`proiecte`, `orgs`, `v2-intrari`, …). One row for each tab. |
| `commit` | The full commit hash that held the pushed CSV. |
| `sha256` | The SHA-256 of the CSV bytes that `push` wrote. A reader runs `git show <commit>:<path>` and compares it. |
| `time` | UTC time of the push, `YYYY-MM-DDTHH:MM:SSZ`. |

`push` writes a marker only when the CSV it pushed is the file at `HEAD`. Otherwise it warns and keeps the old row.
A marker that names an unknown commit, or a commit with other bytes, is an error. A row without `tab`, `commit` or `sha256`,
or two rows for one tab, is an error. A person deletes a row to make `sheets.py` forget that tab. Do not edit the tab by hand.

## Taxonomy v2 package

`data/taxonomy-v2/` is the draft `2.0.0-draft.2` (`schema.json` → `version`). It is a **preview and the migration
target**. Every classification in it is a proposal. The production site, `data/` and the default root of every script stay on v1.

Three kinds of root hold v2 data. A script that gets `--data-dir` finds out which kind with `common.data_schema`:

| Root | Marker file | Holds |
| --- | --- | --- |
| v1 | `proiecte.csv` and `taxonomy.json` | The production files above. The default (`data/`). |
| v2 package | `schema.json` | The vocabulary and tables below. `data/taxonomy-v2/`. |
| v2 overlay | `pachet.json` | Only entry-level tables. It takes every other file from its `base`. `data/taxonomy-v2/integrare/` is the one overlay. |

`validate.py --data-dir <root>` runs the package checks of `scripts/taxonomy_v2.py`. `data/taxonomy-v2/validate.py` runs
the same checks (add `--baseline`, `--export` or `--publication`).

### Conventions of the v2 files

- Encoding, separator and quoting are the same as for the v1 CSVs.
- A list cell holds IDs separated by `|`, with no space. The v1 rule (space, new line or comma) does not apply.
- A classification cell holds an ID, never a label. Labels live in `concepte.csv`, `valori.csv` and `arii.csv`.
  An ID has no diacritics. A concept ID is `<scheme>:<name>` (`subiect:finante-publice`).
- An empty cell means unknown or not applicable. A code list has no row for "empty".
- A code with `statut` `retras` cannot be used any more.
- The column lists are in `schema.json` → `headers`. `field_rules` gives each column a rule. A rule has a `kind`
  (`slug`, `text`, `links`, `integer`, `code`, `concept`, `area`, `role`, `lifecycle`, `concept_id`, `concept_ref`, `text_list`)
  and, as the kind needs: `required`, `list` (a code list of `valori.csv`), `scheme` (a concept scheme), `min_items`,
  `max_items` (`null` means unbounded), `level` (`root` or `narrower`), `empty_allowed_when` and `private`.
  A `private` column never reaches the public `data.json`.
- The key of each table is in `schema.json` → `keys`. A missing or repeated key is an error.
- The lifecycle codes are `propus` (proposed), `acceptat` (accepted) and `retras` (withdrawn).

### intrari.csv (v2)

One row for each entry (project, organisation or resource). Today it holds the 122 entries of the v1 catalogue, with the same slugs. Order of columns: as in the table.

| Column | Meaning | Rule |
| --- | --- | --- |
| `slug` | Unique name of the entry; the join key of `observatii/`. | Same format as v1. Required. |
| `tip_entitate` | What the entry is. | Code list `tip_entitate`: `proiect`, `organizatie`, `resursa`, `publicatie`, `set-date`, `campanie`. Required. |
| `sectiune_url` | The site section and the folder of the entry's page. | Code list `sectiune_url`: `proiect`, `organizatie`, `resursa`. Required. `tip_entitate` `organizatie` needs `sectiune_url` `organizatie`. |
| `nume`, `descriere_scurta`, `descriere`, `url`, `linkuri` | The original text and links of the v1 row. | Copied without rewriting. `nume` is required. A role prefix in `linkuri` must be an `id` of `roluri-linkuri.csv`. |
| `subiect_principal` | The one top-level subject that places the entry in the grouped list. | One concept of the scheme `subiect`, top level. It must be in `subiecte`. Empty only when `clasificare_stare` is `de-revizuit`. |
| `subiecte` | The top-level subjects the entry covers. | At least one concept of `subiect`, top level. Empty only in `de-revizuit`. A value needs a `subiect_principal`. |
| `teme` | Narrower subjects. | Concepts of `subiect` that have a broader concept. The top-level subject of each topic must be in `subiecte`. |
| `scopuri` | The civic purpose. | Concepts of the scheme `scop`. |
| `functionalitati` | What a user or the organisation can do. | Concepts of `functie`. |
| `formate` | The form of the content or tool. | Concepts of `format`. |
| `tehnologii` | A technology the entry uses or offers. A subject mention is not enough. | Concepts of `tehnologie`. |
| `institutii_vizate` | The institution types it discusses, serves or uses as a data source. It does not assert ownership. | Concepts of `institutie`. |
| `tip_organizatie` | The kind of organisation. | Concepts of `organizatie`. Only when `tip_entitate` is `organizatie`. |
| `maturitate` | The stage, when the sources show one. | Zero or one concept of `maturitate`: `experiment`, `prototip`, `pilot`, `operational`. |
| `nivel_acoperire` | How far the entry reaches. | Code list `nivel_acoperire`: `national`, `local`, `international`, `necunoscut`. Required. `local` needs an area of type `judet` or `localitate`. |
| `arii_acoperite` | The areas it covers. | IDs of `arii.csv`. |
| `detaliere_date` | The geographic detail of the data, independent of project reach. | Optional code: `agregat-national`, `judete`, `localitati`, `judete-localitati`. Empty means unverified or not applicable. |
| `dovada_detaliere` | The evidence page for the recorded data detail. | An HTTP(S) URL is required when `detaliere_date` is set. |
| `localitate_originala` | The v1 `oras`, unchanged. | Text. It does not limit the coverage. |
| `autor_original` | The v1 `autor`, unchanged. | Text. `relatii.csv` holds the structured form. |
| `contact` | The v1 `contact`. | Text. |
| `civictech_original` | The v1 `civictech`, kept as legacy data. It is not a new certification. | Code list `civictech_original`: `0`, `1` or empty. |
| `stare` | The v1 manual state. | Code list `stare_manual`: `arhivat`, `offline` or empty. It does not describe maturity or review. |
| `nota` | Internal note. | Text. Private. |
| `clasificare_stare` | Is the classification ready? | Code list `clasificare_stare`: `propus`, `acceptat`, `de-revizuit`. Required. It is not an HTTP status. |
| `incredere` | How well the sources support the classification. In the overlay it is the lowest confidence among the entry's claims. | Code list `incredere`: `mica`, `medie`, `mare`. Required. It is not a calibrated probability. |
| `sursa_fisier`, `sursa_rand` | The source of the v1 row: `proiecte.csv` or `orgs.csv`, and the CSV record number (the header is record 1). | Private. `sursa_rand` is an integer. |
| `nota_clasificare` | Internal note on the classification. | Text. Private. |

`validate.py --baseline` proves that the text columns equal the rows of `source/` that `sursa_fisier` and `sursa_rand` name.
A list in `intrari.csv` has no repeated, blank or padded item.

### concepte.csv

The controlled vocabulary. One row for each concept. The model follows SKOS, but the files are not an RDF export.

| Column | Meaning | Rule |
| --- | --- | --- |
| `id` | `<scheme>:<name>`. | Unique. The part before `:` must equal `schema`. Lower case, no diacritics. |
| `schema` | The concept scheme. | Code list `concept_schema`: `subiect`, `scop`, `functie`, `format`, `tehnologie`, `institutie`, `maturitate`, `organizatie`. |
| `eticheta_ro`, `eticheta_en` | The preferred labels. | Required. A label is unique in its scheme and language (case ignored). |
| `alternative_ro` | Other Romanian labels the search should find. | `\|`-separated text. Optional. |
| `definitie_ro` | The definition. | Required. |
| `mai_larg` | The broader concept. | A concept of the same scheme. The hierarchy has no cycle. A top-level subject has none. |
| `asociate` | Related concepts. | Concept IDs. |
| `statut` | Lifecycle. | Code list `concept_statut`: `propus`, `acceptat`, `retras`. |

A new concept needs a new `id`. Do not change an `id` to correct a label.

### valori.csv

The code lists of the package. One row for each code.

| Column | Meaning |
| --- | --- |
| `lista` | The name of the code list. |
| `cod` | The code. `lista` and `cod` together are unique. A code has no `\|` and no padding. |
| `eticheta_ro`, `eticheta_en` | The labels. `eticheta_ro` is required. |
| `definitie_ro` | The meaning of the code. |
| `statut` | `propus`, `acceptat` or `retras`. The checks refuse a `retras` code in data. |
| `ordine` | An integer, unique in the list. It sets the order on the site and in the Form. |

Every list is used by a column of `schema.json`, and every list that `schema.json` names exists. Both directions are errors.

| List | Used by | Codes |
| --- | --- | --- |
| `tip_entitate` | `intrari.csv` `tip_entitate` | `proiect`, `organizatie`, `resursa`, `publicatie`, `set-date`, `campanie` |
| `sectiune_url` | `intrari.csv` `sectiune_url` | `proiect`, `organizatie`, `resursa` |
| `detaliere_date` | `intrari.csv` `detaliere_date` | `agregat-national`, `judete`, `localitati`, `judete-localitati` |
| `nivel_acoperire` | `intrari.csv` | `national`, `local`, `international`, `necunoscut` |
| `clasificare_stare` | `intrari.csv` | `propus`, `acceptat`, `de-revizuit` |
| `incredere` | `intrari.csv` | `mica`, `medie`, `mare` |
| `stare_manual` | `intrari.csv` `stare` | `arhivat`, `offline` |
| `civictech_original` | `intrari.csv` | `0`, `1` |
| `concept_schema` | `concepte.csv` `schema` | `subiect`, `scop`, `functie`, `format`, `tehnologie`, `institutie`, `maturitate`, `organizatie` |
| `concept_statut` | `concepte.csv` `statut` | `propus`, `acceptat`, `retras` |
| `relatie_predicat` | `relatii.csv` `predicat` | `atribuit_in_sursa`, `creat_de`, `mentinut_de`, `publicat_de`, `finantat_de`, `parte_din`, `ofera`, `foloseste`, `date_din` |
| `relatie_stare` | `relatii.csv` `stare` | `rol_neconfirmat`, `propus`, `acceptat`, `respins` |
| `tip_arie` | `arii.csv` `tip` | `tara`, `regiune`, `judet`, `localitate` |
| `prioritate` | `revizuire.csv` | `mare`, `medie`, `mica` |
| `revizuire_stare` | `revizuire.csv` `stare` | `deschis`, `acceptat`, `respins`, `amanat`, `tehnic` |
| `mapare_relatie` | `mapari-externe.csv` `relatie` | `closeMatch`, `exactMatch`, `broadMatch`, `narrowMatch`, `relatedMatch` |
| `mapare_stare` | `mapari-externe.csv` `stare_mapare` | `propus`, `acceptat`, `respins` |

### Link roles and hosts

`roluri-linkuri.csv` lists the link roles. `gazde-linkuri.csv` says which host gives which role. Together they replace
`linkuri.roluri` of `taxonomy.json` for a v2 root.

| File | Column | Meaning |
| --- | --- | --- |
| `roluri-linkuri.csv` | `id` | The role (`github`, `donatii`, …). Lower-case letters only, because it appears in a `role:URL` token. The role `web` must exist: it is the fallback. |
| | `eticheta_ro`, `eticheta_en`, `definitie_ro` | Labels and meaning. |
| | `statut`, `ordine` | Lifecycle and order, as in `valori.csv`. |
| `gazde-linkuri.csv` | `gazda` | A plain lower-case host, such as `facebook.com`. No scheme, path or wildcard. Unique. |
| | `rol` | The `id` of a role. |

A role that shows a network logo also needs code in `NETWORK_ROLES` (`scripts/common.py`) and `NETWORK` in the browser code.

### relatii.csv

Structured relations between an entry and a person, an organisation or another entry. The predicate `date_din` records a named data provider or source publication.
It remains separate from authorship and monitored institutions.

| Column | Meaning | Rule |
| --- | --- | --- |
| `id` | The relation (`L001`, …). | Unique. |
| `subiect` | The entry the relation is about. | A `slug` of `intrari.csv`. |
| `predicat` | The kind of relation. | Code list `relatie_predicat`. `atribuit_in_sursa` means "named in the source, role unknown". |
| `obiect` | The entry on the other end. | A `slug` of `intrari.csv`. Fill exactly one of `obiect` and `obiect_literal`. |
| `obiect_literal` | The other end as text, when it is not an entry. | Text. |
| `camp_sursa`, `valoare_sursa` | The v1 column and value that the relation comes from. | An accepted role other than `atribuit_in_sursa` needs `valoare_sursa`. |
| `stare` | Has an editor confirmed it? | Code list `relatie_stare`. `rol_neconfirmat` means the role is not confirmed; the site then shows the name neutrally. |

For `date_din`, use `obiect_literal` for the canonical provider name, or `obiect` for a catalogue entry.
Set `camp_sursa=surse_date` and put the evidence page URL in `valoare_sursa`.
The public build exports accepted rows as `dataSources: [{name, evidence}]`.
It excludes these rows from `attributions`. Empty sources mean unknown, not that the project has no sources.
Only accept providers explicitly identified by the project. Do not infer them from its subject or author.
These relations are edited in the repository; the existing Sheets tabs do not sync them.

### arii.csv

The geographic areas for `arii_acoperite`. An area ID does not imply a SIRUTA or NUTS code.

| Column | Meaning | Rule |
| --- | --- | --- |
| `id` | `<type>:<name>` (`tara:RO`, `judet:ilfov`, `localitate:iasi`). | Unique. |
| `eticheta_ro` | The label. | Required. |
| `tip` | The kind of area. | Code list `tip_arie`. |
| `parinte` | The area that contains it. | Area IDs. No cycle. |
| `cod_iso_3166_1` | The ISO country code. | Two capital letters, or empty. |

An entry applies in an area when one of its areas is that area, contains it or lies inside it.

### revizuire.csv (v2)

The review queue: concrete questions for the editor, and the editor's decisions. The package file holds R001–R066, which
describe the draft.1 manual proposal. The overlay has its own file; see [Integration overlay](#integration-overlay-integrare).

| Column | Meaning | Rule |
| --- | --- | --- |
| `id` | The item. `R` is the base queue, `C` an uncertainty or conflict of the classification run, `S` a semantic concern of the evaluation, `V` a vocabulary proposal. | Unique. |
| `slug` | The entry. | A `slug` of `intrari.csv`. |
| `camp` | What the question is about. | A column of `intrari.csv`, or `clasificare` (the whole classification), or `vocabular`. |
| `valoare_originala` | The current value. | Text. |
| `propunere` | The proposal. In the overlay an open item starts with "Recomandare:". A recommendation is not a decision. | Text. |
| `motiv` | Why. In the overlay `integrare.py` appends the evidence after "Dovadă:". | Text. A `tehnic` item needs it. |
| `prioritate` | How urgent. | Code list `prioritate`. |
| `stare` | Where the item stands. | Code list `revizuire_stare`: `deschis` (open), `acceptat`, `respins`, `amanat` (deferred), `tehnic`. |
| `decizie_editor` | The editor's decision. | `acceptat` and `respins` need it. |

The state `tehnic` ("technically closed") closes an item that needs no editorial decision. Its premise does not apply to
the current value, it duplicates another item, or a fix resolved it. It needs a `motiv` and an empty `decizie_editor`.
The publication gate counts an item only when its state is `deschis` and its priority is `mare`.

### mapari-externe.csv

Proposed mappings of local concepts to EuroVoc. They are separate from the entry classifications.

| Column | Meaning | Rule |
| --- | --- | --- |
| `concept_local` | The local concept. | An ID of `concepte.csv`. |
| `vocabular` | The target vocabulary. | `EuroVoc`. For it, `uri_tinta` and the two labels must equal the official snapshot in `reference/eurovoc-response.json`. |
| `relatie` | The kind of match. | Code list `mapare_relatie`. Use `exactMatch` only for equal meaning; the current rows use `closeMatch`. |
| `uri_tinta`, `eticheta_tinta_ro`, `eticheta_tinta_en` | The target concept. | The pair `concept_local` and `uri_tinta` is unique. |
| `identificator_verificat_la` | The date the identifier was checked at the source. | Date. |
| `stare_mapare` | Has an editor accepted the match? | Code list `mapare_stare`. |
| `nota` | A note. | Text. |

### Settings, contract and history

| File | Holds | Edited by |
| --- | --- | --- |
| `setari.json` | `site`: the same keys as [site.json](#sitejson) (`issues`, `sheet`, `tabs`, `email`). `tabs.intrari` is the `gid` of the Sheet tab `v2-intrari`; it is `null` until that tab exists. `nota`: a note. Sections and link roles are not here. | a person |
| `schema.json` | The contract: `version`, the lifecycle codes, `keys`, `field_rules`, `headers`, and which files are authoritative, generated or historical. | a person, only when the model changes |
| `versiuni.json` | The version history. The last version must equal `schema.json` → `version`. | a person, for a new version |
| `manifest.json` | The draft.1 counts and the SHA-256 of every file in `source/` and `reference/`. | nobody |
| `catalogue.json` | A JSON export of the tables, for programs. Generated; never an editing source. | `validate.py --export` |
| `clasificare-input.csv` | The input of the classification experiment: the original text of the 122 entries, with no v2 classification. | nobody |
| `atribuiri-initiale.csv` | History: the draft.1 assignments, with `slug`, `camp`, `concept`, `baza`, `campuri_sursa`, `dovada`, `stare` and `data`. | nobody |
| `corespondente-v1.csv` | History: the crosswalk from the v1 domain, type and keyword terms to candidate concepts (`camp_original`, `termen_original`, `concepte_candidate`, `regula`, `nota`). It is not a replacement table. | nobody |
| `source/` | Exact copies of the top-level files of `data/` at the start of the migration. | nobody |
| `reference/` | The EuroVoc query and response, and the method sources. | nobody |
| `runs/` | The sealed classification run `2026-10-19-reasoned-evidence`. | nobody |

`validate.py` refuses a change to a file of `source/` or `reference/`, because the hashes in `manifest.json` no longer match.
It also refuses a second source for sections or link roles in `setari.json`.

### Integration overlay: integrare/

`data/taxonomy-v2/integrare/` is an overlay. It holds the classification of the sealed run `2026-10-19-reasoned-evidence`,
with three corrections from the evaluation. Its `pachet.json` names the files it owns (`local_files`) and takes the rest
(vocabulary, code lists, areas, relations, `observatii/`, `source/`) from its `base`, the package. The status is the
same as the package: every classification is a proposal.

| File | Written by | Holds |
| --- | --- | --- |
| `pachet.json` | `integrare.py --write` | `purpose`, `base`, `local_files`, `headers` (the columns of the overlay's own tables), `source_run` (the run and the hashes of its files), `notes` and `counts`. |
| `intrari.csv` | `integrare.py --write` | The columns of the package `intrari.csv`. The classification comes from the sealed responses and from `modificari.csv`. The text, links, contact, `stare` and `nota` come from `source/`, by `sursa_fisier` and `sursa_rand`. |
| `revizuire.csv` | `integrare.py --write` | The columns of the package `revizuire.csv`. The base queue R, reconciled with `reconciliere.csv`, and the items C, S and V. |
| `rezultate.csv` | `integrare.py --write` | One row for each entry; see below. |
| `propuneri-vocabular.csv` | `integrare.py --write` | The proposed concepts and areas; see below. |
| `modificari.csv` | a person | The change log; see below. |
| `reconciliere.csv` | a person | The reconciliation of the review queue; see below. |
| `catalogue.json` | `validate.py --root … --export` | The JSON export of the overlay. |

`integrare.py` rebuilds `intrari.csv`, `revizuire.csv`, `rezultate.csv`, `propuneri-vocabular.csv` and `pachet.json` from the
run and the two hand-edited files. CI runs it without `--write` and fails when `integrare/` differs from a fresh assembly.
A hand edit of `intrari.csv` or `revizuire.csv` therefore fails that check; a correction goes into `modificari.csv`.
The brief `docs/briefs/v2-migration-completion.md` (slice F) plans a step that detaches the overlay from the run before the
owner edits it. That step does not exist yet.

**rezultate.csv**

| Column | Meaning |
| --- | --- |
| `slug` | The entry. |
| `rezultat` | The status of the sealed answer: `classified`, `partial` or `insufficient_evidence`. An entry with `insufficient_evidence` has no classification and the state `de-revizuit`. |
| `raspuns` | The path of the sealed answer under `runs/<run>/`. |
| `sha256` | The hash of that answer. |
| `incertitudini`, `conflicte` | The number of uncertainties and conflicts in the answer. |
| `modificari` | The IDs of `modificari.csv` that changed this entry, `\|`-separated. |

**modificari.csv.** An append-only log of the corrections that a person made. Add rows. Do not rewrite a row.

| Column | Meaning |
| --- | --- |
| `id` | `M001`, … |
| `data` | The date of the change. |
| `slug`, `camp` | The entry and the column. The column must not be a preserved text column, `slug`, `sursa_fisier` or `sursa_rand`. |
| `tip` | `valoare` when the value changes. `dovada` when the value stays and only the evidence changes. `dovada` needs `inainte` equal to `dupa`; `valoare` needs them to differ. |
| `inainte`, `dupa` | The value before and after. `inainte` must equal the value in the assembled `intrari.csv`. |
| `motiv` | Why. |
| `dovada` | A quote and its locator. `integrare.py` checks that the quote is in its source. |

**reconciliere.csv.** It compares each review item with the current `intrari.csv`. `integrare.py` applies it when it assembles
`revizuire.csv`. The base queue stays unchanged, and no classification changes. Every R item has a row. A C, S or V item can have one.

| Column | Meaning |
| --- | --- |
| `id` | The review item: `R…`, `C…`, `S…` or `V…`. |
| `rezultat` | `pastrat` (the text stays), `rescris` (the field, current value, recommendation and reason are written again) or `tehnic` (the state becomes `tehnic`). |
| `camp` | A column of `intrari.csv`, `clasificare` or `vocabular`. |
| `valoare_originala` | The current value in `integrare/intrari.csv`. |
| `propunere` | The recommendation. An open item starts with "Recomandare:" and names a value or an action. |
| `motiv` | Why. `integrare.py` appends the evidence after "Dovadă:". |
| `dovada` | Evidence tokens separated by `\|`. `rescris` and `tehnic` need at least one. `pastrat` has none. |

An evidence token is `file.csv:key:column` (`clasificare-input.csv:efor:oras_original`, `integrare/intrari.csv:crpe:arii_acoperite`)
or `runs/<run>/responses/<slug>.json:key` (also `key[field=value]`). `integrare.py` refuses a token that does not resolve.

**propuneri-vocabular.csv.** Concepts and areas that the run or the evaluation proposes. None is in `concepte.csv` or
`arii.csv`, and none is assigned to an entry. `integrare.py` refuses an `id` that already exists there.

| Column | Meaning |
| --- | --- |
| `id` | The proposed ID (`format:calendar`, `tara:republica-moldova`). |
| `tip` | `concept` or `arie`. |
| `schema` | The concept scheme, or the area type. |
| `eticheta_ro`, `eticheta_en`, `definitie_ro` | The proposed labels and definition. |
| `mai_larg` | The broader existing IDs, `\|`-separated. |
| `slug` | The entries that need the term, `\|`-separated. |
| `motiv`, `dovada` | Why, and the evidence. |
| `stare` | `propus`. |

Each (entry, proposed term) pair has one review item `V…`. The model run does not decide: the owner chooses whether to add a
proposal to the vocabulary.

### Observations: observatii/

The generated files of the profiler, the search and the model review, for a v2 root. They are the v2 copies of the v1 files in
`data/`. A package root and the overlay on top of it share one folder, `data/taxonomy-v2/observatii/`, because the overlay does
not list it in `local_files`. `profile.py`, `search.py` and `review.py` with `--data-dir` read and write only this folder (and
the images in `site/img/`, named by slug). They never write `intrari.csv`. `validate.py` and `build.py` read it.

| File | Columns | Written by |
| --- | --- | --- |
| `profil.csv` | `PROFIL_COLS`; see [profil.csv](#profilcsv) | `profile.py`; `search.py` for `mentions`, `mention_hosts`, `search_social` |
| `mentiuni.csv` | `MENTIUNI_COLS`; see [mentiuni.csv](#mentiunicsv). A person sets `editor`. | `search.py` |
| `mentiuni_etichete.csv` | `ETICHETE_COLS`; see [mentiuni_etichete.csv](#mentiuni_etichetecsv). It does not exist until the first v2 review run. | `review.py` |
| `review/raw.jsonl` | One JSON object for each reviewed entry; see below. | `review.py` |
| `review/sugestii.csv` | `slug`, `camp`, `actual`, `propus`, `motiv`, `sursa`, `incredere` | `review.py` |
| `review/propuneri-vocabular.csv` | `slug`, `schema`, `eticheta_ro`, `definitie_ro`, `motiv`, `dovada` | `review.py` |

`review/` is ignored by the repository. A v2 header must equal the header of the matching snapshot in `source/`.
Rows for a slug that left the catalogue stay in the files, and they do not create an entry.

- `sugestii.csv`. One row for each suggested change. `camp` is a v2 column (`subiecte`, `teme`, `scopuri`, `functionalitati`,
  `formate`, `tehnologii`, `institutii_vizate`, `subiect_principal`, …), `relatii` (an attribution) or `linkuri`. `propus` lists
  the proposed IDs. `sursa` holds the URL and the quote that back a technology or a typed role. The v1 file has no `sursa`.
  A person accepts a suggestion by hand. The script never writes `intrari.csv` and never sets a classification to `acceptat`.
- `propuneri-vocabular.csv` (review). A term that no ID covers. It never becomes an ID by itself.
- `raw.jsonl`. Keys: `slug`, `model`, `cost`, `cache_read`, `mentiuni_map` (the id of each result sent → its URL), `inputs`,
  `review` (the model's answer) and, on v2, `respinse` (claims that the script dropped). A failed request has `slug`, `eroare` and
  `cost` only. `inputs` holds five hashes: `entry` (the text sent), `urls` (the set of result URLs sent), `vocabulary`, `prompt`
  (instructions and answer schema) and `model`. An entry is due again when one hash changes. The file stays local, so a fresh
  checkout treats every entry as due.
- A v2 answer keeps a technology or a typed role only with a source: a URL that was supplied, and a quote of at least 12
  characters that the supplied text contains.

### form-v2.json

The answer map of the planned v2 proposal Form. `form.py --data-dir <v2 root>` plans the v2 questions from the vocabulary,
offline. This file turns the label of an answer into an ID, so that a renamed label never changes what an old response means.

| Key | Meaning |
| --- | --- |
| `version` | An integer. `form.py --write-map` raises it by one when it adds a title or a label. |
| `titles` | The 13 question titles, in Form order. Once the v2 Form is live, they are the column names of `propuneri`. `--import` needs them in the export. |
| `answers` | For each choice question (`Ce propui?`, `Subiecte`, `Formate`, `Acoperire`): label → ID. |
| `kind_section` | For each entity kind, the site section it belongs to (`proiect`, `organizatie` or `resursa`). |

A label is never removed from `answers`. `--write-map` refuses to give a label another ID. `--check` exits 1 when the map
lacks a label of the plan. `--import FILE.csv` reads an export of the tab `propuneri` and writes `intrari.csv` rows: IDs from
this map, `clasificare_stare` `propus`, `incredere` `mica`. An unknown label is reported and left out. A response with no
subject or several subjects gets `de-revizuit` and empty `subiect_principal` and `subiecte`; the ticked IDs go to
`nota_clasificare`. The proposer's e-mail is not copied. A person copies the rows into `intrari.csv`. `--apply` and `--save`
refuse a v2 root.

## data.json of the v2 model

`build.py --data-dir <v2 root> --site-dir <folder> --allow-draft` writes a `data.json` with `schemaVersion` 2 for
`site/app.js`. It keeps the v1 fields whose meaning is unchanged (text, links, profile, status, score, images)
and replaces the v1 classification:

- `kind` is `sectiune_url`; `entityType` is `tip_entitate`; `row` is the entry's record in `intrari.csv`.
- `sheet` is `{tab, row}`. While `tabs.intrari` in `setari.json` is `null`, it holds the v1 tab and the v1 row.
- `primarySubject` (an ID or null), `subjects`, `topics`, `purposes`, `capabilities`, `formats`, `technologies`,
  `institutions`, `organisationTypes`: concept IDs. `maturity` is one ID or null, never an array.
- `coverageLevel` and `areas`: the coverage code and area IDs.
- `dataDetail`, `dataDetailEvidence`: geographic data detail and its evidence URL.
- `dataSources`: `{name, evidence}` for each accepted data provider or publication.
- `attributions`: `{name, org, role, accepted}`. `role` is the relation predicate; an unconfirmed role shows neutrally.
- `legacy`: the original `domeniu`, `tips`, `keywords`, `fel`, `acoperire` and `oras`, only for old bookmarks.
- Top level: `draft` (true while any classification is not accepted), `vocabulary` (the used concepts with labels,
  alternative labels, definitions and broader IDs; the used areas; the scheme, section, entity-type, coverage and
  predicate labels; the subject order) and `legacyTaxonomy`.

The v2 `score` replaces the keyword term of documentation with one yes/no signal: a primary subject exists.
Notes, source rows, confidence, review items and model evidence never reach `data.json`.

A build without `--allow-draft` applies the publication gate first (see below), so it refuses today's data.

**The publication gate.** `validate.py --data-dir <v2 root> --publication` adds two rules to the package checks. Every entry
must have `clasificare_stare` `acceptat`. No review item may be `deschis` with priority `mare`. Items in the states `tehnic`
and `amanat` do not count. `build.py` without `--allow-draft` applies the same rule. `validate.py` applies it only with `--publication`. The gate passes
only after the owner accepts the classifications.

## Keeping this file complete

Every column of `PROIECTE_COLS`, `ORGS_COLS`, `PROFIL_COLS`, `MENTIUNI_COLS` and `ETICHETE_COLS`, and every header of
`schema.json` and `pachet.json`, must appear in this file as a name between backticks. `scripts/test_docs.py` checks it in CI. The same check by hand,
from the repository root, prints the missing names, or `none`:

```sh
python3 - <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
import common
text = open("docs/DATA-SCHEMA.md", encoding="utf-8").read()
lists = {n: getattr(common, n) for n in ("PROIECTE_COLS", "ORGS_COLS", "PROFIL_COLS", "MENTIUNI_COLS", "ETICHETE_COLS")}
for path in ("data/taxonomy-v2/schema.json", "data/taxonomy-v2/integrare/pachet.json"):
    for table, cols in json.load(open(path, encoding="utf-8"))["headers"].items():
        lists[f"{path.split('/')[-1]}: {table}"] = cols
for name, cols in lists.items():
    print(name, [c for c in cols if f"`{c}`" not in text] or "none")
EOF
```


### Documentation evidence (`observatii/documentare/`)

`scripts/collect_docs.py` collects methodology, about and `llms.txt` pages without a paid service.
The collector does not change editorial tables or public fields.

- `index.json`: generated collection records, keyed by entry slug. Each page keeps its requested URL, final URL, HTTP status,
  fetch time, document kind, project/shared-host scope, collection state, text hash and snapshot path.
- `rezumat.csv`: generated summary. Columns: `slug`, `url`, `stare_colectare`, `pagini_colectate`, `metodologie`, `despre`,
  `llms`, `completitudine_inventar`. These are collection results, not accepted project classifications.
- `pagini/*.json`: downloaded text, headings, links, input candidates and table candidates. These files stay local and are gitignored.
  A snapshot is keyed by URL and text hash. Raw text has a 60,000-character limit; `truncated` records that limit.
- `pilot-inventare.json`: five editorial draft inventories. Each field records its role, proposed or explicit type, optional unit,
  source URL, snapshot hash and character interval. Every profile is partial and needs review.
  Checked dataset examples can also carry JSON pointers, metadata dimensions, upstream providers and separate endpoint probe results.
  This file is a pilot, not an authoritative schema or a public-build input.

`documentatie-gasita` means that the collector found a candidate first-party page or section. It does not prove completeness.
`documentatie-neconfirmata` means that this bounded pass found no usable project-specific documentation.
HTTP errors, network errors, HTML at a `llms.txt` address and homepage copies remain separate page states.
Shared-host documentation is retained with `scope=gazda-comuna`. It does not become project-specific evidence automatically.

The collector strips scripts and does not run JavaScript. Input and table candidates are not verified variable definitions.
A declared API route is not a checked working endpoint. Keep API checks and their outcomes separate.
After a new checkout, use `--force` to retrieve the local snapshots needed to review the evidence intervals.
