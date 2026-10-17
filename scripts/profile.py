# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "selectolax>=1.0", "pillow>=10", "playwright>=1.48"]
# ///
"""Profile every project URL: liveness, metadata, og:image, icon, screenshot fallback.

    uv run scripts/profile.py                 # profile entries not yet in data/profil.csv
    uv run scripts/profile.py --force         # re-profile everything
    uv run scripts/profile.py --only a,b      # just these slugs
    uv run scripts/profile.py --no-shots      # skip the browser screenshot pass

Writes data/profil.csv and images into site/img/{og,icon}/.
"""
import argparse
import asyncio
import io
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageOps
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from common import DATA, SITE, load_entries, load_profile, save_profile

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
REPO_SKIP = re.compile(r"/(sponsors|features|about|pricing|login|topics|marketplace)(/|$)", re.I)
SOCIAL_HOSTS = {
    h: r["key"]
    for r in json.loads((DATA / "taxonomy.json").read_text())["linkuri"]["roluri"]
    if r["key"] not in ("github", "gitlab")
    for h in r["hosts"]
}
SHARE = re.compile(r"sharer|/share|intent/|shareArticle|/dialog/|/plugins/|/hashtag/|/watch\?|/embed/|/events/|/groups/", re.I)
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
    out["icon_candidates"] = [u for _, u in icons] + [urljoin(base, "/favicon.ico")]
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
    args = ap.parse_args()

    OG_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    profile = load_profile()
    entries = [e for e in load_entries() if e["url"]]
    only = {s for s in args.only.split(",") if s}
    if only:
        todo = [e for e in entries if e["slug"] in only]
    else:
        todo = [e for e in entries if args.force or e["slug"] not in profile]
    log(f"profiling {len(todo)} of {len(entries)} entries")

    sem = asyncio.Semaphore(8)
    opts = dict(headers=HEADERS, follow_redirects=True, timeout=httpx.Timeout(20, connect=10), max_redirects=8)
    async with httpx.AsyncClient(**opts) as client, httpx.AsyncClient(verify=False, **opts) as insecure:
        results = await asyncio.gather(*(profile_one(sem, client, insecure, e) for e in todo))
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
