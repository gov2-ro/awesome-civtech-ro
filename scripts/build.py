"""Merge proiecte.csv + orgs.csv + profil.csv into site/data.json (the browser's copy), site/feed.xml
(RSS, newest projects first) and site/proiect/<slug>/index.html (one page per entry, for link previews and
search engines; git ignores them, the Pages workflow builds them). All generated, not edited.
The page's folder is the entry's tab: site/proiect/, site/organizatie/ or site/resursa/.

    python3 scripts/build.py
"""
import hashlib
import html
import json
import math
import re
import shutil
from email.utils import format_datetime
from xml.sax.saxutils import escape
from datetime import date, datetime, timezone

from common import (BOILERPLATE, DATA, ETICHETE, LINKICON_DIR, NETWORK_ROLES, SITE, domain_of, is_kept, link_host, load_entries,
                    load_mentions, load_profile, parse_link, read_csv, split_list, split_tip)

CODE_ROLES = ("github", "gitlab", "cod")
SITE_URL = "https://civtech.gov2.ro/"
FEED_SIZE = 40
PAGE_KINDS = ("proiect", "organizatie", "resursa")  # the folders under site/ that entry_pages() owns
DEFAULT_SHARE = {"src": "img/share.png", "w": 1106, "h": 558}


def pick_desc(desc: str, prof: dict) -> tuple[str, str]:
    """The curated description unless empty or boilerplate; then the site's own meta description."""
    if desc and not BOILERPLATE.match(desc):
        return desc, "catalog"
    d = prof.get("description", "")
    if len(d) >= 40 and prof.get("status") in ("activ", "mutat"):
        return d, "site"
    return "", ""


def next_row(rows: dict[str, int], tab: str) -> int:
    """The next row number of a tab of the Sheet (the tab has the CSV's rows, in order, under a header)."""
    rows[tab] += 1
    return rows[tab]


def authors(cell: str, orgs: dict[str, dict]) -> list[dict]:
    """The `autor` cell as a list of {name, org}. A name that is the slug of a row in orgs.csv becomes that
    organisation (its own name, and `org` = its slug); any other name stays as written."""
    out = {}
    for name in re.split(r"\s+[/&]\s+|,\s*", cell or ""):
        name = name.strip()
        if len(name) <= 2:
            continue
        a = {"name": orgs[name]["nume"], "org": name} if name in orgs else {"name": name, "org": ""}
        out.setdefault(a["org"] or a["name"], a)
    return list(out.values())


def keywords(cell: str, rules: dict) -> list[str]:
    out = []
    for k in cell.split(","):
        k = re.sub(r"\s+", "-", k.strip().lower())
        if not k or re.match(r"^loca?l?:", k) or k in rules["ignora"]:
            continue
        k = rules["alias"].get(k, k)
        if k not in out:
            out.append(k)
    return out


def links(cell: str, social: dict, roles: list[dict]) -> list[dict]:
    """The 'linkuri' cell ("rol:URL" or bare URL), then social links the profiler found on the homepage."""
    label = {r["key"]: r["label"] for r in roles}
    out = {}
    for tok in split_list(cell):
        role, url = parse_link(tok, roles)
        out.setdefault(role if role not in ("web", *CODE_ROLES) else url,
                       {"role": role, "label": label[role], "url": url, "src": "manual"})
    for role, url in social.items():
        if re.search(r"/(events|groups)/", url):
            continue
        out.setdefault(role, {"role": role, "label": label.get(role, role), "url": url, "src": "site"})
    # A link that shows no network logo shows the favicon of its host, when the profiler stored one.
    for l in out.values():
        host = link_host(l["url"])
        if l["role"] not in NETWORK_ROLES and (LINKICON_DIR / f"{host}.webp").exists():
            l["icon"] = f"img/linkicon/{host}.webp"
    order = list(label)
    return sorted(out.values(), key=lambda l: order.index(l["role"]))


def repo_stats(p: dict) -> dict:
    """GitHub facts of the entry's repository for the drawer; only the values the profiler found."""
    if not p.get("repo"):
        return {}
    out = {"name": p["repo"], "url": f"https://github.com/{p['repo']}", "archived": bool(p.get("repo_archived"))}
    for col, key in (("stars", "stars"), ("forks", "forks"), ("open_issues", "issues"), ("commits", "commits"),
                     ("contributors", "contributors")):
        if p.get(col) not in (None, ""):
            out[key] = num(p[col])
    for col, key in (("last_commit", "last"), ("license", "license"), ("language", "language")):
        if p.get(col):
            out[key] = p[col]
    return out


def status_of(stare: str, prof: dict) -> str:
    if stare:
        return stare
    s = prof.get("status")
    if not s:
        return "neverificat"
    # Gone, and the Wayback Machine has not seen it for a year: the project has ended, not just a glitch.
    if s == "offline" and (years_since(prof.get("last_capture", "")) or 0) > 1:
        return "arhivat"
    return {"mutat": "activ", "blocat": "necunoscut", "parcat": "offline"}.get(s, s)


def num(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def years_since(d: str) -> float | None:
    return (date.today() - date.fromisoformat(d)).days / 365.25 if d else None


def last_activity(p: dict) -> str:
    """Newest sign of life: a dated update, else the copyright year in the footer."""
    cy = num(p.get("copyright_year"))
    return max(p.get("updated", ""), f"{cy}-12-31" if cy and cy <= date.today().year else "")


def since(p: dict) -> tuple[str, str]:
    """Earliest trace: first Wayback capture or repo creation; the first TLS certificate only when
    neither exists, since a domain can be older than the project now living on it."""
    seen = min(((d, s) for d, s in ((p.get("first_seen", ""), "arhiva"), (p.get("repo_created", ""), "cod")) if d),
               default=("", ""))
    return seen if seen[0] else ((p["cert_first"], "certificat") if p.get("cert_first") else ("", ""))


def reach_features(mentions: list[dict], labels: list[dict]) -> dict[str, dict]:
    """Per slug, from the kept search results: how many distinct hosts give independent attention (the page is about
    the entry, and the page is not the entry's own channel, as labelled by review.py), split by kind of source, and
    the date of the newest such page. Without labels the kept hosts stand in for `indep` and the rest is 0."""
    kept: dict[str, list[dict]] = {}
    for r in mentions:
        if is_kept(r):
            kept.setdefault(r["slug"], []).append(r)
    label = {(l["slug"], l["url"]): l for l in labels}
    labelled = {l["slug"] for l in labels}
    hosts = lambda rows: len({r["host"] for r in rows})
    out = {}
    for slug in kept.keys() | labelled:
        rows = kept.get(slug, [])
        if slug not in labelled:
            out[slug] = {"indep": hosts(rows), "stiri": 0, "cercetare": 0, "guvern": 0, "ultima": ""}
            continue
        good = [r for r in rows if (l := label.get((slug, r["url"]))) and l["despre_proiect"] == "1" and l["independent"] == "1"]
        of = lambda kind: [r for r in good if label[(slug, r["url"])]["tip_sursa"] == kind]
        out[slug] = {"indep": hosts(good), "stiri": hosts(of("stire")), "cercetare": hosts(of("cercetare")),
                     "guvern": hosts(of("guvern")), "ultima": max((r["date"] for r in good), default="")}
    return out


NO_REACH = {"indep": 0, "stiri": 0, "cercetare": 0, "guvern": 0, "ultima": ""}


def score(e: dict, p: dict, alive: bool, desc: str, img, reach: dict) -> int:
    """0–100 relevance estimate: recent activity, reach, volume, longevity and how well it is documented.
    A heuristic for ordering, not a verdict; the weights are meant to be tuned."""
    lg = lambda v, top: min(1.0, math.log1p(num(v)) / math.log1p(top))
    act = years_since(last_activity(p))
    activity = 0.3 if act is None else 1 if act < .25 else .75 if act < 1 else .45 if act < 2 else .2 if act < 4 else 0
    opr = float(p.get("opr") or 0)
    # Weights sum to 1; every term is log-scaled except Open PageRank.
    r = (.30 * lg(p.get("archive_months"), 120) + .20 * lg(reach["indep"], 15) + .10 * lg(reach["stiri"], 10)
         + .05 * lg(reach["cercetare"] + reach["guvern"], 5) + .15 * min(1.0, opr / 6)
         + .10 * lg(p.get("wiki_refs"), 20) + .10 * lg(p.get("stars"), 200))
    volume = lg(p.get("sitemap_urls"), 5000)
    age = years_since(since(p)[0])
    longevity = min(1.0, (age or 0) / 8)
    docs = sum([bool(e["descriere_scurta"]), bool(desc), bool(e.get("cuvinte")), bool(img)]) / 4
    total = 30 * activity + 25 * r + 15 * volume + 15 * longevity + 15 * docs
    return round(total * (1 if alive else .4))


def feed(items: list[dict], generated: datetime) -> str:
    """RSS 2.0 of live projects, newest first by `since` (first trace on the web, not the date added here)."""
    live = [i for i in items if i["kind"] == "proiect" and i["since"] and i["status"] not in ("offline", "arhivat")]
    out = []
    for i in sorted(live, key=lambda i: i["since"], reverse=True)[:FEED_SIZE]:
        when = datetime.fromisoformat(i["since"]).replace(tzinfo=timezone.utc)
        link = f"{SITE_URL}{i['kind']}/{i['slug']}/"
        out.append(f"""<item><title>{escape(i['name'])}</title><link>{escape(link)}</link><guid isPermaLink="true">{escape(link)}</guid>
<description>{escape(i['tagline'] or i['desc'] or '')}</description><pubDate>{format_datetime(when)}</pubDate></item>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>CivTech România — proiecte noi</title><link>{SITE_URL}</link>
<atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>
<description>Cele mai noi proiecte din colecția CivTech România.</description><language>ro</language>
<lastBuildDate>{format_datetime(generated)}</lastBuildDate>
{chr(10).join(out)}
</channel></rss>
"""


def clip(text: str, n: int) -> str:
    """`text` cut at a word boundary before `n` characters, with an ellipsis."""
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0] if " " in text[:n] else text[:n]
    return cut.rstrip(" ,.;:–-") + "…"


ASSET_LINKS = {"style.css": r'(href="style\.css)(\?v=[0-9a-f]+)?(")', "app.js": r'(src="app\.js)(\?v=[0-9a-f]+)?(")'}


def stamp_assets() -> bool:
    """Put a hash of style.css and app.js in their links in site/index.html (?v=<hash>). Cloudflare and browsers keep
    these two files for hours (measured: cache-control max-age=14400, cf-cache-status HIT), while the page itself is not
    cached; a changed file gets a new address, so the new page never meets the old file. Run it before the page writers,
    which copy index.html. Returns True when index.html changed."""
    path = SITE / "index.html"
    doc = path.read_text(encoding="utf-8")
    for name, rx in ASSET_LINKS.items():
        digest = hashlib.sha1((SITE / name).read_bytes()).hexdigest()[:10]
        doc, n = re.subn(rx, lambda m: f"{m.group(1)}?v={digest}{m.group(3)}", doc)
        if n != 1:
            raise SystemExit(f"site/index.html must link {name} exactly once (found {n})")
    changed = doc != path.read_text(encoding="utf-8")
    if changed:
        path.write_text(doc, encoding="utf-8")
    return changed


def esc(v) -> str:
    return html.escape(str(v), quote=True)


def swap(doc: str, pattern: str, repl: str) -> str:
    doc, n = re.subn(pattern, lambda _: repl, doc, count=1)
    if not n:
        raise SystemExit(f"site/index.html has no {pattern}: the page writers in build.py need it")
    return doc


def page_head(template: str, *, title: str, text: str, url: str, img: dict, alt: str, depth: int) -> str:
    """site/index.html with this page's title, description, canonical address and share image in <head>, and a <base>
    so that the page's relative paths reach the site root from `depth` folders down."""
    doc = swap(template, r"<title>.*?</title>", f"<title>{esc(title)}</title>")
    doc = swap(doc, r'<meta charset="utf-8">', f'<meta charset="utf-8">\n<base href="{"../" * depth}">')
    doc = swap(doc, r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(text)}">')
    doc = swap(doc, r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{url}">')
    for key, value in {"og:url": url, "og:title": title, "og:description": text, "og:image": SITE_URL + img["src"],
                       "og:image:width": img["w"], "og:image:height": img["h"], "og:image:alt": alt,
                       "twitter:title": title, "twitter:description": text, "twitter:image": SITE_URL + img["src"]}.items():
        attr = "name" if key.startswith("twitter:") else "property"
        doc = swap(doc, rf'<meta {attr}="{key}" content="[^"]*">', f'<meta {attr}="{key}" content="{esc(value)}">')
    return doc


def entry_pages(items: list[dict]) -> int:
    """One page per entry at site/<kind>/<slug>/index.html: index.html with that entry's own <head> (see page_head)
    and the entry's text in <noscript>. app.js reads the slug from the path and opens the entry."""
    template = (SITE / "index.html").read_text(encoding="utf-8")
    for kind in {i["kind"] for i in items} | set(PAGE_KINDS):
        shutil.rmtree(SITE / kind, ignore_errors=True)
    for i in items:
        slug, name, kind = i["slug"], i["name"], i["kind"]
        text = clip(i["desc"] or i["tagline"] or "", 200) or "Director de instrumente civice, date deschise și proiecte de bună guvernare din România."
        img = i["img"] if i["img"] and i["img"]["kind"] != "logo" else DEFAULT_SHARE
        doc = page_head(template, title=f"{name} — CivTech România", text=text, url=f"{SITE_URL}{kind}/{slug}/", img=img, alt=name, depth=2)
        # With a <base>, a bare "#fragment" would leave the page: point it at this page.
        doc = doc.replace('href="#', f'href="{kind}/{slug}/#')
        nojs = (f'<noscript><article class="nojs"><h1>{esc(name)}</h1>'
                + (f"<p>{esc(i['tagline'])}</p>" if i["tagline"] else "")
                + (f"<p>{esc(i['desc'])}</p>" if i["desc"] else "")
                + (f'<p><a href="{esc(i["url"])}">{esc(i["domain"])}</a></p>' if i["url"] else "")
                + '<p><a href="./">CivTech România</a></p></article></noscript>')
        doc = swap(doc, r'<a class="skip"', nojs + '\n<a class="skip"')
        out = SITE / kind / slug
        out.mkdir(parents=True)
        (out / "index.html").write_text(doc, encoding="utf-8")
    return len(items)


ARCHIVE_LEAD = {
    "proiect": "{n} proiecte civic tech din România, pe domenii.",
    "organizatie": "{n} organizații care fac civic tech, transparență și participare în România.",
    "resursa": "{n} resurse: liste, articole, ghiduri, campanii și cercetări.",
}


def archive_pages(items: list[dict], tax: dict) -> int:
    """One list of every entry of a kind at site/<kind>/index.html (/proiect/, /organizatie/, /resursa/): plain HTML,
    readable without scripts, each entry linking to its own page. Projects are grouped by domain, the others run A-Z.
    Call it after entry_pages(), which clears the folders."""
    template = (SITE / "index.html").read_text(encoding="utf-8")
    kinds = {k["key"]: k["label"] for k in tax["kinds"]}
    domains = {d["key"]: d for d in tax["domenii"]}
    tips = {t["key"]: t["label"] for t in tax["tipuri"]}
    fels = {f["key"]: f["label"] for f in tax["fel"]}
    counts = {k: sum(1 for i in items if i["kind"] == k) for k in kinds}

    def entry(i: dict) -> str:
        kind_label = fels.get(i["fel"], "") if i["kind"] == "resursa" and i["fel"] != "resursa" else ""
        parts = [kind_label, *(tips.get(t, "") for t in i["tips"]), i["oras"] if i["acoperire"] == "local" else ""]
        meta = " · ".join(dict.fromkeys(p for p in parts if p))
        gone = f' <span class="arch-gone">{esc(i["status"])}</span>' if i["status"] in ("arhivat", "offline") else ""
        icon = f'<img class="fav fav-name" src="{esc(i["icon"])}" alt="" width="24" height="24" loading="lazy">' if i["icon"] else ""
        blurb = clip(i["tagline"] or i["desc"], 160)
        return (f'<li class="arch-item"><a class="arch-name" href="{i["kind"]}/{esc(i["slug"])}/">{icon}{esc(i["name"])}</a>{gone}'
                + (f'<span class="arch-meta">{esc(meta)}</span>' if meta else "")
                + (f'<p class="arch-blurb">{esc(blurb)}</p>' if blurb else "") + "</li>")

    for kind, label in kinds.items():
        mine = [i for i in items if i["kind"] == kind]
        if kind == "proiect":
            groups = [(d["label"], d["hint"], [i for i in mine if i["domeniu"] == d["key"]]) for d in domains.values()]
        else:
            groups = [("", "", mine)]
        body = "".join((f'<section class="arch-group"><h2>{esc(g)} <span class="n">{len(rows)}</span></h2>' + (f'<p class="arch-hint">{esc(h)}</p>' if h else "") if g else "<section>")
                       + f'<ul class="arch-list">{"".join(entry(i) for i in rows)}</ul></section>' for g, h, rows in groups if rows)
        lead = ARCHIVE_LEAD[kind].format(n=len(mine))
        nav = "".join(f'<a href="{k}/"{" aria-current=" + chr(34) + "page" + chr(34) if k == kind else ""}>{esc(name)} <span class="n">{counts[k]}</span></a>'
                      for k, name in kinds.items())
        doc = page_head(template, title=f"{label} — CivTech România", text=lead, url=f"{SITE_URL}{kind}/", img=DEFAULT_SHARE,
                        alt="CivTech România", depth=1)
        head = doc[:doc.index("<body>")]
        page = f"""{head}<body class="archive">
<header class="arch-hdr wrap">
  <a class="arch-brand" href="./">CivTech România</a>
  <nav class="arch-nav" aria-label="Arhive">{nav}</nav>
  <a class="btn btn-outline" href="./?k={kind}">Caută și filtrează</a>
</header>
<main class="wrap arch">
  <h1>{esc(label)}</h1>
  <p class="arch-lead">{esc(lead)} <a href="./?k={kind}">Lista interactivă</a> are căutare și filtre.</p>
  {body}
</main>
<footer class="footer wrap"><p class="mono small muted">actualizat: {esc(max((i["checked"] for i in items), default=""))} · <a href="./">civtech.gov2.ro</a> · <a href="feed.xml">RSS</a></p></footer>
</body>
</html>
"""
        (SITE / kind / "index.html").write_text(page, encoding="utf-8")
    return len(kinds)


def main():
    tax = json.loads((DATA / "taxonomy.json").read_text())
    roles = tax["linkuri"]["roluri"]
    profile = load_profile()
    features = reach_features(load_mentions(), read_csv(ETICHETE) if ETICHETE.exists() else [])
    items = []
    entries = load_entries()
    orgs = {e["slug"]: e for e in entries if e["kind"] == "organizatie"}
    rows = {"proiecte": 1, "orgs": 1}  # the Sheet's row of an entry: row 1 is the header, then the CSV order
    for n, e in enumerate(entries):
        p = profile.get(e["slug"], {})
        # A retired project's live URL shows something else now: ignore what the profiler saw there.
        retired = e["stare"] in ("arhivat", "offline")
        live = {} if retired else p
        desc, desc_src = pick_desc(e["descriere"], live)
        lk = links(e["linkuri"], live.get("social") or {}, roles)
        code_link = next((l for l in lk if l["role"] in CODE_ROLES), None)
        code = code_link["url"] if code_link else (live.get("repos") or [""])[0]
        img = live.get("image")
        moved = live.get("status") == "mutat"
        final = live.get("final_url") or e["url"]
        status = status_of(e["stare"], p)
        alive = status in ("activ", "necunoscut")
        act = last_activity(p)
        reach = features.get(e["slug"], NO_REACH)
        repo = repo_stats(p)
        items.append({
            "id": n + 1,
            "slug": e["slug"],
            "kind": e["kind"],
            "row": next_row(rows, "orgs" if e["kind"] == "organizatie" else "proiecte"),
            "fel": e.get("fel", ""),
            "civictech": e.get("civictech") == "1",
            "name": e["nume"],
            "tagline": e["descriere_scurta"],
            "desc": desc,
            "descSrc": desc_src,
            "domeniu": e["domeniu"],
            "tips": split_tip(e.get("tip", "")),
            "acoperire": e["acoperire"] or "national",  # a missing value means national
            "oras": e["oras"],
            "keywords": keywords(e.get("cuvinte", ""), tax["cuvinte"]),
            "links": [l for l in lk if l is not code_link],
            "url": final if moved else e["url"],
            "domain": domain_of(final if moved else e["url"]) if e["url"] else "",
            "movedFrom": domain_of(e["url"]) if moved else "",
            "authors": authors(e.get("autor", ""), orgs),
            "code": code,
            **({"repo": repo} if repo else {}),
            "contact": e.get("contact", ""),
            "status": status,
            "httpStatus": live.get("http_status"),
            "checked": (p.get("fetched_at") or "")[:10],
            "since": since(p)[0],
            "sinceSrc": since(p)[1],
            "updated": p.get("updated", ""),
            "updatedSrc": p.get("updated_src", ""),
            # Up, but no sign of an edit in three years.
            "stale": act[:4] if alive and act and (years_since(act) > 3 or p.get("repo_archived")) else "",
            "score": score(e, p, alive, desc, img, reach),
            "reach": reach,
            "img": img,
            "icon": live.get("icon", ""),
            "wayback": p.get("wayback") or (f"https://web.archive.org/web/{e['url']}" if e["url"] and status in ("offline", "arhivat") else ""),
        })
    items.sort(key=lambda x: re.sub(r"[^a-z0-9]", "", x["name"].lower()))
    checked = sorted({i["checked"] for i in items if i["checked"]})
    tax_out = {k: v for k, v in tax.items() if k != "cuvinte"}
    now = datetime.now(timezone.utc)
    out = {
        "generated": now.isoformat(timespec="seconds"),
        "checked": checked[-1] if checked else "",
        "taxonomy": tax_out,
        "site": {k: v for k, v in json.loads((DATA / "site.json").read_text(encoding="utf-8")).items() if k != "_doc"},
        "items": items,
    }
    (SITE / "data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    by = {}
    for i in items:
        by[i["status"]] = by.get(i["status"], 0) + 1
    (SITE / "feed.xml").write_text(feed(items, now))
    stamp_assets()
    pages = entry_pages(items)
    archives = archive_pages(items, tax)
    print(f"wrote {len(items)} entries to site/data.json  {by}; site/feed.xml; {pages} entry pages and {archives} archives in site/{{{','.join(PAGE_KINDS)}}}/")


if __name__ == "__main__":
    main()
