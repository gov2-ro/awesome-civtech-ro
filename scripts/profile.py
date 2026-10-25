# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "selectolax>=1.0", "pillow>=10", "playwright>=1.48"]
# ///
"""Profile every project URL: liveness, metadata, og:image, icon, screenshot fallback.

    uv run scripts/profile.py                 # profile entries not yet in data/profil.csv
    uv run scripts/profile.py --force         # re-profile everything
    uv run scripts/profile.py --only a,b      # just these slugs
    uv run scripts/profile.py --no-shots      # skip the browser screenshot pass
    uv run scripts/profile.py --extra         # only refresh age, activity, GitHub stats and link favicons for every entry
    uv run scripts/profile.py --opr           # Open PageRank (key: OPR_API_KEY)
    uv run scripts/profile.py --data-dir data/taxonomy-v2/integrare --only a,b   # a v2 root

Writes data/profil.csv and images into site/img/{og,icon,linkicon}/. Web search lives in scripts/search.py.
--data-dir selects the data root (default: the public root, PUBLIC_ROOT in common.py). A v2 root supplies the entries and keeps its profile in its
observatii/profil.csv (an overlay uses its base's). Images stay in site/img/, named by slug.

A refresh never drops what other stages wrote: common.merge_profile keeps mentions, mention_hosts and search_social
(search.py), opr (--opr), and the --extra signals for which the new fetch found nothing (cert_first, wiki_refs, repo
fields...). The merge runs on every path that replaces a row, --force included.

A person can set an entry's image: save it as site/img/og/<slug>.webp, then run the profiler for that slug (--only).
The profiler records it with img_source "manual" and never fetches over it. (An image that the profiler wrote
itself names its source, and is refreshed on --force.)

A host in data/taxonomy-v2/colectare-interzisa.csv is never requested: no page, image, icon, feed, sitemap, screenshot or
browser render, in any mode (--force and --extra included). The run prints one line per entry it skips and leaves the entry's
profile row as it is; it never writes `offline` or an error because of the list. A redirect to a listed host is not followed
(an httpx request hook refuses it; the browser cannot resolve a listed host), and the entry then keeps its row too.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import httpx
    from PIL import Image, ImageOps
    from selectolax.lexbor import LexborHTMLParser as HTMLParser
except ImportError:  # the pure helpers (and the tests) work without them; main() asks for them
    httpx = Image = ImageOps = HTMLParser = None

from common import (load_env, FORBIDDEN_STATE, PUBLIC_ROOT, LINKICON_DIR, NETWORK_ROLES, ROLES, SHARE, SITE, SOCIAL_HOSTS, ForbiddenHost, domain_of,
                    browser_args, forbidden, link_host, link_roles, load_catalogue, load_profile, merge_profile, note_failed_request, observation_paths,
                    parse_link, refuse_forbidden, save_profile, skip_line, split_list)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "ro,en;q=0.8"}
OG_DIR = SITE / "img" / "og"
ICON_DIR = SITE / "img" / "icon"
ICON_WANT = 64  # px: the entry's icon is replaced while it is smaller and a candidate offers more
LINKICON_WANT = 32  # px: link favicons show at 14-16 px
MAX_HTML = 3_000_000
MAX_IMG = 12_000_000
MIN_COVER_W = 400  # narrower og images are treated as missing
PARKED = re.compile(
    r"domain (is|may be) for sale|buy this domain|this domain is parked|domeniul .{0,30}de vânzare|"
    r"parkingcrew|sedoparking|hugedomains|dan\.com|afternic|domain has expired|domeniu expirat|"
    r"you are all set to go|this domain is managed at namebright|is coming soon",
    re.I,
)
REPO = re.compile(r"^https?://(www\.)?(github\.com|gitlab\.com|codeberg\.org)/[\w.-]+(/[\w.-]+)?/?$", re.I)
GH_REPO = re.compile(r"^https?://(www\.)?github\.com/([\w.-]+/[\w.-]+?)(\.git)?/?$", re.I)
REPO_SKIP = re.compile(r"/(sponsors|features|about|pricing|login|topics|marketplace)(/|$)", re.I)
LOGO = re.compile(r"logo", re.I)
COOKIE_CSS = """
#onetrust-banner-sdk, #onetrust-consent-sdk, #CybotCookiebotDialog, .cc-window, .cc-banner,
#cookie-law-info-bar, .cky-consent-container, #cmplz-cookiebanner-container, .cookie-notice-container,
#cookie-notice, .fc-consent-root, #usercentrics-root, [id*="cookie-banner" i], [class*="cookie-banner" i],
[id*="cookieconsent" i], [class*="cookieconsent" i], [class*="consent-banner" i], [aria-label*="cookie" i]
{ display: none !important; }
"""


def log(*a):
    print(*a, file=sys.stderr, flush=True)


async def refuse_listed(request):
    """httpx request hook of every client in this script. httpx calls it before each request, a redirect hop included, so a
    redirect to a listed host (colectare-interzisa.csv) raises ForbiddenHost instead of reaching that host."""
    refuse_forbidden(str(request.url))


async def refuse_route(route, refused: list):
    """Playwright route handler (async API) of the browser pass: abort a request to a listed host, whatever started it.
    The address of an aborted navigation goes to `refused`."""
    request = route.request
    if forbidden(request.url) is None:
        await route.continue_()
        return
    if request.is_navigation_request():
        refused.append(request.url)
    await route.abort()


def without_forbidden(entries: list[dict]) -> list[dict]:
    """The entries that may be requested. A listed entry gets no request in any stage and keeps its profile row as it is;
    one line says so. This is not a profile result: nothing is written for it."""
    kept = []
    for e in entries:
        row = forbidden(e["url"])
        if row is None:
            kept.append(e)
        else:
            log(skip_line(e["slug"], row))
    return kept


def reg_domain(host: str) -> str:
    parts = host.lower().removeprefix("www.").split(".")
    return ".".join(parts[-2:])


def meta(tree: HTMLParser, *names: str) -> str:
    for n in names:
        node = tree.css_first(f'meta[property="{n}"]') or tree.css_first(f'meta[name="{n}"]')
        if node and (v := (node.attributes.get("content") or "").strip()):
            return v
    return ""


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def save_image(data: bytes, dest_stem, max_w: int) -> dict | None:
    """Decode, normalise and store as WebP. Returns dims + dominant colour, or None if unusable."""
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    w, h = im.size
    if w > max_w:
        im = im.resize((max_w, round(h * max_w / w)), Image.LANCZOS)
    im.save(f"{dest_stem}.webp", "WEBP", quality=82, method=5)
    return {"w": w, "h": h, "color": dominant_color(im)}


def dominant_color(im) -> str:
    """The image's average colour on white, as #rrggbb."""
    flat = Image.new("RGB", im.size, (255, 255, 255))
    flat.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
    r, g, b = flat.resize((1, 1), Image.BOX).getpixel((0, 0))
    return f"#{r:02x}{g:02x}{b:02x}"


def manual_image(slug: str, old: dict | None) -> dict | None:
    """An image that a person put in site/img/og/<slug>.webp: a file the profiler did not write. It is the entry's
    image, recorded with source "manual", and no fetch or screenshot replaces it. A file that an earlier run wrote
    (the old profile row names its source) is not manual and is refreshed as usual."""
    f = OG_DIR / f"{slug}.webp"
    if not f.exists():
        return None
    source = ((old or {}).get("image") or {}).get("source_url", "")
    if source and source != "manual":
        return None
    try:
        with Image.open(f) as im:
            im.load()
            w, h = im.size
            color = dominant_color(im if im.mode in ("RGB", "RGBA") else im.convert("RGBA"))
    except Exception:
        return None
    return {"w": w, "h": h, "color": color, "src": f"img/og/{slug}.webp", "kind": "logo" if w / h < 1.3 else "og", "source_url": "manual"}


async def get(client: httpx.AsyncClient, url: str, limit: int):
    refuse_forbidden(url)  # before the request; the client's request hook checks each redirect hop
    async with client.stream("GET", url) as r:
        body = bytearray()
        async for chunk in r.aiter_bytes():
            body += chunk
            if len(body) > limit:
                break
        return r, bytes(body)


async def fetch_page(client, insecure, url: str) -> dict:
    out = {"url": url}
    try:
        try:
            r, body = await get(client, url, MAX_HTML)
        except httpx.ConnectError as e:
            if "CERTIFICATE" not in str(e).upper() and "SSL" not in str(e).upper():
                raise
            out["ssl_error"] = True
            r, body = await get(insecure, url, MAX_HTML)
    except ForbiddenHost as e:  # the address, or a redirect target, is on the list: no profile result, no error
        out["colectare_interzisa"] = e.row
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        return out
    out["http_status"] = r.status_code
    out["final_url"] = str(r.url)
    if "html" not in r.headers.get("content-type", "html"):
        return out
    html = body.decode(r.encoding or "utf-8", errors="replace")
    tree = HTMLParser(html)
    base = str(r.url)
    t = tree.css_first("title")
    out["title"] = clean(t.text()) if t else ""
    out["description"] = clean(meta(tree, "og:description", "description", "twitter:description"))
    out["og_title"] = clean(meta(tree, "og:title", "twitter:title"))
    out["site_name"] = clean(meta(tree, "og:site_name", "application-name"))
    h = tree.css_first("html")
    out["lang"] = (h.attributes.get("lang") or "").strip() if h else ""
    out["parked"] = bool(PARKED.search(html[:200_000]))
    imgs = [meta(tree, n) for n in ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")]
    src = tree.css_first('link[rel="image_src"]')
    imgs.append(src.attributes.get("href", "") if src else "")
    out["image_candidates"] = list(dict.fromkeys(urljoin(base, i) for i in imgs if i))
    host = urlparse(base).hostname or ""
    host_of_page = host.removeprefix("www.")
    repos, social = [], {}
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if REPO.match(href) and not REPO_SKIP.search(href):
            repos.append(href.rstrip("/"))
        host = (urlparse(href).hostname or "").lower().removeprefix("www.").removeprefix("m.")
        role = SOCIAL_HOSTS.get(host)
        path = urlparse(href).path.strip("/")
        # One profile link per network; skip share buttons and bare network home pages.
        # linkedin.com/in/… is a person (a team page), not the project's own profile.
        if role and path and not SHARE.search(href) and role not in social and not (role == "linkedin" and path.startswith("in/")):
            social[role] = href.split("#")[0]
    # On a GitHub page the repo links are GitHub's own chrome (github.com/mcp, /features…); the page is the repo.
    if host_of_page in ("github.com", "gitlab.com"):
        repos = [base.split("?")[0].split("#")[0]]
    out["repos"] = list(dict.fromkeys(repos))[:5]
    out["social"] = social
    return out


async def fetch_image(client, slug: str, candidates: list[str]) -> dict | None:
    for u in candidates:
        if u.startswith("data:"):
            continue
        try:
            r, body = await get(client, u, MAX_IMG)
            if r.status_code >= 400 or not body:
                continue
        except Exception:
            continue
        info = save_image(body, OG_DIR / slug, 1200)
        if not info or info["w"] < MIN_COVER_W:
            continue
        # Squarish images are logos, not covers: the UI centres them instead of cropping.
        kind = "logo" if info["w"] / info["h"] < 1.3 else "og"
        return {**info, "src": f"img/og/{slug}.webp", "kind": kind, "source_url": u}
    return None


def icon_candidates(tree: HTMLParser, base: str) -> list[str]:
    """Icon URLs, best first: the icons the page declares (largest first), logo images in the page header,
    then the usual paths and two icon services (both answer 404 when they have nothing)."""
    icons = []
    for link in tree.css("link[rel]"):
        rel = (link.attributes.get("rel") or "").lower()
        if "icon" in rel and link.attributes.get("href"):
            size = re.match(r"(\d+)", link.attributes.get("sizes") or "")
            score = int(size.group(1)) if size else (180 if "apple" in rel else 32)
            icons.append((score, urljoin(base, link.attributes["href"])))
    icons.sort(reverse=True)
    logos = []
    for img in tree.css("header img, nav img, [role=banner] img, a[rel=home] img"):
        src = (img.attributes.get("src") or "").strip()
        tags = " ".join(img.attributes.get(a) or "" for a in ("class", "id", "alt", "src"))
        if src and not src.startswith("data:") and not src.split("?")[0].lower().endswith(".svg") and LOGO.search(tags):
            logos.append(urljoin(base, src))
    host = urlparse(base).hostname or ""
    return list(dict.fromkeys([u for _, u in icons] + logos[:3] + [
        urljoin(base, "/apple-touch-icon.png"), urljoin(base, "/favicon.ico"), f"https://icons.duckduckgo.com/ip3/{host}.ico",
        f"https://www.google.com/s2/favicons?domain={host}&sz=128"]))


def probe(body: bytes) -> tuple[int, int] | None:
    """Pixel size of an image that decodes, else None (an SVG does not)."""
    try:
        im = Image.open(io.BytesIO(body))
        im.load()
        return im.size
    except Exception:
        return None


def stored_side(path) -> int:
    """Short side of a stored image, 0 when there is none."""
    try:
        with Image.open(path) as im:
            return min(im.size)
    except Exception:
        return 0


async def fetch_icon(client, stem: str, candidates: list[str], dest=ICON_DIR, want=ICON_WANT, max_w=128, beat=0) -> str:
    """Store the first candidate that is roughly square and `want` px wide, else the largest one found, as
    `dest/stem.webp`. Returns the path under site/, or "" when no candidate is larger than `beat` px."""
    best, best_rank = None, beat
    for u in candidates:
        try:
            r, body = await get(client, u, 2_000_000)
            if r.status_code >= 400 or not body:
                continue
        except Exception:
            continue
        size = probe(body)
        if not size or min(size) < 16:
            continue
        # A wide wordmark is a poor icon: it ranks below any square one.
        rank = min(size) if max(size) <= 2 * min(size) else 1
        if rank > best_rank:
            best, best_rank = body, rank
        if best_rank >= want:
            break
    if not best:
        return ""
    save_image(best, dest / stem, max_w)
    return f"img/{dest.name}/{stem}.webp"


async def wayback(client, url: str) -> str:
    try:
        r = await client.get("https://archive.org/wayback/available", params={"url": url}, timeout=20)
        snap = r.json().get("archived_snapshots", {}).get("closest", {})
        return snap.get("url", "") if snap.get("available") else ""
    except Exception:
        return ""


async def archive_months(client, url: str) -> list[str] | None:
    """Months (YYYYMMDD of the first capture in each) with a successful Wayback capture, oldest first.
    The first gives the age; how many there are says how much the web noticed the site."""
    target = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    for attempt in range(4):
        try:
            r = await client.get("https://web.archive.org/cdx/search/cdx", timeout=60, params={
                "url": target, "output": "json", "fl": "timestamp", "filter": "statuscode:200",
                "collapse": "timestamp:6"})
            r.raise_for_status()
            return [row[0][:8] for row in r.json()[1:]]
        except Exception:
            await asyncio.sleep(5 * 2 ** attempt)  # the CDX API rate-limits bursts
    return None  # unknown, as opposed to [] (never archived)


def ymd(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if ts else ""


def gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if tok := os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {tok}"
    return h


GH = {"calls": 0, "left": {}, "stopped": False}  # requests made; rate limit left per API resource; set when GitHub refuses on a rate limit


async def gh_get(client, path: str, **params):
    """GET on the GitHub API. None when the call failed. A rate limit stops every later call: the run reports it,
    and a field the call would have filled stays as it was (a failed call is never a zero)."""
    if GH["stopped"]:
        return None
    try:
        r = await client.get(f"https://api.github.com{path}", headers=gh_headers(), params=params, timeout=20)
    except Exception as ex:
        log(f"  github   ERR {path}: {type(ex).__name__}")
        return None
    GH["calls"] += 1
    left = r.headers.get("x-ratelimit-remaining")
    if left and left.isdigit():
        GH["left"][r.headers.get("x-ratelimit-resource", "core")] = int(left)
    if r.status_code in (403, 429) and (left == "0" or "rate limit" in r.text.lower()):
        GH["stopped"] = True
        log(f"  github   RATE LIMIT at {path} (resets {r.headers.get('x-ratelimit-reset')}); no more GitHub calls in this run")
        return None
    return r


async def github(client, repo: str) -> dict:
    r = await gh_get(client, f"/repos/{repo}")
    if r is None or r.status_code != 200:
        if r is not None:
            log(f"  github   {r.status_code} /repos/{repo}")
        return {}
    return r.json()


async def gh_count(client, path: str, **params) -> int | None:
    """How many items a list endpoint holds, read from the page number of the Link header's rel="last" with
    per_page=1. 1 without a Link header and one item, 0 for an empty list. None when the call failed."""
    r = await gh_get(client, path, per_page=1, **params)
    if r is None:
        return None
    if r.status_code in (204, 409):  # an empty repository answers 409 on commits and 204 on contributors
        return 0
    if r.status_code != 200:
        log(f"  github   {r.status_code} {path}")
        return None
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', r.headers.get("link", ""))
    return int(m.group(1)) if m else len(r.json())


async def github_stats(client, gh: dict) -> dict:
    """Open issues, commits, contributors, last commit, licence and language of a repo (its API object is `gh`).
    A key is missing from the result when its call failed. `open_issues_count` counts pull requests too, so the
    open pull requests are taken off."""
    name = gh["full_name"]
    lic = (gh.get("license") or {}).get("spdx_id") or ""
    out = {"license": "" if lic == "NOASSERTION" else lic, "language": gh.get("language") or ""}
    r = await gh_get(client, f"/repos/{name}/commits", per_page=1)
    if r is not None and r.status_code in (200, 409):
        items = r.json() if r.status_code == 200 else []
        m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', r.headers.get("link", ""))
        out["commits"] = int(m.group(1)) if m else len(items)
        out["last_commit"] = (((items[0].get("commit") or {}).get("committer") or {}).get("date") or "")[:10] if items else ""
    if (n := await gh_count(client, f"/repos/{name}/contributors", anon=1)) is not None:
        out["contributors"] = n
    if gh.get("has_issues", True) and (n := await gh_count(client, f"/repos/{name}/pulls", state="open")) is not None:
        out["open_issues"] = max(0, gh.get("open_issues_count", 0) - n)
    return out


_gh_search_lock = asyncio.Lock()


async def github_find(client, host: str) -> str:
    """A repo whose homepage is the site, for projects that don't link their code.
    The search API allows 30 requests a minute with a token (10 without)."""
    async with _gh_search_lock:
        await asyncio.sleep(2.2 if os.environ.get("GITHUB_TOKEN") else 6.5)
        r = await gh_get(client, "/search/repositories", q=f'"{host}" in:readme,description', per_page=30)
        items = r.json().get("items", []) if r is not None and r.status_code == 200 else []
    # The homepage alone is not enough: an organisation points all its repos at its own site.
    flat = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    label = flat(host.split(".")[0])
    for it in items:
        home = re.sub(r"^https?://(www\.)?", "", (it.get("homepage") or "").lower()).split("/")[0]
        name = flat(it["name"])
        if home == host and (label in name or name in label):
            return it["full_name"]
    return ""


async def cert_first(client, host: str) -> str:
    """Earliest TLS certificate issued for the host (certificate transparency, via crt.sh)."""
    for attempt in range(3):
        try:
            r = await client.get("https://crt.sh/", params={"q": host, "output": "json"}, timeout=120)
            if r.status_code == 200:
                rows = r.json()
                names = lambda x: {n.strip().lower() for n in (x.get("name_value") or "").split("\n")}
                dates = [x["not_before"][:10] for x in rows if host in names(x)]
                return min(dates, default="")
        except Exception:
            pass
        await asyncio.sleep(5 * 2 ** attempt)  # crt.sh is often overloaded
    return ""


async def open_pagerank(client, profile: dict, entries: list[dict]):
    """Open PageRank (0–10, from Common Crawl links), 100 domains per request. Needs OPR_API_KEY."""
    key = os.environ.get("OPR_API_KEY")
    if not key:
        log("OPR_API_KEY not set; skipping Open PageRank")
        return
    by_dom = {}
    for e in entries:
        if urlparse(e["url"]).path.strip("/") == "":
            by_dom.setdefault(domain_of(e["url"]), []).append(e["slug"])
    doms = list(by_dom)
    for i in range(0, len(doms), 100):
        r = await client.get("https://openpagerank.com/api/v1.0/getPageRank", headers={"API-OPR": key},
                             params=[("domains[]", d) for d in doms[i:i + 100]], timeout=30)
        for row in r.json().get("response", []):
            for slug in by_dom.get(row.get("domain"), []):
                profile[slug]["opr"] = row.get("page_rank_decimal") or 0
                log(f"  opr      {profile[slug]['opr']:<5} {slug}")


async def sitemap_info(client, base: str) -> tuple[str, int]:
    """Newest lastmod and number of URLs, following one level of sitemap index (robots.txt first)."""
    roots = []
    try:
        r, body = await get(client, urljoin(base, "/robots.txt"), 200_000)
        if r.status_code == 200:
            roots = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", body.decode("utf-8", "replace"))
    except Exception:
        pass
    roots = roots or [urljoin(base, "/sitemap.xml")]
    mods, urls, todo, seen = [], 0, list(dict.fromkeys(roots))[:3], set()
    while todo and len(seen) < 25:
        u = todo.pop(0)
        seen.add(u)
        try:
            r, body = await get(client, u, 10_000_000)
            if r.status_code != 200:
                continue
            root = ET.fromstring(body)
        except Exception:
            continue
        for el in root.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "lastmod" and el.text and re.match(r"\d{4}-\d\d-\d\d", el.text.strip()):
                mods.append(el.text.strip()[:10])
            elif tag == "loc" and el.text:
                if root.tag.endswith("sitemapindex"):
                    if el.text.strip() not in seen:
                        todo.append(el.text.strip())
                else:
                    urls += 1
    return max(mods, default=""), urls


FEED_PATHS = ["/feed/", "/rss.xml", "/feed.xml", "/atom.xml", "/rss/", "/index.xml"]
FEED_DATE = re.compile(r"<(?:pubDate|published|updated|dc:date)>\s*([^<]+?)\s*<", re.I)


def parse_date(s: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M %z"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.match(r"(\d{4}-\d\d-\d\d)", s.strip())
    return m.group(1) if m else ""


async def feed_latest(client, base: str, linked: list[str]) -> tuple[str, str]:
    """(feed URL, newest item date) from a linked feed or the usual paths."""
    for u in [*linked, *(urljoin(base, p) for p in FEED_PATHS)][:8]:
        try:
            r, body = await get(client, u, 3_000_000)
            text = body.decode("utf-8", "replace")
            if r.status_code != 200 or not re.search(r"<(rss|feed|rdf:RDF)\b", text[:3000]):
                continue
            dates = [d for d in (parse_date(x) for x in FEED_DATE.findall(text)) if d]
            return str(r.url), max(dates, default="")
        except Exception:
            continue
    return "", ""


async def wp_latest(client, base: str) -> str:
    """Newest post or page date from the WordPress REST API."""
    out = ""
    for kind in ("posts", "pages"):
        try:
            refuse_forbidden(base)
            r = await client.get(urljoin(base, f"/wp-json/wp/v2/{kind}"), timeout=20,
                                 params={"per_page": 1, "orderby": "modified", "_fields": "modified"})
            if r.status_code == 200 and isinstance(js := r.json(), list) and js:
                out = max(out, js[0].get("modified", "")[:10])
        except Exception:
            pass
    return out


async def wiki_refs(client, domain: str) -> int | None:
    """Wikipedia articles (ro + en) linking to the domain. None when a call failed: the count is unknown, not 0."""
    n = 0
    for lang in ("ro", "en"):
        try:
            r = await client.get(f"https://{lang}.wikipedia.org/w/api.php", timeout=20, params={
                "action": "query", "list": "exturlusage", "euquery": domain, "eulimit": 500,
                "eunamespace": 0, "format": "json", "euprop": "title"})
            js = r.json()
            if not isinstance(js, dict) or "query" not in js:  # an error object or a rate-limit page
                return None
            n += len({x["title"] for x in js["query"].get("exturlusage", [])})
        except Exception:
            return None
    return n


async def header_lastmod(client, url: str) -> str:
    try:
        refuse_forbidden(url)
        r = await client.head(url, timeout=15)
        lm = r.headers.get("last-modified")
        return datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT").strftime("%Y-%m-%d") if lm else ""
    except Exception:
        return ""


COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–—]\s*)?((?:19|20)\d\d)", re.I)


async def extras_one(sem, client, e: dict, p: dict):
    """Signals for age, activity and reach. Last update is the newest of: repo push, feed item,
    WordPress edit, sitemap lastmod, Last-Modified. Dates of today or later are what dynamic
    pages report for themselves, not real edits."""
    async with sem:
        url = p.get("final_url") or e["url"]
        alive = p.get("status") in ("activ", "mutat", "blocat")
        # A project on a subpage of a bigger site: the host's sitemap, feed and links are not its own.
        rooted = urlparse(e["url"]).path.strip("/") == ""
        months = await archive_months(client, e["url"])
        if months is not None:
            p["first_seen"], p["last_capture"] = ymd(months[0]) if months else "", ymd(months[-1]) if months else ""
            p["archive_months"] = len(months)
        cands = []
        repos = [m.group(2) for u in [e["url"], *re.findall(r"https?://\S+", e.get("linkuri", "")), *(p.get("repos") or [])]
                 if (m := GH_REPO.match(u.rstrip(",")))]
        host = (urlparse(e["url"]).hostname or "").lower().removeprefix("www.")
        if not repos and rooted and alive and (found := await github_find(client, host)):
            repos = [found]
            p["repos"] = [f"https://github.com/{found}", *(p.get("repos") or [])]
        if repos and (gh := await github(client, repos[0])):
            cands.append(((gh.get("pushed_at") or "")[:10], "cod"))
            p["repo"], p["stars"], p["forks"] = gh.get("full_name", repos[0]), gh.get("stargazers_count", 0), gh.get("forks_count", 0)
            p["repo_created"], p["repo_archived"] = (gh.get("created_at") or "")[:10], gh.get("archived", False)
            p.update(await github_stats(client, gh))
        if rooted:
            p["cert_first"] = p.get("cert_first") or await cert_first(client, host)
        if alive:
            linked, html, icons = [], "", []
            try:
                r, body = await get(client, url, MAX_HTML)
                html = body.decode(r.encoding or "utf-8", errors="replace")
                tree = HTMLParser(html)
                icons = icon_candidates(tree, str(r.url))
                linked = [urljoin(str(r.url), l.attributes["href"]) for l in tree.css('link[rel="alternate"][href]')
                          if re.search(r"rss|atom", l.attributes.get("type") or "")]
                gen = tree.css_first('meta[name="generator"]')
                p["generator"] = clean(gen.attributes.get("content") or "")[:60] if gen else ""
                body_el = tree.body
                p["words"] = len((body_el.text(separator=" ") if body_el else "").split())
            except Exception:
                pass
            years = [int(y) for y in COPYRIGHT.findall(html)]
            p["copyright_year"] = max(years) if years else ""
            p["feed"], feed_date = await feed_latest(client, url, linked) if rooted else ("", "")
            lastmod, p["sitemap_urls"] = await sitemap_info(client, url) if rooted else ("", "")
            # An icon under ICON_WANT px gives way to a larger one, when the page or an icon service offers it.
            have = stored_side(SITE / p["icon"]) if p.get("icon") else 0
            if have < ICON_WANT and (new := await fetch_icon(client, e["slug"], icons or icon_candidates(HTMLParser(""), url), beat=have)):
                log(f"  icon     {have or '-'} -> {stored_side(SITE / new)} px {e['slug']}")
                p["icon"] = new
            wp = await wp_latest(client, url) if rooted and ("wp-content" in html or "wordpress" in (p.get("generator") or "").lower()) else ""
            cands += [(feed_date, "feed"), (wp, "wordpress"), (lastmod, "sitemap"), (await header_lastmod(client, url), "server")]
        else:
            cands.append((p.get("last_capture", ""), "arhiva"))
        refs = await wiki_refs(client, domain_of(e["url"]) if rooted else re.sub(r"^https?://(www\.)?", "", e["url"]).rstrip("/"))
        if refs is not None:  # a failed call leaves the stored count as it was
            p["wiki_refs"] = refs
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        best = max(((d, s) for d, s in cands if d and d < recent), default=("", ""))
        p["updated"], p["updated_src"] = best
        log(f"  extra    {p.get('first_seen') or '----------'} {best[0] or '----------'} {best[1]:9} "
            f"arch:{p.get('archive_months', 0):<3} pages:{p.get('sitemap_urls', '-')!s:<5} wiki:{p.get('wiki_refs', '-')} {e['slug']}")


async def link_icon_one(sem, client, host: str, url: str) -> bool:
    """Favicon of one host, from its home page, into site/img/linkicon/<host>.webp."""
    async with sem:
        home = urlparse(url)._replace(path="/", params="", query="", fragment="").geturl()
        try:
            r, body = await get(client, home, MAX_HTML)
            tree = HTMLParser(body.decode(r.encoding or "utf-8", errors="replace"))
            cands = icon_candidates(tree, str(r.url))
        except Exception:
            cands = icon_candidates(HTMLParser(""), home)
        ok = bool(await fetch_icon(client, host, cands, dest=LINKICON_DIR, want=LINKICON_WANT, max_w=32))
        log(f"  linkicon {'ok ' if ok else 'ERR'} {host}")
        return ok


async def link_icons(client, entries: list[dict], profile: dict, force: bool, roles: list[dict] = ROLES):
    """Favicons for the links that show no network logo: the hosts in `linkuri` and in the social links the
    profiler found, once per host (an existing file is kept unless `force`)."""
    hosts, listed = {}, set()
    for e in entries:
        links = [parse_link(t, roles) for t in split_list(e.get("linkuri", ""))]
        links += list((profile.get(e["slug"], {}).get("social") or {}).items())
        for role, url in links:
            if role not in NETWORK_ROLES and (h := link_host(url)):
                if forbidden(url):  # the home page and the icon of a listed host are not requested
                    listed.add(h)
                    continue
                hosts.setdefault(h, url)
    todo = {h: u for h, u in hosts.items() if force or not (LINKICON_DIR / f"{h}.webp").exists()}
    log(f"link favicons: {len(hosts)} hosts, {len(hosts) - len(todo)} stored already, {len(todo)} to fetch"
        + (f"; {FORBIDDEN_STATE}, not requested: {', '.join(sorted(listed))}" if listed else ""))
    sem = asyncio.Semaphore(6)
    done = await asyncio.gather(*(link_icon_one(sem, client, h, u) for h, u in todo.items()))
    log(f"link favicons: {sum(done)} fetched, {len(done) - sum(done)} failed")


def classify(p: dict) -> str:
    if p.get("error"):
        # A timeout is inconclusive (slow host, geo-blocking); the browser pass decides.
        return "blocat" if "Timeout" in p["error"] else "offline"
    st = p.get("http_status", 0)
    if st in (401, 403, 429, 503):
        return "blocat"  # bot protection; the browser pass decides
    if st >= 400:
        return "offline"
    if p.get("parked"):
        return "parcat"
    if urlparse(p["url"]).path.strip("/") and p.get("final_url") and not urlparse(p["final_url"]).path.strip("/"):
        return "offline"  # a project subpage that now redirects to the host's homepage is gone
    if p.get("final_url") and reg_domain(urlparse(p["final_url"]).hostname or "") != reg_domain(
        urlparse(p["url"]).hostname or ""
    ):
        return "mutat"
    return "activ"


async def profile_one(sem, client, insecure, e: dict, old: dict | None = None) -> dict | None:
    """The profile of one entry, or None when the address (or a redirect target) is on the list of forbidden hosts:
    then no request reached the host, and the caller leaves the stored row as it is."""
    async with sem:
        slug, url = e["slug"], e["url"]
        p = await fetch_page(client, insecure, url)
        if p.get("colectare_interzisa"):
            log(skip_line(slug, p["colectare_interzisa"]))
            return None
        c = insecure if p.get("ssl_error") else client
        p["status"] = classify(p)
        candidates = p.pop("image_candidates", [])
        if manual := manual_image(slug, old):
            p["image"] = manual
        elif p["status"] in ("activ", "mutat", "blocat"):
            p["image"] = await fetch_image(c, slug, candidates)
        if p["status"] in ("offline", "parcat"):
            p["wayback"] = await wayback(client, url)
        p["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        img = (p.get("image") or {}).get("kind", "-")
        log(f"  {p['status']:8} {p.get('http_status', '---')} img:{img:5} {slug}  {p.get('error', '')}")
        return p


async def screenshots(profile: dict, slugs: list[str]):
    """Browser pass: confirm 'blocat' sites and capture a cover where there is no og image."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        # The browser cannot resolve a listed host, so a redirect hop that no route handler sees fails inside the browser.
        launch_args = browser_args()
        try:
            browser = await pw.chromium.launch(channel="chrome", args=launch_args)
        except Exception:
            browser = await pw.chromium.launch(args=launch_args)
        ctx = await browser.new_context(
            viewport={"width": 1200, "height": 630}, user_agent=UA, locale="ro-RO", ignore_https_errors=True,
            bypass_csp=True,
        )
        refused: list[str] = []  # navigations to a listed host that failed in the browser, for the page being shot

        async def guard(route):
            await refuse_route(route, refused)

        await ctx.route("**/*", guard)  # a navigation, a link or a script that leads to a listed host is aborted
        ctx.on("requestfailed", lambda request: note_failed_request(request, refused))  # ... and so is a redirect hop (unresolvable)
        for slug in slugs:
            p = profile[slug]
            if (row := forbidden(p["url"])) is not None:
                log(skip_line(slug, row))
                continue
            refused.clear()
            page = await ctx.new_page()
            try:
                resp = await page.goto(p["url"], wait_until="load", timeout=30_000)
                await page.add_style_tag(content=COOKIE_CSS)
                await page.wait_for_timeout(2500)
                if refused:  # the page led to a listed host: no status change, no cover, no error
                    log(skip_line(slug, forbidden(refused[0])))
                    continue
                status = resp.status if resp else 0
                if p["status"] == "blocat":
                    # 401/403/429/503 in a real browser too: bot wall, still unknown.
                    p["status"] = "activ" if status < 400 else "blocat" if status in (401, 403, 429, 503) else "offline"
                    p["title"] = p.get("title") or clean(await page.title())
                if p["status"] in ("activ", "mutat") and not p.get("image"):
                    png = await page.screenshot(type="png")
                    info = save_image(png, OG_DIR / slug, 1200)
                    p["image"] = {**info, "src": f"img/og/{slug}.webp", "kind": "screenshot", "source_url": p["url"]}
                log(f"  shot     {status} {slug}")
            except Exception as ex:
                if refused:  # the browser refused a navigation to a listed host: that is not an error of the site
                    log(skip_line(slug, forbidden(refused[0])))
                    continue
                if p["status"] == "blocat" and "Timeout" not in str(ex):
                    p["status"] = "offline"
                log(f"  shot     ERR {slug}: {str(ex)[:100]}")
            finally:
                await page.close()
        await browser.close()


def github_report():
    log(f"github: {GH['calls']} requests, rate limit left {GH['left']}")
    if GH["stopped"]:
        sys.exit("GitHub refused on a rate limit: the stats of the entries after that call are not updated. Run it again later.")


def need_libraries():
    if httpx is None or Image is None or HTMLParser is None:
        sys.exit("httpx, pillow and selectolax are missing: run this script with `uv run scripts/profile.py`")


async def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=PUBLIC_ROOT, help="data root (default: the public root, PUBLIC_ROOT in common.py); a v2 root keeps its profile in observatii/")
    ap.add_argument("--force", action="store_true", help="re-profile everything; with --extra, fetch the link favicons again")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--extra", action="store_true", help="age, activity and reach signals (free)")
    ap.add_argument("--opr", action="store_true", help="Open PageRank (OPR_API_KEY)")
    args = ap.parse_args()
    need_libraries()

    root = args.data_dir.resolve()
    path = observation_paths(root)["profile"]
    roles = link_roles(root)
    OG_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    LINKICON_DIR.mkdir(parents=True, exist_ok=True)
    profile = load_profile(path)
    entries = [e for e in load_catalogue(root) if e["url"]]
    only = {s for s in args.only.split(",") if s}
    if only:
        todo = [e for e in entries if e["slug"] in only]
    else:
        # A changed url counts as never profiled.
        todo = [e for e in entries if args.force or e["slug"] not in profile or profile[e["slug"]].get("url") != e["url"]]
    # The request hook refuses a redirect hop to a listed host; the entries on the list never reach a client (without_forbidden).
    opts = dict(headers=HEADERS, follow_redirects=True, timeout=httpx.Timeout(20, connect=10), max_redirects=8,
                event_hooks={"request": [refuse_listed]})
    if args.extra or args.opr:
        todo = without_forbidden([e for e in (todo if only else entries) if e["slug"] in profile])
        before = {e["slug"]: dict(profile[e["slug"]]) for e in todo}
        async with httpx.AsyncClient(verify=False, **opts) as client:
            if args.extra:
                log(f"extra signals for {len(todo)} entries")
                sem = asyncio.Semaphore(3)
                await asyncio.gather(*(extras_one(sem, client, e, profile[e["slug"]]) for e in todo))
                await link_icons(client, todo, profile, args.force, roles)
            if args.opr:
                await open_pagerank(client, profile, todo)
        for slug, old in before.items():  # a call that failed in this run leaves the stored value
            profile[slug] = merge_profile(old, profile[slug])
        save_profile(profile, path)
        github_report()
        return
    todo = without_forbidden(todo)
    log(f"profiling {len(todo)} of {len(entries)} entries")

    sem = asyncio.Semaphore(8)
    async with httpx.AsyncClient(**opts) as client, httpx.AsyncClient(verify=False, **opts) as insecure:
        results = await asyncio.gather(*(profile_one(sem, client, insecure, e, profile.get(e["slug"])) for e in todo))
        # None: a redirect led to a listed host. That entry keeps its stored row and gets no further request.
        done = [(e, p) for e, p in zip(todo, results) if p is not None]
        todo = [e for e, _ in done]
        await asyncio.gather(*(extras_one(sem, insecure, e, p) for e, p in done))
        for e, p in done:
            profile[e["slug"]] = merge_profile(profile.get(e["slug"]), p)
        await link_icons(insecure, todo, profile, args.force, roles)

    if not args.no_shots:
        need = [e["slug"] for e in todo if profile[e["slug"]]["status"] == "blocat"
                or (profile[e["slug"]]["status"] in ("activ", "mutat") and not profile[e["slug"]].get("image"))]
        log(f"browser pass for {len(need)} entries")
        if need:
            await screenshots(profile, need)

    save_profile(profile, path)
    counts = {}
    for p in profile.values():
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    log("status:", counts)
    github_report()


if __name__ == "__main__":
    asyncio.run(main())
