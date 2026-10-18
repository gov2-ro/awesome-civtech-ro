# Brief: link icons and GitHub repo stats

Owner model: Sonnet. Requested by the owner on 2026-10-18.

## Goal

1. In the entry drawer (`site/app.js`, `fmt` near line 374), a link to a known network shows that
   network's logo instead of its name. Other links show a small favicon of their host before the
   label (`Donații`, `Date`, `Despre`…).
2. For an entry with a GitHub repository, the drawer shows the repo's stars, forks, open issues,
   commits, contributors, last commit and licence.

## Decisions (fixed)

- **D1. Network logos are inline SVG in `app.js`**, one `<symbol>` sprite or a small map
  `role → path`, for the roles in `data/taxonomy.json` → `linkuri.roluri` that are networks:
  facebook, instagram, linkedin, x, bluesky, mastodon, threads, tiktok, youtube, telegram,
  discord, github, gitlab. Take the paths from Simple Icons (CC0). No external requests, no CDN.
  Colour: `currentColor`, so the icons follow the theme. Size ~18 px, one row, a gap between icons.
- **D2. Accessibility:** each icon link has `aria-label` and `title` with the network name (e.g.
  "Facebook"). Keyboard focus stays visible. The text label disappears visually for network links
  only.
- **D3. Favicons for other links are downloaded at profile time**, never hot-linked. In
  `profile.py`, for each non-network link host in `linkuri` and in the profiler's `social`, fetch
  the host's favicon (reuse `fetch_icon` / the icon-candidate logic) into
  `site/img/linkicon/<host>.webp`, at most once per host (skip when the file exists, unless
  `--force`). `build.py` adds `icon: "img/linkicon/<host>.webp"` to a link when the file exists.
  The drawer shows it at 14–16 px before the label; without a file, the label alone.
- **D4. The entry's own logo:** the profiler already stores `icon`. Also try a larger logo when
  the page offers one (`apple-touch-icon`, `icon` with the largest `sizes`, a `<img>` whose
  class/alt/src contains "logo" in the header). Keep the best one as `site/img/icon/<slug>.webp`
  (≥ 64 px when available). Do not add a new column if `icon` can carry it.
- **D5. GitHub stats** in `profile.py` `--extra` (where `github()` runs now). New `profil.csv`
  columns, added to `PROFIL_COLS` in `common.py`: `open_issues`, `commits`, `contributors`,
  `last_commit`, `license`, `language`. Keep `stars`, `forks`, `repo_created`, `repo_archived`.
  - commits and contributors: `GET /repos/{r}/commits?per_page=1` and
    `/contributors?per_page=1&anon=1`; read the count from the `Link: rel="last"` page number
    (1 when there is no `Link` header and the list has one item, 0 when empty).
  - `open_issues`: `open_issues_count` from the repo object counts PRs too; use the search API
    only if it stays under the rate limit, otherwise keep `open_issues_count` and name it so in
    the UI ("issues + PR deschise").
  - Use `GITHUB_TOKEN` when set (`gh auth token` gives one); stop and report if you get 403 rate
    limits, never write zeros for a failed call.
- **D6. Drawer:** a "Cod" row when `code` is a GitHub repo: `★ 12 · 3 forks · 5 issues · 240
  commits · 4 contribuitori · ultimul commit 2026-10-14 · MIT`. Romanian labels, mono small like
  the other meta rows. Omit parts that are empty. `build.py` passes these fields in `data.json`
  under `repo: {...}` per item, only for items that have a repo.

## Rules

- Stay in `scripts/`, `site/`, `data/profil.csv` (generated), `CONTRIBUTING.md`/`README.md` only if
  a column is user-visible, `docs/BACKLOG.md`, `docs/ACTIVITY.md`.
- Never edit `proiecte.csv`, `orgs.csv`, `taxonomy.json`.
- No new dependency beyond what `profile.py` already declares.
- Match the code style around you. Do not commit.

## Run and check

```sh
uv run scripts/profile.py --extra            # all entries; GitHub stats + link favicons
uv run scripts/profile.py --only factual,funky-citizens,ro-api-hub,code4ro   # logos
python3 scripts/validate.py && python3 scripts/build.py
python3 -m http.server -d site 8000
```

Check in headless Chromium (Playwright), light and dark, 1280 px and 390 px: the drawer of
`funky-citizens` (six networks + Donații), `ro-api-hub` (repo stats), `efor`. Save screenshots
in the session scratchpad and list their paths.

## Report

Files changed; how many link hosts got a favicon and how many failed; how many repos got stats,
with 3 examples; GitHub requests made and the rate limit left; anything assumed; screenshots.
Add an ACTIVITY entry and flip/add BACKLOG items.
