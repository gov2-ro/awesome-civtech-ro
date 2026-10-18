"""Shared loading of the editable CSVs (proiecte, orgs) and the generated profile and mention CSVs."""
import csv
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"


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

ROLES = json.loads((DATA / "taxonomy.json").read_text())["linkuri"]["roluri"]
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


def is_kept(row: dict) -> bool:
    """A search result counts when the editor keeps it, or when the editor is silent and no rule dropped it."""
    return row["editor"] == "1" or (row["editor"] == "" and row["regula"] == "")


def load_mentions() -> list[dict]:
    """Every row of mentiuni.csv (empty when search.py has not run)."""
    return read_csv(MENTIUNI) if MENTIUNI.exists() else []


def load_entries() -> list[dict]:
    """Every listed entry: projects and resources from proiecte.csv, organisations from orgs.csv."""
    out = []
    for r in read_csv(DATA / "proiecte.csv"):
        out.append({**r, "kind": r["fel"] or "proiect", "url": to_href(r["url"]) if r["url"] else ""})
    for r in read_csv(DATA / "orgs.csv"):
        out.append({**r, "kind": "organizatie", "url": to_href(r["url"]) if r["url"] else ""})
    return out


def load_profile() -> dict:
    """slug -> profile dict, in the shape scripts/profile.py produces."""
    if not PROFILE.exists():
        return {}
    out = {}
    for r in read_csv(PROFILE):
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


def save_profile(profile: dict):
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
    write_csv(PROFILE, PROFIL_COLS, rows)
