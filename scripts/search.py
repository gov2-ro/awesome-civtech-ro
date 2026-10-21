# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Find pages that mention each entry (Serper = Google, Brave) and keep every result for inspection.

    uv run scripts/search.py --dry-run --only factual,declic   # print the queries; no requests
    uv run scripts/search.py                                   # entries that have no rows yet
    uv run scripts/search.py --only a,b --force                # query these again
    uv run scripts/search.py --provider brave                  # one provider only (serper | brave | all)
    uv run scripts/search.py --prune-only                      # apply the rules to the stored rows; no requests
    uv run scripts/search.py --data-dir data/taxonomy-v2/integrare --dry-run --only a,b   # a v2 root

Needs SERPER_API_KEY and BRAVE_API_KEY. Writes data/mentiuni.csv, one row per (slug, url). Every row
keeps the rule that would drop it (`regula`); a person overrides the rules in the `editor` column
(1 keeps, 0 drops) and search.py keeps that column on every rewrite. Then it recomputes `mentions`,
`mention_hosts` and `search_social` in data/profil.csv from the kept rows.

--data-dir selects the data root (default: the public root, PUBLIC_ROOT in common.py). A v2 root supplies the entries and keeps mentiuni.csv and
profil.csv in its observatii/ folder (an overlay uses its base's). On a v2 root the author names come from the
attribution relations (a literal, or the name of the target entry), with `autor_original` as the fallback, and the
author's own site is the URL of a relation target that is an organisation entry. A literal never matches an
organisation by its name.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

try:
    import httpx
except ImportError:  # the pure functions (and the tests) work without it; the search itself needs it
    httpx = None

from common import (load_env, PUBLIC_ROOT, MENTIUNI_COLS, SHARE, SOCIAL_HOSTS, data_schema, domain_of, is_kept, is_url, load_catalogue,
                    load_mentions, load_profile, observation_paths, save_profile, split_list, write_csv)

SERPER = "https://google.serper.dev/search"
BRAVE = "https://api.search.brave.com/res/v1/web/search"
SERPER_PAGES = 2  # of 10 results, for the domain query
BRAVE_COUNT = 20  # results per request, the API maximum
GAP = {"serper": 0.3, "brave": 1.1}  # seconds between request starts (Brave: 1 request/s)
USD = {"serper": 0.001, "brave": 0.005}  # per request, from the providers' price lists
MAX_SNIPPET = 300

# Prune rules, first match wins. Each regex is searched in the host and in the full URL. A rule only
# marks a row (`regula`); the editor sees every result and overrides in the `editor` column.
# `propriu` (the entry's own site, its linked sites, its author's sites) is checked last, per entry.
# The hosts below come from the first full run (2026-10-18): extend them as the editor prunes.
host_rx = lambda *hosts: r"(^|\.)(" + "|".join(re.escape(h) for h in hosts) + r")$"
NETWORKS = {"facebook", "instagram", "linkedin", "x", "bluesky", "mastodon", "threads", "tiktok", "youtube", "telegram", "discord"}
RULES = [(name, re.compile(rx, re.I)) for name, rx in [
    # App stores and online shops: they list anything under any name.
    ("magazin", host_rx("play.google.com", "apps.apple.com", "itunes.apple.com", "appgallery.huawei.com", "apkpure.com",
                        "apkmirror.com", "aptoide.com", "chromewebstore.google.com", "addons.mozilla.org", "apps.microsoft.com",
                        "emag.ro", "amazon.com", "ebay.com", "trendyol.com", "olx.ro", "etsy.com", "aliexpress.com")
     + r"|chrome\.google\.com/webstore"),
    ("social", host_rx(*(h for h, role in SOCIAL_HOSTS.items() if role in NETWORKS), "pinterest.com")),
    ("cod", host_rx("github.com", "gitlab.com", "codeberg.org", "bitbucket.org")),  # the repo is profiled already
    ("registru", host_rx("listafirme.ro", "listafirme.eu", "firmejust.ro", "listamarci.ro", "termene.ro", "risco.ro", "firme.info",
                         "topfirme.com", "mfinante.gov.ro", "openapi.ro", "confidas.ro", "infocui.ro", "bizoo.ro", "targetare.ro",
                         "totalfirme.ro", "firme-on-line.ro", "radarfirme.ro", "metricbiz.ro", "identitate.ro", "dnb.com")),
    # Pages generated for any domain or name: site checkers, review aggregators, contact finders.
    ("ferma", host_rx("scamadviser.com", "mydomaincontact.com", "rocketreach.co", "virustotal.com", "similarweb.com",
                      "trustpilot.com", "urlscan.io", "who.is")),
    # Sites that answer any name: dictionaries, job boards, music, film and football databases.
    ("zgomot", host_rx("context.reverso.net", "dexonline.ro", "dictionary.cambridge.org", "collinsdictionary.com",
                       "en.wiktionary.org", "ro.bab.la", "cum-se-scrie.ro", "glassdoor.com", "indeed.com", "bestjobs.eu",
                       "ejobs.ro", "open.spotify.com", "imdb.com", "transfermarkt.ro", "coursicle.com")),
]]
# Authors that are not an entry of their own; the sites below count as the author's own channel.
AUTOR_SITES = {"funky citizens": ["funky.ong", "funkycitizens.org"], "code for romania": ["code4.ro"]}
# Hosts where every subdomain belongs to somebody else: "own site" means the full host there.
SHARED = re.compile(r"(^|\.)(github\.io|gitlab\.io|netlify\.app|vercel\.app|pages\.dev|web\.app|firebaseapp\.com|"
                    r"herokuapp\.com|blogspot\.[a-z.]+|wordpress\.com|wixsite\.com|google\.com)$")

STATS = {p: {"requests": 0, "ok": 0, "errors": 0, "credits": 0} for p in GAP}
LIMIT: dict[str, "Limiter"] = {}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


class SearchError(Exception):
    """A provider answered with an error, or with something that is not a search page. Never zero results."""


class Limiter:
    def __init__(self, gap: float):
        self.gap, self.next, self.lock = gap, 0.0, asyncio.Lock()

    async def wait(self):
        async with self.lock:
            if (d := self.next - time.monotonic()) > 0:
                await asyncio.sleep(d)
            self.next = time.monotonic() + self.gap


def norm_date(s: str, today: date | None = None) -> str:
    """ISO date from the formats the providers return (2024-05-01T..., Jan 5, 2024, 5 ian. 2024, 3 days ago); '' if unknown."""
    today = today or date.today()
    s = "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower()) if not unicodedata.combining(c)).strip()
    if m := re.match(r"(\d{4})-(\d\d)-(\d\d)", s):
        return m.group(0)
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    ro = {"ian": 1, "mai": 5, "iun": 6, "iul": 7, "noi": 11}  # Romanian abbreviations that differ from English
    mon = lambda w: ro.get(w[:3]) or (months.index(w[:3]) + 1 if w[:3] in months else 0)
    try:
        if m := re.match(r"(\d{1,2})\s+([a-z]{3,})\.?,?\s+(\d{4})", s):
            return date(int(m.group(3)), mon(m.group(2)), int(m.group(1))).isoformat()
        if m := re.match(r"([a-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})", s):
            return date(int(m.group(3)), mon(m.group(1)), int(m.group(2))).isoformat()
    except ValueError:
        return ""
    if m := re.search(r"(\d+)\s+(min|hour|ora|ore|day|zi|week|saptam|month|luna|luni|year|an)", s):
        days = {"min": 0, "hour": 0, "ora": 0, "ore": 0, "day": 1, "zi": 1, "week": 7, "saptam": 7,
                "month": 30, "luna": 30, "luni": 30, "year": 365, "an": 365}[m.group(2)]
        return (today - timedelta(days=int(m.group(1)) * days)).isoformat()
    return ""


async def call(client: httpx.AsyncClient, prov: str, send) -> httpx.Response:
    """One request with spacing; transient failures (network, 429, 5xx) are retried before they count as an error."""
    err = ""
    for attempt in range(3):
        await LIMIT[prov].wait()
        STATS[prov]["requests"] += 1
        try:
            r = await send()
        except httpx.HTTPError as ex:
            err = f"{type(ex).__name__}: {str(ex)[:120]}"
        else:
            if r.status_code != 429 and r.status_code < 500:
                return r
            err = f"HTTP {r.status_code}"
        await asyncio.sleep(3 * 2 ** attempt)
    raise SearchError(err)


def json_of(r: httpx.Response, prov: str) -> dict:
    try:
        js = r.json()
    except ValueError:
        raise SearchError(f"{prov}: HTTP {r.status_code}, not JSON: {r.text[:120]!r}") from None
    if not isinstance(js, dict):
        raise SearchError(f"{prov}: unexpected response {str(js)[:120]}")
    return js


async def serper(client, q: str, page: int) -> list[dict]:
    """Google results. Unquoted: the free tier rejects phrase queries with HTTP 400."""
    r = await call(client, "serper", lambda: client.post(
        SERPER, headers={"X-API-KEY": os.environ["SERPER_API_KEY"]}, timeout=30,
        json={"q": q, "gl": "ro", "hl": "ro", "num": 10, "page": page}))
    js = json_of(r, "serper")
    if r.status_code != 200 or "message" in js or "error" in js:
        raise SearchError(f"serper: HTTP {r.status_code} {js.get('message') or js.get('error')}")
    if "organic" in js:
        rows = js["organic"]
    elif isinstance(js.get("searchParameters"), dict):
        rows = []  # a valid page without hits
    else:
        raise SearchError(f"serper: unexpected response {str(js)[:120]}")
    STATS["serper"]["credits"] += js.get("credits", 1)
    return [{"url": o.get("link", ""), "title": o.get("title", ""), "snippet": o.get("snippet", ""), "date": o.get("date", "")}
            for o in rows]


async def brave(client, q: str, page: int) -> list[dict]:
    """Brave results; they carry `page_age`, which Google results often lack."""
    r = await call(client, "brave", lambda: client.get(
        BRAVE, headers={"Accept": "application/json", "X-Subscription-Token": os.environ["BRAVE_API_KEY"]}, timeout=30,
        params={"q": q, "count": BRAVE_COUNT, "country": "ALL", "search_lang": "ro"}))
    js = json_of(r, "brave")
    if r.status_code != 200 or js.get("type") == "ErrorResponse" or "error" in js:
        raise SearchError(f"brave: HTTP {r.status_code} {str(js.get('error'))[:200]}")
    web = js.get("web")
    if web is None and (js.get("type") == "search" or isinstance(js.get("query"), dict)):
        rows = []  # Brave leaves `web` out when nothing matched
    elif isinstance(web, dict) and isinstance(web.get("results"), list):
        rows = web["results"]
    else:
        raise SearchError(f"brave: no web.results in the response: {str(js)[:120]}")
    tags = lambda t: unescape(re.sub(r"<[^>]+>", "", t or ""))
    return [{"url": o.get("url", ""), "title": tags(o.get("title")), "snippet": tags(o.get("description")),
             "date": o.get("page_age") or o.get("age") or ""} for o in rows]


PROVIDERS = {"serper": serper, "brave": brave}


def first_author(autor: str) -> str:
    """The first of several authors, without a bracketed note: more names would only narrow the search."""
    return re.sub(r"\s*\(.*?\)", "", re.split(r"\s*[/&;]\s*", autor.strip())[0]).strip()


# v2 attribution predicates that name who made the entry. A funder, a parent or a used entry is not its author.
AUTHOR_PREDICATES = ("atribuit_in_sursa", "creat_de", "mentinut_de", "publicat_de")
note_off = lambda name: re.sub(r"\s*\(.*?\)", "", name).strip()


def relation_authors(e: dict) -> list[dict]:
    """The attribution relations of a v2 entry that name an author (see AUTHOR_PREDICATES), in table order."""
    return [a for a in e.get("attributions") or [] if a["predicate"] in AUTHOR_PREDICATES and a["name"]]


def author_name(e: dict) -> str:
    """The author for the queries: the first author. v2: the first relation (a literal, or the name of the target
    entry); without relations, and for v1, the first part of the original `autor` text."""
    rel = relation_authors(e)
    return note_off(rel[0]["name"]) if rel else first_author(e.get("autor", ""))


def author_parts(e: dict) -> list[tuple[str, str]]:
    """(name, key into `orgs`) of each author, for own_sites(). v2 with relations: the key is the target's slug (empty
    for a literal: a similar name is no identity). The original text is the fallback; v1 reads the `autor` cell and
    looks organisations up by their flat name."""
    rel = relation_authors(e)
    if rel:
        return [(note_off(a["name"]), a["slug"]) for a in rel]
    v2 = "attributions" in e
    parts = (note_off(a) for a in re.split(r"\s*[/&;]\s*", e.get("autor", "")))
    return [(a, "" if v2 else flat(a)) for a in parts if a]


def is_rooted(e: dict) -> bool:
    return bool(e["url"]) and urlparse(e["url"]).path.strip("/") == ""


def plan(e: dict, providers: set[str]) -> list[tuple[str, str, int]]:
    """(provider, query, pages). A path-based entry gets name queries only: the domain describes the host, not the entry."""
    dom, nume, autor = domain_of(e["url"]), re.sub(r'["\s]+', " ", e["nume"]).strip(), author_name(e)
    if autor.lower() in nume.lower():  # "gov2 gov2": the author adds nothing
        autor = ""
    out = []
    if is_rooted(e):
        out.append(("serper", f"{dom} -site:{dom}", SERPER_PAGES))
    if not (is_rooted(e) and nume.lower().removeprefix("www.") == dom):  # the domain query covers a name that is the domain
        out.append(("serper", f"{nume} {autor}".strip(), 1))
        out.append(("brave", f'"{nume}" {autor}'.strip(), 1))
    return [q for q in out if q[0] in providers]


def site_key(host: str) -> str:
    """Registered domain, so that the parent site counts as the entry's own; the full host on shared platforms."""
    host = host.removeprefix("www.")
    if SHARED.search(host):
        return host
    parts = host.split(".")
    return ".".join(parts[-3 if len(parts) > 2 and parts[-2] in ("com", "co", "org", "net", "gov", "edu", "ac") else -2:])


def flat(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", x.lower())


def own_sites(e: dict, p: dict, orgs: dict[str, str]) -> set[str]:
    """Sites that are the entry's own channel: its url (and where that redirects), every site in `linkuri`, and the
    sites of its authors (an organisation of the catalogue, a domain used as a name, or AUTOR_SITES). `orgs` maps the
    key of author_parts() to the organisation's URL: v1 the flat name, v2 the slug of an organisation entry."""
    urls = [e["url"], p.get("final_url", ""), *(re.sub(r"^[a-z]+:(?=https?://)", "", t) for t in split_list(e.get("linkuri", "")))]
    for a, key in author_parts(e):
        urls += [orgs.get(key, "") if key else "", a if is_url(a) else "", *AUTOR_SITES.get(a.lower(), [])]
    return {site_key(h) for u in urls if u and (h := urlparse(u if "//" in u else "//" + u).hostname)}


def organisation_urls(entries: dict[str, dict], v2: bool) -> dict[str, str]:
    """The URLs that count as an author's own site, keyed as author_parts() looks them up. v1: the flat name of each
    organisation row. v2: the slug of each entry of type organizatie, and no other target (a project or a resource
    that a relation names is not an organisation)."""
    if v2:
        return {s: e["url"] for s, e in entries.items() if e["entity_type"] == "organizatie" and e["url"]}
    return {flat(e["nume"]): e["url"] for e in entries.values() if e["kind"] == "organizatie" and e["url"]}


def rule_of(row: dict, own: set[str]) -> str:
    for name, rx in RULES:
        if rx.search(row["host"]) or rx.search(row["url"]):
            return name
    return "propriu" if site_key(row["host"]) in own else ""


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def make_rows(slug: str, prov: str, q: str, hits: list[dict], now: str) -> list[dict]:
    rows = []
    for rank, h in enumerate(hits, 1):
        url = h["url"].split("#")[0]
        if not url.startswith("http"):
            continue
        rows.append({"slug": slug, "provider": prov, "query": q, "rank": rank, "url": url, "host": host_of(url),
                     "title": re.sub(r"\s+", " ", h["title"]).strip(), "date": norm_date(h["date"]),
                     "snippet": re.sub(r"\s+", " ", h["snippet"]).strip()[:MAX_SNIPPET],
                     "regula": "", "editor": "", "fetched_at": now})
    return rows


def merge(old: list[dict], new: list[dict], ran: set[str]) -> list[dict]:
    """Rows of the providers that did not run stay; new rows follow, one per URL (the first one wins, and lends
    its date if it has none). A row with an `editor` value survives even when the search no longer returns it."""
    out: dict[str, dict] = {}
    for r in [*(r for r in old if r["provider"] not in ran), *new]:
        if (have := out.get(r["url"])) is None:
            out[r["url"]] = dict(r)
        else:
            have["date"] = have["date"] or r["date"]
            have["snippet"] = have["snippet"] or r["snippet"]
    editor = {r["url"]: r["editor"] for r in old if r["editor"]}
    for u, v in editor.items():
        out.setdefault(u, next(dict(r) for r in old if r["url"] == u))
        out[u]["editor"] = v
    return list(out.values())


def social_profiles(rows: list[dict], e: dict) -> dict:
    """Profiles of the entry on social networks and GitHub that the search turned up. Only handles that carry the
    entry's name count: results also hold posts that merely mention it."""
    label = flat(domain_of(e["url"]).split(".")[0]) if is_rooted(e) else flat(e["nume"])
    out = {}
    for r in rows:
        if r["editor"] == "0":
            continue
        host = r["host"].removeprefix("m.")
        role = SOCIAL_HOSTS.get(host) or ("github" if host == "github.com" else None)
        handle = flat((urlparse(r["url"]).path.strip("/").split("/") or [""])[0].removeprefix("@"))
        if role and len(handle) > 3 and len(label) > 3 and (label in handle or handle in label) and not SHARE.search(r["url"]):
            out.setdefault(role, r["url"].split("?")[0])
    return out


def update_profile(rows: list[dict], entries: dict[str, dict], path: Path):
    """mentions, mention_hosts and search_social in the profile CSV at `path`, from the kept rows of every slug that has rows."""
    profile = load_profile(path)
    for slug in dict.fromkeys(r["slug"] for r in rows):
        if slug not in profile or slug not in entries:
            continue
        mine = [r for r in rows if r["slug"] == slug]
        hosts = list(dict.fromkeys(r["host"] for r in mine if is_kept(r)))
        profile[slug].update(mentions=len(hosts), mention_hosts=" ".join(hosts[:12]), search_social=social_profiles(mine, entries[slug]))
    save_profile(profile, path)


def write_rows(rows: list[dict], path: Path):
    write_csv(path, MENTIUNI_COLS, sorted(rows, key=lambda r: r["slug"]))  # stable: query order stays within a slug


def report(rows: list[dict]):
    kept = [r for r in rows if is_kept(r)]
    by_rule: dict[str, int] = {}
    for r in rows:
        by_rule[r["regula"] or "(none)"] = by_rule.get(r["regula"] or "(none)", 0) + 1
    log(f"rows {len(rows)}  kept {len(kept)}  slugs {len({r['slug'] for r in rows})}  "
        f"by rule {dict(sorted(by_rule.items(), key=lambda kv: -kv[1]))}  editor set {sum(1 for r in rows if r['editor'])}")
    hosts: dict[str, list] = {}
    for r in kept:
        hosts.setdefault(r["host"], []).append(r["slug"])
    log("most frequent kept hosts (rows / entries):")
    for h, s in sorted(hosts.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:20]:
        log(f"  {len(s):4} {len(set(s)):3}  {h}")


async def run(todo: list[dict], plans: dict, old: dict[str, list[dict]], rows: list[dict], profile: dict, orgs: dict[str, str], path: Path):
    failed, sem = [], asyncio.Semaphore(4)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    async def one(client, e):
        slug = e["slug"]
        new = []
        async with sem:
            for prov, q, pages in plans[slug]:
                hits = []
                try:
                    for page in range(1, pages + 1):
                        got = await PROVIDERS[prov](client, q, page)
                        STATS[prov]["ok"] += 1
                        hits += got
                        if len(got) < 10 and prov == "serper":
                            break
                except SearchError as ex:
                    STATS[prov]["errors"] += 1
                    failed.append(slug)
                    log(f"  {prov:6} ERR {slug}: {q!r}: {ex}  (rows of {slug} unchanged)")
                    return
                new += make_rows(slug, prov, q, hits, now)
                log(f"  {prov:6} {len(hits):3} {slug}  {q}")
        mine = merge(old.get(slug, []), new, {p for p, _, _ in plans[slug]})
        own = own_sites(e, profile.get(slug, {}), orgs)
        for r in mine:
            r["regula"] = rule_of(r, own)
        rows[:] = [r for r in rows if r["slug"] != slug] + mine
        write_rows(rows, path)  # after every entry: paid results must survive a crash

    async with httpx.AsyncClient(follow_redirects=True) as client:
        await asyncio.gather(*(one(client, e) for e in todo))
    return failed


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=PUBLIC_ROOT, help="data root (default: the public root, PUBLIC_ROOT in common.py); a v2 root keeps its files in observatii/")
    ap.add_argument("--only", default="", help="comma-separated slugs")
    ap.add_argument("--force", action="store_true", help="query again the slugs that already have rows")
    ap.add_argument("--provider", choices=["serper", "brave", "all"], default="all")
    ap.add_argument("--dry-run", action="store_true", help="print the queries; no requests")
    ap.add_argument("--prune-only", action="store_true", help="apply the rules to the stored rows; no requests")
    args = ap.parse_args()

    root = args.data_dir.resolve()
    obs = observation_paths(root)
    entries = {e["slug"]: e for e in load_catalogue(root)}
    profile = load_profile(obs["profile"])
    rows = load_mentions(obs["mentions"])
    old: dict[str, list[dict]] = {}
    for r in rows:
        old.setdefault(r["slug"], []).append(r)
    orgs = organisation_urls(entries, data_schema(root) == "v2")
    only = {s for s in args.only.split(",") if s}
    if unknown := only - entries.keys():
        sys.exit(f"unknown slugs: {', '.join(sorted(unknown))}")

    if args.prune_only:
        if not rows:
            sys.exit(f"{obs['mentions']} is empty: run search.py first")
        owns = {s: own_sites(entries[s], profile.get(s, {}), orgs) for s in old if s in entries}
        for r in rows:
            r["regula"] = rule_of(r, owns.get(r["slug"], set()))
        write_rows(rows, obs["mentions"])
        update_profile(rows, entries, obs["profile"])
        report(rows)
        return

    providers = {"serper", "brave"} if args.provider == "all" else {args.provider}
    todo = [e for e in entries.values() if (not only or e["slug"] in only) and (args.force or e["slug"] not in old)]
    plans = {e["slug"]: plan(e, providers) for e in todo}
    todo = [e for e in todo if plans[e["slug"]]]
    need = {p: sum(pages if p == "serper" else 1 for pr, _, pages in sum(plans.values(), []) if pr == p) for p in GAP}
    log(f"{len(todo)} entries to query ({len([s for s in (only or entries) if s in old])} skipped: rows exist, use --force)"
        if not args.force else f"{len(todo)} entries to query")
    if args.dry_run:
        for e in todo:
            log(f"{e['slug']:30} {'domain' if is_rooted(e) else 'path  '} " + " | ".join(f"{p}: {q}" for p, q, _ in plans[e['slug']]))
        log(f"at most {need['serper']} Serper and {need['brave']} Brave requests, ≈ ${sum(need[p] * USD[p] for p in GAP):.3f}")
        return
    for p in providers:
        if not os.environ.get(f"{p.upper()}_API_KEY"):
            sys.exit(f"{p.upper()}_API_KEY not set")
    if httpx is None:
        sys.exit("httpx is missing: run this script with `uv run scripts/search.py`")
    LIMIT.update({p: Limiter(g) for p, g in GAP.items()})
    failed = []
    try:
        failed = asyncio.run(run(todo, plans, old, rows, profile, orgs, obs["mentions"]))
    finally:
        if rows:
            update_profile(rows, entries, obs["profile"])
    cost = sum(STATS[p]["credits"] * USD[p] if p == "serper" else STATS[p]["requests"] * USD[p] for p in GAP)
    for p in GAP:
        log(f"{p:6} requests {STATS[p]['requests']}  ok {STATS[p]['ok']}  errors {STATS[p]['errors']}"
            + (f"  credits {STATS[p]['credits']}" if p == "serper" else ""))
    log(f"cost ≈ ${cost:.3f}")
    report(rows)
    if failed:
        log(f"FAILED {len(set(failed))} entries (rows unchanged; run again): {', '.join(sorted(set(failed)))}")
        sys.exit(1)


if __name__ == "__main__":
    main()
