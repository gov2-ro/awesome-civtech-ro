"""Merge proiecte.csv + orgs.csv + profil.csv into site/data.json (the browser's copy; generated, not edited).

    python3 scripts/build.py
"""
import json
import math
import re
from datetime import date, datetime, timezone

from common import (BOILERPLATE, DATA, ETICHETE, SITE, domain_of, is_kept, load_entries, load_mentions, load_profile, read_csv,
                    split_list, split_tip, to_href)

CODE_ROLES = ("github", "gitlab", "cod")


def pick_desc(desc: str, prof: dict) -> tuple[str, str]:
    """The curated description unless empty or boilerplate; then the site's own meta description."""
    if desc and not BOILERPLATE.match(desc):
        return desc, "catalog"
    d = prof.get("description", "")
    if len(d) >= 40 and prof.get("status") in ("activ", "mutat"):
        return d, "site"
    return "", ""


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
    by_host = {h: r["key"] for r in roles for h in r["hosts"]}
    label = {r["key"]: r["label"] for r in roles}
    out = {}
    for tok in split_list(cell):
        m = re.match(r"^([a-z]+):(https?://.+)$", tok)
        role, url = (m.group(1), m.group(2)) if m and m.group(1) in label else (None, to_href(tok))
        role = role or by_host.get(domain_of(url).removeprefix("m."), "web")
        out.setdefault(role if role not in ("web", *CODE_ROLES) else url,
                       {"role": role, "label": label[role], "url": url, "src": "manual"})
    for role, url in social.items():
        if re.search(r"/(events|groups)/", url):
            continue
        out.setdefault(role, {"role": role, "label": label.get(role, role), "url": url, "src": "site"})
    order = list(label)
    return sorted(out.values(), key=lambda l: order.index(l["role"]))


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


def main():
    tax = json.loads((DATA / "taxonomy.json").read_text())
    roles = tax["linkuri"]["roluri"]
    profile = load_profile()
    features = reach_features(load_mentions(), read_csv(ETICHETE) if ETICHETE.exists() else [])
    items = []
    for n, e in enumerate(load_entries()):
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
        items.append({
            "id": n + 1,
            "slug": e["slug"],
            "kind": e["kind"],
            "civictech": e.get("civictech") == "1",
            "name": e["nume"],
            "tagline": e["descriere_scurta"],
            "desc": desc,
            "descSrc": desc_src,
            "domeniu": e["domeniu"],
            "tips": split_tip(e.get("tip", "")),
            "acoperire": e["acoperire"],
            "oras": e["oras"],
            "keywords": keywords(e.get("cuvinte", ""), tax["cuvinte"]),
            "links": [l for l in lk if l is not code_link],
            "url": final if moved else e["url"],
            "domain": domain_of(final if moved else e["url"]) if e["url"] else "",
            "movedFrom": domain_of(e["url"]) if moved else "",
            "org": e.get("autor", ""),
            "code": code,
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
    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checked": checked[-1] if checked else "",
        "taxonomy": tax_out,
        "items": items,
    }
    (SITE / "data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    by = {}
    for i in items:
        by[i["status"]] = by.get(i["status"], 0) + 1
    print(f"wrote {len(items)} entries to site/data.json  {by}")


if __name__ == "__main__":
    main()
