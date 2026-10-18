# Data schema

This file explains every column of every data file, and the rules that check them.
[ARCHITECTURE.md](ARCHITECTURE.md) shows how the files connect.
[CONTRIBUTING.md](../CONTRIBUTING.md) tells a contributor (in Romanian) how to fill in a row.

The column lists are in `scripts/common.py` (`PROIECTE_COLS`, `ORGS_COLS`, `PROFIL_COLS`,
`MENTIUNI_COLS`, `ETICHETE_COLS`). When a column changes, change that file, `validate.py`,
`build.py` and this file together.

| File | Written by | Section |
| --- | --- | --- |
| `data/proiecte.csv` | a person | [proiecte.csv](#proiectecsv) |
| `data/orgs.csv` | a person | [orgs.csv](#orgscsv) |
| `data/taxonomy.json` | a person | [taxonomy.json](#taxonomyjson) |
| `data/profil.csv` | `profile.py` and `search.py` | [profil.csv](#profilcsv) |
| `data/mentiuni.csv` | `search.py`; a person sets `editor` | [mentiuni.csv](#mentiunicsv) |
| `data/mentiuni_etichete.csv` | `review.py` | [mentiuni_etichete.csv](#mentiuni_etichetecsv) |
| `data/form.json` | `form.py --save` | [form.json](#formjson) |
| `data/site.json` | a person | [site.json](#sitejson) |
| `site/data.json` | `build.py` | [data.json](#datajson) |

## Rules for every CSV

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
| `img_source` | Where the image came from: the image address, or the page address for a screenshot. |
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

`profile.py --force` drops `mentions`, `mention_hosts` and `search_social`. Run
`search.py --prune-only` after it to restore them.

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
for the plan to order the questions like the CSV.

## site.json

Where a visitor can report a problem with an entry: the drawer's "Semnalează o problemă". `build.py`
copies the file into `data.json` as `site`. An empty value hides that option.

| Key | Meaning |
| --- | --- |
| `issues` | Address of GitHub's "new issue" page. The site adds a title and a body that name the entry. |
| `sheet` | Address of the Google Sheet, ending in `/edit`. The site adds the tab and the entry's row. |
| `tabs` | The Sheet's tab ids, `proiecte` and `orgs`: the number after `gid=` in the Sheet's address. |
| `email` | An address for the "send an e-mail" option. Empty by default, so that option is hidden. |

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
  years, or its repository is archived.
