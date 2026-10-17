# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic>=0.70", "httpx>=0.27", "selectolax>=1.0", "playwright>=1.48"]
# ///
"""Ask Claude Haiku to review each entry against its live homepage and suggest corrections.

    uv run scripts/review.py --only factual,465   # a few entries
    uv run scripts/review.py --limit 10           # the first 10 not reviewed yet
    uv run scripts/review.py                      # everything not reviewed yet (--force: all again)

Needs ANTHROPIC_API_KEY. Nothing is written to proiecte.csv: suggestions land in data/review/
(raw.jsonl, one answer per entry, and sugestii.csv, one row per changed field) for a person to
accept or reject. A full run is ~110 requests of ~6k tokens, a few US cents on Haiku.
"""
import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import anthropic
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from common import DATA, domain_of, load_entries, load_profile, split_list, split_tip

MODEL = "claude-haiku-5-5"
OUT = DATA / "review"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MAX_TEXT = 12_000  # characters of homepage text sent per entry
PRICE = {"in": 0.10, "out": 0.50, "cache_read": 0.01}  # USD per million tokens, Haiku 5.5

TAX = json.loads((DATA / "taxonomy.json").read_text())
ROLES = list(dict.fromkeys([r["key"] for r in TAX["linkuri"]["roluri"]] + ["web"]))

SYSTEM = """You review entries in CivTech România, a public directory of Romanian civic-tech projects, \
open-data tools, good-governance initiatives and the organisations behind them. For each entry you get \
the current catalogue row, what an automated profiler recorded about the site, and the text and outgoing \
links of the project's homepage as fetched today.

Your answer goes to a human editor who accepts or rejects each field; nothing you write is published \
unchecked. That shapes how you work:

- Base every statement on the material provided. When the homepage does not say something (who made it, \
which city, what data it uses), keep the current value, or leave the field empty if there is none. A \
guess costs the editor more time than a gap.
- Keep what is already right. If a current field is accurate, return it unchanged; rewording a good \
description only creates review work. Change what is wrong, missing, outdated or clearly improvable, and \
list each change with its reason in `probleme`.
- Write in Romanian with diacritics (ș, ț, ă, â, î), plainly and factually, without marketing adjectives \
or the project's own slogans. `descriere_scurta`: one line under 90 characters saying what the thing \
does. `descriere`: two or three sentences on what it does, for whom, and from which data or sources.
- `linkuri`: the project's own presence elsewhere: its social profiles, code repositories, donation, \
contact or data/API pages, picked from the outgoing links you are given (or already in the row and still \
plausible). Leave out share buttons, the platform's generic pages, the web agency that built the site, \
funders' logos and unrelated organisations. A link to the author's or parent organisation's profile \
counts only when the project has none of its own; say so in `evidence`. Never invent a URL.
- `stare`: `activ` if the site works and shows recent upkeep; `abandonat` if it loads but is visibly \
frozen (stale dates, a past election or campaign, "proiect încheiat", empty or broken data); `offline` if \
the address no longer serves this project (error, parked domain, redirect to something else); `incert` \
when you cannot tell. Use the profiler's dates as well as the page.
- `civictech`: true when made by civil society, volunteers, journalists, researchers or independent \
developers for public benefit; false for official government portals and commercial products.
- `domeniu`: the single best-fitting theme. `tip`: one or more types, the main one first.
- `cuvinte`: 2 to 6 keywords, taken from the existing vocabulary whenever one fits; lowercase, words \
joined with hyphens. Put any keyword not in the vocabulary in `cuvinte_noi` too, so the editor sees it.
- For an organisation (`kind: organizatie`) `tip` and `civictech` matter less; describe what the \
organisation does.

The taxonomy and the existing keyword vocabulary follow."""


def taxonomy_block(entries: list[dict]) -> str:
    vocab = {}
    for e in entries:
        for k in e.get("cuvinte", "").split(","):
            k = re.sub(r"\s+", "-", k.strip().lower())
            if k:
                vocab[k] = vocab.get(k, 0) + 1
    return json.dumps({
        "domenii": [{k: d[k] for k in ("key", "label", "hint")} for d in TAX["domenii"]],
        "tipuri": [{k: t[k] for k in ("key", "label")} for t in TAX["tipuri"]],
        "acoperire": [a["key"] for a in TAX["acoperire"]],
        "roluri_linkuri": [{"key": r["key"], "hosts": r.get("hosts", [])} for r in TAX["linkuri"]["roluri"]],
        "vocabular_cuvinte": dict(sorted(vocab.items(), key=lambda kv: -kv[1])),
    }, ensure_ascii=False, indent=1)


def schema() -> dict:
    s = lambda **kw: {"type": "string", **kw}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["stare", "stare_motiv", "civictech", "civictech_motiv", "descriere_scurta", "descriere",
                     "domeniu", "tip", "cuvinte", "cuvinte_noi", "acoperire", "oras", "autor", "linkuri",
                     "probleme", "incredere"],
        "properties": {
            "stare": s(enum=["activ", "abandonat", "offline", "incert"]),
            "stare_motiv": s(),
            "civictech": {"type": "boolean"},
            "civictech_motiv": s(),
            "descriere_scurta": s(),
            "descriere": s(),
            "domeniu": s(enum=[d["key"] for d in TAX["domenii"]]),
            "tip": {"type": "array", "items": s(enum=[t["key"] for t in TAX["tipuri"]])},
            "cuvinte": {"type": "array", "items": s()},
            "cuvinte_noi": {"type": "array", "items": s()},
            "acoperire": s(enum=[a["key"] for a in TAX["acoperire"]]),
            "oras": s(),
            "autor": s(),
            "linkuri": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["role", "url", "evidence"],
                "properties": {"role": s(enum=ROLES), "url": s(), "evidence": s()}}},
            "probleme": {"type": "array", "items": s()},
            "incredere": s(enum=["mare", "medie", "mica"]),
        },
    }


class Page:
    def __init__(self, url: str, html: str, status: int):
        self.url, self.text, self.status_code = url, html, status


def fetch(url: str) -> Page:
    r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "ro,en;q=0.8"}, follow_redirects=True,
                  timeout=25, verify=False)
    return Page(str(r.url), r.text, r.status_code)


_browser = None


def render(url: str) -> Page:
    """For pages built in the browser: the DOM after scripts ran."""
    global _browser
    if _browser is None:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        try:
            _browser = pw.chromium.launch(channel="chrome")
        except Exception:
            _browser = pw.chromium.launch()
    page = _browser.new_page(user_agent=UA, locale="ro-RO", ignore_https_errors=True)
    try:
        resp = page.goto(url, wait_until="load", timeout=30_000)
        page.wait_for_timeout(2000)
        return Page(page.url, page.content(), resp.status if resp else 0)
    finally:
        page.close()


def parse(r) -> tuple[str, dict, dict]:
    """Visible text, links to other hosts, and same-site pages that often hold credits or social links."""
    tree = HTMLParser(r.text)
    for n in tree.css("script, style, noscript, svg, template"):
        n.decompose()
    text = re.sub(r"\s+", " ", tree.body.text(separator=" ") if tree.body else "").strip()
    host = (urlparse(r.url).hostname or "").removeprefix("www.")
    ext, own = {}, {}
    for a in tree.css("a[href]"):
        href = urljoin(r.url, a.attributes.get("href") or "").split("#")[0]
        if not href.startswith("http"):
            continue
        label = re.sub(r"\s+", " ", a.text() or a.attributes.get("aria-label") or a.attributes.get("title") or "")[:60]
        h = (urlparse(href).hostname or "").removeprefix("www.")
        if h and not h.endswith(host):
            ext.setdefault(href, label)
        elif re.search(r"despre|about|echip|team|contact|credit|parteneri|cine-suntem", href, re.I):
            own.setdefault(href, label)
    return text, ext, own


def homepage(url: str) -> dict:
    try:
        r = fetch(url)
    except Exception as ex:
        return {"eroare": f"{type(ex).__name__}: {str(ex)[:160]}"}
    text, ext, own = parse(r)
    if len(text) < 400:  # probably rendered by JavaScript
        try:
            r = render(url)
            text, ext, own = parse(r)
        except Exception:
            pass
    # The about/contact pages often name the authors and link the profiles the homepage leaves out.
    for u in list(own)[:2]:
        try:
            t, e2, _ = parse(fetch(u))
        except Exception:
            continue
        text += f" \n[{u}] " + t[:3000]
        for k, v in e2.items():
            ext.setdefault(k, v)
    return {
        "http_status": r.status_code, "url_final": r.url,
        "text": text[:MAX_TEXT] + (" […]" if len(text) > MAX_TEXT else ""),
        "linkuri_externe": [{"url": u, "text": t.strip()} for u, t in list(ext.items())[:150]],
        "pagini_interne": list(own)[:15],
    }


def entry_message(e: dict, p: dict) -> str:
    row = {k: e.get(k, "") for k in ("slug", "kind", "nume", "descriere_scurta", "descriere", "url", "linkuri",
                                        "domeniu", "tip", "cuvinte", "acoperire", "oras", "autor", "civictech", "stare")}
    prof = {k: p.get(k) for k in ("status", "final_url", "http_status", "title", "og_title", "description", "social",
                                   "repos", "first_seen", "updated", "updated_src", "copyright_year", "feed",
                                   "sitemap_urls", "repo_archived", "mention_hosts", "search_social") if p.get(k) not in (None, "", [], {})}
    page = homepage(e["url"]) if e["url"] else {"eroare": "fără url"}
    return json.dumps({"rand_actual": row, "profil_automat": prof, "pagina": page}, ensure_ascii=False, indent=1)


def review(client: anthropic.Anthropic, system: list, e: dict, user: str) -> dict:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema()}},
        messages=[{"role": "user", "content": user}],
    )
    u = msg.usage
    cost = ((u.input_tokens + (u.cache_creation_input_tokens or 0)) * PRICE["in"]
            + (u.cache_read_input_tokens or 0) * PRICE["cache_read"] + u.output_tokens * PRICE["out"]) / 1e6
    if msg.stop_reason == "refusal":
        return {"slug": e["slug"], "eroare": "refusal", "cost": cost}
    if msg.stop_reason == "max_tokens":
        return {"slug": e["slug"], "eroare": "max_tokens", "cost": cost}
    text = next(b.text for b in msg.content if b.type == "text")
    return {"slug": e["slug"], "model": MODEL, "cost": cost, "cache_read": u.cache_read_input_tokens or 0,
            "review": json.loads(text)}


def norm_list(cell: str) -> list[str]:
    return [re.sub(r"\s+", "-", k.strip().lower()) for k in cell.split(",") if k.strip()]


def diff_rows(e: dict, r: dict) -> list[dict]:
    """One row per field where the suggestion differs from the catalogue."""
    out = []
    add = lambda field, cur, new, why="": out.append(
        {"slug": e["slug"], "camp": field, "actual": cur, "propus": new, "motiv": why, "incredere": r["incredere"]})
    stare_now = e.get("stare") or "activ"
    if r["stare"] in ("abandonat", "offline") and stare_now not in ("arhivat", "offline"):
        add("stare", e.get("stare", ""), "arhivat" if r["stare"] == "abandonat" else "offline", r["stare_motiv"])
    for f in ("descriere_scurta", "descriere", "domeniu", "acoperire", "oras", "autor"):
        if r[f].strip() and r[f].strip() != e.get(f, "").strip():
            add(f, e.get(f, ""), r[f])
    if e["kind"] != "organizatie":
        if r["tip"] and r["tip"] != split_tip(e.get("tip", "")):
            add("tip", e.get("tip", ""), ", ".join(r["tip"]))
        if r["civictech"] != (e.get("civictech") == "1"):
            add("civictech", e.get("civictech", ""), "1" if r["civictech"] else "0", r["civictech_motiv"])
    if set(r["cuvinte"]) != set(norm_list(e.get("cuvinte", ""))):
        add("cuvinte", e.get("cuvinte", ""), ", ".join(r["cuvinte"]),
            ("noi: " + ", ".join(r["cuvinte_noi"])) if r["cuvinte_noi"] else "")
    have = {re.sub(r"^https?://(www\.)?", "", u.split(":", 1)[1] if re.match(r"^[a-z]+:https?://", u) else u).rstrip("/").lower()
            for u in split_list(e.get("linkuri", ""))} | {domain_of(e["url"])}
    for l in r["linkuri"]:
        key = re.sub(r"^https?://(www\.)?", "", l["url"]).rstrip("/").lower()
        if key not in have and l["role"] != "web":
            add("linkuri", "", f"{l['role']}:{l['url']}", l["evidence"])
    if out and r["probleme"]:
        out[0]["motiv"] = "; ".join(filter(None, [out[0]["motiv"], *r["probleme"]]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true", help="print the request for the first entry; no API call")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    raw_path = OUT / "raw.jsonl"
    done = {}
    if raw_path.exists():
        for line in raw_path.read_text().splitlines():
            r = json.loads(line)
            if "review" in r:
                done[r["slug"]] = r
    entries = load_entries()
    profile = load_profile()
    only = {s for s in args.only.split(",") if s}
    todo = [e for e in entries if (e["slug"] in only if only else args.force or e["slug"] not in done)]
    if args.limit:
        todo = todo[:args.limit]
    print(f"reviewing {len(todo)} entries with {MODEL}", file=sys.stderr)

    if args.dry_run:
        e = todo[0]
        print(SYSTEM + "\n\n" + taxonomy_block(entries))
        print("\n----- user -----\n" + entry_message(e, profile.get(e["slug"], {})))
        print("\n----- schema -----\n" + json.dumps(schema(), ensure_ascii=False))
        return
    client = anthropic.Anthropic()
    # Same bytes on every request, so the instructions + taxonomy are cached after the first call.
    system = [{"type": "text", "text": SYSTEM + "\n\n" + taxonomy_block(entries), "cache_control": {"type": "ephemeral"}}]
    msgs = {}
    for e in todo:
        print(f"  fetching {e['slug']}", file=sys.stderr)
        msgs[e["slug"]] = entry_message(e, profile.get(e["slug"], {}))
    results = []
    if todo:  # warm the cache once instead of letting the first parallel calls all write it
        results.append(review(client, system, todo[0], msgs[todo[0]["slug"]]))
        with ThreadPoolExecutor(args.workers) as pool:
            results += list(pool.map(lambda e: review(client, system, e, msgs[e["slug"]]), todo[1:]))

    total = 0.0
    for r in results:
        total += r.get("cost", 0)
        if "review" in r:
            done[r["slug"]] = r
        print(f"  {r['slug']:30} {r.get('eroare') or r['review']['stare'] + ' / ' + r['review']['incredere']}"
              f"  ${r.get('cost', 0):.4f}", file=sys.stderr)
    raw_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()))

    by_slug = {e["slug"]: e for e in entries}
    rows = [row for slug, r in done.items() if slug in by_slug for row in diff_rows(by_slug[slug], r["review"])]
    with open(OUT / "sugestii.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "camp", "actual", "propus", "motiv", "incredere"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"cost this run ≈ ${total:.3f}; {len(rows)} suggested changes in {OUT / 'sugestii.csv'}", file=sys.stderr)


if __name__ == "__main__":
    main()
