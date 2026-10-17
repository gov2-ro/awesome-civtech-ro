"""Merge proiecte.csv + orgs.csv + profil.csv into site/data.json (the browser's copy; generated, not edited).

    python3 scripts/build.py
"""
import json
import re
from datetime import datetime, timezone

from common import BOILERPLATE, DATA, SITE, domain_of, load_entries, load_profile, split_list, to_href

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
    return {"mutat": "activ", "blocat": "necunoscut", "parcat": "offline"}.get(s, s)


def main():
    tax = json.loads((DATA / "taxonomy.json").read_text())
    roles = tax["linkuri"]["roluri"]
    profile = load_profile()
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
        img = None if e["imagine"] == "none" else live.get("image")
        moved = live.get("status") == "mutat"
        final = live.get("final_url") or e["url"]
        status = status_of(e["stare"], p)
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
            "tip": e.get("tip", ""),
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
            "img": img,
            "icon": live.get("icon", ""),
            "wayback": p.get("wayback") or (f"https://web.archive.org/web/{e['url']}" if e["url"] and status in ("offline", "arhivat") else ""),
            "sursa": e["sursa"],
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
