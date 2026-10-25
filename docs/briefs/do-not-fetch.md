# Brief: a list of hosts that no collector requests

Status: ready for Sonnet. Owner approval: 2026-10-26 ("go ahead").

## Problem

Some sites forbid automated access. `harta-firmelor.ro` answers every automated request with HTTP 429 (a Vercel Security Checkpoint), and its `llms.txt` says "Extragerea automată și în masă a datelor de pe site nu este permisă."
Today only the two addresses that the owner saved are protected (`collect_docs.py` and `inventory.py` skip an address with an owner-saved copy).
Other runs still request the site:

- `profile.py` requests every entry's home page (httpx), its images and icons, and renders pages with Playwright. On a blocked site it gets the checkpoint page. The profile can then record the site as unreachable, and `build.py` shows that status on the public site.
- `collect_docs.py` (discovery of `llms.txt`, `/api`, `/docs` and similar) and `inventory.py` request other addresses of the same site, also with `--force`.
- Find any other script that requests a project's own site (for example `review.py`, which renders kept search results with Playwright, and the `--extra` signals of `profile.py`). `search.py` calls only the search APIs; confirm that.

## Goal

One hand-edited list of hosts. Every script that requests a URL checks the list first. A listed host gets no request, and the script records why.

## Design (decided)

1. **File**: `data/taxonomy-v2/colectare-interzisa.csv`, hand-edited, UTF-8, comma-separated, round-trippable through Google Sheets.
   Columns: `gazda` (a host name; it also covers its subdomains), `motiv` (Romanian, one sentence), `dovada` (a URL or a short quote), `data` (YYYY-MM-DD, when the restriction was seen), `nota` (optional).
   First row: `harta-firmelor.ro`, motive: the site rejects automated requests (HTTP 429, Vercel Security Checkpoint) and its `llms.txt` forbids automated extraction; evidence `https://harta-firmelor.ro/llms.txt`; date 2026-10-24.
   It covers `api.harta-firmelor.ro` too: the official API needs a key that we do not have.
2. **Shared check** in `scripts/common.py` (stdlib only): load the list once; `forbidden(url) -> dict | None` returns the row for the URL's host or a parent host, else `None`. Match on host labels, so `notharta-firmelor.ro` does not match. Ignore a leading `www.`.
3. **Every request path calls the check before the request**, including redirects where the client follows them itself (a redirect to a listed host must not be followed; for httpx, check `final_url`/each hop or disable auto-redirect for that call — choose the smallest correct change and say what you chose).
   The skipped result has a distinct state, `colectare-interzisa`, with the row's `motiv`. It is never an error, never a failed attempt, and never "offline".
4. **`profile.py`**: for a listed entry, make no request (no page, image, icon, screenshot, Playwright render). Keep the entry's existing `profil.csv` row as it is; never write `offline` or `necunoscut` because of the list. Print one line per skipped entry.
5. **`collect_docs.py` and `inventory.py`**: skip listed URLs before the request budget counts them; the request log (`RequestLog`) gets no row for them. Owner-saved copies stay valid and are still verified by `--check`.
6. **`validate.py`**: check the file (header, a valid host in `gazda`, non-empty `motiv`, a valid date, no duplicate host). Warn when a listed host is the `url` host of no entry (it may be stale); that is a warning, not an error.
7. **Docs**: `docs/DATA-SCHEMA.md` (the file and its columns), `data/taxonomy-v2/README.md` (one Romanian paragraph for editors: when to add a row, and that the owner then saves the pages by hand and imports them with `--import-saved`), the CLAUDE.md data-pipeline note (one line), `docs/BACKLOG.md` (flip the item "A guard for sites that forbid automated access" to `[x]`), `docs/ACTIVITY.md`, `docs/RELEASES.md` (minor bump, tag).

## Tests (offline, stdlib `unittest`)

- `forbidden()`: exact host, subdomain, `www.`, a look-alike host that must not match, a URL without host, an empty file.
- Each collector with a listed host and a fake transport: 0 requests, the state `colectare-interzisa`, no log row, no change to `profil.csv` for that entry, no failed-attempt mark. A redirect from an allowed host to a listed host is not followed.
- `validate.py` on a bad file (missing column, bad host, duplicate).
- A mutation check: disable the guard and confirm that at least two tests fail. Report which.

## Limits

- Make no network request during the work. Use fakes.
- Do not change the review files (`revizuire.csv`, `relatii.csv`, `inventar-concepte.json`) or any generated file by hand.
- Stop and ask if a step changes the public data model (`site/data.json` keys) or needs a new dependency.
- The owner has uncommitted work in the main checkout. Work in your own worktree, commit there, and do not touch the main checkout.

## Report

What you measured (tests run/skipped, the mutation result, the `validate.py` and `inventory.py --check` output), what you assumed, every request path you found and how each one is guarded, and anything you left out.
