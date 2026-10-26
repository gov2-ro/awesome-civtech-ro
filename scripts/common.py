"""Shared loading of the editable CSVs (proiecte, orgs) and the generated profile and mention CSVs.

A data root is either the v1 layout (data/: proiecte.csv, orgs.csv, taxonomy.json) or a taxonomy v2 package or
overlay (schema.json or pachet.json; see scripts/taxonomy_v2.py). PUBLIC_ROOT is the default root of every script.
"""
import csv
import json
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
# The data root that feeds the public site, and the default --data-dir of every script. Since the cutover it is the
# taxonomy v2 integration copy (before, the v1 root data/). Only this root may write site/.
PUBLIC_ROOT = DATA / "taxonomy-v2" / "integrare"


def load_env(path: Path = ROOT / ".env"):
    """Read KEY=value lines from the repo's .env (gitignored) into os.environ. Variables already set win,
    so CI secrets and `export` still override the file."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip().removeprefix("export ").strip(), v.strip().strip("'\""))
PROFILE = DATA / "profil.csv"
MENTIUNI = DATA / "mentiuni.csv"
ETICHETE = DATA / "mentiuni_etichete.csv"

# Column order of the editable files. Contributions (PRs, the Google Sheet) use the same headers.
PROIECTE_COLS = ["slug", "fel", "nume", "descriere_scurta", "descriere", "url", "linkuri", "domeniu", "tip", "cuvinte",
                 "acoperire", "oras", "autor", "contact", "civictech", "stare", "nota"]
ORGS_COLS = ["slug", "nume", "descriere_scurta", "descriere", "url", "linkuri", "domeniu", "cuvinte", "acoperire", "oras",
             "stare", "nota"]
# Profile: flat columns, plus JSON for the one nested value (social links by network).
PROFIL_COLS = ["slug", "url", "final_url", "http_status", "status", "error", "ssl_error", "parked", "title", "og_title",
               "site_name", "description", "lang", "repos", "social", "img_src", "img_kind", "img_w", "img_h",
               "img_color", "img_source", "icon", "wayback", "first_seen", "last_capture", "archive_months", "updated", "updated_src", "feed",
               "generator", "words", "copyright_year", "sitemap_urls", "cert_first", "repo", "repo_created", "repo_archived", "stars", "forks",
               "open_issues", "commits", "contributors", "last_commit", "license", "language",
               "wiki_refs", "opr", "mentions", "mention_hosts", "search_social", "fetched_at"]
# Search results (scripts/search.py). `editor` is the only column a person edits: 1 keeps, 0 drops, empty follows `regula`.
MENTIUNI_COLS = ["slug", "provider", "query", "rank", "url", "host", "title", "snippet", "date", "regula", "editor", "fetched_at"]
# LLM labels of the kept results (scripts/review.py); generated, never hand-edited.
ETICHETE_COLS = ["slug", "url", "despre_proiect", "tip_sursa", "independent", "model", "labelled_at"]

# The production taxonomy, for the v1 scripts. A v2 root has its own lists: load_vocabulary(data_dir).
_TAX = json.loads((DATA / "taxonomy.json").read_text()) if (DATA / "taxonomy.json").exists() else {}
ROLES = _TAX.get("linkuri", {}).get("roluri", [])
# `fel` (the column of proiecte.csv) -> the tab it belongs to: articles, guides, campaigns and research all sit under "resursa".
FEL_KIND = {f["key"]: f["kind"] for f in _TAX.get("fel", [])}
# Profile links by network: host -> role key, from the taxonomy (GitHub and GitLab are code, not social).
SOCIAL_HOSTS = {h: r["key"] for r in ROLES if r["key"] not in ("github", "gitlab") for h in r["hosts"]}
# Link roles that show a network logo in the drawer (NETWORK in site/app.js). Every other link shows the favicon of its host.
NETWORK_ROLES = ("facebook", "instagram", "linkedin", "x", "bluesky", "mastodon", "threads", "tiktok", "youtube", "telegram",
                 "discord", "github", "gitlab")
LINKICON_DIR = SITE / "img" / "linkicon"
# Share buttons and other URLs that are not a profile page.
SHARE = re.compile(r"sharer|/share|intent/|shareArticle|/dialog/|/plugins/|/hashtag/|/watch\?|/embed/|/events/|/groups/", re.I)

# Descriptions that carry no information (kept for imports from other catalogues).
BOILERPLATE = re.compile(
    r"^(Aplicație / resursă pentru transparență|Inițiativă axată pe|Instrument civic digital|-na-$)", re.I
)


def is_url(s: str) -> bool:
    return bool(re.match(r"^(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?$", s.strip())) and " " not in s.strip()


def to_href(s: str) -> str:
    s = s.strip()
    return s if re.match(r"^https?://", s, re.I) else "https://" + s


def domain_of(url: str) -> str:
    return re.sub(r"^www\.", "", re.sub(r"^https?://", "", url, flags=re.I)).split("/")[0].lower()


def split_list(cell: str) -> list[str]:
    """A list cell: a JSON array, or values separated by spaces, newlines, | or commas (a comma at a
    value's end, as people type lists in Sheets, never belongs to the URL)."""
    cell = (cell or "").strip()
    if cell.startswith("["):
        return [str(x).strip() for x in json.loads(cell) if str(x).strip()]
    return [x for x in re.split(r"[\s|]+|,(?=\s|$)", cell) if x]


def link_host(url: str) -> str:
    """The host of a link, as the file name of its favicon in site/img/linkicon/."""
    return re.sub(r"[^\w.-]", "_", (urlparse(url).hostname or "").lower().removeprefix("www."))


def parse_link(tok: str, roles: list[dict]) -> tuple[str, str]:
    """(role, url) of one token of the `linkuri` cell: "rol:URL", or a bare URL whose role follows from its host."""
    m = re.match(r"^([a-z]+):(https?://.+)$", tok)
    if m and m.group(1) in {r["key"] for r in roles}:
        return m.group(1), m.group(2)
    url = to_href(tok)
    return {h: r["key"] for r in roles for h in r["hosts"]}.get(domain_of(url).removeprefix("m."), "web"), url


def split_tip(cell: str) -> list[str]:
    """The tip cell: one or more keys, comma-separated, the main one first."""
    return list(dict.fromkeys(t.strip() for t in (cell or "").split(",") if t.strip()))


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def write_csv(path: Path, cols: list[str], rows: list[dict]):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# --- Sites that forbid automated access ---------------------------------------------------------------------------------------
# data/taxonomy-v2/colectare-interzisa.csv (hand-edited) lists the hosts that no script requests. A listed host also covers its
# subdomains. Every script that opens a connection to a project's site calls forbidden() before the request, and again for each
# redirect it follows. A skipped request has the state `colectare-interzisa` with the `motiv` of the row. It is never an error,
# never a failed attempt, and never `offline`.
FORBIDDEN_STATE = "colectare-interzisa"
FORBIDDEN_COLS = ["gazda", "motiv", "dovada", "data", "nota"]
FORBIDDEN_PATH = DATA / "taxonomy-v2" / "colectare-interzisa.csv"


class ForbiddenHost(Exception):
    """Raised in place of a request to a listed host. `url` is the address; `row` is the line of the list that covers it."""

    def __init__(self, url: str, row: dict):
        super().__init__(f"{FORBIDDEN_STATE}: {url} ({row.get('motiv', '')})")
        self.url, self.row = url, row


def listed_host(host: str) -> str:
    """A host name as the list compares it: lower case, no trailing dot, no leading `www.`."""
    return (host or "").strip().lower().rstrip(".").removeprefix("www.")


def host_of(url: str) -> str:
    """The host of a URL, as listed_host writes it. Empty when the URL has no host (or cannot be parsed)."""
    try:
        return listed_host(urlparse(url).hostname or "")
    except ValueError:
        return ""


@lru_cache(maxsize=None)
def _forbidden_rows(path: str) -> tuple[dict, ...]:
    p = Path(path)
    if not p.exists():
        return ()
    with open(p, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:  # an empty file lists nothing
            return ()
        missing = [c for c in ("gazda", "motiv") if c not in reader.fieldnames]
        if missing:  # a list that cannot be read must stop the run, not silently allow every request
            raise ValueError(f"{p}: lipsesc coloanele {', '.join(missing)}")
        rows = [{k: (v or "").strip() for k, v in r.items() if k} for r in reader]
    return tuple(r for r in rows if r.get("gazda"))


def forbidden_rows(path: Path | None = None) -> list[dict]:
    """The rows of the list (loaded once per file). Empty when the file is absent."""
    return list(_forbidden_rows(str(path or FORBIDDEN_PATH)))


def forbidden(url: str, rows: list[dict] | None = None) -> dict | None:
    """The row of the list that covers the host of `url`, else None. A host matches itself and its subdomains, by whole
    labels (`notharta-firmelor.ro` does not match `harta-firmelor.ro`). A leading `www.` is ignored. `rows` replaces the file."""
    host = host_of(url)
    if not host:
        return None
    for row in forbidden_rows() if rows is None else rows:
        listed = listed_host(row.get("gazda", ""))
        if listed and (host == listed or host.endswith("." + listed)):
            return row
    return None


def refuse_forbidden(url: str, rows: list[dict] | None = None):
    """Raise ForbiddenHost when `url` is on a listed host. Call it before every request, and for each redirect hop."""
    row = forbidden(url, rows)
    if row is not None:
        raise ForbiddenHost(url, row)


def skip_line(slug: str, row: dict) -> str:
    """The one line that a script prints for an entry it does not request."""
    return f"  {FORBIDDEN_STATE} {slug}: {row.get('motiv', '')} [{row.get('gazda', '')}]"


def refuse_route(route, refused: list | None = None):
    """Playwright route handler (sync API) for a context or a page: abort a request to a listed host that a navigation, a link
    or a script starts, and let the rest go on. The address of an aborted navigation goes to `refused`.

    A route handler does NOT see the redirect hop of a request that it let through (measured with Chromium on loopback: the
    server received the request for the listed host). Browsers are therefore also launched with browser_args(), and
    note_failed_request() records the hop that the browser could not resolve."""
    request = route.request
    if forbidden(request.url) is None:
        route.continue_()
        return
    if refused is not None and request.is_navigation_request():
        refused.append(request.url)
    route.abort()


def browser_args(rows: list[dict] | None = None) -> list[str]:
    """Arguments for chromium.launch(). They make every listed host, and its subdomains, unresolvable inside the browser, so no
    request reaches it, not even the hop of a redirect that no route handler sees. A browser behind a proxy resolves nothing itself
    and would ignore the rule; the scripts start the browser without a proxy."""
    rules = []
    for row in forbidden_rows() if rows is None else rows:
        host = listed_host(row.get("gazda", ""))
        if host:
            rules += [f"MAP {host} ~NOTFOUND", f"MAP *.{host} ~NOTFOUND"]
    return [f"--host-resolver-rules={', '.join(rules)}"] if rules else []


def note_failed_request(request, refused: list):
    """Playwright `requestfailed` listener: the browser could not make a request to a listed host (a route aborted it, or its
    name does not resolve after a redirect). A navigation goes to `refused`, so the caller can tell it from an offline site."""
    if forbidden(request.url) is not None and request.is_navigation_request():
        refused.append(request.url)


def is_kept(row: dict) -> bool:
    """A search result counts when the editor keeps it, or when the editor is silent and no rule dropped it."""
    return row["editor"] == "1" or (row["editor"] == "" and row["regula"] == "")


def load_mentions(path: Path = MENTIUNI) -> list[dict]:
    """Every row of mentiuni.csv (empty when search.py has not run)."""
    return read_csv(path) if path.exists() else []


def load_entries(data_dir: Path = DATA) -> list[dict]:
    """Every listed entry of a v1 root: projects and resources from proiecte.csv, organisations from orgs.csv."""
    tax = json.loads((data_dir / "taxonomy.json").read_text()) if data_dir != DATA else _TAX
    fel_kind = {f["key"]: f["kind"] for f in tax.get("fel", [])}
    out = []
    for r in read_csv(data_dir / "proiecte.csv"):
        out.append({**r, "kind": fel_kind.get(r["fel"] or "proiect", "proiect"), "url": to_href(r["url"]) if r["url"] else ""})
    for r in read_csv(data_dir / "orgs.csv"):
        out.append({**r, "kind": "organizatie", "url": to_href(r["url"]) if r["url"] else ""})
    return out


def data_schema(data_dir: Path = PUBLIC_ROOT) -> str:
    """'v2' for a taxonomy v2 package or overlay, 'v1' for the production layout. Anything else is an error."""
    from taxonomy_v2 import is_v2
    if is_v2(data_dir):
        return "v2"
    if (data_dir / "proiecte.csv").exists() and (data_dir / "taxonomy.json").exists():
        return "v1"
    raise SystemExit(f"{data_dir}: not a data root (no proiecte.csv + taxonomy.json, schema.json or pachet.json)")


def observation_paths(data_dir: Path = PUBLIC_ROOT) -> dict[str, Path]:
    """The generated observation files of a root: data/*.csv for v1, observatii/*.csv for v2 (an overlay uses its
    base's). `review` is the folder of review.py's raw answers and suggestions. A v2 run never reads or writes the
    immutable copies in source/."""
    if data_schema(data_dir) == "v1":
        return {"profile": data_dir / "profil.csv", "mentions": data_dir / "mentiuni.csv", "labels": data_dir / "mentiuni_etichete.csv",
                "review": data_dir / "review"}
    from taxonomy_v2 import Files
    obs = Files(data_dir).observations
    return {"profile": obs / "profil.csv", "mentions": obs / "mentiuni.csv", "labels": obs / "mentiuni_etichete.csv", "review": obs / "review"}


def split_ids(cell: str) -> list[str]:
    """A v2 ID list cell: values separated by `|`, without spaces. Not the comma rule of split_tip."""
    from taxonomy_v2 import values
    return values(cell)


def load_vocabulary(data_dir: Path = PUBLIC_ROOT) -> dict:
    """The controlled lists of a root. v1: taxonomy.json as it is. v2: concepts, code lists (with labels), areas and
    link roles from their CSVs, assembled in memory; nothing is written back."""
    if data_schema(data_dir) == "v1":
        return json.loads((data_dir / "taxonomy.json").read_text())
    from taxonomy_v2 import load
    pkg = load(data_dir)
    return {"schema_version": pkg.version, "concepts": pkg.concepts, "codes": pkg.codes, "areas": pkg.areas,
            "roles": pkg.link_roles(), "sections": pkg.sections(), "site": pkg.settings["site"], "package": pkg}


def link_roles(data_dir: Path = PUBLIC_ROOT) -> list[dict]:
    """The link roles [{key, label, hosts}] of a root, in their editorial order."""
    voc = load_vocabulary(data_dir)
    return voc["roles"] if "roles" in voc else voc["linkuri"]["roluri"]


def load_catalogue(data_dir: Path = PUBLIC_ROOT) -> list[dict]:
    """Every entry of a root, with the fields that both schemas share: slug, nume, descriere_scurta, descriere,
    url, linkuri, stare, contact, kind (the URL section) and row (its record in the edited table, header = 1).
    v2 entries add their facets (lists; maturity and the primary subject are a string or None), the resolved
    attribution relations, and `legacy`: the original v1 record's category, types and keywords, read from the
    source snapshot, for old bookmarks. Private notes and source metadata stay out."""
    if data_schema(data_dir) == "v1":
        rows = {"proiecte": 1, "orgs": 1}
        out = []
        for e in load_entries(data_dir):
            tab = "orgs" if e["kind"] == "organizatie" else "proiecte"
            rows[tab] += 1
            out.append({**e, "row": rows[tab]})
        return out
    from taxonomy_v2 import load, read_table, source_row, values
    pkg = load(data_dir)
    sources = {n: read_table(pkg.files.path(f"source/{n}"))[1] for n in ("proiecte.csv", "orgs.csv") if pkg.files.path(f"source/{n}").exists()}
    relations: dict[str, list[dict]] = {}
    for r in pkg.tables["relatii.csv"]:
        target = pkg.entries.get(r["obiect"])
        relations.setdefault(r["subiect"], []).append({
            "predicate": r["predicat"], "state": r["stare"], "slug": r["obiect"], "literal": r["obiect_literal"],
            "name": target["nume"] if target else r["obiect_literal"], "evidence": r["valoare_sursa"]})
    out = []
    for n, (slug, raw) in enumerate(pkg.entries.items(), 2):
        original = source_row(pkg, sources, raw) or {}
        r = {k: v.strip() for k, v in raw.items()}  # the CSV keeps the original bytes; display them trimmed, as v1 does
        out.append({
            "slug": slug, "nume": r["nume"], "descriere_scurta": r["descriere_scurta"], "descriere": r["descriere"],
            "url": to_href(r["url"]) if r["url"] else "", "linkuri": r["linkuri"], "stare": r["stare"], "contact": r["contact"],
            "kind": r["sectiune_url"], "row": n, "entity_type": r["tip_entitate"],
            "primary_subject": r["subiect_principal"] or None, "subjects": values(r["subiecte"]), "topics": values(r["teme"]),
            "purposes": values(r["scopuri"]), "capabilities": values(r["functionalitati"]), "formats": values(r["formate"]),
            "technologies": values(r["tehnologii"]), "institutions": values(r["institutii_vizate"]), "autor": r["autor_original"],
            "organisation_types": values(r["tip_organizatie"]), "maturity": r["maturitate"] or None,
            "data_detail": r.get("detaliere_date", ""), "data_detail_evidence": r.get("dovada_detaliere", ""),
            "data_relation": r.get("relatie_date", ""),  # the code of valori.csv list `relatie_date`; empty means not assessed
            "coverage_level": r["nivel_acoperire"], "areas": values(r["arii_acoperite"]), "locality": r["localitate_originala"],
            "civictech": r["civictech_original"], "classification_state": r["clasificare_stare"],
            "attributions": [a for a in relations.get(slug, []) if a["predicate"] != "date_din"],
            "data_sources": [a for a in relations.get(slug, []) if a["predicate"] == "date_din" and a["state"] == "acceptat"],
            "legacy": {k: original.get(k, "") for k in ("fel", "domeniu", "tip", "cuvinte", "acoperire", "oras")} if original else {},
        })
    return out


def public_catalogue(data_dir: Path = PUBLIC_ROOT) -> list[dict]:
    """load_catalogue without the hidden entries (v2 `clasificare_stare` `ascuns`): what the public build shows.
    `row` keeps the entry's record in the edited table, so the Sheet links of the other entries do not move."""
    from taxonomy_v2 import HIDDEN
    return [e for e in load_catalogue(data_dir) if e.get("classification_state") != HIDDEN]


def years_since(d: str) -> float | None:
    return (date.today() - date.fromisoformat(d)).days / 365.25 if d else None


def status_of(stare: str, prof: dict) -> str:
    """The status that the site shows for an entry: the editor's `stare`, else what the profiler saw."""
    if stare:
        return stare
    s = prof.get("status")
    if not s:
        return "neverificat"
    # Gone, and the Wayback Machine has not seen it for a year: the project has ended, not just a glitch.
    if s == "offline" and (years_since(prof.get("last_capture", "")) or 0) > 1:
        return "arhivat"
    return {"mutat": "activ", "blocat": "necunoscut", "parcat": "offline"}.get(s, s)


# The scope of the variable inventory (docs/briefs/data-relation.md, section 3). One rule serves `/date/`, `/date/lista/`,
# `inventar/<slug>.json`, the inventory markers of the explorer, the coverage export and the default selection of
# collect_docs.py and inventory.py.
INACTIVE_STATUSES = ("offline", "arhivat")  # the group `inactiv` of STATUS in site/app.js
IN_SCOPE_RELATIONS = ("date-publice", "date-proprii", "calcul")  # the codes of `relatie_date` that keep an entry in scope
UNASSESSED = "neevaluat"  # the name of an empty `relatie_date`; the column never holds it
OUT_OF_SCOPE = ("in-afara-ariei", "inactiv", "fara-date", UNASSESSED)  # the reasons; the first that applies is the one reported

# The public pages show the relation to data in two groups, not in five states (docs/briefs/data-relation.md, section 9). `cu-date` is the
# scope of the variable inventory; `fara-date` takes `fara-date` and an empty value. This tuple is the one definition: build.py writes it to
# `vocabulary.dataGroups` in data.json, and the facet `dat` of site/app.js reads it there. `/date/` and `/date/lista/` count their left-out
# entries by the group `fara-date` and by `inactiv` (`public_reason`). The coverage export keeps the internal state `neevaluat`.
DATA_GROUPS = (
    {"key": "cu-date", "label": "Lucrează cu date", "codes": IN_SCOPE_RELATIONS},
    {"key": "fara-date", "label": "Fără date", "codes": ("fara-date", "")},
)


def inventory_exclusion(kind: str, status: str, relation: str) -> str:
    """Why an entry is out of the variable inventory, or an empty string when it is in scope. An entry is in scope when it
    is a project or a resource, its built status is not inactive, and its `relatie_date` is `date-publice`, `date-proprii`
    or `calcul`. An empty value and `fara-date` both leave it out. A code that valori.csv does not list counts as empty."""
    if kind not in ("proiect", "resursa"):
        return OUT_OF_SCOPE[0]
    if status in INACTIVE_STATUSES:
        return OUT_OF_SCOPE[1]
    if relation in IN_SCOPE_RELATIONS:
        return ""
    return OUT_OF_SCOPE[2] if relation == OUT_OF_SCOPE[2] else UNASSESSED


def data_group(relation: str) -> str:
    """The key of the group of DATA_GROUPS that a `relatie_date` value belongs to. An empty value, and a code that valori.csv does not list,
    belong to `fara-date`."""
    for group in DATA_GROUPS:
        if relation in group["codes"]:
            return group["key"]
    return DATA_GROUPS[-1]["key"]


def public_reason(reason: str) -> str:
    """The reason that the public pages name for a reason of `inventory_exclusion`: `neevaluat` joins `fara-date`. The other reasons stay."""
    return DATA_GROUPS[-1]["key"] if reason == UNASSESSED else reason


def inventory_scope(entries: list[dict], data_dir: Path = PUBLIC_ROOT) -> dict[str, str]:
    """slug -> reason (see `inventory_exclusion`; empty when in scope) for catalogue entries of a v2 root, with the status that
    build.py gives each one. A v1 root has no `relatie_date`, so every entry of it counts as in scope."""
    if data_schema(data_dir) != "v2":
        return {e["slug"]: "" for e in entries}
    profile = load_profile(observation_paths(data_dir)["profile"])
    return {e["slug"]: inventory_exclusion(e["kind"], status_of(e["stare"], profile.get(e["slug"], {})), e.get("data_relation", ""))
            for e in entries}


def load_profile(path: Path = PROFILE) -> dict:
    """slug -> profile dict, in the shape scripts/profile.py produces."""
    if not path.exists():
        return {}
    out = {}
    for r in read_csv(path):
        p = {k: r[k] for k in PROFIL_COLS if r.get(k) and not k.startswith("img_") and k not in ("slug", "repos", "social")}
        if r["http_status"]:
            p["http_status"] = int(r["http_status"])
        for k in ("ssl_error", "parked", "repo_archived"):
            if k in p:
                p[k] = p[k] == "1"
        p["repos"] = split_list(r["repos"])
        p["social"] = json.loads(r["social"]) if r["social"] else {}
        p["search_social"] = json.loads(r.get("search_social") or "{}")
        if r["img_src"]:
            p["image"] = {"src": r["img_src"], "kind": r["img_kind"], "w": int(r["img_w"]), "h": int(r["img_h"]),
                          "color": r["img_color"], "source_url": r["img_source"]}
        out[r["slug"]] = p
    return out


def save_profile(profile: dict, path: Path = PROFILE):
    rows = []
    for slug, p in sorted(profile.items()):
        im = p.get("image") or {}
        rows.append({
            **{k: p.get(k, "") for k in PROFIL_COLS},
            "slug": slug,
            "ssl_error": "1" if p.get("ssl_error") else "",
            "parked": "1" if p.get("parked") else "",
            "repo_archived": "1" if p.get("repo_archived") else "",
            "repos": " ".join(p.get("repos") or []),
            "social": json.dumps(p["social"], ensure_ascii=False) if p.get("social") else "",
            "search_social": json.dumps(p["search_social"], ensure_ascii=False) if p.get("search_social") else "",
            "img_src": im.get("src", ""), "img_kind": im.get("kind", ""), "img_w": im.get("w", ""),
            "img_h": im.get("h", ""), "img_color": im.get("color", ""), "img_source": im.get("source_url", ""),
        })
    write_csv(path, PROFIL_COLS, rows)


# Profile columns that other stages write. A fresh HTTP profile never has them, and a refresh never drops them.
SEARCH_COLS = ("mentions", "mention_hosts", "search_social")  # scripts/search.py
OPR_COLS = ("opr",)  # scripts/profile.py --opr
# Signals of `profile.py --extra`, in groups that change together; the first column leads. A refresh that finds
# nothing for the lead keeps the old group: a failed call must never turn a known value into a blank.
EXTRA_GROUPS = (("archive_months", "first_seen", "last_capture"), ("updated", "updated_src"), ("cert_first",), ("wiki_refs",),
                ("repo", "repo_created", "repo_archived", "stars", "forks", "open_issues", "commits", "contributors",
                 "last_commit", "license", "language"),
                ("feed",), ("generator",), ("words",), ("copyright_year",), ("sitemap_urls",), ("icon",))


def has_value(v) -> bool:
    """A found value. 0 and False are values; None and the empty string are not."""
    return v is not None and v != ""


def merge_profile(old: dict | None, fresh: dict) -> dict:
    """A fresh HTTP profile joined with the stored row of the same slug (both in the shape of load_profile). Pure.
    Columns of the other stages (SEARCH_COLS, OPR_COLS) survive. A group of EXTRA_GROUPS keeps its old values when the
    fresh profile found nothing for its lead column; with the same lead value (the same repository), it keeps the old
    members that the fresh profile lacks. A row for a new address (`url` differs) keeps only SEARCH_COLS: the other
    signals describe the old site."""
    out = dict(fresh)
    if not old:
        return out
    for col in SEARCH_COLS:
        if not has_value(out.get(col)) and has_value(old.get(col)):
            out[col] = old[col]
    if has_value(old.get("url")) and has_value(out.get("url")) and old["url"] != out["url"]:
        return out
    for col in OPR_COLS:
        if not has_value(out.get(col)) and has_value(old.get(col)):
            out[col] = old[col]
    for lead, *members in EXTRA_GROUPS:
        if has_value(out.get(lead)) and str(out[lead]) != str(old.get(lead)):
            continue  # a new lead value: the fresh group replaces the old one
        for col in (lead, *members):
            if not has_value(out.get(col)) and has_value(old.get(col)):
                out[col] = old[col]
    return out


def kept_by_slug(mentions: list[dict]) -> dict[str, list[dict]]:
    """The kept rows of mentiuni.csv, grouped by slug."""
    out: dict[str, list[dict]] = {}
    for r in mentions:
        if is_kept(r):
            out.setdefault(r["slug"], []).append(r)
    return out


def label_coverage(mentions: list[dict], labels: list[dict]) -> dict:
    """How much of the kept search results the labels cover. A label belongs to the kept row of the same slug and URL;
    a label whose URL is no longer kept (the editor dropped it, or the search no longer returns it) counts for nothing.
    Returns the kept rows (`kept`), the labelled ones (`labelled`), `ratio` (1.0 when nothing is kept) and, for the slugs
    that have kept rows, how many are `full` (every kept row labelled), `partial` or `none`."""
    have = {(l["slug"], l["url"]) for l in labels}
    kept = kept_by_slug(mentions)
    labelled = full = partial = none = 0
    for slug, rows in kept.items():
        n = sum(1 for r in rows if (slug, r["url"]) in have)
        labelled += n
        full += n == len(rows)
        partial += 0 < n < len(rows)
        none += n == 0
    total = sum(len(rows) for rows in kept.values())
    return {"kept": total, "labelled": labelled, "ratio": labelled / total if total else 1.0,
            "slugs": len(kept), "full": full, "partial": partial, "none": none}


def coverage_line(cov: dict) -> str:
    """The coverage in one line, for the output of review.py and build.py."""
    return (f"labels {cov['labelled']}/{cov['kept']} kept rows ({cov['ratio']:.0%}); of {cov['slugs']} entries with kept rows, "
            f"{cov['full']} are fully labelled, {cov['partial']} partly, {cov['none']} not at all")
