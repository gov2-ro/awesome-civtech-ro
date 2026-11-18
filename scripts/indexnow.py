#!/usr/bin/env python3
"""Tell search engines which pages of civtech.gov2.ro changed in a deploy, through IndexNow (Bing, Yandex, Seznam,
Naver and others share the submissions). Stdlib only. The Pages workflow runs it twice:

    python3 scripts/indexnow.py plan --site-dir site --out $RUNNER_TEMP/indexnow-urls.txt     # before the upload
    python3 scripts/indexnow.py submit --urls $RUNNER_TEMP/indexnow-urls.txt                  # after the deploy

`plan` hashes the page behind each address of site/sitemap.xml and writes site/indexnow.json (address -> hash). It reads
the same file from the live site, the one of the previous deploy, and writes the addresses that are new or changed.
With no earlier file (the first deploy), every address counts as changed. `submit` posts them to the IndexNow API.

The key is the name and the content of site/<key>.txt (hand-made, tracked): the engines fetch it to check that the
submitter controls the host. A failed submission prints a GitHub warning and exits 0: it never fails a deploy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

SITE_URL = "https://civtech.gov2.ro/"
HOST = "civtech.gov2.ro"
ENDPOINT = "https://api.indexnow.org/indexnow"
MANIFEST = "indexnow.json"
MAX_URLS = 10_000  # the protocol's limit per request
KEY_RX = re.compile(r"^[A-Za-z0-9-]{8,128}$")
# Parts of a page that change with no change to what a reader sees: the cache-busting hash on the CSS and JS links.
NOISE = re.compile(rb"\?v=[0-9a-f]+")


def key_file(site: Path) -> Path:
    """The one key file at the root of site/: a name of 8-128 letters, digits or dashes, with the name as its content."""
    found = [p for p in site.glob("*.txt") if KEY_RX.match(p.stem) and p.read_text(encoding="utf-8").strip() == p.stem]
    if len(found) != 1:
        raise SystemExit(f"{site} must hold exactly one IndexNow key file (<key>.txt that contains <key>); found {len(found)}")
    return found[0]


def sitemap_urls(site: Path) -> list[str]:
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ElementTree.parse(site / "sitemap.xml").getroot()
    return [loc.text.strip() for loc in root.findall("s:url/s:loc", ns) if loc.text]


def page_of(url: str, site: Path) -> Path:
    if not url.startswith(SITE_URL):
        raise SystemExit(f"{url} is not on {SITE_URL}")
    return site / url[len(SITE_URL):] / "index.html"


def manifest(site: Path) -> dict[str, str]:
    """Address -> SHA-1 of its page, without the asset hashes (NOISE)."""
    out = {}
    for url in sitemap_urls(site):
        page = page_of(url, site)
        if not page.exists():
            raise SystemExit(f"sitemap.xml names {url}, but the build has no {page}")
        out[url] = hashlib.sha1(NOISE.sub(b"", page.read_bytes())).hexdigest()
    return out


def changed(new: dict[str, str], old: dict[str, str] | None) -> list[str]:
    """The addresses that are new or whose page changed. A removed address is not sent: its page answers 404, and the
    engines drop it when they visit it again."""
    if old is None:
        return list(new)
    return [u for u, h in new.items() if old.get(u) != h]


def fetch_live(url: str, timeout: float = 20) -> dict[str, str] | None:
    """The manifest of the previous deploy, or None when there is none (404) or it cannot be read."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "civtech-indexnow"}), timeout=timeout) as r:
            data = json.load(r)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        print(f"no earlier manifest at {url} ({e}); every address counts as changed")
        return None


def payload(urls: list[str], key: str) -> dict:
    return {"host": HOST, "key": key, "keyLocation": f"{SITE_URL}{key}.txt", "urlList": urls[:MAX_URLS]}


def warn(msg: str) -> None:
    print(f"::warning title=IndexNow::{msg}" if "GITHUB_ACTIONS" in os.environ else f"warning: {msg}")


def plan(site: Path, out: Path, live: str | None) -> list[str]:
    key_file(site)
    new = manifest(site)
    old = fetch_live(live) if live else None
    urls = changed(new, old)
    (site / MANIFEST).write_text(json.dumps(new, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    out.write_text("".join(u + "\n" for u in urls), encoding="utf-8")
    print(f"{len(new)} addresses in the sitemap; {len(urls)} new or changed since the last deploy")
    return urls


def submit(urls: list[str], key: str, endpoint: str = ENDPOINT, timeout: float = 30) -> int:
    if not urls:
        print("nothing to submit")
        return 0
    body = json.dumps(payload(urls, key)).encode()
    req = urllib.request.Request(endpoint, data=body, method="POST", headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            print(f"IndexNow: HTTP {r.status}, {min(len(urls), MAX_URLS)} addresses submitted")
            return r.status
    except urllib.error.HTTPError as e:  # 400 bad request, 403 key not valid, 422 address not on the host, 429 too many
        warn(f"HTTP {e.code} for {len(urls)} addresses: {e.read()[:300].decode(errors='replace')}")
        return e.code
    except (urllib.error.URLError, TimeoutError) as e:
        warn(f"no answer from {endpoint}: {e}")
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="write site/indexnow.json and the list of new or changed addresses")
    p.add_argument("--site-dir", type=Path, default=Path("site"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--live", default=SITE_URL + MANIFEST, help="the manifest of the previous deploy; '' for none")
    s = sub.add_parser("submit", help="post the addresses to the IndexNow API")
    s.add_argument("--urls", type=Path, required=True)
    s.add_argument("--site-dir", type=Path, default=Path("site"))
    s.add_argument("--dry-run", action="store_true", help="print the request; send nothing")
    a = ap.parse_args()
    if a.cmd == "plan":
        plan(a.site_dir, a.out, a.live or None)
        return
    key = key_file(a.site_dir).stem
    urls = [u for u in a.urls.read_text(encoding="utf-8").split() if u]
    if a.dry_run:
        print(json.dumps(payload(urls, key), indent=1)[:2000])
        return
    submit(urls, key)


if __name__ == "__main__":
    sys.exit(main())
