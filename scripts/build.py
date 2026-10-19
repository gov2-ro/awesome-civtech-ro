"""Merge proiecte.csv + orgs.csv + profil.csv into site/data.json (the browser's copy), site/feed.xml
(RSS, newest projects first), site/llms.txt (the whole list as Markdown, for language models; llmstxt.org) and
site/proiect/<slug>/index.html (one page per entry, for link previews and
search engines; git ignores them, the Pages workflow builds them). All generated, not edited.
The page's folder is the entry's tab: site/proiect/, site/organizatie/ or site/resursa/.

    python3 scripts/build.py
    python3 scripts/build.py --site-dir /tmp/civtech-v1                     # the same site, written elsewhere
    python3 scripts/build.py --data-dir data/taxonomy-v2/integrare --site-dir /tmp/civtech-v2 --allow-draft

--data-dir selects the data root (default data/, the v1 layout). A taxonomy v2 root builds the v2 payload
(schemaVersion 2) with the v2 browser code from site-v2/. --site-dir writes every output, page deletion, asset stamp
and image there: it first copies the template, assets and images of site/, so a preview never touches site/.
A v2 build needs --site-dir until the source cutover. It also refuses proposed classifications unless
--allow-draft is given; the preview then says that its classifications are proposals.
"""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import sys
from collections import Counter
from email.utils import format_datetime
from xml.sax.saxutils import escape
from datetime import date, datetime, timezone

from pathlib import Path

from common import (BOILERPLATE, DATA, NETWORK_ROLES, ROOT, SITE, coverage_line, data_schema, domain_of, kept_by_slug, label_coverage,
                    link_host, load_catalogue, load_entries, load_mentions, load_profile, load_vocabulary, observation_paths,
                    parse_link, read_csv, split_list, split_tip)

CODE_ROLES = ("github", "gitlab", "cod")
SITE_URL = "https://civtech.gov2.ro/"
FEED_SIZE = 40
REPO_URL = "https://github.com/gov2-ro/awesome-civtech-ro"
PAGE_KINDS = ("proiect", "organizatie", "resursa")  # the folders under site/ that entry_pages() owns
DEFAULT_SHARE = {"src": "img/share.png", "w": 1106, "h": 558}
SITE_V2 = ROOT / "site-v2"  # the v2 browser code; a v2 build copies it over the template in its --site-dir
GENERATED = ("data.json", "feed.xml", "llms.txt", *PAGE_KINDS)  # what a build writes; never copied from site/


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


def links(cell: str, social: dict, roles: list[dict], site: Path = SITE) -> list[dict]:
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
        if l["role"] not in NETWORK_ROLES and (site / "img" / "linkicon" / f"{host}.webp").exists():
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


def last_activity(p: dict, today: date | None = None) -> str:
    """Newest sign of life: a dated update wins. Only without one, the copyright year in the footer stands in, as
    <year>-01-01 and never after today (many footers print the current year by script, so it is weak evidence)."""
    if p.get("updated"):
        return p["updated"]
    cy = num(p.get("copyright_year"))
    fallback = f"{cy:04d}-01-01" if cy else ""
    return fallback if fallback and fallback <= (today or date.today()).isoformat() else ""


def since(p: dict) -> tuple[str, str]:
    """Earliest trace: first Wayback capture or repo creation; the first TLS certificate only when
    neither exists, since a domain can be older than the project now living on it."""
    seen = min(((d, s) for d, s in ((p.get("first_seen", ""), "arhiva"), (p.get("repo_created", ""), "cod")) if d),
               default=("", ""))
    return seen if seen[0] else ((p["cert_first"], "certificat") if p.get("cert_first") else ("", ""))


def reach_features(mentions: list[dict], labels: list[dict]) -> dict[str, dict]:
    """Per slug, from the kept search results: how many distinct hosts give independent attention (the page is about
    the entry, and the page is not the entry's own channel, as labelled by review.py), split by kind of source, and
    the date of the newest such page. A label counts for the kept row of the same slug and URL; a label for a URL that
    is no longer kept counts for nothing. Three cases:
    - every kept row is labelled: `indep` counts the labelled independent hosts only;
    - some are: `indep` also counts the hosts of the unlabelled kept rows, and the entry carries `provisional: true`
      (the other counts and `ultima` come from the labels, so they are lower bounds);
    - none is (no review yet, or every label is stale): the kept hosts stand in for `indep` and the rest is 0."""
    kept = kept_by_slug(mentions)
    label = {(l["slug"], l["url"]): l for l in labels}
    hosts = lambda rows: len({r["host"] for r in rows})
    out = {}
    for slug in kept.keys() | {l["slug"] for l in labels}:
        rows = kept.get(slug, [])
        done = [r for r in rows if (slug, r["url"]) in label]
        if rows and not done:
            out[slug] = {"indep": hosts(rows), "stiri": 0, "cercetare": 0, "guvern": 0, "ultima": ""}
            continue
        good = [r for r in done if label[(slug, r["url"])]["despre_proiect"] == "1" and label[(slug, r["url"])]["independent"] == "1"]
        open_rows = [r for r in rows if (slug, r["url"]) not in label]
        of = lambda kind: [r for r in good if label[(slug, r["url"])]["tip_sursa"] == kind]
        out[slug] = {"indep": hosts(good + open_rows), "stiri": hosts(of("stire")), "cercetare": hosts(of("cercetare")),
                     "guvern": hosts(of("guvern")), "ultima": max((r["date"] for r in good), default=""),
                     **({"provisional": True} if open_rows else {})}
    return out


NO_REACH = {"indep": 0, "stiri": 0, "cercetare": 0, "guvern": 0, "ultima": ""}


def score(e: dict, p: dict, alive: bool, desc: str, img, reach: dict, classified: bool) -> int:
    """0–100 relevance estimate: recent activity, reach, volume, longevity and how well it is documented.
    A heuristic for ordering, not a verdict; the weights are meant to be tuned. `classified` is one yes/no signal
    (v1: keywords exist; v2: a primary subject exists), so more assigned concepts never raise the score."""
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
    docs = sum([bool(e["descriere_scurta"]), bool(desc), classified, bool(img)]) / 4
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


ASSET_LINKS = {"style.css": r'(href="style\.css)(\?v=[0-9a-f]+)?(")', "app.js": r'(src="app\.js)(\?v=[0-9a-f]+)?(")',
               "v2.css": r'(href="v2\.css)(\?v=[0-9a-f]+)?(")'}


def stamp_assets(site: Path = SITE) -> bool:
    """Put a hash of style.css and app.js in their links in site/index.html (?v=<hash>). Cloudflare and browsers keep
    these two files for hours (measured: cache-control max-age=14400, cf-cache-status HIT), while the page itself is not
    cached; a changed file gets a new address, so the new page never meets the old file. Run it before the page writers,
    which copy index.html. Returns True when index.html changed."""
    path = site / "index.html"
    doc = path.read_text(encoding="utf-8")
    for name, rx in ASSET_LINKS.items():
        if not (site / name).exists() and name not in ("style.css", "app.js"):
            continue
        digest = hashlib.sha1((site / name).read_bytes()).hexdigest()[:10]
        doc, n = re.subn(rx, lambda m: f"{m.group(1)}?v={digest}{m.group(3)}", doc)
        if n != 1:
            raise SystemExit(f"{path} must link {name} exactly once (found {n})")
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


def entry_pages(items: list[dict], site: Path = SITE) -> int:
    """One page per entry at site/<kind>/<slug>/index.html: index.html with that entry's own <head> (see page_head)
    and the entry's text in <noscript>. app.js reads the slug from the path and opens the entry."""
    template = (site / "index.html").read_text(encoding="utf-8")
    for kind in {i["kind"] for i in items} | set(PAGE_KINDS):
        shutil.rmtree(site / kind, ignore_errors=True)
    for i in items:
        slug, name, kind = i["slug"], i["name"], i["kind"]
        text = clip(i["desc"] or i["tagline"] or "", 200) or "Colecție de instrumente civice, date deschise și proiecte de bună guvernare din România."
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
        out = site / kind / slug
        out.mkdir(parents=True)
        (out / "index.html").write_text(doc, encoding="utf-8")
    return len(items)


ARCHIVE_LEAD = {
    "proiect": "{n} proiecte civic tech din România, pe domenii.",
    "organizatie": "{n} organizații care fac civic tech, transparență și participare în România.",
    "resursa": "{n} resurse: liste, articole, ghiduri, campanii și cercetări.",
}


def archive_pages(items: list[dict], tax: dict, site: Path = SITE) -> int:
    """The v1 archives: projects grouped by domain, the others A-Z (see write_archives)."""
    domains = {d["key"]: d for d in tax["domenii"]}
    tips = {t["key"]: t["label"] for t in tax["tipuri"]}
    fels = {f["key"]: f["label"] for f in tax["fel"]}

    def meta(i: dict) -> str:
        kind_label = fels.get(i["fel"], "") if i["kind"] == "resursa" and i["fel"] != "resursa" else ""
        parts = [kind_label, *(tips.get(t, "") for t in i["tips"]), i["oras"] if i["acoperire"] == "local" else ""]
        return " · ".join(dict.fromkeys(p for p in parts if p))

    def groups(kind: str, mine: list[dict]) -> list[tuple[str, str, list[dict]]]:
        if kind == "proiect":
            return [(d["label"], d["hint"], [i for i in mine if i["domeniu"] == d["key"]]) for d in domains.values()]
        return [("", "", mine)]

    return write_archives(items, {k["key"]: k["label"] for k in tax["kinds"]}, groups, meta, site)


def write_archives(items: list[dict], kinds: dict[str, str], groups, meta, site: Path, leads: dict = ARCHIVE_LEAD, note: str = "") -> int:
    """One list of every entry of a kind at site/<kind>/index.html (/proiect/, /organizatie/, /resursa/): plain HTML,
    readable without scripts, each entry linking to its own page. `groups(kind, items)` gives (title, hint, items)
    sections and `meta(item)` its small grey line. Call it after entry_pages(), which clears the folders."""
    template = (site / "index.html").read_text(encoding="utf-8")
    counts = {k: sum(1 for i in items if i["kind"] == k) for k in kinds}

    def entry(i: dict) -> str:
        meta_line = meta(i)
        gone = f' <span class="arch-gone">{esc(i["status"])}</span>' if i["status"] in ("arhivat", "offline") else ""
        icon = f'<img class="fav fav-name" src="{esc(i["icon"])}" alt="" width="24" height="24" loading="lazy">' if i["icon"] else ""
        blurb = clip(i["tagline"] or i["desc"], 160)
        return (f'<li class="arch-item"><a class="arch-name" href="{i["kind"]}/{esc(i["slug"])}/">{icon}{esc(i["name"])}</a>{gone}'
                + (f'<span class="arch-meta">{esc(meta_line)}</span>' if meta_line else "")
                + (f'<p class="arch-blurb">{esc(blurb)}</p>' if blurb else "") + "</li>")

    for kind, label in kinds.items():
        mine = [i for i in items if i["kind"] == kind]
        body = "".join((f'<section class="arch-group"><h2>{esc(g)} <span class="n">{len(rows)}</span></h2>' + (f'<p class="arch-hint">{esc(h)}</p>' if h else "") if g else "<section>")
                       + f'<ul class="arch-list">{"".join(entry(i) for i in rows)}</ul></section>' for g, h, rows in groups(kind, mine) if rows)
        lead = leads[kind].format(n=len(mine)) + (f" {note}" if note else "")
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
        (site / kind / "index.html").write_text(page, encoding="utf-8")
    return len(kinds)


def llms_txt(items: list[dict], tax: dict) -> str:
    """site/llms.txt of a v1 build: projects grouped by domain, resources by `fel`, organisations A-Z (see llms_doc)."""
    domains = tax["domenii"]
    fels = {f["key"]: f["label"] for f in tax["fel"] if f["kind"] == "resursa"} | {"resursa": "Liste și colecții"}
    projects = [i for i in items if i["kind"] == "proiect"]
    res = [i for i in items if i["kind"] == "resursa"]
    sections = [(f"Proiecte: {d['label']}", [i for i in projects if i["domeniu"] == d["key"]]) for d in domains]
    sections.append(("Organizații", [i for i in items if i["kind"] == "organizatie"]))
    sections += [(f"Resurse: {label}", [i for i in res if i["fel"] == key]) for key, label in fels.items()]
    sections.append(("Resurse: altele", [i for i in res if i["fel"] not in fels]))
    sources = (f"- [proiecte.csv]({REPO_URL}/blob/main/data/proiecte.csv): sursa editată de om pentru proiecte și resurse\n"
               f"- [orgs.csv]({REPO_URL}/blob/main/data/orgs.csv): sursa editată de om pentru organizații\n")
    return llms_doc(items, sections, sources)


def llms_doc(items: list[dict], sections: list[tuple[str, list[dict]]], sources: str, note: str = "") -> str:
    """site/llms.txt (format: llmstxt.org): what the site is, where the data is, and every entry as a Markdown link to
    its own page, in the given (title, items) sections (`items` is sorted)."""

    def line(i: dict) -> str:
        blurb = clip(i["tagline"] or i["desc"], 200).rstrip(".")
        gone = f" ({i['status']})" if i["status"] in ("arhivat", "offline") else ""
        text = ". ".join(t for t in (blurb, f"Site: {i['url']}" if i["url"] else "") if t)
        return f"- [{i['name']}]({SITE_URL}{i['kind']}/{i['slug']}/){gone}" + (f": {text}" if text else "")

    def section(title: str, rows: list[dict]) -> str:
        return f"## {title}\n\n" + "\n".join(line(i) for i in rows) + "\n" if rows else ""

    projects = [i for i in items if i["kind"] == "proiect"]
    orgs = [i for i in items if i["kind"] == "organizatie"]
    res = [i for i in items if i["kind"] == "resursa"]
    checked = max((i["checked"] for i in items), default="")
    parts = [f"""# CivTech România

> Colecție curatoriată de proiecte civic tech, organizații și resurse din România: instrumente civice, date deschise
> și proiecte de bună guvernare. {len(projects)} proiecte, {len(orgs)} organizații, {len(res)} resurse.

Fiecare intrare are o pagină proprie la {SITE_URL}<tip>/<slug>/ (tip: proiect, organizatie, resursa). Starea
(activ, offline, arhivat) vine dintr-o verificare automată a site-ului; ultima verificare: {checked}. Textele sunt în
limba română. Datele sunt reutilizabile conform EUPL v1.2.{note}

## Date

- [data.json]({SITE_URL}data.json): toate intrările, cu taxonomia, linkurile, starea și scorul de relevanță
{sources}- [DATA-SCHEMA.md]({REPO_URL}/blob/main/docs/DATA-SCHEMA.md): coloanele fiecărui fișier
- [CONTRIBUTING.md]({REPO_URL}/blob/main/CONTRIBUTING.md): cum se propune un proiect
- [feed.xml]({SITE_URL}feed.xml): RSS cu cele mai noi proiecte
"""]
    parts += [section(title, rows) for title, rows in sections]
    return "\n".join(p for p in parts if p)


def observed(e: dict, p: dict, roles: list[dict], site: Path) -> dict:
    """The fields that come from the profile and links rather than from classification, shared by both schemas."""
    # A retired project's live URL shows something else now: ignore what the profiler saw there.
    retired = e["stare"] in ("arhivat", "offline")
    live = {} if retired else p
    desc, desc_src = pick_desc(e["descriere"], live)
    lk = links(e["linkuri"], live.get("social") or {}, roles, site)
    code_link = next((l for l in lk if l["role"] in CODE_ROLES), None)
    moved = live.get("status") == "mutat"
    final = live.get("final_url") or e["url"]
    status = status_of(e["stare"], p)
    act = last_activity(p)
    alive = status in ("activ", "necunoscut")
    return {
        "live": live, "desc": desc, "descSrc": desc_src, "links": [l for l in lk if l is not code_link],
        "url": final if moved else e["url"], "domain": domain_of(final if moved else e["url"]) if e["url"] else "",
        "movedFrom": domain_of(e["url"]) if moved else "",
        "code": code_link["url"] if code_link else (live.get("repos") or [""])[0], "repo": repo_stats(p),
        "status": status, "alive": alive, "img": live.get("image"),
        # Up, but no sign of an edit in three years.
        "stale": act[:4] if alive and act and (years_since(act) > 3 or p.get("repo_archived")) else "",
        "wayback": p.get("wayback") or (f"https://web.archive.org/web/{e['url']}" if e["url"] and status in ("offline", "arhivat") else ""),
    }


def items_v1(data_dir: Path, site: Path) -> tuple[list[dict], dict]:
    """The v1 items and the rest of data.json, from proiecte.csv, orgs.csv and taxonomy.json."""
    tax = json.loads((data_dir / "taxonomy.json").read_text())
    roles = tax["linkuri"]["roluri"]
    obs = observation_paths(data_dir)
    profile = load_profile(obs["profile"])
    features = reach_features(load_mentions(obs["mentions"]), read_csv(obs["labels"]) if obs["labels"].exists() else [])
    items = []
    entries = load_entries(data_dir)
    orgs = {e["slug"]: e for e in entries if e["kind"] == "organizatie"}
    rows = {"proiecte": 1, "orgs": 1}  # the Sheet's row of an entry: row 1 is the header, then the CSV order
    for n, e in enumerate(entries):
        p = profile.get(e["slug"], {})
        o = observed(e, p, roles, site)
        reach = features.get(e["slug"], NO_REACH)
        items.append({
            "id": n + 1,
            "slug": e["slug"],
            "kind": e["kind"],
            "row": next_row(rows, "orgs" if e["kind"] == "organizatie" else "proiecte"),
            "fel": e.get("fel", ""),
            "civictech": e.get("civictech") == "1",
            "name": e["nume"],
            "tagline": e["descriere_scurta"],
            "desc": o["desc"],
            "descSrc": o["descSrc"],
            "domeniu": e["domeniu"],
            "tips": split_tip(e.get("tip", "")),
            "acoperire": e["acoperire"] or "national",  # a missing value means national
            "oras": e["oras"],
            "keywords": keywords(e.get("cuvinte", ""), tax["cuvinte"]),
            "links": o["links"],
            "url": o["url"],
            "domain": o["domain"],
            "movedFrom": o["movedFrom"],
            "authors": authors(e.get("autor", ""), orgs),
            "code": o["code"],
            **({"repo": o["repo"]} if o["repo"] else {}),
            "contact": e.get("contact", ""),
            "status": o["status"],
            "httpStatus": o["live"].get("http_status"),
            "checked": (p.get("fetched_at") or "")[:10],
            "since": since(p)[0],
            "sinceSrc": since(p)[1],
            "updated": p.get("updated", ""),
            "updatedSrc": p.get("updated_src", ""),
            "stale": o["stale"],
            "score": score(e, p, o["alive"], o["desc"], o["img"], reach, bool(e.get("cuvinte"))),
            "reach": reach,
            "img": o["img"],
            "icon": o["live"].get("icon", ""),
            "wayback": o["wayback"],
        })
    items.sort(key=lambda x: re.sub(r"[^a-z0-9]", "", x["name"].lower()))
    head = {
        "taxonomy": {k: v for k, v in tax.items() if k != "cuvinte"},
        "site": {k: v for k, v in json.loads((data_dir / "site.json").read_text(encoding="utf-8")).items() if k != "_doc"},
    }
    return items, head


def subject_groups(pkg) -> list[dict]:
    """The top-level subjects, in the concept table's order."""
    return [c for c in pkg.concepts.values() if c["schema"] == "subiect" and not c["mai_larg"] and c["statut"] != "retras"]


def items_v2(root: Path, site: Path) -> tuple[list[dict], dict]:
    """The v2 items and the rest of data.json, from a taxonomy v2 root. Facets are concept and area IDs; the
    vocabulary block gives their labels. Private columns (notes, source rows, confidence, review) stay out."""
    vocab = load_vocabulary(root)
    pkg = vocab["package"]
    roles = vocab["roles"]
    legacy_tax = json.loads(pkg.files.path("source/taxonomy.json").read_text(encoding="utf-8"))
    obs = observation_paths(root)
    profile = load_profile(obs["profile"])
    features = reach_features(load_mentions(obs["mentions"]), read_csv(obs["labels"]) if obs["labels"].exists() else [])
    # "Corectează în tabel" opens the entry's row in the Sheet. Until the Sheet has the v2 tab (tabs.intrari is null),
    # it opens the v1 tab, which still holds the entry's texts and links; the v1 row comes from data/, which the Sheet mirrors.
    site_cfg = {k: v for k, v in pkg.settings["site"].items() if k != "_doc"}
    v1_rows = None
    if site_cfg.get("tabs", {}).get("intrari") is None and (DATA / "site.json").exists():
        site_cfg["tabs"] = {**json.loads((DATA / "site.json").read_text(encoding="utf-8")).get("tabs", {}), **site_cfg.get("tabs", {})}
        v1_rows = {e["slug"]: {"tab": "orgs" if e["kind"] == "organizatie" else "proiecte", "row": e["row"]} for e in load_catalogue(DATA)}
    items = []
    for n, e in enumerate(load_catalogue(root)):
        p = profile.get(e["slug"], {})
        o = observed(e, p, roles, site)
        reach = features.get(e["slug"], NO_REACH)
        legacy = e["legacy"]
        items.append({
            "id": n + 1,
            "slug": e["slug"],
            "kind": e["kind"],
            "entityType": e["entity_type"],
            "row": e["row"],
            "sheet": {"tab": "intrari", "row": e["row"]} if v1_rows is None else v1_rows.get(e["slug"]),
            "civictech": e["civictech"] == "1",
            "name": e["nume"],
            "tagline": e["descriere_scurta"],
            "desc": o["desc"],
            "descSrc": o["descSrc"],
            "primarySubject": e["primary_subject"],
            "subjects": e["subjects"],
            "topics": e["topics"],
            "purposes": e["purposes"],
            "capabilities": e["capabilities"],
            "formats": e["formats"],
            "technologies": e["technologies"],
            "institutions": e["institutions"],
            "organisationTypes": e["organisation_types"],
            "maturity": e["maturity"],
            "coverageLevel": e["coverage_level"],
            "areas": e["areas"],
            # Unresolved roles stay neutral: `role` is the predicate, `accepted` says whether an editor confirmed it.
            "attributions": [{"name": a["name"], "org": a["slug"] if a["slug"] in pkg.entries else "", "role": a["predicate"],
                              "accepted": a["state"] == "acceptat"} for a in e["attributions"]],
            "links": o["links"],
            "url": o["url"],
            "domain": o["domain"],
            "movedFrom": o["movedFrom"],
            "code": o["code"],
            **({"repo": o["repo"]} if o["repo"] else {}),
            "contact": e["contact"],
            "status": o["status"],
            "httpStatus": o["live"].get("http_status"),
            "checked": (p.get("fetched_at") or "")[:10],
            "since": since(p)[0],
            "sinceSrc": since(p)[1],
            "updated": p.get("updated", ""),
            "updatedSrc": p.get("updated_src", ""),
            "stale": o["stale"],
            "score": score(e, p, o["alive"], o["desc"], o["img"], reach, bool(e["primary_subject"])),
            "reach": reach,
            "img": o["img"],
            "icon": o["live"].get("icon", ""),
            "wayback": o["wayback"],
            # The original v1 classification, only to interpret old bookmarks (?d=, ?t=, ?kw=, ?c=) with their v1 meaning.
            "legacy": {"domeniu": legacy.get("domeniu", ""), "tips": split_tip(legacy.get("tip", "")),
                       "keywords": keywords(legacy.get("cuvinte", ""), legacy_tax["cuvinte"]), "fel": legacy.get("fel", ""),
                       "acoperire": legacy.get("acoperire", "") or "national", "oras": legacy.get("oras", "")} if legacy else {},
        })
    items.sort(key=lambda x: re.sub(r"[^a-z0-9]", "", x["name"].lower()))

    # Only the concepts and areas that some entry uses, plus their broader concepts: unused choices stay hidden.
    used = {c for i in items for f in ("subjects", "topics", "purposes", "capabilities", "formats", "technologies", "institutions",
                                        "organisationTypes") for c in i[f]} | {i["maturity"] for i in items if i["maturity"]}
    used |= {a for c in list(used) for a in pkg.ancestors(c)}
    areas = {a for i in items for a in i["areas"]}
    todo = list(areas)
    while todo:
        parent = pkg.areas[todo.pop()]["parinte"]
        for a in filter(None, parent.split("|")):
            if a not in areas:
                areas.add(a)
                todo.append(a)
    code_list = lambda lst: [{"key": k, "label": r["eticheta_ro"], "labelEn": r["eticheta_en"]}
                             for k, r in pkg.codes.get(lst, {}).items() if r["statut"] != "retras"]
    head = {
        "schemaVersion": pkg.version,
        # Proposed classifications reach the page only in an --allow-draft preview, which says so.
        "draft": any(e["clasificare_stare"] != "acceptat" for e in pkg.entries.values()),
        "vocabulary": {
            "schemes": code_list("concept_schema"),
            "concepts": [{"id": c["id"], "scheme": c["schema"], "label": c["eticheta_ro"], "labelEn": c["eticheta_en"],
                          "alt": [a for a in c["alternative_ro"].split("|") if a], "def": c["definitie_ro"],
                          "broader": [b for b in c["mai_larg"].split("|") if b]} for c in pkg.concepts.values() if c["id"] in used],
            "subjectOrder": [c["id"] for c in subject_groups(pkg)],
            "areas": [{"id": a["id"], "label": a["eticheta_ro"], "type": a["tip"], "parent": a["parinte"]}
                      for a in pkg.areas.values() if a["id"] in areas],
            "kinds": [{"key": s["key"], "label": s["label"]} for s in pkg.sections()],
            "entityTypes": code_list("tip_entitate"),
            "coverage": code_list("nivel_acoperire"),
            "predicates": code_list("relatie_predicat"),
        },
        "legacyTaxonomy": {k: legacy_tax[k] for k in ("domenii", "tipuri", "fel", "acoperire")},
        "site": site_cfg,
    }
    return items, head


ARCHIVE_LEAD_V2 = {**ARCHIVE_LEAD, "proiect": "{n} proiecte civic tech din România, pe subiecte."}
# The "classifications are proposals" note in the archives and llms.txt; hidden for now. site-v2/app.js has its own switch.
DRAFT_NOTE = False
NO_SUBJECT = ("Fără subiect stabilit", "clasificare incompletă: sursele nu stabilesc subiectul")


def pages_v2(items: list[dict], head: dict, site: Path) -> tuple[str, int]:
    """llms.txt and the archives of a v2 build: projects grouped by primary subject (each entry once), the other
    kinds A-Z; the grey line names the entity type, a format, the local areas and the other subjects."""
    v = head["vocabulary"]
    label = {c["id"]: c["label"] for c in v["concepts"]} | {a["id"]: a["label"] for a in v["areas"]}
    ent = {t["key"]: t["label"] for t in v["entityTypes"]}
    order = v["subjectOrder"]

    def hint(rows: list[dict]) -> str:
        # The group's most frequent topics, in the style of the v1 domain hints ("buget, achiziții, ...").
        top = Counter(t for i in rows for t in i["topics"]).most_common(4)
        return ", ".join(l[0].lower() + l[1:] if l[1:2].islower() else l for l in (label[t] for t, _ in top))
    by_subject = lambda rows: [(label[s], hint([i for i in rows if i["primarySubject"] == s]), [i for i in rows if i["primarySubject"] == s]) for s in order] + [
        (NO_SUBJECT[0], NO_SUBJECT[1], [i for i in rows if not i["primarySubject"]])]

    def meta(i: dict) -> str:
        kind_label = ent[i["entityType"]] if i["entityType"] not in (i["kind"], "organizatie") else ""
        local = [label[a] for a in i["areas"] if a.split(":")[0] in ("localitate", "judet")]
        others = [label[s] for s in i["subjects"] if s != i["primarySubject"]]
        parts = [kind_label, *(label[f] for f in i["formats"][:1]), *local, f"și: {', '.join(others)}" if others else ""]
        return " · ".join(dict.fromkeys(p for p in parts if p))

    def groups(kind: str, mine: list[dict]):
        return [(t, h, rows) for t, h, rows in by_subject(mine)] if kind == "proiect" else [("", "", mine)]

    note = "Previzualizare: clasificările sunt propuneri, încă neacceptate." if head["draft"] and DRAFT_NOTE else ""
    archives = write_archives(items, {k["key"]: k["label"] for k in v["kinds"]}, groups, meta, site, ARCHIVE_LEAD_V2, note)
    projects = [i for i in items if i["kind"] == "proiect"]
    res = [i for i in items if i["kind"] == "resursa"]
    sections = [(f"Proiecte: {t}", rows) for t, _, rows in by_subject(projects)]
    sections.append(("Organizații", [i for i in items if i["kind"] == "organizatie"]))
    sections += [(f"Resurse: {t['label']}", [i for i in res if i["entityType"] == t["key"]]) for t in v["entityTypes"]]
    sources = f"- [intrari.csv]({REPO_URL}/blob/main/data/taxonomy-v2/intrari.csv): tabelul editat de om (propunere v2)\n"
    return llms_doc(items, sections, sources, f" {note}" if note else ""), archives


def prepare_site(site: Path, v2: bool):
    """Copy the template, assets and images of site/ into a separate output folder (and the v2 browser code over them),
    so that the build there never changes site/. Refuse a folder that holds something other than a site."""
    if site.exists() and any(site.iterdir()) and not (site / "index.html").exists():
        raise SystemExit(f"{site} is not empty and has no index.html; choose a new or a previous output folder")
    if site.is_relative_to(ROOT):
        raise SystemExit(f"{site}: write a separate build outside the repository")
    site.mkdir(parents=True, exist_ok=True)
    for src in SITE.iterdir():
        if src.name in GENERATED:
            continue
        if src.is_dir():
            shutil.copytree(src, site / src.name, dirs_exist_ok=True)
        else:
            shutil.copy2(src, site / src.name)
    if v2:
        for src in SITE_V2.iterdir():
            shutil.copy2(src, site / src.name)
        index = site / "index.html"
        doc = index.read_text(encoding="utf-8")
        if 'href="v2.css' not in doc:
            link = re.search(r'<link rel="stylesheet" href="style\.css[^"]*">', doc).group(0)
            index.write_text(doc.replace(link, link + '\n<link rel="stylesheet" href="v2.css">'), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DATA, help="data root (default: data/)")
    parser.add_argument("--site-dir", type=Path, default=SITE, help="output folder (default: site/)")
    parser.add_argument("--allow-draft", action="store_true", help="v2 preview: allow proposed classifications")
    args = parser.parse_args()
    data_dir, site = args.data_dir.resolve(), args.site_dir.resolve()
    v2 = data_schema(data_dir) == "v2"
    if v2:
        import taxonomy_v2
        if site == SITE:
            raise SystemExit("a v2 build writes to a separate --site-dir until the source cutover; site/ stays the v1 site")
        errors, _ = taxonomy_v2.check(data_dir, publication=not args.allow_draft)
        if errors:
            print("\n".join(errors[:20]), file=sys.stderr)
            hint = "" if args.allow_draft else " (a preview of proposed classifications needs --allow-draft)"
            raise SystemExit(f"{len(errors)} errors in {data_dir}{hint}")
    elif args.allow_draft:
        parser.error("--allow-draft applies to a v2 data root")
    if site != SITE:
        prepare_site(site, v2)
    items, head = (items_v2 if v2 else items_v1)(data_dir, site)
    checked = sorted({i["checked"] for i in items if i["checked"]})
    now = datetime.now(timezone.utc)
    out = {"generated": now.isoformat(timespec="seconds"), "checked": checked[-1] if checked else ""}
    if v2:
        out = {"schemaVersion": head.pop("schemaVersion"), **out}
    out |= {**head, "items": items}
    (site / "data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    by = {}
    for i in items:
        by[i["status"]] = by.get(i["status"], 0) + 1
    (site / "feed.xml").write_text(feed(items, now))
    stamp_assets(site)
    if v2:
        pages = entry_pages(items, site)
        llms, archives = pages_v2(items, out, site)
    else:
        llms = llms_txt(items, head["taxonomy"])
        pages = entry_pages(items, site)
        archives = archive_pages(items, head["taxonomy"], site)
    (site / "llms.txt").write_text(llms, encoding="utf-8")
    where = site.relative_to(ROOT) if site.is_relative_to(ROOT) else site
    obs = observation_paths(data_dir)
    coverage = label_coverage(load_mentions(obs["mentions"]), read_csv(obs["labels"]) if obs["labels"].exists() else [])
    print(f"wrote {len(items)} entries to {where}/data.json  {by}; {where}/feed.xml; {where}/llms.txt; {pages} entry pages and "
          f"{archives} archives in {where}/{{{','.join(PAGE_KINDS)}}}/" + (f"  [{out['schemaVersion']}{', draft' if out['draft'] else ''}]" if v2 else "")
          + f"; {coverage_line(coverage)}")


if __name__ == "__main__":
    main()
