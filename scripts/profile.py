# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "selectolax>=1.0", "pillow>=10", "playwright>=1.48"]
# ///
"""Profile every project URL: liveness, metadata, og:image, icon, screenshot fallback.

    uv run scripts/profile.py                 # profile entries not yet in data/profil.csv
    uv run scripts/profile.py --force         # re-profile everything
    uv run scripts/profile.py --only a,b      # just these slugs
    uv run scripts/profile.py --no-shots      # skip the browser screenshot pass
    uv run scripts/profile.py --extra         # only refresh age, activity and reach signals for every entry
    uv run scripts/profile.py --opr           # Open PageRank (key: OPR_API_KEY)

Writes data/profil.csv and images into site/img/{og,icon}/. Web search lives in scripts/search.py.
"""
import argparse
import asyncio
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageOps
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from common import SHARE, SITE, SOCIAL_HOSTS, domain_of, load_entries, load_profile, save_profile

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "ro,en;q=0.8"}
OG_DIR = SITE / "img" / "og"
ICON_DIR = SITE / "img" / "icon"
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
COOKIE_CSS = """
#onetrust-banner-sdk, #onetrust-consent-sdk, #CybotCookiebotDialog, .cc-window, .cc-banner,
#cookie-law-info-bar, .cky-consent-container, #cmplz-cookiebanner-container, .cookie-notice-container,
#cookie-notice, .fc-consent-root, #usercentrics-root, [id*="cookie-banner" i], [class*="cookie-banner" i],
[id*="cookieconsent" i], [class*="cookieconsent" i], [class*="consent-banner" i], [aria-label*="cookie" i]
{ display: none !important; }
"""


def log(*a):
    print(*a, file=sys.stderr, flush=True)


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
    flat = Image.new("RGB", im.size, (255, 255, 255))
    flat.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
    r, g, b = flat.resize((1, 1), Image.BOX).getpixel((0, 0))
    return {"w": w, "h": h, "color": f"#{r:02x}{g:02x}{b:02x}"}


async def get(client: httpx.AsyncClient, url: str, limit: int):
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
    icons = []
    for link in tree.css("link[rel]"):
        rel = (link.attributes.get("rel") or "").lower()
        if "icon" in rel and link.attributes.get("href"):
            size = re.match(r"(\d+)", link.attributes.get("sizes") or "")
            score = int(size.group(1)) if size else (180 if "apple" in rel else 32)
            icons.append((score, urljoin(base, link.attributes["href"])))
    icons.sort(reverse=True)
    host = urlparse(base).hostname or ""
    # Icon services as a last resort; both answer 404 when they have nothing.
    out["icon_candidates"] = [u for _, u in icons] + [urljoin(base, "/favicon.ico"),
                              f"https://icons.duckduckgo.com/ip3/{host}.ico", f"https://www.google.com/s2/favicons?domain={host}&sz=128"]
    repos, social = [], {}
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if REPO.match(href) and not REPO_SKIP.search(href):
            repos.append(href.rstrip("/"))
        host = (urlparse(href).hostname or "").lower().removeprefix("www.").removeprefix("m.")
        role = SOCIAL_HOSTS.get(host)
        path = urlparse(href).path.strip("/")
        # One profile link per network; skip share buttons and bare network home pages.
        if role and path and not SHARE.search(href) and role not in social:
            social[role] = href.split("#")[0]
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


async def fetch_icon(client, slug: str, candidates: list[str]) -> str:
    for u in candidates:
        try:
            r, body = await get(client, u, 2_000_000)
            if r.status_code >= 400 or not body:
                continue
        except Exception:
            continue
        info = save_image(body, ICON_DIR / slug, 128)
        if info and info["w"] >= 16:
            return f"img/icon/{slug}.webp"
    return ""


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


async def github(client, repo: str) -> dict:
    try:
        r = await client.get(f"https://api.github.com/repos/{repo}", headers=gh_headers(), timeout=20)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


_gh_search_lock = asyncio.Lock()


async def github_find(client, host: str) -> str:
    """A repo whose homepage is the site, for projects that don't link their code.
    The search API allows 30 requests a minute with a token (10 without)."""
    async with _gh_search_lock:
        await asyncio.sleep(2.2 if os.environ.get("GITHUB_TOKEN") else 6.5)
        try:
            r = await client.get("https://api.github.com/search/repositories", headers=gh_headers(), timeout=20,
                                 params={"q": f'"{host}" in:readme,description', "per_page": 30})
            items = r.json().get("items", []) if r.status_code == 200 else []
        except Exception:
            return ""
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
            r = await client.get(urljoin(base, f"/wp-json/wp/v2/{kind}"), timeout=20,
                                 params={"per_page": 1, "orderby": "modified", "_fields": "modified"})
            if r.status_code == 200 and isinstance(js := r.json(), list) and js:
                out = max(out, js[0].get("modified", "")[:10])
        except Exception:
            pass
    return out


async def wiki_refs(client, domain: str) -> int:
    """Wikipedia articles (ro + en) linking to the domain."""
    n = 0
    for lang in ("ro", "en"):
        try:
            r = await client.get(f"https://{lang}.wikipedia.org/w/api.php", timeout=20, params={
                "action": "query", "list": "exturlusage", "euquery": domain, "eulimit": 500,
                "eunamespace": 0, "format": "json", "euprop": "title"})
            n += len({x["title"] for x in r.json().get("query", {}).get("exturlusage", [])})
        except Exception:
            pass
    return n


async def header_lastmod(client, url: str) -> str:
    try:
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
        repos = [m.group(2) for u in [*re.findall(r"https?://\S+", e.get("linkuri", "")), *(p.get("repos") or [])]
                 if (m := GH_REPO.match(u.rstrip(",")))]
        host = (urlparse(e["url"]).hostname or "").lower().removeprefix("www.")
        if not repos and rooted and alive and (found := await github_find(client, host)):
            repos = [found]
            p["repos"] = [f"https://github.com/{found}", *(p.get("repos") or [])]
        if repos and (gh := await github(client, repos[0])):
            cands.append(((gh.get("pushed_at") or "")[:10], "cod"))
            p["repo"], p["stars"], p["forks"] = gh.get("full_name", repos[0]), gh.get("stargazers_count", 0), gh.get("forks_count", 0)
            p["repo_created"], p["repo_archived"] = (gh.get("created_at") or "")[:10], gh.get("archived", False)
        if rooted:
            p["cert_first"] = p.get("cert_first") or await cert_first(client, host)
        if alive:
            linked, html = [], ""
            try:
                r, body = await get(client, url, MAX_HTML)
                html = body.decode(r.encoding or "utf-8", errors="replace")
                tree = HTMLParser(html)
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
            if not p.get("icon"):
                host = urlparse(url).hostname or ""
                p["icon"] = await fetch_icon(client, e["slug"], [
                    urljoin(url, "/apple-touch-icon.png"), urljoin(url, "/favicon.ico"),
                    f"https://icons.duckduckgo.com/ip3/{host}.ico", f"https://www.google.com/s2/favicons?domain={host}&sz=128"])
            wp = await wp_latest(client, url) if rooted and ("wp-content" in html or "wordpress" in (p.get("generator") or "").lower()) else ""
            cands += [(feed_date, "feed"), (wp, "wordpress"), (lastmod, "sitemap"), (await header_lastmod(client, url), "server")]
        else:
            cands.append((p.get("last_capture", ""), "arhiva"))
        p["wiki_refs"] = await wiki_refs(client, domain_of(e["url"]) if rooted else re.sub(r"^https?://(www\.)?", "", e["url"]).rstrip("/"))
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        best = max(((d, s) for d, s in cands if d and d < recent), default=("", ""))
        p["updated"], p["updated_src"] = best
        log(f"  extra    {p.get('first_seen') or '----------'} {best[0] or '----------'} {best[1]:9} "
            f"arch:{p.get('archive_months', 0):<3} pages:{p.get('sitemap_urls', '-')!s:<5} wiki:{p['wiki_refs']} {e['slug']}")


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


async def profile_one(sem, client, insecure, e: dict) -> dict:
    async with sem:
        slug, url = e["slug"], e["url"]
        p = await fetch_page(client, insecure, url)
        c = insecure if p.get("ssl_error") else client
        p["status"] = classify(p)
        if p["status"] in ("activ", "mutat", "blocat"):
            p["image"] = await fetch_image(c, slug, p.pop("image_candidates", []))
            p["icon"] = await fetch_icon(c, slug, p.pop("icon_candidates", []))
        else:
            p.pop("image_candidates", None)
            p.pop("icon_candidates", None)
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
        try:
            browser = await pw.chromium.launch(channel="chrome")
        except Exception:
            browser = await pw.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1200, "height": 630}, user_agent=UA, locale="ro-RO", ignore_https_errors=True,
            bypass_csp=True,
        )
        for slug in slugs:
            p = profile[slug]
            page = await ctx.new_page()
            try:
                resp = await page.goto(p["url"], wait_until="load", timeout=30_000)
                await page.add_style_tag(content=COOKIE_CSS)
                await page.wait_for_timeout(2500)
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
                if p["status"] == "blocat" and "Timeout" not in str(ex):
                    p["status"] = "offline"
                log(f"  shot     ERR {slug}: {str(ex)[:100]}")
            finally:
                await page.close()
        await browser.close()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--extra", action="store_true", help="age, activity and reach signals (free)")
    ap.add_argument("--opr", action="store_true", help="Open PageRank (OPR_API_KEY)")
    args = ap.parse_args()

    OG_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    profile = load_profile()
    entries = [e for e in load_entries() if e["url"]]
    only = {s for s in args.only.split(",") if s}
    if only:
        todo = [e for e in entries if e["slug"] in only]
    else:
        # A changed url counts as never profiled.
        todo = [e for e in entries if args.force or e["slug"] not in profile or profile[e["slug"]].get("url") != e["url"]]
    opts = dict(headers=HEADERS, follow_redirects=True, timeout=httpx.Timeout(20, connect=10), max_redirects=8)
    if args.extra or args.opr:
        todo = [e for e in (todo if only else entries) if e["slug"] in profile]
        async with httpx.AsyncClient(verify=False, **opts) as client:
            if args.extra:
                log(f"extra signals for {len(todo)} entries")
                sem = asyncio.Semaphore(3)
                await asyncio.gather(*(extras_one(sem, client, e, profile[e["slug"]]) for e in todo))
            if args.opr:
                await open_pagerank(client, profile, todo)
        save_profile(profile)
        return
    log(f"profiling {len(todo)} of {len(entries)} entries")

    sem = asyncio.Semaphore(8)
    async with httpx.AsyncClient(**opts) as client, httpx.AsyncClient(verify=False, **opts) as insecure:
        results = await asyncio.gather(*(profile_one(sem, client, insecure, e) for e in todo))
        await asyncio.gather(*(extras_one(sem, insecure, e, p) for e, p in zip(todo, results)))
    for e, p in zip(todo, results):
        profile[e["slug"]] = p

    if not args.no_shots:
        need = [e["slug"] for e in todo if profile[e["slug"]]["status"] == "blocat"
                or (profile[e["slug"]]["status"] in ("activ", "mutat") and not profile[e["slug"]].get("image"))]
        log(f"browser pass for {len(need)} entries")
        if need:
            await screenshots(profile, need)

    save_profile(profile)
    counts = {}
    for p in profile.values():
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    log("status:", counts)


if __name__ == "__main__":
    asyncio.run(main())
