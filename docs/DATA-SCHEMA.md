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
| `data/taxonomy-v2/colectare-interzisa.csv` | a person | [colectare-interzisa.csv](#colectare-interzisacsv) |
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
`validate.py` also warns, and never fails, when an entry with `relatie_date` `fara-date` has extracted fields:
it reads `campuri_din_surse` in `observatii/inventare/rezumat.csv`. One of the two records is wrong, and the editor decides which.

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
| `relatie_date` | How the entry relates to data. | Optional code: `date-publice`, `date-proprii`, `calcul`, `fara-date`. Empty means not assessed. Only a project or a resource has one: a value on an organisation is an error. `fara-date` and `detaliere_date` exclude each other. When two codes apply, use the first one in the list order. The Form has no question for it. |
| `localitate_originala` | The v1 `oras`, unchanged. | Text. It does not limit the coverage. |
| `autor_original` | The v1 `autor`, unchanged. | Text. `relatii.csv` holds the structured form. |
| `contact` | The v1 `contact`. | Text. |
| `civictech_original` | The v1 `civictech`, kept as legacy data. It is not a new certification. | Code list `civictech_original`: `0`, `1` or empty. |
| `stare` | The v1 manual state. | Code list `stare_manual`: `arhivat`, `offline` or empty. It does not describe maturity or review. |
| `nota` | Internal note. | Text. Private. |
| `clasificare_stare` | Is the classification ready? Does the entry go on the public site? | Code list `clasificare_stare`: `propus`, `acceptat`, `de-revizuit`, `ascuns`. Required. It is not an HTTP status. `ascuns` (hidden) keeps the entry, its classification and its observations in the data. The public build leaves the entry out (see the publication gate). A hidden entry still needs a full classification. |
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
| `relatie_date` | `intrari.csv` `relatie_date` | `date-publice`, `date-proprii`, `calcul`, `fara-date` |
| `nivel_acoperire` | `intrari.csv` | `national`, `local`, `international`, `necunoscut` |
| `clasificare_stare` | `intrari.csv` | `propus`, `acceptat`, `de-revizuit`, `ascuns` |
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
| `id` | The item. `R` is the base queue, `C` an uncertainty or conflict of the classification run, `S` a semantic concern of the evaluation, `V` a vocabulary proposal, `D` a proposed data provider (`camp=surse_date`). D132–D146 share their number with the `propus` rows L132–L146 of `relatii.csv`; D147 and later have no relation row until an editor accepts them. | Unique. |
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

### colectare-interzisa.csv

`data/taxonomy-v2/colectare-interzisa.csv` lists the sites that forbid automated access. No script requests a listed host.
A person edits the file. It belongs to the package, not to one root: every script reads this file, whatever `--data-dir` says.
`scripts/common.py` holds the constants (`FORBIDDEN_COLS`, `FORBIDDEN_PATH`, `FORBIDDEN_STATE`) and the one check, `forbidden(url)`.
The encoding, separator and quoting are those of the other CSV files.

| Column | Meaning |
| --- | --- |
| `gazda` | A host name in lower case, without scheme, path, port or `www.`. A row covers its subdomains: `harta-firmelor.ro` also covers `api.harta-firmelor.ro`. The match is by whole labels, so `notharta-firmelor.ro` does not match. A leading `www.` on the requested host is ignored. Required and unique. |
| `motiv` | One sentence in Romanian: why the site is on the list. Required. The scripts print it. |
| `dovada` | A URL or a short quote that shows the restriction. |
| `data` | `YYYY-MM-DD`: when the restriction was seen. Required. |
| `nota` | Optional. For example, which related hosts the row covers. |

`validate.py` checks the file: the header, a valid host in `gazda` (not `www.`), a non-empty `motiv`, a valid `data`, and no duplicate host.
An absent file is an error, because an absent list leaves every site open. A row without `dovada` is a warning. A row whose host is the `url` host of no entry
is a warning too: the row may be stale. A script that cannot read the file (a header without `gazda` or `motiv`) stops. An empty or absent file lists nothing.

**What a script does with a listed host.** It makes no request: no page, image, icon, feed, sitemap, screenshot or browser render, and no request for a redirect target.
`--force` does not change this. The skipped result has the state `colectare-interzisa` and carries the `motiv` of the row. It is never an error, never a failed attempt, never `offline` or `necunoscut`.

| Script | Behaviour |
| --- | --- |
| `profile.py` | In every mode (`--force`, `--extra`, `--opr` and the browser pass included) a listed entry is left out. One line per entry goes to the error output. The stored row of `profil.csv` stays as it is. The profile never gets a result because of the list. Link favicons skip a listed host. A redirect to a listed host stops (an httpx request hook for each hop; in the browser, a route handler and a resolver rule, see below); the entry keeps its row. |
| `review.py` | A listed entry gets no download and no model request. Its stored answer, suggestions and labels stay. A redirect to a listed host skips the entry in the same way. |
| `collect_docs.py` | A listed entry gets the record state `colectare-interzisa` with `motiv` and no pages, and an earlier record of it stays as it is (no `ultima_incercare`). A page whose redirect led to a listed host has the page state `colectare-interzisa` and keeps its earlier copy. The request budget does not count a listed address, and the request log gets no row for it. |
| `inventory.py` | A source on a listed host is not requested, `--force`, `--force-url` and `--probe` included. The run prints `colectare-interzisa: not requested: URL (motiv)`; `report['interzise']` lists the addresses. A body that the inventory retained earlier stays the evidence. A copy saved by the owner stays valid and `--check` still verifies it. The request log gets no row; `--probe` writes no cache file for it. |
| `render_pages.py` | A listed URL is dropped before the browser starts. A request to a listed host that a navigation, a script or a link starts is aborted, and a redirect to it fails inside the browser. The render record then has `stare` `colectare-interzisa`, `motiv` and `gazda_interzisa`. |
| `search.py`, `sheets.py`, `form.py` | They request search and Google APIs only, never a project site. The list does not apply. |

**Browsers.** A Playwright route handler does not see the redirect hop of a request that it let through. Measured with Chromium on loopback (2026-10-26): the local server
received the request for the listed name. So `profile.py`, `review.py` and `render_pages.py` start Chromium with `common.browser_args()`, a `--host-resolver-rules` argument
that maps every listed host and its subdomains to `~NOTFOUND`. The browser then cannot resolve them, and Playwright reports the hop as a failed navigation request
(`common.note_failed_request`). The route handler stays as a second layer for the first request and for scripts. A browser behind a proxy resolves nothing itself and would ignore the rule;
the scripts start it without a proxy.

When the owner adds a row, the owner saves the pages by hand and imports them with `--import-saved` (see [Pages saved by the owner](#documentation-evidence-observatiidocumentare)).

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
- `dataRelation`: the code of `relatie_date`, or an empty string when the entry is not assessed. `vocabulary.dataRelations` lists the codes
  with their labels, in list order: `[{key, label, labelEn}]`.
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
must have `clasificare_stare` `acceptat` or `ascuns`. No review item may be `deschis` with priority `mare`. Items in the states `tehnic`
and `amanat` do not count, and neither do the items of a hidden entry. `build.py` without `--allow-draft` applies the same rule. `validate.py` applies it only with `--publication`. The gate passes
only after the owner accepts the classifications.

**Hidden entries.** An entry with `clasificare_stare` `ascuns` stays in `intrari.csv`, `relatii.csv`, the Sheet and `observatii/`.
`common.public_catalogue()` leaves it out, and `build.py` reads only that list. So the entry is absent from `data.json`, the entry
pages, the archives, `feed.xml`, `llms.txt`, the vocabulary counts and the inventory pages (`--with-inventory`), and the ids of the other
entries stay contiguous. The Sheet links of the other entries do not move: `row` keeps the entry's record in the table. A relation from
another entry to a hidden entry shows its name but no link. A hidden entry is not a draft: `draft` ignores it. The profiler writes
its images to `site/img/`, which the public site would serve, so remove the images of a hidden entry (`profile.py --force --only <slug>` makes them again).

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

**Pages saved by the owner.** A site can answer every automated request with a security checkpoint and forbid automated extraction in its terms.
The owner can still open a page in their own browser and save it. `collect_docs.py --import-saved SLUG URL FILE --saved-at 2026-10-25T20:39:00+02:00 [--note TEXT]`
keeps such a file as a documentation page. It makes no request. The time needs a UTC offset and cannot be in the future. The file must be UTF-8 text of at most 2,000,000 bytes.
The page is read like a collected page (kind from the address, scope from the catalogue address, text, links). It has these keys, and nothing else says who made it:

- `origine`: `copie-salvata-de-proprietar`. A fetched page has no `origine`. The tools never write this value for a fetched page, and never label a saved page as fetched.
- `salvat_la`: the time as the owner gave it. `fetched_at` is the same instant in UTC and is the retrieval time. `http_status` is null.
- `nume_fisier` (the name of the file, without its directory), `sha256_fisier` (the SHA-256 of the file's bytes) and `nota_copie` (the optional note).
- `sha256` is the hash of the extracted text, as for every page. A plain-text file loses its outer spaces in the text, so `sha256_fisier` and `sha256` can differ.

A saved page replaces a page with the same address that failed, or an older saved page. It never replaces a page that was fetched and collected (an error).
A later run of the collector does not request an address that holds a saved page: the page stays as it is and gets no `ultima_incercare`.
The other addresses of the same entry follow the ordinary rules, so a run with `--force` requests them, unless the host is in [colectare-interzisa.csv](#colectare-interzisacsv):
a listed host is never requested. Add a site that forbids automated access to that list before the first run.
`inventory.py --check` verifies a saved page: its keys are consistent, and the retained text has the recorded `sha256`. A text that is absent from the checkout is listed as unavailable and is never counted as verified.
The owner keeps the file; the import command can run again from it, and its hash identifies the copy.

The collector strips scripts and does not run JavaScript. Input and table candidates are not verified variable definitions.
A declared API route is not a checked working endpoint. Keep API checks and their outcomes separate.
After a new checkout, use `--force` to retrieve the local snapshots needed to review the evidence intervals.


### Variable inventory drafts (`observatii/inventare/`)

`scripts/inventory.py` reads the cached first-party documentation. It follows up to three explicit schema/data links per entry.
It accepts OpenAPI, JSON Schema, CSV and JSON. It excludes configuration files and unrelated hosts.
An explicitly linked GitHub blob can resolve to its raw file. Verified metadata links from the editorial pilot remain reusable seeds.
The collector's optional `--follow-data-links` also discovers edition and data pages. Its page limit still applies.

All files below are generated review material. Only the explicit preview build reads them. No editorial table changes automatically.

- `proiecte.json`: one draft per catalogue entry. `scop`, `permite` and `formate_catalogate` reuse the existing catalogue.
  `intrari_utilizator` holds HTML control candidates. `surse_structurate` references source IDs, and `lacune` records gaps.
  Profiles remain `propunere`; completeness is only `partial` or `neconfirmat`.
- `seturi-date.json`: structured source records, keyed by a URL-derived ID. Each records HTTP status, retrieval time, body hash,
  immutable snapshot path, parser format and field records. Shared schema fields keep all their operation bindings.
  `final_url` is the address after redirects. A signed Google export address (`*.googleusercontent.com/export/…`) keeps its host, file ID and query;
  `inventory.public_url` replaces its token and Google account segments with `…`. The local cache keeps the full address.
- `campuri.csv`: `proiecte`, `sursa_id`, `url`, `format`, `rol`, `nume`, `cale`, `tip_declarat`, `tipuri_observate`,
  `tip_semantic`, `unitate`, `descriere`, `operatii`, `pointer_dovada`, `stare_tip`.
- `intrari-utilizator.csv`: `slug`, `nume`, `tip_control_html`, `descriere`, `url_dovada`, `pointer_snapshot`, `stare_tip`.
- `rezumat.csv`: `slug`, `stare`, `completitudine`, `controale_utilizator`, `surse_structurate`, `campuri_din_surse`.
- `descoperiri.json`: the discovery registry. One record per project and source URL (see below).
- `jurnal-cereri.csv`: the request log of named collection batches (see below).
- `adaugari/*.json`: specification files for explicitly identified sources (see below). `randare/*.json`: browser renders of single pages (see below).
- `surse/*.json`: local HTTP response bodies and cached failures; gitignored. Immutable versions include the body hash in their name.
  A failed response never replaces a cached good body.

**Discovery registry (`descoperiri.json`).** The registry records which structured source belongs to which project, and why.
It is separate from the per-run file limit. A smaller limit never deletes a discovery. Keys of each record:

- `proiect`, `url`, `sursa_id`: the project slug, the source URL and its ID (`sursa_id` is the first 20 hex digits of the SHA-256 of the URL).
- `stare`: `activ` (the project uses the source; its profile lists the ID), `descoperit` (found in the documentation, not admitted
  because the limit was reached) or `retras` (retired on purpose, with a reason).
- `metoda`: `link-in-documentatie`, `url-in-text`, `dovada-pilot`, `adaugat-explicit`, `repo-la-revizie` or `membru-anterior`.
  `membru-anterior` marks a membership that existed before the registry; its locator may be unknown.
- `parinte`: the page or repository where the source was found, or `null`.
- `dovada`: the locator of the discovery, or `null`. Keys: `url` (the parent page), `sha256` (hash of its text), `snapshot`
  (its local snapshot, relative to `observatii/`), `pointer` (`/links/N` is the Nth link of the page; `/text` with `interval`
  `[start, end]` is a character span of the page text) and `revizie` (for a repository path).
- `locator_stare`: `cunoscut` or `necunoscut`. An unavailable original locator stays `necunoscut`; the script never invents one.
  Later documentation can complete it (history event `locator-completat`).
- `link_original`, `descoperit_la` (retrieval time of the parent page, or `null`), `prioritate` (lower first), `nota` (optional).
- `dovezi_suplimentare`: optional list of further locators, each with `rol`. For a dataset-metadata source, `ruta-metadate-set` locates the
  documented route and `utilizare-in-proiect` locates the sentence in a project's own page that names the dataset code.
  A locator made by `--add-sources-file` also holds `fragment`, the exact text at `interval`. `inventory.py --check` verifies the page hash,
  the interval or link index, and the fragment whenever the documentation snapshot is present.
- `retras`: `null`, or `motiv` (required), `la` and `stare_anterioara`. `istoric`: events `admis`, `adaugat`, `retras`, `reactivat`,
  `locator-completat`, each with a time.

Rules. A project's profile lists exactly its `activ` records. Discovery admits new sources only until a project has `--max-files`
members (default 3); it never removes a member. A retired source stays in the registry and in `seturi-date.json`.
Discovery never reactivates it. A temporary HTTP 401, 404 or timeout retires nothing. `--retire SLUG URL --reason TEXT` retires;
`--add-source SLUG URL --method M --parent URL --note TEXT` adds an explicitly identified source.
`--add-sources-file FILE` adds many: a JSON list of `{proiect, url, metoda, parinte, nota, locate: {pagina, text}, dovezi: [{pagina, text, rol, proiect?}]}`.
Each `text` must occur in the collected page; otherwise the run stops before it writes anything. A project named by an addition or
a retirement counts as selected. `--force-url URL` fetches one source again without refreshing the others.

**Incremental runs.** `inventory.py` reads the tracked state before it reconstructs candidates. `--only` selects projects.
A run changes only the selected projects and the sources that they use. Every other profile, source reference and field record
stays as it is; only the derived `campuri_din_surse` follows a shared source. An entry that has no tracked profile counts as selected.

| Situation | Result |
| --- | --- |
| Request fails, source had field evidence | The record keeps its fields, hash and snapshot. `ultima_incercare` (`la`, `stare`, `http_status`, `eroare`) records the attempt. |
| The new body does not parse | Same as a failed request. |
| The new body parses and differs | The new fields replace the old. `versiuni_anterioare` lists the earlier `sha256`, `fetched_at` and `snapshot`. |
| A fresh success | `ultima_incercare` disappears. |
| Offline or request limit, cached body absent, source tracked | The tracked record stays. The run lists it (`no local body` or `not inspected`). |
| Offline, cached body absent, source never tracked | State `necolectat`, no fields. |
| A documentation snapshot is absent for a selected project | Its previous HTML control candidates stay, with a warning. |
| Tracked file unreadable, unknown slug, invalid proposed state | The run stops before it writes anything. |

`ultima_incercare` is the only mark of stale evidence. The explorer shows `fetched_at` as "consultat la" (consulted on), never as "verified".
When `ultima_incercare` exists the preview adds `refreshFailed` (`date`, `status`, `state`) to the source and `stale` to the inventory
summary, and the interface says that the information can be old.

The run builds all six generated files in memory, validates the state (unique IDs, references, registry and profile agreement,
no field evidence lost, previous versions retained), parses each proposed file, and then replaces the files. A failure leaves every
tracked file unchanged. A replay from identical caches gives identical bytes (`--offline` twice). `--dry-run` writes nothing.

**Request log (`jurnal-cereri.csv`).** `--lot NAME` turns on the log for a batch. Columns: `lot`, `la`, `metoda`, `url`, `stare`,
`http_status`, `octeti`, `cache` (`da` for reuse of a body already in the process, `nu` for a direct request), `scop`. It holds no headers
or credentials. `--budget N` limits the direct requests of the lot across runs; `--max-requests N` limits one run. A request over the
limit is not made; the source stays uninspected and appears in the run output. The fetcher does not retry. Binary bodies (`PK` zip or
spreadsheet, PDF, gzip, bodies with NUL bytes) get the state `format-binar` and no decoded text.

**Evidence check.** `inventory.py --check` makes no request and writes nothing. It prints four separate numbers: evidence errors
(a changed body, a wrong hash, an invalid pointer, a broken reference), bodies hash-verified, bodies unavailable on this checkout
(not verified, never counted as verified), and sources whose last refresh failed. Only errors fail the check;
`--strict-snapshots` also fails on unavailable bodies. When the registry holds copies that the owner saved, a second line counts them apart (see "Pages saved by the owner").

**Dataset facts of INS TEMPO metadata (`set_date`, `catalog`).** A source of format `metadate-ins` (a response of the ins.gov2.ro
route `/api/datasets/{matrix_code}`) keeps its dimension fields (role `dimensiune`) and adds one `set_date` record. Each fact holds
`valoare`, `pointer` (into the retained body) and `baza`:

- `declarat-in-metadate`: present in the response. `cod`, `denumire` (`ro`, `en`), `actualizat`, `categorie`, `definitie_indicator`,
  `metodologie`, `observatii` (the source note, verbatim), `randuri`, and the unit options of the unit dimension.
  Markup in a free text is removed (`transformare: marcaj-eliminat`); its links stay in `legaturi`.
- `calculat-de-api`: derived by the API's own profiler, not declared by INS. `perioada` (`an_min`, `an_max`, `granularitate`),
  `niveluri_geografice`, `arhetip`.
- `observat-in-optiuni`: counted from the dimension options in the body. `niveluri_in_optiuni`, `ani_in_optiuni`.

An indicator, a dimension and a dimension value are different things. The dataset has one indicator, described by `definitie_indicator`.
`dimensiuni` lists the dimensions (`nume`, `eticheta`, `tip`, `cod_dimensiune`, declared and returned option counts, `pointer`).
Dimension values appear only as `exemple_coduri` (at most five per dimension): `cod` is the source code (`sdmx_value`), `eticheta` the display
label, `id_sursa` the source identifier, `pointer` the option. `trunchiat` says that more options exist. A value is never a variable.
`unitati` lists the declared unit options. A unit option that the API did not type has `tip_unitate: null`. The dataset has no field `unitate`
unless the response declares one. `licenta` is `null` with `licenta_motiv` when the response has no licence member. The record names no
publisher and no original producer; the note in `observatii` may name the producer, and a reviewer reads it. The API host is the source URL.
`diviziuni` lists the split variants of the dataset. `inventory.py --check` recomputes `set_date` from the retained body and compares.

A source of format `lista-ins` (a dataset listing response with an integer `total` and cards that hold `matrix_code`) keeps its observed
fields and a `catalog` record: `total`, `carduri_in_esantion`, `complet` (always `false` when cards are fewer than `total`) and up to five cards.
A sample of the listing says nothing about datasets that it does not contain, and a one-card sample does not verify pagination.

Other parser rules added with the INS pass:
- A JSON object with more than 100 keys is a keyed collection. The parser samples its first 25 values under the path component `{*}`
  and records one field with role `colectie-cu-chei` and `numar_chei`. Keys never become field names. Smaller objects stay records.
- A JSON document with an `openapi` or `swagger` member is an API contract only when the member holds a version number.
  A member that holds a URL marks a data index; it is parsed as sampled JSON.

**Text-format readers (`citire`, format names).** A source that is neither a schema nor a data file can still declare fields. The registry
record of such a source holds `citire`: a reader name, or `{tip, ...options}`. Without `citire`, the URL extension picks `.cs`, `.sql`, `.php` or `.md`.
HTML at a schema or data address stays an error unless `citire` names a reader. The source keeps `citire`, so a replay uses the same reader.
All readers return the common field keys and add the keys below; none infers a meaning, a unit or a type that the text does not state.

| Format (`citire`) | What it reads | Field keys and notes |
| --- | --- | --- |
| `html-tabele` | HTML tables. `{tip: html-tabele, tabele: [2]}` selects tables by position. | A dictionary table (a name column plus a description, unit or type column) gives one field per row: `descriere`, `unitate` (the cell), `perioada_declarata`, `actualizat_declarat`; `stare_tip` `declarat-in-tabel-documentatie`. A data table gives one field per header cell: `unitate` only when the header ends with a unit in parentheses (`Tranșa (mld lei)` gives `mld lei`), `tipuri_observate` from up to five rows of the same width as the header (`forma-numerica`, `forma-de-data`, `text`, `null`: how the cell is written, never a storage type; a CUI column looks numeric and stays an identifier), `stare_tip` `antet-tabel-html`. A headerless two-column table whose second cell lists items (`group \| a, b, c`) gives one field per item with `grup`, `stare_tip` `declarat-in-text-documentatie`. Tables with a `Cookie` column are consent notices and are skipped. Locator `/tabele/T/randuri/R`, `/tabele/T/antet/C` (1-based table). |
| `markdown` | Pipe tables of a markdown document. | Only dictionary tables (name column plus description, unit or type column). Same keys as the HTML dictionary. |
| `csharp` | Public properties and enum members of classes, records and structs. | `tip_declarat` (the C# type), `obligatoriu` (`[Required]`), `grup` (the class). A `[FromQuery]` property has role `parametru-api`, `loc` `query`, and the public name as `nume` (`nume_in_cod` keeps the property). Enum members have role `cod-enumerare` and `valoare`. `stare_tip` `declarat-in-cod-sursa`; `pointer` `char:START-END`, `linie`. |
| `sql` | `CREATE TABLE` columns and single-column `ALTER TABLE ... ADD`. | `tip_declarat` (the SQL type with its length), `obligatoriu` (`NOT NULL`), `grup` (the table), `modificare` `alter-add` for an added column. Key clauses are not columns. |
| `php` | Laravel migrations, API resources and class constants. | A migration column: `tip_declarat` is the builder method (`smallInteger`), `modificatori` the chained calls, `obligatoriu` false when `nullable`, `valori_enum` for `enum`, `descriere` for `comment`, `formula_declarata` for a stored or virtual generated column. `foreignIdFor(Model::class)` gives `<model>_id` with `baza_numelui` `conventie-laravel`. A resource key (`toArray`) has role `camp-raspuns`, `expresie` (the source expression), and `descriere` and `tip_declarat` only from the docblock directly above it. A nested array gives a dotted path. A constant gives role `cod-enumerare`, `valoare`, `grup` (the prefix), `descriere` (a trailing comment). |
| `json-comentat` | Annotated JSON examples in fenced code blocks of a document. | `cale` is `heading::path`; `valori_enum` holds the alternatives of a `"a \| b"` string; `tip_referinta` holds a bare type name (`Speaker`); `descriere` holds the comment of the key's line; `tipuri_observate` records the kind of the example value. `stare_tip` `exemplu-in-documentatie`: the document shows the key, it does not promise a type. |
| `js-acces` | Names that inline page scripts read from a record object. `{tip: js-acces, obiecte: [fields]}`. | `stare_tip` `utilizat-in-cod-pagina`, `accesari`. It shows what the page uses; it is not a schema and it does not read the data behind the page. |
| `html-api-docs` | An API reference page whose endpoints are cards: a method badge, a path template with `:name` segments, access badges, a `Cache:` label, a description and a `Parametri:` line. `{tip: html-api-docs, contract: URL}`; `contract` names the OpenAPI source of the same project (optional). | Module `inventory_apidocs`. See "API reference pages" below. Request inputs and response members become fields; operations are a separate list. `stare_tip` `declarat-in-documentatie-api`; locator `char:START-END`. |
| `html-carduri-csv` | A page whose cards offer CSV files: a title, a description, a download link to a `.csv` file, a list of labelled values (`Rânduri`, `Perioada`, `Măsurat la`, `Surse`) and, under the heading `Coloanele`, a list of columns (name and description). `{tip: html-carduri-csv}`. | Module `inventory_csvcards`. See "Pages of CSV files" below. Each column is a field; each file is a dataset in the source key `seturi`. `stare_tip` `declarat-in-lista-documentatie`; locator `char:START-END`. |
| `js-literale` | The data that a page script holds as literals, and the schema.org `Dataset` of its JSON-LD. `{tip: js-literale, tabele: true}`; `tabele` (`true`, or a list of positions) adds the table readers of the same page, and their fields come first. | Module `inventory_literals`. See "Data literals in page scripts" below. `stare_tip` `observat-in-esantion-json` (a path in a literal) or `declarat-in-metadate` (a `variableMeasured` entry); locator `char:START-END`. |
| `html-lista-seturi` | A page whose tables list data sets: a heading above each table, and one row for each set with a subcategory, a title, a description, related reports and links to external files. `{tip: html-lista-seturi}`. | Module `inventory_setlist`. See "Pages that list data sets" below. It returns no field: the page declares no column. The data sets are in the source key `seturi`. Locator `char:START-END`. |

New `stare_tip` values (`js-literale` adds none: it reuses `observat-in-esantion-json` and `declarat-in-metadate`): `declarat-in-cod-sursa`, `antet-tabel-html`, `declarat-in-tabel-documentatie`, `declarat-in-text-documentatie`,
`exemplu-in-documentatie`, `utilizat-in-cod-pagina`; `html-api-docs` also uses `declarat-in-documentatie-api`; `html-carduri-csv` uses `declarat-in-lista-documentatie`
(the page lists the column with its description; the list is not a table and not a type declaration). `baza_tipului` of a source in these formats is `cod-sau-documentatie`.
`--check` parses the retained body again and compares every field, so a changed interval, pointer or type is an error.

**API reference pages (`html-api-docs`).** The reader keeps three kinds of fact apart and never calls the API.

- Operations: the source key `operatii`, one record for each card. Keys: `operatie` (`GET /api/company/{cui}`: the method and the template, with `:name` written as `{name}`),
  `metoda`, `cale`, `categorie` (the heading above the card), `descriere`, `acces` (the badges as written, for example `Pro`, `x402`), `cache` (the label as written, which can be an untranslated key such as `cache.6h`),
  `pointer` (`char:START-END`: the method badge and the path template). `descriere` is `null` and `descriere_cheie_nerezolvata` holds the text when the page shows an untranslated key (`ep.x.description`) instead of a description.
  `cache` is `null` when the card has no label. An operation is not a variable, and the field counts do not include it.
- Request inputs: fields with role `parametru-api` (a path or query parameter) or `corp-cerere` (a member of `body: { cuis: string[] }`). Each field has `operatie` and `aparitii` like the OpenAPI fields.
  `descriere` is the text after a dash (`cui — 1-10 cifre`); `indicatie_pagina` is the text in parentheses (`limit (1-50, default 20)`); `valori_enum` holds the alternatives of a hint such as `(authority|supplier|both)`.
  `tip_declarat` is set only when the page writes a type; the page text is never turned into a type. `loc` is `path` when the name is a `:segment` of the template (`baza_loc` `sablon-cale`),
  `query` when the card's example request writes the name in its query string (`exemplu-cerere`), `body` for a body member (`corp-declarat`), and `null` otherwise: the page does not say where such a parameter goes.
  `obligatoriu` is absent. The locator of a parameter is its item in the `Parametri:` line, or the `:segment` of the template when the line does not list it.
  A text with an unknown shape, brackets that do not close, markup in the `Parametri:` line, a duplicated operation or a page with no card is an error (state `eroare-parsare`); the reader never guesses.
- Response members: fields with role `camp-raspuns` and group `plic-raspuns`. They are the names in the line `Format: { success, data, meta }` (`stare_tip` `declarat-in-documentatie-api`) and the keys of the JSON error example
  under the heading with `(429)` (`stare_tip` `exemplu-in-documentatie`, `status_raspuns` `429`, `tipuri_observate` from the example value). They have no `operatie`: the page states them for the whole API. They are generic envelope members, not business variables.

**Pages of CSV files (`html-carduri-csv`).** The reader keeps what the page states about each file it offers, and never downloads a file. It makes no request.

- Datasets: the source key `seturi`, one record for each card with a download link, in page order. Each fact has `valoare`, `pointer` (`char:START-END`, an interval of the retained body)
  and `baza` `declarat-in-pagina`. Keys: `fisier` (the file name), `adresa` (the link resolved against the page address; `legatura` keeps the link as written, `transformare` `legatura-rezolvata`), `titlu`,
  `descriere`, `randuri` (an integer when the page writes one), `perioada` (the text as written, for example `1990 → 2026` or `situația la 11.09.2026`; it is not turned into a range), `masurat_la`
  (an ISO date; `text` keeps the page's `zz.ll.aaaa` and `transformare` says so; a date that does not parse stays text), `surse` (the sources named by the page, one fact each, in page order),
  `licenta`, `coloane` (the column names in page order) and `pointer` (the whole card). A missing fact is `null` (`surse` is `[]`). Nothing is inferred from a file name or a title.
- `licenta` is the licence that the page states once for its files: `valoare` (`CC BY 4.0`), `acopera` `fisierele-paginii`, `url` (the link marked `rel="license"`) and `atribuire` (the attribution line), each a fact with a locator.
  It is `null` when the page has no licence card.
- A source name (`surse`) is the label that the page writes (`MFP — bilanțurile`). It is not a provider: the review items name the provider and the roles of producer, distributor and project author.
- Fields: one for each listed column. `nume` is the column name, `cale` is `<file>::<column>` and `grup` is the file name (the same column name in two files is two fields), `rol` `camp-date`, `descriere` is the text of the page with entities decoded,
  `tip_declarat` is null (the page declares no type), and `perioada_declarata` is the period of the file. `unitate` and `baza_unitatii` (`declarat-in-descriere`) appear only when the description writes a unit after `în`
  (`în lei nominali`); a column name such as `median_turnover_lei` is not evidence of a unit. The locator is the interval from the `<dt>` of the column to the end of its `<dd>`.
- A page with no file card, a file offered twice, a column listed twice in one file or a column without a description is an error (state `eroare-parsare`); the reader never guesses.
- `--check` parses the retained body again and compares the fields and the datasets.

**Pages that list data sets (`html-lista-seturi`).** The reader keeps what the page states about each data set. It never opens a link and makes no request, not even to `www.google.com`.

- The page has one `<h3>` heading for each category. Below each heading is a table with the header cells `Categoria secundară`, `Baza de date`, `Descrierea setului`, `Rapoarte relevante` and `Link` (accents and case do not matter). One body row is one data set.
- Datasets: the source key `seturi`, one record for each row, in page order. Each fact has `valoare`, `pointer` (`char:START-END`, an interval of the retained body) and `baza` `declarat-in-pagina`.
  `valoare` is the text of the interval with the tags removed, the entities decoded and the spaces collapsed. A no-break space counts as a space.
  Keys: `categorie` (the heading), `subcategorie`, `titlu`, `descriere`, `rapoarte` (one `{text, adresa}` for each link of the fourth cell; `[]` when the cell has no link), `legaturi` and `pointer` (the whole row).
- `legaturi`: one record for each link of the fifth cell, in page order. Keys: `eticheta` (the link text), `text_dupa` (the text after the link up to the next tag, or null; a lone `/` is a separator and gives null),
  `adresa` (the target), `tip`, `id_document` and `gid`. `tip` is `foaie-google` (`docs.google.com/spreadsheets/d/ID`), `fisier-drive` (`drive.google.com/file/d/ID`), `dosar-drive`
  (`drive.google.com/drive/.../folders/ID`) or `alta-legatura`. `id_document` is the identifier in the address. `gid` is the number of `#gid=N` as text (`"0"` is a sheet number), or null.
  `tip` classifies the address only. A Drive file can be any kind of file, so `fisier-drive` does not say that the file is a spreadsheet.
- A link that the page wraps as `https://www.google.com/url?q=TARGET&...` keeps the page's own address in `adresa.legatura` and gets the TARGET (the `q` parameter, percent-decoded) in `adresa.valoare`,
  with `transformare` `legatura-google-desfacuta`. The pointer addresses the `href` as the page writes it.
- A data set is not a file. Several rows can link to one folder (three rows of the Expert Forum page share one Drive folder), and a row can link to several sheets. The reader keeps one record for each row.
- A page with no table of this shape, a row that is not five cells wide, a data set with no title, a `google.com/url` link without `q`, and the same title with the same links twice are errors (state `eroare-parsare`).
- `--check` parses the retained body again and compares the data sets.

**Datasette database listings (`baza-datasette`).** The reader keeps what the listing of a Datasette database states (`/<database>.json`: `database`, `tables`, `hidden_count`, `views`, and the
metadata members `source`, `source_url`, `license`, `license_url`). It is not a text format: the registry needs no `citire`, because the format comes from the shape of the JSON
(a `database` name, a `tables` list and a `views` member). It requests no table, no view and no query, so it reads no row. Module `inventory_datasette`.

- Fields: one for each column of each visible table (`hidden` false), in table order. `nume` is the column name as written (a trailing space stays), `cale` is `<table>.<column>`, `grup` is the table,
  `rol` is `coloana-sql`, `tip_declarat` is null (the listing declares no type), `stare_tip` is `declarat-in-lista-baza`, and `pointer` is the JSON pointer of the column (`/tables/N/columns/M`).
  `randuri_tabel` is the row count of the table as the server counted it when it answered; the key is absent when the listing gives no integer count. A column name that two tables share gives two fields.
- Database facts: the source key `baza`. `nume`, `marime_octeti` (the size in bytes), `sursa` and `adresa_sursa` (the declared source), `licenta`, `tabele` (one record for each visible table: `nume`, `randuri`, `coloane`, `pointer`),
  `tabele_ascunse` (the declared count of hidden tables), `ascunse_in_lista` (the hidden tables that the list holds) and `vederi` (the views: `nume` and `pointer`, nothing else). Each fact has `valoare`, `pointer` and `baza`:
  `declarat-in-metadate` (the metadata of the server: source and licence), `declarat-in-lista` (names and the hidden count) or `calculat-de-server` (the size and the row counts: the server computed them when it answered).
  A fact that the listing lacks is `null`.
- `licenta` is the licence that the metadata declares: `valoare` (as written, for example `CC Attribution 4.0 License`), `acopera` `tabelele-bazei`, `url` (the member `license_url`, as written) and `atribuire` (the member `source`, word for word).
  It is `null` when the listing has no `license` member: a licence address alone is not a licence.
- A hidden table (the full-text index tables `*_fts*`) gets no field. A view has no column in the listing, so it is named and nothing more. Primary keys, foreign keys, saved queries and the other members of the listing are not read.
  The `source` of the listing names who published the database. It is the project author or the distributor, not a provider of the data; the review items name the provider.
- A table or a view with no name, a table named twice, a table with no column list or no boolean `hidden`, a column with no name, a column twice in one table and a `source` that is not text are errors (state `eroare-parsare`); the reader never guesses.
  A hidden table is not checked for columns.
- `baza_tipului` of such a source is `lista-fara-tipuri`: names without types. `--check` parses the retained body again and compares the fields and `baza`.

**CSV header options (`citire` `{"tip": "csv", ...}`).** The plain CSV reader takes the first row as the header. It refuses a header with an empty or repeated cell.
A tab that people keep by hand may have a title above its header, or empty header cells. The registry names an exception for one source (module `inventory_sheet`):

- `rand_antet` (a whole number from 1): the header is this row. The rows above it are kept in the source key `antet.randuri_deasupra` as `{rand, celule: [{celula, valoare}]}`:
  the non-empty cells with their spreadsheet address (`A1`), cut at 300 characters. The editor who sets `rand_antet` has seen that these rows are a title.
- `coloane_fara_nume`: only the value `omise`. Empty header cells are left out of the fields and listed in `antet.celule_antet_goale` (`["A1", "F1"]`). A repeated name stays an error.
- An unknown option, or a wrong value, is an error (state `eroare-parsare`). `{"tip": "csv"}` alone, or no `citire`, keeps the plain rules.
- The field keeps `nume` and `cale` exactly as the cell is written (line breaks and trailing spaces included), `coloana_csv` (the 0-based position in the sheet, also when an empty cell before it was left out)
  and `pointer` `celula:B2` (the header cell, row counted from 1). `tip_declarat` is null and `stare_tip` is `neprecizat-in-antet-csv`, as for the plain reader.
- The source key `antet` exists only when options are set: `rand_antet`, `randuri_deasupra`, `celule_antet_goale`. `--check` parses the retained body again and compares the fields and `antet`.

**Data literals in page scripts (`js-literale`).** A single-page tool often keeps its data inside the page. No schema describes that data. The page still shows what it holds.
The reader makes no request and runs no script.

- A candidate declaration is a `const`, `let` or `var` at the start of a line, with an object or an array as its value. The reader keeps it when the value is a literal.
  A literal holds only strings, numbers, `true`, `false`, `null`, arrays and objects. Bare keys, single quotes, comments and trailing commas are allowed.
- A data island is a script of type `application/json`. The reader names it by its `id`. A script with `src` is not read. A repeated name gets a suffix (`DATA#2`).
- Each path in a literal is a field. Keys: `nume` (the last part of the path), `cale` (the variable and the path, for example `DATA.c{*}.m[]`), `tipuri_observate`, `variabila`, `rol` `camp-date`,
  `stare_tip` `observat-in-esantion-json`, `pointer` and `linie`. The `pointer` is `char:START-END`: the first node at that path in the retained body.
  The field has no declared type, no unit and no description, because the page declares none.
- The bounds are 25 elements of an array, 25 members of a collection, seven levels and 2,000 fields. `limita_atinsa` says that a bound was reached.
- An object is a keyed collection when it has 100 members or more, or when it has 12 members or more and all its values are of one kind (objects, arrays, strings or numbers).
  A collection has `rol` `colectie-cu-chei`, `numar_chei` and `chei_exemplu` (at most three keys of 40 characters). Its keys are values, such as county names. They never become field names.
  A record with 12 members or more and values of several kinds is still a record.
- An array of rows of one width (2 to 12 cells, all scalars) gives one field for each position, for example `ROWS[][0]` and `ROWS[][1]`.
  The position is a fact. What a position means is an interpretation: a group selector records it with its own evidence.
- `declaratii` (a source key) lists every candidate declaration in page order. Keys: `variabila`, `forma-sursa` (`literal-script` or `json-izolat`), `linie`, `citit`, `pointer`.
  A literal that was read also has `forma` (`obiect` or `tablou`) and `elemente` (the number of members or elements).
  A declaration that was not read has `motiv`: `valoare-nelitera` (code, an identifier, a function, a template string or a spread), `expresie-dupa-literal` (`[...].map(...)` or a comma),
  `cheie-nelitera`, `cheie-fara-valoare`, `sintaxa`, `sir-neinchis`, `comentariu-neinchis`, `literal-neterminat` or `literal-prea-adanc`.
- The comment directly above a declaration is kept as `comentariu`: `valoare`, `pointer` and `trunchiat` (when the text is cut at 600 characters). It is the page's own wording about the variable.
- A declaration in the middle of a line, or inside a function, is not listed. A line inside a literal that was read is data, never a declaration.
- `seturi_ld` (a source key) lists each schema.org `Dataset` in the JSON-LD of the page (`application/ld+json`, also inside `@graph`). The reader does not read the rest of the JSON-LD as data.
  Each fact has `valoare`, `pointer` and `baza` `declarat-in-pagina`.
  Keys: `nume`, `descriere`, `adresa` (`url`), `perioada` (`temporalCoverage`, as written), `acoperire` (the name of `spatialCoverage`), `licenta`, `limba`, `gratuit` (`isAccessibleForFree`),
  the lists `bazat_pe` (`isBasedOn`: addresses or free text), `creator`, `editor` (`publisher`), `cuvinte_cheie` and `variabile_masurate`, and `pointer` (the whole node).
  An object without `name` keeps its `@id` as the value. A missing fact is `null`; a missing list is `[]`.
  `isBasedOn` is a statement of the page. It is not a provider: the review items name the provider and its role.
- Each `variableMeasured` entry is also a field: `rol` `masura`, `stare_tip` `declarat-in-metadate`, `grup` (the name of the data set) and `cale` `Dataset1.variableMeasured.NAME`.
  `descriere` and `unitate` are set only when the page writes `description` and `unitText`.
- `baza_tipului` of such a source is `esantion-date`. `--check` parses the retained body again and compares the fields, `declaratii` and `seturi_ld`.
- A response over 2,000,000 bytes has no retained body (`raspuns-prea-mare`). A bounded range read (`--sample-bytes`) stops at the last complete line. It can end before the script of the page.

**Comparison with the contract.** When `citire.contract` names a source of the same project that is parsed and whose body this checkout holds, `inventory.py` compares the page with it after every run.
Each operation and each request input gets `in_contract`: `{sursa_id, pointer}` of the declaration in the contract, or `null` when the contract does not declare it. A field with no `operatie` has no `in_contract` key
(it was not compared); a source with no `comparatie_contract` was not compared. An input matches on role, operation and name, not on `loc`. The source also gets `comparatie_contract`:
`sursa_id`, `url`, `sha256` (the contract version used), `operatii_comune`, `operatii_doar_in_pagina`, `operatii_doar_in_contract` (names), `intrari_comune`, `intrari_doar_in_pagina` and `intrari_doar_in_contract` (`operation :: name`).
Count a record with `in_contract` set as already known from the contract; count the records with `in_contract` null as documented only by the page. A page record and a contract record that match describe one operation, not two.
`--check` recomputes `operatii`, the fields and the comparison. A contract body that is absent from the checkout makes the comparison "unavailable" (not verified, not an error); the fields and operations are still checked.

**Repository files at a recorded revision.** A file read from a repository carries `metoda` `repo-la-revizie` and a locator
`{url (the tree listing), revizie (the commit), cale, blob_sha, pointer /tree/N, sha256 (of the listing), snapshot}`. The listing is the
recursive tree of that commit (`api.github.com/repos/O/R/git/trees/COMMIT?recursive=1`, from `commits/HEAD`). The raw address contains the commit,
so a later change of the branch cannot change the evidence. `--check` verifies the entry, the listing hash and that the git blob SHA-1 of the retained body is `blob_sha`.
A repository on the same account is not project evidence. The link from the project (a page link, or the repository link that the profiler found on the project
site, locator `{tip: profil, slug, coloana, valoare}`) is a second locator, role `legatura-proiect-repo`. A repository file shows what the code declares at that commit.
It does not prove that the deployed project uses it today.

**Other locator kinds in the registry.** `{pointer: /body, interval, fragment, sha256, snapshot}` locates text in a body kept in the source cache
(a page that the inventory read but did not parse as a source). `{tip: randare, snapshot, pointer /cereri_date/N, valoare}` locates a data request that the browser
helper saw. A `link` locator (`/links/N` of a collected page, with `fragment` the link) is verified like an automatic discovery.

**Pages saved by the owner (`--import-saved`).** `inventory.py --import-saved SLUG URL FILE --saved-at 2026-10-25T20:39:00+02:00 [--note TEXT] [--reading NAME|JSON] [--parent URL]`
keeps a file that the owner saved from their browser as the retained body of `URL`, and adds `URL` to project `SLUG` like `--add-source`. It implies `--offline --only SLUG`
and refuses `--check`, `--probe`, `--dry-run`, `--force` and `--force-url`, so it cannot make a request. `--add-sources-file` can accompany it; a specification for the same address
comes first and keeps its locators and its reader (`citire`). The copy is in the cache before the specifications are resolved, so a specification can locate a fragment in it
(`locate` with `cache: true`, and `dovezi` the same way). The body goes to the ordinary cache (`surse/<id>.json`, gitignored) and, once parsed, to the immutable snapshot. Both are
the same kind of file as a fetched body, so the reader, `--check` and the review interface treat them alike. The source record differs from a fetched one in these keys:

- `origine` `copie-salvata-de-proprietar`, `salvat_la`, `nume_fisier`, `sha256_fisier`, `nota_copie`: as for a saved documentation page (see above).
  `fetched_at` is the saved-at time in UTC, `http_status` is null, `state` is `ok`.
- `sha256` is the hash of the retained body. When the page had no credential masked (`redactari` absent), `sha256` equals `sha256_fisier`, and `--check` reports a difference as an error.
  A masked credential changes the body on purpose, and then the two hashes differ.
- The explorer preview adds `savedByOwner` to the source and writes "copie salvată de proprietar la <date>" instead of "consultat la <date>".

A saved copy is never refreshed: a run with `--force` or `--force-url` makes no request for it, and a tracked saved source without its cache file keeps its record
(`no local body; tracked record kept`). A newer copy replaces the older one through the same command; the earlier version stays in `versiuni_anterioare` with its `origine`.
A fetched body that is already in the cache is never replaced by a saved copy (an error; a cached failure is replaced). When the run fails after the import, the previous cache file is put back.
`--check` verifies the retained body of a saved source like any other body (hash, and for `html-carduri-csv` the fields and datasets), and checks that `http_status` is null, `fetched_at` is the saved-at time and
`sha256_fisier` is a SHA-256. It prints a line "N copies saved by the owner (not fetched): V hash-verified, U unavailable and not verified". A body that is absent is unavailable, never verified.
The coverage export marks an entry with such a source with the lot `S`. The file stays with the owner (it is not in git); the cache and the snapshot are gitignored, so a new checkout imports the file again.

**Credentials.** A public page can embed a credential in its script. The fetcher masks values of the shape of an Airtable personal token,
or of a quoted `api_key`, `token`, `secret`, `password` or `bearer` value of 16 characters or more, in HTML and script bodies, before the body is stored or hashed.
`redactari` counts the masked values. The inventory never uses a credential that a page contains.

**Bounded reads.** `--probe URL ...` (needs `--lot`) fetches into the source cache and changes no record. `--sample-bytes N` asks for a byte range and keeps at most N bytes;
the body ends at its last complete line and the source carries `partial: true`, and its hash is the hash of the sample. A response over 2,000,000 bytes is `raspuns-prea-mare` and has no body.
`scripts/render_pages.py` (optional, PEP 723, needs Playwright's Chromium) opens a page once, writes the same-site fetch and XHR requests to `inventare/randare/*.json`
(`cereri_date`, `corpuri_pastrate`, `corpuri_omise`), and stores up to six JSON or CSV response bodies of 200,000 bytes or less as sources with `via: browser`. It never clicks, types or submits.
The server may refuse a plain request for an address that the browser reached; the helper does not work around that refusal. Browser rows in the request log have `cache` `browser`.

**Specification files (`adaugari/`).** `inventory.py --add-sources-file` reads `adaugari/*.json`: the investigation inputs. A specification names the project, URL, method, parent, a
`locate` or `repo` request for the discovery locator, `dovezi` for further locators, `citire` and `nota`. Replaying the files from complete caches gives the same registry.

The documentation collector keeps the pages that an earlier run collected and a later run cannot collect again. The page stays and
gains `ultima_incercare` (`fetched_at`, `state`, `http_status`, `error`). A page collected again replaces its earlier copy.

Type evidence remains distinct:

- `declarat-in-schema`: a property or parameter in a published schema. A missing declared type stays empty.
- `declarat-in-metadate`: a dataset dimension declared in live metadata. Semantic types do not assert its storage type.
- `observat-in-esantion-json`: a type observed in sampled values, including nulls. It is not a type contract.
- `neprecizat-in-antet-csv`: a CSV header; its storage/logical type remains unknown. Identifier values are not coerced to numbers.
- `control-html-candidat`: a visible HTML control, which may be a generic search or newsletter field.

Field records are paths scoped to a source. They are not a count of independent business variables.
Two representations of the same dataset can expose overlapping fields; this pass does not assert their equivalence.
Extraction bounds are 2,000 fields per source, seven nested levels and 25 sample elements per JSON array.
`limita_atinsa` marks a field or sample limit. All results remain partial even when no limit was reached.
Endpoint contracts describe permitted requests and responses; reading a contract does not execute or verify every operation.

`--check` makes no requests and rewrites nothing. It checks source hashes, source IDs, JSON pointers, CSV headers,
explicit schema types, source references, control-list hashes and control attributes. Local snapshots are required.
A new checkout needs `collect_docs.py --force` and `inventory.py --force` before the regenerated inventories can be checked.


### Coverage export and report

`scripts/inventory_report.py` writes `observatii/inventare/acoperire.csv` (one row for each of the 140 catalogue entries) and the readable report `docs/reports/inventory-expansion.md`.
`--check` compares both with a fresh computation. The hand-edited input is `data/taxonomy-v2/inventar-note.json`: limits, blockers and next steps of each entry, the narrative of the report and the verification results.
The keys `lot_c2` and `retea_c2` hold the narrative and the network summary of batch C2; the notes of its entries also carry `blocaj_en` (the blocker, in English, for the report).
The export keeps fields, business groups, declarations, observations and unknowns apart. A raw field total is never the progress measure.

| Column | Meaning and denominator |
| --- | --- |
| `slug`, `tip_entitate` | The entry and its type in the catalogue (`proiect`, `resursa`, `publicatie`, `organizatie`). |
| `investigat_in_lot` | The collection lots that touched the entry: `C` (the primary batch), `B` (INS metadata attached), `B2` (a source added for a named gap), `C2` (the three active projects of public-sector data), `S` (a page that the owner saved by hand), `baza` (fields from the first pass only). Empty: not investigated. |
| `stare_investigare` | `cu-surse-structurate` (at least one parsed source), `blocat` (sources only failed, or the notes file records a blocker for an entry that has no source record: a host that refused every request), `neinvestigat-in-lot`, `in-afara-ariei` (organisations: the finder lists projects and resources). |
| `surse_structurate` | Parsed structured sources in the profile. A source that several entries share counts for each. |
| `campuri_din_surse` | Source-scoped field records of those sources. They are paths, not independent variables. |
| `concepte_propuse` | Distinct proposed groups that contain at least one field of the entry. Empty when there is no source. |
| `campuri_cu_definitie` | Fields whose own record has a description that the source declares (schema text, a docblock, a dictionary table cell, a comment). Catalogue text and group definitions are not counted. |
| `campuri_cu_tip_declarat` | Fields with a declared type (schema, code). |
| `campuri_cu_tip_observat` | Fields with types observed in sample values or in the written form of table cells. |
| `masuri_cu_unitate`, `masuri_fara_unitate` | Semantic measures only: a field with the role `masura`, a dictionary-table row, or a member of a group in the category `masura` or `iesire-derivata`. A measure has a unit when the field declares one or the matching selector has a unit fact with evidence. Generic fields are not measures. Empty (unknown) when the entry has no source. |
| `surse_cu_provenienta_verificata` | Active registry records with a known discovery locator that holds a page hash, a git blob hash or a recorded profile value. `inventory.py --check` verifies the locators when the snapshots exist. |
| `limite`, `blocaj`, `urmatorul_pas` | Romanian notes. Limits come from the notes file and the source flags (`partial`, `limita_atinsa`, a failed refresh). A blocker is also filled from a failed source. |

An empty cell means unknown. A zero means that the count was made and found nothing.

### Proposals for the relation to data

`observatii/inventare/relatie-date-propuneri.csv` holds a proposal of `relatie_date` for each project and resource (hidden entries included). A person writes it once from the repository's own evidence: `formate`, `functionalitati`, `descriere`, the cached page text, `profil.csv` and the inventory. No request is made. No script reads it. The owner decides, and only then does a value reach `intrari.csv`.

| Column | Meaning |
| --- | --- |
| `slug` | The entry. |
| `nume`, `url` | Copies of the entry's name and address from `intrari.csv`, to help the owner open the site. |
| `pagina` | The entry's page on the public site; empty for a hidden entry. |
| `propunere` | A code of the list `relatie_date`, or empty when the evidence does not settle it. An empty value means: not assessed. |
| `baza` | One sentence that names the evidence. |
| `incredere` | `mare` (direct evidence: an accepted source, extracted fields or page text that says it), `medie` (the description or the page implies it) or `mica` (thin evidence; always `mica` when `propunere` is empty). |

### Explorer inventory preview

`build.py --with-inventory` reads inventory metadata and writes `/date/`, `/date/lista/` and `inventar/*.json`.
The flag requires taxonomy v2. It does not change editorial acceptance. The Pages workflow uses it since 2026-10-26, so the public site
shows the inventories; a build without the flag removes `date/` and `inventar/` from its site directory.
A source whose data sets all declare the same licence carries `licence` (`name`, `url`, `attribution`), and the field browser credits it.

- Each relevant item gets `inventory`: field/parameter count, source count, field examples, search keywords,
  documentation links, the original declaration count (`positions`), and `partial=true`.
- Structured fields are written to `inventar/<slug>.json`, loaded only when the visitor opens the field browser.
  Those payloads hold source URLs, field descriptions, declared or observed types, units, roles, references and operations.
- Repeated API parameters with the same source, type, description and location share a display row.
  The row keeps its individual references and operations. Other field records remain distinct.
- Declared extras enter the payload when present: `enum` (declared alternatives), `formula`, `group`, `period`, `value`, `line`, `expression`, `required`.
  A source adds `dataset` (code, name, update date, period, geographic levels, declared units, dimensions; the interface says that INS metadata comes from a mirror),
  `partial` (read as a bounded sample), `viaBrowser`, `savedByOwner` (a copy that the owner saved by hand) and `refreshFailed`.
- The URL of a Google Sheet tab ends in `export`, so the title of such a source comes from the page of the same project that lists it (format `html-lista-seturi`):
  `Foaie Google · <title of the data set>`, and, when the data set links several tabs, `· <label of the link>` (the text after the link, or its text). A tab with no such page keeps the title of its format.
- HTML control candidates, raw snapshots, hashes, browser request dumps and network diagnostics do not enter the preview payload.
- Documentation-only entries link their collected first-party pages. Entries with no inventory evidence get no marker.

`inventory_site.py` supplies this projection. `check_inventory_preview.py` checks lazy loading, field/main search,
source/role selection, partial labels, CSV unknown types, retry recovery, inert descriptions and narrow layouts.

### Local review interface

`scripts/review_ui.py` is a local tool (stdlib only, never published; `build.py` copies none of it). It reviews two queues in a browser and writes the repository files.
Git is the audit trail: the tool never commits, and its page shows `git status`, `git diff --stat` and the commands to run next.

```sh
python3 scripts/review_ui.py [--port 8790] [--data-dir data/taxonomy-v2/integrare]   # then open http://127.0.0.1:8790/
```

| Queue | Items | Files written |
| --- | --- | --- |
| Providers | `revizuire.csv` items with `camp=surse_date` (D132 and later) | `integrare/revizuire.csv`, `integrare/relatii.csv` |
| Variable groups | The groups of `inventar-concepte.json` and their members (selectors) | `data/taxonomy-v2/inventar-concepte.json` |

Provider decisions follow the rules of [relatii.csv](#relatiicsv) and [revizuire.csv (v2)](#revizuirecsv-v2). The note field is required; the tool writes one line.

| Action | Item | Relation row (`relatii.csv`) |
| --- | --- | --- |
| Accept | `acceptat`; `decizie_editor` = `Acceptat <date>: <note>` | The row named in `propunere` (`L132: …`) becomes `acceptat` with `camp_sursa=surse_date`, `valoare_sursa=<evidence URL>` and the confirmed provider name. Without such a row, a `date_din` row with the next free `L` id is appended, and `decizie_editor` says `Acceptat <date> (rând L147): <note>`. |
| Reject | `respins`; `Respins <date>: <note>` | A linked row becomes `respins`. A row that this item appended and no commit holds is removed; a committed one becomes `respins`. |
| Defer | `amanat`; `Amânat <date>: <note>` | A linked row stays (or goes back to) `propus`. |
| Duplicate | `tehnic`, empty `decizie_editor`, `motiv` = `Duplicat: D153. <note> Motiv inițial: <old motiv>` | The other item must exist, differ from this one, belong to the same project and not be a duplicate itself. An acceptance of this item is withdrawn. |
| Reset | The item is put back to its value at `HEAD` | The linked row is put back to `HEAD`; a row that this item appended and `HEAD` lacks is removed. |

The tool refuses a second accepted source with the same name for one project. It never edits `propunere`, and it edits `motiv` only for a duplicate.
Group decisions: `Revizuit`, `Resping` and `Amân` need a note. `Revizuit` also needs every member `confirmat` or `exclus`, one `confirmat` member, and an explicit tick
for each statement whose basis is `deductie-din-dovezi`. A member changes only while its group is `propus` or `amanat`; `Resetează` puts the group and its members back to `HEAD`.

Every write reads the file, applies one decision, validates the result (`taxonomy_v2.check` with the publication gate; `validate_concept` for each group) and replaces the
file atomically. New errors refuse the write. The request carries the SHA-256 of each file that the page loaded; a different hash on disk (an editor, a Sheet pull, `git checkout`)
refuses the write. A file that does not load and save back byte for byte (BOM, line ending, quoting, indentation, final newline) is refused, never rewritten.
Every request needs `Host` = `localhost` or `127.0.0.1` with the server port; a POST also needs the per-process token that the page carries (else HTTP 403). The server makes no network request.
The evidence panel reads the retained copies that `inventory.py --check` reads (`surse/`, `documentare/pagini/`; both stay out of git). `verificat` needs a recorded hash that matches the retained text
and the fragment in it; `schimbat` means the hash differs; `indisponibil local` means no copy; `fără amprentă` means the item records no hash (shown, never called verified).
The check panel runs `validate.py --publication`, `inventory.py --check` and `inventory_report.py --check` in subprocesses, and shows the accepted providers at `HEAD` against the working tree.
`inventory_report.py` counts provider items and groups by state.

### Cross-project data finder preview

The same flag generates `/date/` and `inventar/index.json`. It adds a navigation link in the explorer preview.
It also generates `/date/lista/`, a static table with one row per project or resource that has extracted fields and one column per family:
a cell names the groups (normalised names) of that family that the entry has. The last column, "Altele", counts the distinct names of fields in no group.
Entries without fields are named once below the table.

Counting rule: a field with a non-null `in_contract` restates a record of another source. It stays in `seturi-date.json` and `campuri.csv` as evidence,
but counts, group memberships and the preview use the restated record only (`inventory_state.counted_fields`; in the preview it becomes `also` on that record).
The index includes all 106 projects and 21 resources. Organisations remain in the ordinary explorer.
Each entry carries its catalogue description, subjects, institutions, accepted providers, inventory summary and proposed variable matches.
The page fetches one discovery index. Results appear in batches of 24. Full per-project fields remain separate.
An ordinary rebuild removes stale draft pages and payloads from a reused isolated output folder.

`data/taxonomy-v2/inventar-concepte.json` is hand-edited. It is separate from generated inventory records. Every group is a proposal for discovery:
membership says that a field plausibly carries the variable, never that two datasets can be joined. A group has these keys:

- `id`, `label` (Romanian), `definition` (Romanian), `categorie`: `identificator`, `dimensiune`, `masura`, `intrare-utilizator` or `iesire-derivata`
  (a value that the source computes). Use a category only when the evidence supports it.
- `baza_definitiei`: how the definition was made. All current definitions are `parafraza-editoriala` (editorial wording). The bases are
  `declaratie-directa` (the source says it), `observatie-esantion` (seen in sample values), `deductie-din-dovezi` (two or more pieces of evidence agree) and `parafraza-editoriala`.
- `dovezi`: evidence for the definition: `{sursa (a source, documentation or cached page URL), text (which retained copy: sursa, documentatie or cache), fragment (an exact text of that copy), sha256 (of that copy when asserted), baza}`.
  `inventory.py --check` finds the retained copy of that kind. A missing fragment is an error. A changed hash is reported as stale: the interpretation must be read again.
  The same address can have a different text in each kind of copy (a page body and its collected text), so a hash is compared only with a copy of the same kind;
  a checkout without that copy reports the evidence as unavailable, never as verified or stale.
- `ambiguitati`: open questions and candidates that are kept out of the group on purpose.
- `selectors`: alternatives; a field joins the group when any selector of its project matches.
- `familie`: the family of the group, an `id` of the top-level `familii` list. Optional; a group without one is listed last as "Altele".

The top-level `familii` list sorts the groups for browsing by what they describe. Each family has `id`, `label` (Romanian) and `descriere`.
The order of the list is the display order. The current families are `identificatori`, `geografie` and `timp` (keys that cut across subjects),
then `firme`, `achizitii`, `populatie-teritoriu`, `mediu`, `alegeri` and `parlament`. A family is a reading aid: it says nothing about compatibility,
and it is separate from `categorie` (the role of the variable: identifier, dimension, measure). `inventory.py --check` and the review interface reject
a duplicate family id, a family without a label and a group that names an unknown family.

A selector has `projects` (required) and at least one of `names` or `path`. It may also have `source` (a source URL or a list), `role` (field roles), `context`
(what the field describes in that project, for example the CUI of the authority or of the supplier), `fapte` and `nota`. Every constraint that the selector supplies
must match; this is what lets an ambiguous name such as `REF_AREA` join the county group for POP107D and not for TRN139A. `path` is the exact field path.
A fact in `fapte` has `cheie`, `valoare`, `baza` and, unless it is an editorial paraphrase, a `dovada` with the same shape as `dovezi`.
Generic names such as `id`, `value`, `name` and `year` join a group only through a selector that also names a source, a path or a role.
Each match keeps up to three examples from different sources, the original field role and representation, the type evidence, the path, the source URL and the reference.
The finder index adds the category, the ambiguity notes and the evidence links of each group, and the context and unit facts of each example.

Review state of a group and of its members (written by [the review interface](#local-review-interface); a missing key means `propus`, so a file without them stays valid):

| Level | Key | Values | Rule |
| --- | --- | --- | --- |
| Group | `stare` | `propus`, `revizuit`, `respins`, `amanat` | An unknown value fails validation. `revizuit` means "the editor checked the members and the wording"; it never makes a group a join key. |
| Group | `decizie_editor` | Text | Needed for `revizuit` and `respins`. |
| Group | `data_revizie` | ISO date | Set by each decision. |
| Selector (member) | `stare` | `propus`, `confirmat`, `exclus` | An unknown value fails validation. A `revizuit` group cannot hold a `propus` member. |
| Selector (member) | `nota_editor` | Text | Needed for `exclus`. |

An `exclus` selector stays in the file for history and never matches a field (`inventory_concepts.selector_matches`; every caller honours this, and `inventory.py --check`
does not ask it to match). A `respins` group produces no matches in the finder and no entry in `inventar/index.json`; a `revizuit`, `propus` or `amanat` group appears,
and the finder shows its state as a badge (`variables[].state` in the index). The review tool writes the new keys after the existing ones, in the order of the table.
The top-level `"stare": "propunere"` of the file keeps its meaning: groups remain discovery aids, never join keys.

Current groups (33; the last three are proposals of batch C2, state `propus`): identifiers `cui`, `cpv`, `siruta`; dimensions `judet`, `localitate`, `perioada-de-referinta`, `grup-politic`; measures `populatie`, `locuinte`,
`lungime-drumuri`, `cifra-afaceri`, `profit-net`, `numar-salariati`, `valoare-achizitie-directa`, seven environmental measures (`co2`, `pm25`, `pm10`, `temperatura-aer`,
`umiditate-relativa`, `presiune-atmosferica`, `viteza-vantului`), election counts (`alegatori-inscrisi`, `alegatori-lista-permanenta`, `alegatori-prezenti`, `voturi-valide`, `voturi-nule`),
`voturi-pentru`, `voturi-impotriva`, `voturi-abtinere`; derived output `rata-prezenta`; measures `casatorii`, `divorturi` and `studenti` (family `populatie-teritoriu`). Unit facts exist only where a source declares or implies one with evidence
(for example `co2` in ppm from the project page). The seven baseline groups keep every membership that v0.13.0 supported.

An INS dataset has a measure field `OBS_VALUE` (role `masura`, `stare_tip` `declarat-in-documentatie-api`). The API documentation (llms.txt) names `OBS_VALUE` as the observation column of
every dataset; the metadata supplies the indicator definition (`descriere`) and the declared unit (`unitate`, or `unitati_declarate` when a dataset declares more than one).
The documentation sentence is kept as `dovada_externa` and `--check` looks for it in the collected llms.txt page.

Provider groups use accepted `date_din` relations. Parliament has one display label; both chambers keep their separate evidence.
Target institutions use the existing `institutions` facet. They never become data providers through this projection.
All selected variables must occur in a matching entry. Other facets use OR within the facet and AND between facets.
Counts measure distinct entries. Values with at most three matches stay under `Mai multe`; selected values remain visible.
The URL stores search, resource inclusion and repeated facet parameters. Browser navigation restores those selections.
Entries with missing inventories remain searchable through their catalogue fields. Missing evidence does not assert missing data.
