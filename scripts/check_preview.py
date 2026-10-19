# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Browser acceptance checks for a v2 preview: desktop and mobile filtering, counts, direct links, archives, old
bookmarks, search labels. It reads the preview's own data.json for the expected numbers; it changes nothing.

    python3 scripts/build.py --data-dir data/taxonomy-v2/integrare --site-dir /tmp/civtech-v2 --allow-draft
    python3 -m http.server -d /tmp/civtech-v2 8765 &
    uv run scripts/check_preview.py http://localhost:8765/

Exits 1 when a check fails. Playwright needs its Chromium (`uv run --with playwright playwright install chromium`).
"""
import json
import sys
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
DB = json.loads(urllib.request.urlopen(BASE + "data.json").read())
C = {c["id"]: c for c in DB["vocabulary"]["concepts"]}
A = {a["id"]: a for a in DB["vocabulary"]["areas"]}
results = []


def ok(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def ancestors(i):
    out, todo = [], list(C.get(i, {}).get("broader", []))
    while todo:
        b = todo.pop()
        if b not in out:
            out.append(b)
            todo += C.get(b, {}).get("broader", [])
    return out


def subj_set(it):
    return set(it["subjects"]) | {a for t in it["topics"] for a in ancestors(t) if not C[a]["broader"]}


def topic_set(it):
    return set(it["topics"]) | {a for t in it["topics"] for a in ancestors(t) if C[a]["broader"]}


def up(a):
    out = []
    while A.get(a, {}).get("parent"):
        a = A[a]["parent"]
        out.append(a)
    return out


def applies(it, x):
    return any(a == x or a in up(x) or x in up(a) for a in it["areas"])


INACTIVE = ("offline", "arhivat")
visible = lambda kind: [i for i in DB["items"] if i["kind"] == kind and i["status"] not in INACTIVE]
count_text = lambda page: int(page.locator('[data-slot="toolbar"] .count b').inner_text())
errors = []

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))

    def go(path):
        page.goto(BASE + path)
        page.wait_for_selector('[data-slot="toolbar"] .count')

    # 1. Default grouped view: every visible project once, under its primary subject.
    go("")
    projects = visible("proiect")
    shown = page.locator('[data-slot="results"] [data-open]').evaluate_all("els => els.map(e => e.dataset.open)")
    ok("default view shows each visible project once", sorted(shown) == sorted(i["slug"] for i in projects), f"{len(shown)} rows, {len(projects)} expected")
    heads = page.locator('[data-slot="results"] .group-head h2').all_inner_texts()
    expected_heads = [C[s]["label"] for s in DB["vocabulary"]["subjectOrder"] if any(i["primarySubject"] == s for i in projects)]
    ok("default groups follow the primary subjects", heads == expected_heads, f"{len(heads)} groups")
    ok("draft notice is hidden for now", page.locator(".draft-note").count() == 0)
    titles = page.locator('[data-slot="side"] .facet > summary .kicker').all_inner_texts()
    ok("sidebar order", titles[:6] == ["SUBIECT", "TEMĂ", "CE POȚI FACE", "FORMAT", "UNDE SE APLICĂ", "MAI MULTE FILTRE"] or
       [t.upper() for t in titles[:6]] == ["SUBIECT", "TEMĂ", "CE POȚI FACE", "FORMAT", "UNDE SE APLICĂ", "MAI MULTE FILTRE"], " / ".join(titles))
    ok("filter help names OR and AND", "oricare" in page.locator(".fhelp").inner_text())

    # 2. Subject counts: each option counts unique entries, with the other facets applied.
    fin, gov = "subiect:finante-publice", "subiect:guvernare-democratie"
    for sid in (fin, gov):
        n = int(page.locator(f'[data-slot="side"] .fopt[data-val="{sid}"] .n').inner_text())
        ok(f"subject count {sid}", n == sum(sid in subj_set(i) for i in projects), str(n))
    # 3. One subject: a flat list under that subject, including secondary-subject entries.
    page.click(f'[data-slot="side"] .fopt[data-val="{fin}"]')
    want = [i for i in projects if fin in subj_set(i)]
    ok("subject filter count", count_text(page) == len(want), f"{count_text(page)} vs {len(want)}")
    ok("subject filter is one flat group", page.locator('[data-slot="results"] .group').count() == 1)
    secondary = [i["slug"] for i in want if i["primarySubject"] != fin]
    shown = page.locator('[data-slot="results"] [data-open]').evaluate_all("els => els.map(e => e.dataset.open)")
    ok("secondary-subject entries appear under the selected subject", all(s in shown for s in secondary), f"{len(secondary)} secondary")
    ok("URL holds subj", "subj=" in page.url)
    # 4. OR within the facet.
    page.click(f'[data-slot="side"] .fopt[data-val="{gov}"]')
    want = [i for i in projects if {fin, gov} & subj_set(i)]
    ok("two subjects: OR, unique entries", count_text(page) == len(want), f"{count_text(page)} vs {len(want)}")
    # 5. AND across facets, with counts that ignore the own facet.
    cap = "functie:comparare"
    exp_cap_count = sum(cap in i["capabilities"] for i in want)
    if page.locator('[data-facet="cap"]').get_attribute("open") is None:
        page.click('[data-facet="cap"] > summary')
    n = int(page.locator(f'[data-facet="cap"] .tag[data-val="{cap}"] .n').inner_text())
    ok("capability count applies the subject filter", n == exp_cap_count, f"{n} vs {exp_cap_count}")
    page.focus(f'[data-facet="cap"] .tag[data-val="{cap}"]')
    page.keyboard.press("Enter")
    page.wait_for_timeout(200)
    want_and = [i for i in want if cap in i["capabilities"]]
    ok("subject AND capability", count_text(page) == len(want_and), f"{count_text(page)} vs {len(want_and)}")
    ok("focus stays on the pressed facet button", page.evaluate("document.activeElement?.dataset?.val") == cap)
    sub_counts = {sid: int(page.locator(f'[data-slot="side"] .fopt[data-val="{sid}"] .n').inner_text()) for sid in (fin, gov)}
    ok("subject counts apply the capability filter", all(sub_counts[s] == sum(s in subj_set(i) and cap in i["capabilities"] for i in projects) for s in sub_counts), str(sub_counts))
    pills = page.locator('[data-slot="toolbar"] .pill').all_inner_texts()
    ok("selected filters are labelled pills", any(p.startswith("Subiect: ") for p in pills) and any(p.startswith("Ce poți face: ") for p in pills), " | ".join(pills))

    # 6. Topic ancestry: a broader topic finds entries assigned to its narrower topics.
    narrower = [c for c in C.values() if c["scheme"] == "subiect" and any(C[b]["broader"] for b in c["broader"])]
    if narrower:
        child = narrower[0]
        parent = next(b for b in child["broader"] if C[b]["broader"])
        kind = next((i["kind"] for i in DB["items"] if child["id"] in i["topics"]), "proiect")
        go(f"?k={kind}&topic={urllib.parse.quote(parent)}")
        want = [i for i in visible(kind) if parent in topic_set(i)]
        ok(f"topic ancestry {parent} ⊇ {child['id']}", count_text(page) == len(want) and any(child["id"] in i["topics"] for i in want), f"{count_text(page)} vs {len(want)}")

    # 7. Area: Bucharest includes national entries, labelled as national.
    go("?area=localitate:bucuresti")
    want = [i for i in projects if applies(i, "localitate:bucuresti")]
    ok("area filter includes national coverage", count_text(page) == len(want) and any(i["coverageLevel"] == "national" for i in want), f"{count_text(page)} vs {len(want)}")
    ok("national entries say Național", "Național" in page.locator('[data-slot="results"]').inner_text())

    # 8. Old bookmarks keep their v1 meaning.
    for q, pred in [("d=bani", lambda i: i["legacy"].get("domeniu") == "bani"),
                    ("t=harta,ghid", lambda i: bool({"harta", "ghid"} & set(i["legacy"].get("tips", [])))),
                    ("kw=ai", lambda i: "ai" in i["legacy"].get("keywords", [])),
                    ("c=Arad", lambda i: i["legacy"].get("oras") == "Arad")]:
        go("?" + q)
        want = [i for i in projects if i.get("legacy") and pred(i)]
        pills = page.locator('[data-slot="toolbar"] .pill').all_inner_texts()
        ok(f"v1 bookmark ?{q}", count_text(page) == len(want) and any("(v1)" in p for p in pills), f"{count_text(page)} vs {len(want)}; {pills}")
    go("?o=domeniu")
    ok("v1 ?o=domeniu shows the grouped view", page.locator('[data-slot="results"] .group').count() > 1 and page.locator("#sort").input_value() == "subiect")
    page.goto(BASE + "?p=ce-cumpara-primaria")
    page.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    ok("v1 ?p= moves to the entry address", page.url.rstrip("/").endswith("/proiect/ce-cumpara-primaria"), page.url)

    # 9. Direct links and the detail panel.
    org = next(i for i in DB["items"] if i["kind"] == "organizatie" and i["attributions"] == [] and i["primarySubject"])
    page.goto(BASE + f"organizatie/{org['slug']}/")
    page.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    ok("direct organisation link opens its tab and panel", page.locator('.tab[aria-current="page"]').inner_text().startswith("Organizații")
       and page.locator("#d-title").inner_text() == org["name"])
    drawer = page.locator('[data-slot="drawer"]').inner_text()
    ok("organisation panel: Despre ce / Ce face", "DESPRE CE" in drawer.upper() and "CE FACE" in drawer.upper())
    proj = next(i for i in DB["items"] if i["kind"] == "proiect" and i["attributions"] and not any(a["accepted"] for a in i["attributions"]) and i["status"] == "activ")
    page.goto(BASE + f"proiect/{proj['slug']}/")
    page.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    drawer = page.locator('[data-slot="drawer"]').inner_text()
    ok("unconfirmed attribution is neutral", "rol neconfirmat" in drawer and "Autor" not in drawer.split("\n"), proj["slug"])
    ok("project panel groups", all(g in drawer.upper() for g in ("DESPRE CE", "CE OFERĂ", "ACOPERIRE")))
    img = next(i for i in DB["items"] if i["img"])
    page.goto(BASE + f"{img['kind']}/{img['slug']}/")
    page.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    loaded = page.evaluate("[...document.querySelectorAll('[data-slot=drawer] img')].every(i => i.complete && i.naturalWidth > 0)")
    ok("images resolve from an entry page", loaded, img["slug"])
    page.goto(BASE + "resursa/incentru/") if any(i["slug"] == "incentru" and i["kind"] == "resursa" for i in DB["items"]) else page.goto(BASE + "proiect/incentru/")
    page.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    ok("abstention shows an incomplete classification", "nu stabilesc încă subiectul" in page.locator('[data-slot="drawer"]').inner_text())

    # 10. Archives.
    for kind in ("proiect", "organizatie", "resursa"):
        r = page.goto(BASE + f"{kind}/")
        n = page.locator(".arch-item").count()
        ok(f"archive /{kind}/", r.status == 200 and n == sum(i["kind"] == kind for i in DB["items"]), f"{n} items")
    heads = page.goto(BASE + "proiect/") and page.locator(".arch-group h2").all_inner_texts()
    ok("project archive grouped by primary subject", len(heads) > 5 and any("Fără subiect" in h for h in heads) == any(not i["primarySubject"] and i["kind"] == "proiect" for i in DB["items"]), f"{len(heads)} groups")

    # 11. Search: synonyms, English labels, diacritics; concept suggestions say their facet.
    go("")
    for typed, expect in [("bani publici", "Subiect: Finanțe publice"), ("public procurement", "Temă: Achiziții publice"), ("achizitii", "Temă: Achiziții publice")]:
        page.fill('[data-slot="q"]', typed)
        page.wait_for_selector('[data-slot="ac"]:not([hidden])')
        text = page.locator('[data-slot="ac"]').inner_text()
        ok(f"suggestion for '{typed}'", expect in text, text.replace("\n", " | ")[:160])
    # The AI topic is assigned to organisations only; the AI technology to projects. Each tab suggests its own, by facet.
    go("?k=organizatie")
    page.fill('[data-slot="q"]', "artificial")
    page.wait_for_selector('[data-slot="ac"]:not([hidden])')
    org_text = page.locator('[data-slot="ac"]').inner_text()
    go("")
    page.fill('[data-slot="q"]', "artificial")
    page.wait_for_selector('[data-slot="ac"]:not([hidden])')
    text = page.locator('[data-slot="ac"]').inner_text()
    ok("AI topic and AI technology are distinct suggestions", "Temă: Inteligență artificială" in org_text and "Tehnologie: Utilizează inteligență artificială" in text
       and "Tehnologie:" not in org_text, (org_text + " || " + text).replace("\n", " | ")[:220])
    page.locator('[data-slot="ac"] .ac-opt', has_text="Tehnologie: Utilizează").click()
    pills = page.locator('[data-slot="toolbar"] .pill').all_inner_texts()
    want = [i for i in projects if "tehnologie:ai" in i["technologies"]]
    ok("picked suggestion becomes a pill and a filter", any(p.startswith("Tehnologie: ") for p in pills) and count_text(page) == len(want), f"{pills}; {count_text(page)} vs {len(want)}")
    go("")
    page.fill('[data-slot="q"]', "achizitii")
    page.wait_for_timeout(400)
    ok("free-text search still works without a concept", count_text(page) > 0, str(count_text(page)))

    # 12. Short topic list, labelled badges, dialog focus.
    go("")
    tab_topics = {t for i in DB["items"] if i["kind"] == "proiect" for t in i["topics"]}
    shown_topics = page.locator('[data-slot="side"] [data-facet="topic"] .tag').count()
    ok("topic facet starts short without a subject", len(tab_topics) <= 12 or shown_topics == 12, f"{shown_topics} of {len(tab_topics)}")
    if len(tab_topics) > 12:
        page.click('[data-slot="side"] [data-act="topics"]')
        ok("topic facet expands on request", page.locator('[data-slot="side"] [data-facet="topic"] .tag').count() == len(tab_topics))
        ok("focus stays on the expand button", page.evaluate("document.activeElement?.dataset?.act") == "topics")
    go("?v=list")
    hidden = page.locator('[data-slot="results"] .row-kw .vh').first.inner_text()
    ok("result badges name their facet", hidden.rstrip(": ") in ("Temă", "Format", "Ce poți face"), hidden)
    page.locator('[data-slot="results"] [data-open]').first.click()
    page.wait_for_selector('[data-slot="drawer"]:not([hidden])')
    page.wait_for_timeout(100)
    page.keyboard.press("Control+k")
    ok("search shortcut stays out of an open dialog", page.evaluate("!!document.activeElement.closest('[data-slot=\"drawer\"]')"))
    page.focus('[data-slot="drawer"] [data-act="close"]')
    page.keyboard.press("Shift+Tab")
    ok("Shift+Tab from Close reaches a visible control", page.evaluate(
        "(() => { const a = document.activeElement; return !!a.closest('[data-slot=\"drawer\"]') && a.dataset.act !== 'close' && a.checkVisibility(); })()"))
    page.keyboard.press("Escape")

    # 13. What the v1 site shows must stay: report options, site link, related entries, card types, v1 search words.
    it = next(i for i in DB["items"] if i["kind"] == "organizatie" and i["sheet"])
    go(f"organizatie/{it['slug']}/")
    page.wait_for_selector('[data-slot="drawer"]:not([hidden]) h2')
    flag = page.locator('[data-slot="drawer"] .flag a', has_text="Corectează în tabel")
    ok("report panel opens the entry's Sheet row", flag.count() == 1 and f"gid={DB['site']['tabs'][it['sheet']['tab']]}&range=A{it['sheet']['row']}" in flag.get_attribute("href"),
       str(it["sheet"]))
    link = page.locator('[data-slot="drawer"] .d-url')
    ok("site link is the plain address", link.count() == 1 and it["domain"] in link.inner_text() and "Deschide" not in link.inner_text(), link.inner_text() if link.count() else "none")
    alone = [i for i in DB["items"] if i["kind"] == "organizatie" and i["primarySubject"] and i["status"] not in INACTIVE
             and not any(j["primarySubject"] == i["primarySubject"] and j["slug"] != i["slug"] for j in DB["items"] if j["kind"] == "organizatie")
             and any(i["primarySubject"] in subj_set(j) and j["slug"] != i["slug"] and j["status"] not in INACTIVE for j in DB["items"] if j["kind"] == "organizatie")]
    if alone:
        go(f"organizatie/{alone[0]['slug']}/")
        page.wait_for_selector('[data-slot="drawer"]:not([hidden]) h2')
        ok("related entries include secondary-subject matches", page.locator('[data-slot="drawer"] .related [data-open]').count() > 0, alone[0]["slug"])
    ok("footer offers the Sheet, the Form and GitHub", all(page.locator(f'footer a[href*="{h}"]').count() == 1 for h in ("docs.google.com/spreadsheets", "forms.gle", "/issues/new")))
    go("?o=az&v=cards")
    fmt_item = next(i for i in sorted(projects, key=lambda i: i["name"].lower()) if i["formats"] and i["entityType"] == "proiect")
    meta = page.locator(f'[data-slot="results"] .card[data-open="{fmt_item["slug"]}"] .meta').inner_text()
    ok("card meta names a format", C[fmt_item["formats"][0]]["label"].upper() in meta.upper(), meta)
    old_kw = [i for i in DB["items"] if "date-deschise" in i["legacy"].get("keywords", [])]
    go("?k=" + old_kw[0]["kind"] + "&q=date%20deschise&ina=1")
    shown = page.locator('[data-slot="results"] [data-open]').evaluate_all("els => els.map(e => e.dataset.open)")
    want = [i["slug"] for i in old_kw if i["kind"] == old_kw[0]["kind"]]
    ok("a v1 keyword still finds its entries", all(s in shown for s in want), f"{len(want)} expected")

    # 14. Mobile: subject chips, filter sheet, counts.
    m = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    m.on("pageerror", lambda e: errors.append(str(e)))
    m.goto(BASE)
    m.wait_for_selector('[data-slot="toolbar"] .count')
    chips = m.locator('[data-slot="chips"] .chip').all_inner_texts()
    ok("mobile subject chips", len(chips) > 3 and chips[0].startswith("Toate"), str(len(chips)))
    m.goto(BASE + "?v=cards")
    m.wait_for_selector('[data-slot="results"] .card')
    box = m.locator('[data-slot="results"] .card .media').first.bounding_box()
    ok("mobile cards: a small picture on the left", box and box["width"] <= 80 and box["x"] < 40, str(box))
    m.goto(BASE + "?v=list")
    m.wait_for_selector('[data-slot="results"] .row')
    ok("mobile list: no picture", not m.locator('[data-slot="results"] .list > .row > .thumb').first.is_visible())
    m.goto(BASE)
    m.wait_for_selector('[data-slot="toolbar"] .count')
    m.click(f'[data-slot="chips"] .chip[data-val="{fin}"]')
    want = [i for i in projects if fin in subj_set(i)]
    ok("mobile chip filters by subject", int(m.locator('[data-slot="toolbar"] .count b').inner_text()) == len(want))
    m.click('[data-act="sheet"]')
    m.wait_for_selector('[data-slot="sheet"]:not([hidden]) .facet')
    sheet_titles = m.locator('[data-slot="sheet"] .facet > summary .kicker').all_inner_texts()
    ok("mobile sheet has the facets", "Format" in " ".join(sheet_titles) or "FORMAT" in " ".join(sheet_titles).upper(), " / ".join(sheet_titles))
    fmt_facet = m.locator('[data-slot="sheet"] [data-facet="fmt"]')
    if fmt_facet.get_attribute("open") is None:
        fmt_facet.locator("summary").click()
    first = fmt_facet.locator(".tag:not([disabled])").first
    val, n = first.get_attribute("data-val"), int(first.locator(".n").inner_text())
    first.click()
    btn = m.locator('[data-slot="sheet"] .d-cta .btn-primary').inner_text()
    ok("mobile sheet count follows the choice", str(n) in btn and n == sum(fin in subj_set(i) and val in i["formats"] for i in projects), f"{btn}; {val}")
    ok("mobile sheet keeps the focus on the pressed choice", m.evaluate("document.activeElement?.closest('[data-slot=\"sheet\"]') && document.activeElement.dataset.val") == val)
    toggle = m.locator('[data-slot="sheet"] input[data-act="toggle"]').first
    if toggle.count():
        m.locator('[data-slot="sheet"] [data-facet="optiuni"]').evaluate("d => d.open = true")
        toggle.focus()
        m.keyboard.press("Space")
        ok("mobile sheet keeps the focus on a toggle", m.evaluate("document.activeElement?.dataset?.act") == "toggle")
    m.close()

    ok("no page errors", not errors, "; ".join(errors[:3]))
    browser.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
