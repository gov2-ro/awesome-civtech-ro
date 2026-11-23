"""The entry view as static HTML, and the structured data (JSON-LD) of an entry page.

`build.py` calls `entry_view()` and `json_ld()` for every entry. The markup uses the elements and the classes of the
entry view in site/app.js (`entryHTML`, `tocHTML`, `factsHTML`), so that the page does not jump when app.js renders over
it. Keep the two in step. Decisions 15 and 16 of docs/briefs/entry-page.md say what the page holds.

Paths are relative to the site root: an entry page carries `<base href="../../">`.
"""
import html
import json
import re
import unicodedata
from datetime import date
from urllib.parse import quote, urlencode, urlsplit

SITE_URL = "https://civtech.gov2.ro/"
FRESH_DAYS, NEWEST_DAYS = 183, 60  # as in app.js
STATUS = {"activ": ("Activ", "ok", "activ"), "offline": ("Offline", "bad", "inactiv"), "arhivat": ("Arhivat", "bad", "inactiv"),
          "necunoscut": ("Neconfirmat", "warn", "neconfirmat"), "neverificat": ("Neverificat", "warn", "neconfirmat")}
RANK = {"activ": 0, "neconfirmat": 1, "inactiv": 2}
DETAIL_LABELS = {"agregat-national": "Totaluri naționale", "judete": "Pe județe", "localitati": "Pe localități", "judete-localitati": "Pe județe și localități"}
UPDATED_SRC = {"cod": "ultimul push în depozitul de cod", "feed": "cel mai nou articol din feed", "wordpress": "ultima modificare în WordPress",
               "sitemap": "sitemap", "server": "antetul Last-Modified", "arhiva": "ultima arhivare Wayback"}
SINCE_SRC = {"arhiva": "prima arhivare Wayback", "cod": "crearea depozitului de cod", "certificat": "primul certificat TLS al domeniului"}
LD_TYPE = {"proiect": "WebApplication", "resursa": "CreativeWork", "publicatie": "Report"}  # an organisation: NGO or Organization


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def norm(s) -> str:
    return unicodedata.normalize("NFD", str(s or "").lower()).encode("ascii", "ignore").decode()


def sort_key(i: dict) -> str:
    """app.js `_sort`: the name without accents, spaces and punctuation."""
    return re.sub(r"[^a-z0-9]", "", norm(i["name"]))


def network_paths(app_js: str) -> dict[str, str]:
    """The logo paths of `NETWORK` in app.js, so that the static page and the browser draw the same logos."""
    block = re.search(r"const NETWORK = \{(.*?)\n\};", app_js, re.S)
    return dict(re.findall(r"^\s+(\w+): '([^']+)',?$", block.group(1), re.M)) if block else {}


class Context:
    """What the entry pages share: the labels, the entries by slug, and the left list of each section."""

    def __init__(self, items: list[dict], head: dict, app_js: str = "", today: date | None = None):
        v = head["vocabulary"]
        self.items = items
        self.today = today or date.today()
        self.site = head.get("site") or {}
        self.by = {i["slug"]: i for i in items}
        self.concept = {c["id"]: c for c in v["concepts"]}
        self.label = {c["id"]: c["label"] for c in v["concepts"]} | {a["id"]: a["label"] for a in v["areas"]}
        self.kinds = {k["key"]: k["label"] for k in v["kinds"]}
        self.ent = {e["key"]: e["label"] for e in v["entityTypes"]}
        self.cov = {c["key"]: c["label"] for c in v["coverage"]}
        self.pred = {p["key"]: p["label"] for p in v["predicates"]}
        self.relations = {d["key"]: d["label"] for d in v.get("dataRelations", [])}
        self.subject_order = v["subjectOrder"]
        self.network = network_paths(app_js)
        self.children = {i["slug"]: sorted((c for c in items if any(a["role"] == "parte_din" and a["org"] == i["slug"] for a in c["attributions"])), key=self.order)
                         for i in items}
        self.lists = {k: self.section_list(k) for k in self.kinds}

    # ---- order, as the list view sorts it (app.js `rank`, `lastSign`, `sorted`) ----
    def group(self, i: dict) -> str:
        return STATUS.get(i["status"], STATUS["neverificat"])[2]

    def order(self, i: dict):
        return (RANK[self.group(i)], sort_key(i))

    def last_sign(self, i: dict) -> str:
        fresh = i["since"] and (self.today - date.fromisoformat(i["since"])).days < NEWEST_DAYS
        return max(i["updated"] or "", i["since"] if fresh else "")

    def sorted_default(self, kind: str, rows: list[dict]) -> list[dict]:
        if kind == "proiect":  # the sort `subiect`: the default of the projects tab
            by_name = sorted(rows, key=sort_key)
            by_sign = sorted(by_name, key=lambda i: self.last_sign(i), reverse=True)
            return sorted(by_sign, key=lambda i: RANK[self.group(i)])
        return sorted(rows, key=self.order)

    def section_list(self, kind: str) -> list[tuple[str, list[dict]]]:
        """The left list of a section: no filters, the default grouping. Inactive entries come last in each group."""
        rows = [i for i in self.items if i["kind"] == kind]
        if kind != "proiect":
            return [("", self.sorted_default(kind, rows))]
        groups = [(self.label[s], self.sorted_default(kind, [i for i in rows if i["primarySubject"] == s])) for s in self.subject_order]
        groups.append(("Fără subiect stabilit", self.sorted_default(kind, [i for i in rows if not i["primarySubject"]])))
        return [(g, xs) for g, xs in groups if xs]

    # ---- relations ----
    def author_keys(self, i: dict) -> list[str]:
        return [a["org"] or norm(a["name"]) for a in i["attributions"] if a["role"] != "parte_din"]

    def same_author(self, i: dict) -> list[dict]:
        keys = [i["slug"]] if i["kind"] == "organizatie" else self.author_keys(i)
        return sorted((o for o in self.items if o is not i and o["kind"] != "organizatie" and any(k in keys for k in self.author_keys(o))), key=self.order)

    def subject_set(self, i: dict) -> set[str]:
        """The values the `subj` filter matches for an entry: its subjects, its topics, and their broader concepts."""
        out = set(i["subjects"]) | set(i["topics"])
        todo = [b for t in i["topics"] for b in self.concept.get(t, {}).get("broader", [])]
        while todo:
            b = todo.pop()
            if b not in out:
                out.add(b)
                todo += self.concept.get(b, {}).get("broader", [])
        return out

    def related(self, i: dict, skip: list[dict]) -> list[dict]:
        subject = i["primarySubject"]
        if not subject:
            return []
        rows = [o for o in self.items if o["kind"] == i["kind"] and o is not i and subject in self.subject_set(o) and self.group(o) != "inactiv" and o not in skip]
        shared = lambda o: len([t for t in o["topics"] if t in i["topics"]])
        return sorted(rows, key=lambda o: (o["primarySubject"] != subject, -shared(o), sort_key(o)))[:6]

    def is_fresh(self, i: dict, days: int) -> bool:
        return bool(i["since"]) and (self.today - date.fromisoformat(i["since"])).days < days


# ---- small pieces ----
def href(i: dict) -> str:
    return f"{i['kind']}/{i['slug']}/"


def list_href(kind: str, extra: str = "") -> str:
    return f"?k={kind}{extra}"


def filter_href(kind: str, key: str, val: str) -> str:
    return list_href(kind, f"&{key}={quote(val, safe='')}")


def nav_link(url: str, text: str, cls: str = "", attrs: str = "") -> str:
    klass = f' class="{cls}"' if cls else ""
    return f'<a{klass}{attrs} href="{esc(url)}" data-nav>{text}</a>'


def host_of(url: str) -> str:
    return re.sub(r"/$", "", re.sub(r"^https?://(www\.)?", "", url))


def blurb(i: dict) -> str:
    return i["tagline"] or i["desc"] or ""


def thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def status_dot(i: dict) -> str:
    label, cls, _ = STATUS.get(i["status"], STATUS["neverificat"])
    return f'<span class="dot {cls}" title="{label}"></span>'


def toc_html(i: dict, ctx: Context) -> str:
    def item(o: dict) -> str:
        off = " off" if ctx.group(o) == "inactiv" else ""
        current = ' aria-current="page"' if o is i else ""
        icon = f'<img src="{esc(o["icon"])}" alt="" width="20" height="20" loading="lazy">' if o["icon"] else '<i class="blank"></i>'
        return f'<a class="toc-it{off}" href="{esc(href(o))}" data-open="{esc(o["slug"])}"{current}>{icon}<span>{esc(o["name"])}</span></a>'

    body = "".join((f'<p class="toc-h">{esc(g)} · {len(xs)}</p>' if g else "") + "".join(item(o) for o in xs) for g, xs in ctx.lists[i["kind"]])
    back = nav_link(list_href(i["kind"]), "← filtre", "", ' title="Înapoi la lista cu filtre"')
    top = f'<div class="toc-top">{back}<button class="toc-close" type="button" data-act="toc-close">Închide</button></div>'
    return top + body


def class_html(i: dict, ctx: Context) -> str:
    def chip(key: str, cid: str, main: bool = False) -> str:
        d = ctx.concept.get(cid, {}).get("def")
        return nav_link(filter_href(i["kind"], key, cid), esc(ctx.label.get(cid, cid)), "p-chip" + (" main" if main else ""), f' title="{esc(d)}"' if d else "")
    others = [s for s in i["subjects"] if s != i["primarySubject"]]
    cap_title = "Activități" if i["kind"] == "organizatie" else "Ce poți face"
    rows = [("Subiect", "subj", [i["primarySubject"]] if i["primarySubject"] else []), ("Alte subiecte", "subj", others), ("Teme", "subj", i["topics"]),
            ("Instituții vizate", "inst", i["institutions"]), (cap_title, "cap", i["capabilities"]), ("Format", "fmt", i["formats"]),
            ("Tehnologie", "tech", i["technologies"]), ("Tip", "orgt", i["organisationTypes"]), ("Scop civic", "purpose", i["purposes"])]
    out = [f"<dt>{t}</dt><dd>{''.join(chip(k, c, c == i['primarySubject']) for c in ids)}</dd>" for t, k, ids in rows if ids]
    if i["maturity"]:
        out.append(f'<dt>Maturitate</dt><dd><span class="p-chip plain">{esc(ctx.label.get(i["maturity"], i["maturity"]))}</span></dd>')
    if not i["primarySubject"]:
        out.insert(0, '<dt>Clasificare</dt><dd><span class="muted">Sursele disponibile nu stabilesc încă subiectul acestei intrări.</span></dd>')
    if not out:
        return ""
    return f'<section class="p-sec"><h2>Clasificare</h2><dl class="p-class">{"".join(out)}</dl><p class="p-note">Fiecare etichetă deschide lista cu aceeași etichetă.</p></section>'


def author_link(a: dict, ctx: Context) -> str:
    o = ctx.by.get(a["org"]) if a["org"] else None
    return f'<a href="{esc(href(o))}" data-open="{esc(o["slug"])}">{esc(o["name"])}</a>' if o else f'<a href="?{urlencode({"autor": a["name"]})}" data-nav title="Toate lucrările acestui autor">{esc(a["name"])}</a>'


def author_rows(i: dict, ctx: Context) -> list[tuple[str, str]]:
    groups: dict[str, list] = {}
    for a in (a for a in i["attributions"] if a["role"] != "parte_din"):
        groups.setdefault(ctx.pred.get(a["role"], a["role"]) if a["accepted"] else "Autor", []).append(a)
    rows = [(head, " · ".join(author_link(a, ctx) for a in as_) + (' <span class="muted small">· rol neconfirmat</span>' if head == "Autor" else "")) for head, as_ in groups.items()]
    parents = [a for a in i["attributions"] if a["role"] == "parte_din"]
    return rows + ([("Parte din", " · ".join(author_link(a, ctx) for a in parents))] if parents else [])


def link_one(l: dict, ctx: Context) -> str:
    open_ = f'href="{esc(l["url"])}" target="_blank" rel="noopener"'
    path = ctx.network.get(l["role"])
    if path:
        return (f'<a class="net" {open_} title="{esc(l["label"])}" aria-label="{esc(l["label"])}">'
                f'<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="{path}"/></svg></a>')
    fav = f'<img class="fav" src="{esc(l["icon"])}" alt="" width="14" height="14" loading="lazy">' if l.get("icon") else ""
    text = re.sub(r"^https?://(www\.)?", "", l["url"]) if l["role"] == "web" else l["label"]
    return f'<a class="lk" {open_} title="{esc(l["url"])}">{fav}{esc(text)}</a>'


def link_row(title: str, links: list[dict], ctx: Context):
    if not links:
        return None
    ordered = sorted(links, key=lambda l: l["role"] not in ctx.network)
    return title, f'<span class="p-links">{"".join(link_one(l, ctx) for l in ordered)}</span>'


def code_link(url: str, ctx: Context) -> str:
    m = re.match(r"^https?://(?:www\.)?(github|gitlab)\.com/(.+?)/?$", url, re.I)
    text = m.group(2) if m else re.sub(r"^https?://(www\.)?", "", url)
    logo = f'<svg class="forge" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="{ctx.network.get(m.group(1).lower(), "")}"/></svg>' if m else ""
    title = f' title="{"GitLab" if m.group(1).lower() == "gitlab" else "GitHub"}"' if m else ""
    return f'<a class="code-link" href="{esc(url)}" target="_blank" rel="noopener"{title}>{logo}{esc(text)}</a>'


def repo_row(i: dict, ctx: Context):
    r = i.get("repo")
    if not r:
        return None
    count = lambda v, one, many: "" if v is None else f"{thousands(v)} {one if v == 1 else many}"
    parts = [f"★ {thousands(r['stars'])}" if r.get("stars") is not None else "", count(r.get("forks"), "fork", "forks"), count(r.get("issues"), "issue", "issues"),
             count(r.get("commits"), "commit", "commits"), count(r.get("contributors"), "contribuitor", "contribuitori"),
             f"ultimul commit {r['last']}" if r.get("last") else "", r.get("language") or "", "arhivat" if r.get("archived") else ""]
    parts = [esc(p) for p in parts if p]
    if not (i["code"] and i["code"].rstrip("/").lower() == r["url"].lower()):
        parts.insert(0, f'<a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["name"])}</a>')
    return "Cod", f'<span class="repo mono">{" · ".join(parts)}</span>'


def flag_html(i: dict, ctx: Context) -> str:
    site, sheet = ctx.site, i.get("sheet") or {}
    tab, row = sheet.get("tab"), sheet.get("row")
    enc = lambda s: quote(s, safe="-_.!~*'()")
    subject = enc(f"Problemă la „{i['name']}” ({i['slug']})")
    where = f"În tabel: fila {tab}, rândul {row}\n" if tab else ""
    body = enc(f"Pagina: {SITE_URL}{href(i)}\n{where}\nCe nu e corect sau lipsește?\n")
    opts = []
    if site.get("sheet") and tab and (site.get("tabs") or {}).get(tab) is not None:
        opts.append((f"{site['sheet']}#gid={site['tabs'][tab]}&range=A{row}", "Corectează în tabel", f"Deschide rândul {row} din fila „{tab}”. Modifici direct; schimbarea e verificată înainte să apară pe site."))
    if site.get("email"):
        opts.append((f"mailto:{site['email']}?subject={subject}&body={body}", "Trimite un e-mail", "Mesajul pornește cu numele și adresa paginii."))
    if site.get("issues"):
        opts.append((f"{site['issues']}?title={subject}&body={body}", "Deschide o problemă pe GitHub", "Cere cont GitHub; discuția e publică."))
    if not opts:
        return ""
    lis = "".join(f'<li><a href="{esc(h)}" target="_blank" rel="noopener">{label}</a><span>{esc(note)}</span></li>' for h, label, note in opts)
    return (f'<details class="flag"><summary>Semnalează o problemă</summary><p>Ceva lipsește sau nu e corect aici? Alege varianta care îți vine mai la îndemână:</p><ul>{lis}</ul></details>')


def source_groups(sources: list[dict]) -> list[dict]:
    """One group per source name. (The browser also folds some providers into one short label; the page keeps the names.)"""
    groups: dict[str, dict] = {}
    for s in sources:
        g = groups.setdefault(s["name"], {"name": s["name"], "evidence": []})
        if s["evidence"] not in g["evidence"]:
            g["evidence"].append(s["evidence"])
    return list(groups.values())


def facts_html(i: dict, ctx: Context) -> str:
    alive = ctx.group(i) != "inactiv"
    label, _, _ = STATUS.get(i["status"], STATUS["neverificat"])
    place = ("necunoscută" if i["coverageLevel"] == "necunoscut" and not i["areas"] else
             " · ".join([x for x in [esc(ctx.cov.get(i["coverageLevel"], "")),
                                      *(nav_link(filter_href(i["kind"], "area", a), esc(ctx.label.get(a, a))) for a in i["areas"])] if x]))
    site_row = None
    if i["url"]:
        site_row = ("Site", (f'<a href="{esc(i["url"])}" target="_blank" rel="noopener">{esc(i["domain"])}</a>' if alive else f'<span class="muted">{esc(i["domain"])}</span>')
                    + (f' <span class="muted small">(mutat de pe {esc(i["movedFrom"])})</span>' if i["movedFrom"] else ""))
    sources = ", ".join(
        f'<span class="p-src">{nav_link(filter_href(i["kind"], "source", s["name"]), esc(s["name"]))}'
        + "".join(f'<a class="ev" href="{esc(u)}" target="_blank" rel="noopener" title="Dovada sursei" aria-label="Dovada sursei {esc(s["name"])}">↗</a>' for u in s["evidence"]) + "</span>"
        for s in source_groups(i["dataSources"]))
    since_src = SINCE_SRC.get(i["sinceSrc"], i["sinceSrc"])
    http = f" · HTTP {i['httpStatus']}" if i.get("httpStatus") else ""
    rows = [*author_rows(i, ctx), site_row,
            link_row("Linkuri", [l for l in i["links"] if l["src"] == "manual"], ctx), link_row("Găsite pe site", [l for l in i["links"] if l["src"] == "site"], ctx),
            ("Cod sursă", code_link(i["code"], ctx)) if i["code"] else None, repo_row(i, ctx),
            ("Licență", esc(i.get("repo")["license"])) if i.get("repo") and i.get("repo").get("license") else None,
            ("Contact", esc(i["contact"])) if i["contact"] else None, ("Acoperire", place),
            ("Detaliere date", f'<a href="{esc(i["dataDetailEvidence"])}" target="_blank" rel="noopener">{esc(DETAIL_LABELS.get(i["dataDetail"], i["dataDetail"]))}</a>') if i["dataDetail"] else None,
            ("Date", esc(ctx.relations.get(i["dataRelation"], i["dataRelation"]))) if i["dataRelation"] else None,
            ("Surse de date", sources) if i["dataSources"] else None,
            ("Arhivă", f'<a href="{esc(i["wayback"])}" target="_blank" rel="noopener">Wayback Machine</a>') if i["wayback"] else None,
            ("Prima urmă", f'{esc(i["since"])} <span class="muted small mono">· după {esc(since_src)}</span> <span class="muted small">· nu este data lansării</span>') if i["since"] else None,
            ("Actualizat", f'{esc(i["updated"])} <span class="muted small mono">· după {esc(UPDATED_SRC.get(i["updatedSrc"], i["updatedSrc"]))}</span>') if i["updated"] else None,
            ("Stare", f'{status_dot(i)} {label}' + (f' <span class="muted small">· niciun semn de actualizare după {esc(i["stale"])}</span>' if i["stale"] else "")
             + (f' <span class="muted small mono">· verificat {esc(i["checked"])}{http}</span>' if i["checked"] else ""))]
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in (r for r in rows if r))
    return f'<aside class="p-facts" aria-label="Date despre intrare"><div class="box"><dl>{dl}</dl></div>{flag_html(i, ctx)}</aside>'


def card_html(o: dict) -> str:
    img = f'<img src="{esc(o["icon"])}" alt="" width="40" height="40" loading="lazy">' if o["icon"] else '<i class="blank"></i>'
    return f'<a class="p-card{" off" if o["status"] in ("offline", "arhivat") else ""}" href="{esc(href(o))}" data-open="{esc(o["slug"])}">{img}<b>{esc(o["name"])}</b><span>{esc(blurb(o))}</span></a>'


def cards_section(title: str, rows: list[dict]) -> str:
    return f'<section class="p-sec"><h2>{title} ({len(rows)})</h2><div class="p-cards">{"".join(card_html(o) for o in rows)}</div></section>' if rows else ""


def ro_plural(n: int, one: str, many: str) -> str:
    """`1 câmp`, `5 câmpuri`, `20 de câmpuri`: the Romanian count phrase, as `plural` in site/app.js."""
    return f"1 {one}" if n == 1 else f"{n}{' de' if n % 100 >= 20 or n % 100 == 0 else ''} {many}"


def host_text(url: str) -> str:
    """The host of an address, as `new URL(url).hostname` in site/app.js gives it; the whole text when it is no address."""
    try:
        return urlsplit(url).hostname or url
    except ValueError:
        return url


def dataset_card(c: dict, level: int = 4) -> str:
    """One data-set card (docs/specs/data-set-card.md, section 1) as HTML: the set, then the provider, the record, the period and the access on one line, the identifiers with
    their role, the key variables, the method note, and the basis, the date and the evidence. `level` is the heading level of the set name. Paths are relative to the `<base>` of
    the page, as on the entry page and on `/date/<slug>/`. The same card is on the entry page ("Date & metodă") and on `/date/<slug>/` ("Seturi de date");
    `datasetCard` in site/app.js writes the same markup (with the site root before each path)."""
    provider = c["provider"]
    name = esc(provider["name"])
    provider_html = f'<a href="date/furnizori/#{esc(provider["anchor"])}">{name}</a>' if provider["anchor"] else name
    access = ", ".join(f'<a href="{esc(a["url"])}" target="_blank" rel="noopener">{esc(a["label"])}</a>' if a["url"] else esc(a["label"]) for a in c["access"])
    # The grain repeats the record when its label is in the record text („o achiziție directă” / „Achiziție directă”); it shows only when it adds something.
    grain = f' <small>({esc(c["grain"]["label"])})</small>' if c["grain"] and c["grain"]["label"].casefold() not in c["record"].casefold() else ""
    facts = [f"<span>furnizor: {provider_html}</span>", f"<span>o înregistrare: {esc(c['record'])}{grain}</span>",
             f"<span>perioada: {esc(c['period']) if c['period'] else 'nedeclarată'}</span>"]
    if access:
        facts.append(f"<span>acces: {access}</span>")
    lines = [f'<p class="ds-line">{" · ".join(facts)}</p>']
    if c["identifiers"]:
        ids = " · ".join(f'<span>{esc(x["codeLabel"])} ({esc(x["roleLabel"] or x["namespace"])})</span>' for x in c["identifiers"])
        lines.append(f'<p class="ds-line">Identificatori: {ids}</p>')
    if c["keyVariables"]:
        keys = ", ".join(f'<span>{esc(k["label"])}</span>' for k in c["keyVariables"])
        lines.append(f'<p class="ds-line">Variabile principale: {keys}</p>')
    if c["methodNote"]:
        lines.append(f'<p class="ds-note">Metodă: {esc(c["methodNote"])}</p>')
    meta = ([f"bază: {esc(c['basisLabel'])}"] if c["basisLabel"] else []) + ([f"verificat la {esc(c['checked'])}"] if c["checked"] else [])
    evidence = ", ".join(f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(host_text(u))}</a>' for u in c["evidence"])
    if evidence:
        meta.append(f"dovadă: {evidence}")
    if meta:
        lines.append(f'<p class="ds-meta">{" · ".join(meta)}</p>')
    return f'<article class="ds-card" id="set-{esc(c["id"])}"><h{level}>{esc(c["set"])}</h{level}>{"".join(lines)}</article>'


def dataset_cards(cards: list[dict], level: int = 4) -> str:
    return f'<div class="ds-cards">{"".join(dataset_card(c, level) for c in cards)}</div>'


def data_summary(i: dict) -> str:
    """The static form of "Date & metodă": the count, the examples and a link to the data page (the browser loads the inventory on demand).
    An entry with an accepted card shows the cards first, then the link "Vedere tehnică"; the count and the examples stay under it. An entry without a card has the panel
    that it had before the cards."""
    inv = i.get("inventory")
    cards = i.get("datasets") or []
    counted = bool(inv and inv.get("count"))
    examples = "".join(f"<span><code>{esc(e)}</code></span>" for e in ((inv or {}).get("examples") or []))
    if not cards:
        if not counted:
            return ""
        page = f'<p class="inv-all"><a href="{esc(inv["page"])}">Toate variabilele <span aria-hidden="true">→</span></a></p>' if inv.get("page") else ""
        return (f'<section class="d-inventory" data-inventory-root="{esc(i["slug"])}"><div class="inv-heading"><h3>Date &amp; metodă</h3><span class="inv-status">Inventar parțial</span></div>'
                f'<p class="inv-intro">{inv["count"]} câmpuri și parametri · {inv["sources"]} fișiere consultate</p>'
                f'<p class="inv-note">Extrase automat din sursele de mai jos. Proiectul poate folosi și alte date.</p><div class="inv-examples">{examples}</div>{page}</section>')
    tech = ""
    if inv and inv.get("page"):
        tech = (f'<p class="inv-all inv-tech"><a href="{esc(inv["page"])}">Vedere tehnică: {ro_plural(inv["count"], "câmp", "câmpuri")} din '
                f'{ro_plural(inv["sources"], "document", "documente")} <span aria-hidden="true">→</span></a></p>')
    status = '<span class="inv-status">Inventar parțial</span>' if counted else ""
    intro = "" if tech else f'<p class="inv-intro">{inv["count"]} câmpuri și parametri · {inv["sources"]} fișiere consultate</p>'  # the link „Vedere tehnică” already counts them
    body = (intro + f'<p class="inv-note">Extrase automat din sursele de mai jos. Proiectul poate folosi și alte date.</p><div class="inv-examples">{examples}</div>') if counted else ""
    return (f'<section class="d-inventory" data-inventory-root="{esc(i["slug"])}"><div class="inv-heading"><h3>Date &amp; metodă</h3>{status}</div>'
            f'{dataset_cards(cards)}{tech}{body}</section>')


def sheet_html(i: dict, ctx: Context) -> str:
    kind_label = ctx.kinds[i["kind"]]
    subject = ctx.label.get(i["primarySubject"], "") if i["primarySubject"] else ""
    alive = ctx.group(i) != "inactiv"
    label, _, _ = STATUS.get(i["status"], STATUS["neverificat"])
    flat = [o for _, xs in ctx.lists[i["kind"]] for o in xs]
    at = flat.index(i)
    prev, nxt = (flat[at - 1] if at else None), (flat[at + 1] if at + 1 < len(flat) else None)
    parts = ctx.children[i["slug"]]
    works = [o for o in ctx.same_author(i) if o not in parts]
    related = ctx.related(i, parts + works)
    step = lambda o, cls, small: f'<a{cls} href="{esc(href(o))}" data-open="{esc(o["slug"])}"><small>{small}</small>{esc(o["name"])}</a>' if o else "<span></span>"
    ent = ctx.ent.get(i["entityType"], "") if i["entityType"] not in (i["kind"], "organizatie") else ""
    local = ("Local" if i["coverageLevel"] == "local" and not [a for a in i["areas"] if re.match(r"^(localitate|judet):", a)]
             else ", ".join(ctx.label.get(a, a) for a in i["areas"] if re.match(r"^(localitate|judet):", a))) if i["coverageLevel"] == "local" else ""
    badges = "".join([f"<span>{status_dot(i)}{label}</span>", f"<span>{esc(ent)}</span>" if ent else "", f"<span>{esc(local)}</span>" if local else "",
                      f'<span class="new{" launch" if ctx.is_fresh(i, NEWEST_DAYS) else ""}">apărut recent</span>' if ctx.is_fresh(i, FRESH_DAYS) else "",
                      '<span><svg viewBox="0 0 24 24"><path d="m8 7-5 5 5 5M16 7l5 5-5 5"/></svg>cod public</span>' if i["code"] else ""])
    img = i["img"]
    shot = (f'<div class="p-shot{" logo" if img["kind"] == "logo" else ""}" style="--c:{esc(img["color"])}"><img src="{esc(img["src"])}" alt="Imagine de pe {esc(i["domain"] or i["name"])}" width="{img["w"]}" height="{img["h"]}"></div>'
            if img else "")
    url_ = ""
    if i["url"]:
        url_ = (f'<a class="p-url" href="{esc(i["url"])}" target="_blank" rel="noopener">{esc(host_of(i["url"]))} ↗</a>' if alive
                else f'<span class="p-url off">{esc(host_of(i["url"]))} ↗</span>')
    inv = i.get("inventory") or {}
    data_block = data_summary(i)
    return f"""<button class="toc-btn" type="button" data-act="toc">☰ {esc(kind_label)} · {len(flat)}</button>
    <nav class="p-crumbs" aria-label="Unde ești">{nav_link(list_href(i["kind"]), esc(kind_label))}{f'<span class="sep">›</span>{nav_link(filter_href(i["kind"], "subj", i["primarySubject"]), esc(subject))}' if subject else ""}</nav>
    <section class="p-hero">
      <div>
        <div class="p-title">{f'<img src="{esc(i["icon"])}" alt="" width="56" height="56">' if i["icon"] else ""}<h1 id="d-title" tabindex="-1">{esc(i["name"])}</h1></div>
        {f'<p class="p-tag">{esc(i["tagline"])}</p>' if i["tagline"] else ""}
        {f'<p class="p-desc">{esc(i["desc"])}</p>' + ('<p class="p-note">Descriere preluată de pe site-ul proiectului.</p>' if i["descSrc"] == "site" else "") if i["desc"] else ""}
        <div class="p-cta">
          {url_}
          {f'<a class="btn btn-outline" href="{esc(i["wayback"])}" target="_blank" rel="noopener">Arhivă</a>' if i["wayback"] else ""}
          {f'<a class="btn btn-outline" href="{esc(inv["page"])}">Datele proiectului</a>' if inv.get("page") else ""}
          <div class="d-badges">{badges}</div>
        </div>
      </div>
      {shot}
    </section>
    <div class="p-body">
      <div class="p-main">
        {f'<div class="p-sec p-data">{data_block}</div>' if data_block else ""}
        {class_html(i, ctx)}
        {cards_section("Conține", parts)}
        {cards_section("Proiecte și resurse" if i["kind"] == "organizatie" else "Același autor", works)}
        {cards_section(f"Tot din {esc(subject)}", related) if related else ""}
      </div>
      {facts_html(i, ctx)}
    </div>
    <nav class="p-nav" aria-label="Intrarea anterioară și următoare">
      {step(prev, "", "← anterioara din listă")}
      {nav_link(list_href(i["kind"]), f'<small>înapoi la</small>{esc(kind_label)}', "p-back")}
      {step(nxt, ' class="p-next"', "următoarea din listă →")}
    </nav>"""


def tabs_html(i: dict, ctx: Context) -> str:
    """The header's tabs as plain links to the section archives; app.js replaces them with its own (with counts of the live entries)."""
    counts = {k: sum(1 for o in ctx.items if o["kind"] == k and ctx.group(o) != "inactiv") for k in ctx.kinds}
    current = lambda k: ' aria-current="page"' if k == i["kind"] else ""
    return "".join(f'<a class="tab" href="{k}/"{current(k)}>{esc(l)}<span class="n">{counts[k]}</span></a>' for k, l in ctx.kinds.items())


def entry_view(i: dict, ctx: Context) -> dict[str, str]:
    """The pieces that build.py puts in an entry page: the left list, the sheet and the header's tabs."""
    return {"toc": toc_html(i, ctx), "sheet": sheet_html(i, ctx), "tabs": tabs_html(i, ctx)}


# ---- structured data ----
def json_ld(i: dict, ctx: Context) -> str:
    """One `<script type="application/ld+json">` for the entry page: a WebPage, a BreadcrumbList and the entry itself.
    A field with no value is left out; nothing is invented."""
    page = SITE_URL + href(i)
    site_id = SITE_URL + "#website"
    kind_label = ctx.kinds[i["kind"]]
    if i["kind"] == "organizatie":
        kind = "NGO" if "organizatie:ong" in i["organisationTypes"] else "Organization"
    else:
        kind = LD_TYPE[i["kind"]]
    entry: dict = {"@type": kind, "@id": page, "name": i["name"]}
    if i["desc"] or i["tagline"]:
        entry["description"] = i["desc"] or i["tagline"]
    if i["url"]:
        entry["url"] = i["url"]
    image = (SITE_URL + i["img"]["src"]) if i["img"] else (SITE_URL + i["icon"]) if i["icon"] else ""
    if image:
        entry["image"] = image
    # sameAs names the same thing elsewhere: profiles on networks only, not an API, a donation page or a document.
    same = list(dict.fromkeys(l["url"] for l in i["links"] if l["role"] in ctx.network and l["url"] != i["url"]))
    if same:
        entry["sameAs"] = same
    people = []
    for a in (a for a in i["attributions"] if a["role"] != "parte_din"):
        o = ctx.by.get(a["org"]) if a["org"] else None
        # A name with no entry in the catalogue may be a person or an organisation; the data does not say, so it gets no type.
        people.append({"@type": "Organization", "@id": SITE_URL + href(o), "name": o["name"]} if o else {"name": a["name"]})
    if people and i["kind"] != "organizatie":
        entry["creator" if kind == "WebApplication" else "author"] = people
    parent = next((ctx.by[a["org"]] for a in i["attributions"] if a["role"] == "parte_din" and a["org"] in ctx.by), None)
    if parent:
        entry["isPartOf"] = {"@id": SITE_URL + href(parent), "name": parent["name"]}
    about = [{"@type": "DefinedTerm", "name": ctx.label[s]} for s in dict.fromkeys([*i["subjects"], *i["topics"]]) if s in ctx.label]
    if about:
        entry["about"] = about
    places = [{"@type": "Place", "name": ctx.label[a]} for a in i["areas"] if a in ctx.label]
    if places:
        entry["spatialCoverage"] = places
    if i["updated"]:
        entry["dateModified"] = i["updated"]
    if i.get("repo") and i.get("repo").get("license"):
        entry["license"] = i.get("repo")["license"]
    if kind == "WebApplication" and i["code"]:
        # codeRepository belongs to SoftwareSourceCode, not to WebApplication.
        entry["isBasedOn"] = {"@type": "SoftwareSourceCode", "codeRepository": i["code"]}
    graph = [
        {"@type": "WebSite", "@id": site_id, "url": SITE_URL, "name": "CivTech România", "inLanguage": "ro",
         "publisher": {"@type": "Organization", "name": "gov2.ro", "url": "https://gov2.ro"}},
        {"@type": "WebPage", "@id": page + "#webpage", "url": page, "name": f"{i['name']} — CivTech România", "inLanguage": "ro",
         "isPartOf": {"@id": site_id}, "breadcrumb": {"@id": page + "#breadcrumb"}, "mainEntity": {"@id": page}},
        {"@type": "BreadcrumbList", "@id": page + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "CivTech România", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": kind_label, "item": f"{SITE_URL}{i['kind']}/"},
            {"@type": "ListItem", "position": 3, "name": i["name"], "item": page}]},
        entry,
    ]
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":"))
    return f'<script type="application/ld+json">{data.replace("</", "<\\/")}</script>'
