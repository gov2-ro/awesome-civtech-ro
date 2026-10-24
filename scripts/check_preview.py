# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Browser acceptance checks for a v2 preview: desktop and mobile filtering, counts, direct links, archives, old
bookmarks, search labels, a failed data load and its retry, the page without JavaScript, the canonical and share tags
after opening and closing an entry, and the wording of the observed dates. It reads the preview's own data.json for the
expected numbers; it changes nothing (two checks rewrite data.json in the browser only, with Playwright's `page.route`).

    python3 scripts/build.py --data-dir data/taxonomy-v2/integrare --site-dir /tmp/civtech-v2 --allow-draft
    python3 -m http.server -d /tmp/civtech-v2 8765 &
    uv run scripts/check_preview.py http://localhost:8765/

Exits 1 when a check fails. Playwright needs its Chromium (`uv run --with playwright playwright install chromium`).
"""
import copy
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
# Cloudflare answers 403 to urllib's default User-Agent, so a run against the live site names itself.
DB = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "data.json", headers={"User-Agent": "Mozilla/5.0 (check_preview.py)"})).read())
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
    return any(a == x or x in up(a) for a in it["areas"])


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
    ok("sidebar order", [t.upper() for t in titles[:4]] == ["SUBIECT", "CE POȚI FACE", "SURSE DE DATE", "FORMAT"] and "TEMĂ" not in [t.upper() for t in titles], " / ".join(titles))
    ok("filter help names OR and AND", "oricare" in page.locator(".fhelp").inner_text())

    # 2. Subject counts: each option counts unique entries, with the other facets applied.
    fin, gov = "subiect:finante-publice", "subiect:guvernare-democratie"
    for sid in (fin, gov):
        n = int(page.locator(f'[data-slot="side"] .tag[data-val="{sid}"] .n').inner_text())
        ok(f"subject count {sid}", n == sum(sid in subj_set(i) for i in projects), str(n))
    # 3. One subject: a flat list under that subject, including secondary-subject entries.
    page.click(f'[data-slot="side"] .tag[data-val="{fin}"]')
    want = [i for i in projects if fin in subj_set(i)]
    ok("subject filter count", count_text(page) == len(want), f"{count_text(page)} vs {len(want)}")
    ok("subject filter is one flat group", page.locator('[data-slot="results"] .group').count() == 1)
    secondary = [i["slug"] for i in want if i["primarySubject"] != fin]
    shown = page.locator('[data-slot="results"] [data-open]').evaluate_all("els => els.map(e => e.dataset.open)")
    ok("secondary-subject entries appear under the selected subject", all(s in shown for s in secondary), f"{len(secondary)} secondary")
    ok("URL holds subj", "subj=" in page.url)
    # 4. OR within the facet.
    page.click(f'[data-slot="side"] .tag[data-val="{gov}"]')
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
    sub_counts = {sid: int(page.locator(f'[data-slot="side"] .tag[data-val="{sid}"] .n').inner_text()) for sid in (fin, gov)}
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

    # 7. Local coverage excludes entries assigned only to the country.
    go("?area=localitate:bucuresti")
    want = [i for i in projects if applies(i, "localitate:bucuresti")]
    ok("area filter uses explicit local coverage", count_text(page) == len(want) and all("tara:RO" not in i["areas"] or "localitate:bucuresti" in i["areas"] for i in want), f"{count_text(page)} vs {len(want)}")


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
    every_image = "[...document.querySelectorAll('[data-slot=drawer] img')].every(i => i.complete && i.naturalWidth > 0)"
    try:  # over a real network the images arrive after the panel opens
        page.wait_for_function(every_image, timeout=10000)
    except PlaywrightTimeout:
        pass
    loaded = page.evaluate(every_image)
    ok("images resolve from an entry page", loaded, img["slug"])
    blank = next((i for i in DB["items"] if not i["primarySubject"]), None)  # an abstention; none once every entry has a subject
    if blank:
        page.goto(BASE + f"{blank['kind']}/{blank['slug']}/")
        page.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
        ok("abstention shows an incomplete classification", "nu stabilesc încă subiectul" in page.locator('[data-slot="drawer"]').inner_text(), blank["slug"])

    # 10. Archives.
    for kind in ("proiect", "organizatie", "resursa"):
        r = page.goto(BASE + f"{kind}/")
        n = page.locator(".arch-item").count()
        ok(f"archive /{kind}/", r.status == 200 and n == sum(i["kind"] == kind for i in DB["items"]), f"{n} items")
    heads = page.goto(BASE + "proiect/") and page.locator(".arch-group h2").all_inner_texts()
    ok("project archive grouped by primary subject", len(heads) > 5 and any("Fără subiect" in h for h in heads) == any(not i["primarySubject"] and i["kind"] == "proiect" for i in DB["items"]), f"{len(heads)} groups")

    # 11. Search: synonyms, English labels, diacritics; concept suggestions say their facet.
    go("")
    for typed, expect in [("bani publici", "Subiect: Finanțe publice"), ("public procurement", "Subiect: Achiziții publice"), ("achizitii", "Subiect: Achiziții publice")]:
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
    ok("AI topic and AI technology are distinct suggestions", "Subiect: Inteligență artificială" in org_text and "Tehnologie: Utilizează inteligență artificială" in text
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
    subject = page.locator('[data-slot="side"] [data-facet="subj"]')
    counts = subject.locator('.tag .n').all_inner_texts()
    ok("common subjects sorted by count", list(map(int, counts)) == sorted(map(int, counts), reverse=True))
    ok("rare subjects start hidden", all(int(n) > 3 for n in counts))
    subject.locator('[data-act="more-options"]').click()
    ok("rare subjects expand on request", any(int(n) <= 3 for n in subject.locator('.tag .n').all_inner_texts()))
    ok("focus stays on the expand button", page.evaluate("document.activeElement?.dataset?.act") == "more-options")
    # A root and a topic share OR semantics and count each entry once.
    topic = "subiect:achizitii-publice"
    go("?subj=" + urllib.parse.quote(fin + "," + topic))
    want = [i for i in projects if fin in subj_set(i) or topic in topic_set(i)]
    ok("combined subject and topic use OR", count_text(page) == len(want))
    selected = page.locator('[data-slot="side"] [data-facet="subj"] .tag[aria-pressed="true"]')
    ok("selected options remain visible", selected.count() == 2 and all(selected.nth(i).is_visible() for i in range(2)))
    sourced = next(i for i in projects if i.get("dataSources"))
    source = sourced["dataSources"][0]["name"]
    evidence = sourced["dataSources"][0]["evidence"]
    go("?source=" + urllib.parse.quote(source))
    want = [i for i in projects if source in [d["name"] for d in i.get("dataSources", [])]]
    ok("data source filter counts providers", count_text(page) == len(want))
    go("proiect/" + sourced["slug"] + "/")
    ok("detail links source evidence", page.locator('[data-slot="drawer"] .d-class a', has_text='INS').get_attribute("href") == evidence)
    parliament = next(i for i in DB['items'] if any(d['name'] in ('Camera Deputaților', 'Senatul României') for d in i.get('dataSources', [])))
    want = [i for i in visible(parliament['kind']) if any(d['name'] in ('Camera Deputaților', 'Senatul României') for d in i.get('dataSources', []))]
    go('?k=' + parliament['kind'] + '&source=Parlament')
    ok('Parlament combines chambers and counts each entry once', count_text(page) == len(want))
    go('?k=' + parliament['kind'] + '&source=' + urllib.parse.quote('Senatul României'))
    ok('old chamber filter maps to Parlament', count_text(page) == len(want) and 'Parlament' in page.locator('[data-slot="toolbar"] .pill').inner_text())
    go(parliament['kind'] + '/' + parliament['slug'] + '/')
    ok('detail combines chamber links', page.locator('[data-slot="drawer"] .d-class a', has_text='Parlament').count() == 1)
    go('')
    cap_facet = page.locator('[data-slot="side"] [data-facet="cap"]')
    cap_facet.evaluate('(d) => d.open = true')
    tag = cap_facet.locator('.tag[href]').first
    val = tag.get_attribute('data-val')
    tag.focus()
    page.keyboard.press('Space')
    ok('inline filter supports Space', page.locator('[data-slot="side"] [data-facet="cap"] .tag[aria-pressed="true"]').get_attribute('data-val') == val)
    page.keyboard.press('Enter')
    ok('inline filter supports Enter', page.locator('[data-slot="side"] [data-facet="cap"] .tag[aria-pressed="true"]').count() == 0 and not urllib.parse.urlsplit(page.url).fragment)
    for coverage, predicate in [
        ('national', lambda i: i['coverageLevel'] == 'national' and i.get('dataDetail') == 'agregat-national'),
        ('national-local', lambda i: i['coverageLevel'] == 'national' and i.get('dataDetail') in ('judete', 'localitati', 'judete-localitati')),
        ('local', lambda i: i['coverageLevel'] == 'local'),
        ('national-unknown', lambda i: i['coverageLevel'] == 'national' and not i.get('dataDetail')),
    ]:
        go('?coverage=' + coverage)
        ok('geographic coverage ' + coverage, count_text(page) == sum(predicate(i) for i in projects))
    proposed = next((r for r in DB['items'] if r['slug'] == 'demoanaf'), None)
    ok('unreviewed sources stay out of the public field', proposed is not None and not proposed['dataSources'])
    go("?v=list")
    hidden = page.locator('[data-slot="results"] .row-kw .vh').first.inner_text()
    ok("result badges name their facet", hidden.rstrip(": ") in ("Subiect", "Format", "Ce poți face"), hidden)
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
    first = fmt_facet.locator('.tag:not([disabled]):not([aria-disabled="true"])').first
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

    # 15. A failed data load: a message, a retry button and the three static lists; the retry loads the page.
    def flaky(fail_times, status=None):
        """A route handler that fails the first `fail_times` requests (aborted, or answered with `status`), then lets them through."""
        calls = {"n": 0}

        def handler(route):
            calls["n"] += 1
            if calls["n"] > fail_times:
                route.continue_()
            elif status:
                route.fulfill(status=status, body="unavailable", content_type="text/plain")
            else:
                route.abort()
        return handler, calls

    archive_hrefs = [BASE + f"{k}/" for k in ("proiect", "organizatie", "resursa")]
    hrefs_in = lambda p, sel: p.evaluate("sel => [...document.querySelectorAll(sel)].map(a => a.href)", sel)
    load_errors = []
    f = browser.new_page(viewport={"width": 1280, "height": 900})
    f.on("pageerror", lambda e: load_errors.append(str(e)))
    handler, calls = flaky(2)
    f.route("**/data.json", handler)
    f.goto(BASE)
    f.wait_for_selector('[data-slot="results"] [data-act="retry"]')
    alert = f.locator('[data-slot="results"] [role="alert"]')
    ok("failed data load shows a message and a retry button", alert.count() == 1 and "Nu am putut încărca" in alert.inner_text()
       and "Încearcă din nou" in alert.locator('[data-act="retry"]').inner_text(), alert.inner_text().replace("\n", " | ")[:120])
    ok("failed data load links the three static lists", hrefs_in(f, '[data-slot="results"] [role="alert"] a') == archive_hrefs)
    f.fill('[data-slot="q"]', "achizitii")
    f.evaluate("document.querySelector('[data-act=\"sheet\"]').click()")
    f.wait_for_timeout(300)
    ok("search box and filter button do nothing while the data is missing", not load_errors and f.locator('[data-slot="sheet"]').is_hidden(), "; ".join(load_errors[:2]))
    f.click('[data-act="retry"]')
    f.wait_for_selector('[data-slot="results"] [data-act="retry"]')
    ok("a retry that fails again keeps the message and the focus on the button", f.locator('[data-slot="results"] [role="alert"]').count() == 1
       and f.evaluate("document.activeElement?.dataset?.act") == "retry", f"{calls['n']} requests")
    f.fill('[data-slot="q"]', "")
    f.click('[data-act="retry"]')
    f.wait_for_selector('[data-slot="toolbar"] .count')
    ok("a retry that succeeds loads the list", count_text(f) == len(projects) and f.locator('[role="alert"]').count() == 0 and calls["n"] == 3,
       f"{count_text(f)} results, {calls['n']} requests")
    f.close()
    f = browser.new_page(viewport={"width": 1280, "height": 900})
    handler, calls = flaky(1, status=500)
    f.route("**/data.json", handler)
    f.goto(BASE)
    f.wait_for_selector('[data-slot="results"] [data-act="retry"]')
    shown = "Nu am putut încărca" in f.locator('[data-slot="results"]').inner_text()
    f.click('[data-act="retry"]')
    f.wait_for_selector('[data-slot="toolbar"] .count')
    ok("a server error shows the same message, and the retry works", shown and count_text(f) == len(projects))
    f.close()
    f = browser.new_page(viewport={"width": 1280, "height": 900})
    handler, calls = flaky(1)
    f.route("**/data.json", handler)
    f.goto(BASE + f"proiect/{proj['slug']}/")
    f.wait_for_selector('[data-slot="results"] [data-act="retry"]')
    ok("failed load on an entry page links the lists from the site root", hrefs_in(f, '[data-slot="results"] [role="alert"] a') == archive_hrefs)
    f.click('[data-act="retry"]')
    f.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    ok("retry on an entry page opens the entry", f.locator("#d-title").inner_text() == proj["name"])
    f.close()

    # 16. Without JavaScript: an introduction and the three archives; the footer links the methodology page.
    nojs = browser.new_context(java_script_enabled=False)
    n = nojs.new_page()
    n.goto(BASE)
    intro = n.locator("#results").inner_text()
    ok("without JavaScript the home page has an introduction", "JavaScript" in intro and "Director de instrumente civice" in intro, intro.replace("\n", " | ")[:100])
    links = hrefs_in(n, "#results a")
    ok("without JavaScript the home page links the three archives", links == archive_hrefs and all(nojs.request.get(h).status == 200 for h in links), str(links))
    n.goto(BASE + f"proiect/{proj['slug']}/")
    ok("without JavaScript an entry page shows the entry and links the archives", n.locator("article.nojs h1").inner_text() == proj["name"]
       and hrefs_in(n, "#results a") == archive_hrefs)
    method = "https://github.com/gov2-ro/awesome-civtech-ro/blob/main/docs/METODOLOGIE.md"
    ok("footer links the methodology page", hrefs_in(n, "footer a").count(method) == 1)
    page.goto(BASE)
    page.wait_for_selector('[data-slot="toolbar"] .count')
    ok("footer links the methodology page (with JavaScript)", page.locator(f'footer a[href="{method}"]').count() == 1)
    doc = (Path(__file__).resolve().parent.parent / "docs" / "METODOLOGIE.md").read_text(encoding="utf-8")
    ok("the methodology page is in the repo and covers status, code link, first trace, activity and score",
       all(t in doc for t in ("## 1. Starea", "nu este o licență open source", "Nu este data lansării", "## 4. Ultima actualizare", "## 6. Scorul de relevanță", "Ce favorizează scorul")))

    # 17. Canonical and share metadata follow the address: the static head of an entry page, the home head, and back.
    HEAD_JS = """() => { const g = (s, a = 'content') => document.querySelector(s)?.getAttribute(a) ?? null;
      return { canonical: g('link[rel="canonical"]', 'href'), 'og:url': g('meta[property="og:url"]'), description: g('meta[name="description"]'),
        'og:title': g('meta[property="og:title"]'), 'og:description': g('meta[property="og:description"]'),
        'twitter:title': g('meta[name="twitter:title"]'), 'twitter:description': g('meta[name="twitter:description"]'),
        'og:image': g('meta[property="og:image"]'), 'twitter:image': g('meta[name="twitter:image"]'),
        'og:image:width': g('meta[property="og:image:width"]'), 'og:image:height': g('meta[property="og:image:height"]'),
        'og:image:alt': g('meta[property="og:image:alt"]') }; }"""
    TEXTS = ("description", "og:description", "twitter:description")
    head = lambda p: p.evaluate(HEAD_JS)
    differs = lambda got, want, skip=(): {k: got[k] for k in want if k not in skip and got[k] != want[k]}
    raw = nojs.new_page()  # no script runs here: its head is what build.py wrote

    def raw_head(path):
        raw.goto(BASE + path)
        return head(raw)
    home_head = raw_head("")
    cover = next(i for i in DB["items"] if i["img"] and i["img"]["kind"] != "logo" and i["status"] not in INACTIVE)
    plain = next(i for i in DB["items"] if (not i["img"] or i["img"]["kind"] == "logo") and i["status"] not in INACTIVE)  # no cover: the shared image
    x_head, y_head = raw_head(f"{plain['kind']}/{plain['slug']}/"), raw_head(f"{cover['kind']}/{cover['slug']}/")
    ok("static heads differ: home, entry without a cover, entry with a cover", len({home_head["canonical"], x_head["canonical"], y_head["canonical"]}) == 3
       and y_head["og:image"] != home_head["og:image"] and x_head["og:image"] == home_head["og:image"])
    h = browser.new_page(viewport={"width": 1280, "height": 900})
    h.on("pageerror", lambda e: errors.append(str(e)))
    h.goto(BASE + f"{plain['kind']}/{plain['slug']}/")
    h.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    ok("an entry opened directly keeps its own head", not differs(head(h), x_head), str(differs(head(h), x_head)))
    h.click('[data-slot="drawer"] [data-act="close"]')
    h.wait_for_selector('[data-slot="drawer"][hidden]', state="attached")
    ok("closing a directly opened entry restores the home canonical and share tags", not differs(head(h), home_head), str(differs(head(h), home_head)))
    ok("closing an entry restores the page title", plain["name"] not in h.title())
    h.goto(BASE + f"?k={cover['kind']}&ina=1&o=az")
    h.wait_for_selector('[data-slot="toolbar"] .count')
    ok("the home page keeps its own head", not differs(head(h), home_head), str(differs(head(h), home_head)))
    h.locator(f'[data-slot="results"] [data-open="{cover["slug"]}"] a.stretch').first.click()
    h.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    got = head(h)
    ok("opening an entry in the page sets its canonical and share tags", not differs(got, y_head, TEXTS) and all(got[k].startswith(y_head[k][:30]) for k in TEXTS),
       str(differs(got, y_head, TEXTS)))
    h.go_back()
    h.wait_for_selector('[data-slot="drawer"][hidden]', state="attached")
    ok("Back restores the home canonical and share tags", not differs(head(h), home_head), str(differs(head(h), home_head)))
    h.locator(f'[data-slot="results"] [data-open="{cover["slug"]}"] a.stretch').first.click()
    h.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    h.keyboard.press("Escape")
    h.wait_for_selector('[data-slot="drawer"][hidden]', state="attached")
    ok("Escape restores the home canonical and share tags", not differs(head(h), home_head), str(differs(head(h), home_head)))
    h.goto(BASE + f"?p={plain['slug']}")
    h.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    ok("an old ?p= link gets the entry's canonical", not differs(head(h), x_head, TEXTS), str(differs(head(h), x_head, TEXTS)))
    h.close()

    # 18. Observed dates: badges, columns, sort and toggle say "observed", not "launched" (data.json is rewritten with known dates).
    today = datetime.now(timezone.utc).date()
    a_item, b_item = projects[0], projects[1]
    altered = copy.deepcopy(DB)
    for it, days, src in ((a_item, 30, "arhiva"), (b_item, 120, "cod")):
        row = next(i for i in altered["items"] if i["slug"] == it["slug"])
        row["since"], row["sinceSrc"] = (today - timedelta(days=days)).isoformat(), src
    by_slug = {i["slug"]: i for i in altered["items"]}
    fresh_n = sum(1 for i in altered["items"] if i["kind"] == "proiect" and i["status"] not in INACTIVE and i["since"]
                  and (today - date.fromisoformat(i["since"])).days < 183)
    body = json.dumps(altered, ensure_ascii=False)
    w = browser.new_page(viewport={"width": 1280, "height": 900})
    w.on("pageerror", lambda e: errors.append(str(e)))
    w.route("**/data.json", lambda route: route.fulfill(body=body, content_type="application/json"))
    w.goto(BASE + "?v=list")
    w.wait_for_selector('[data-slot="results"] .row')
    row_a, row_b = (w.locator(f'[data-slot="results"] .row[data-open="{i["slug"]}"]') for i in (a_item, b_item))
    tag_a, tag_b = row_a.locator(".new-tag"), row_b.locator(".new-tag")
    ok("a recent first trace reads \"apărut recent\", not \"lansat\" or \"nou\"", tag_a.inner_text().lower() == "apărut recent" and tag_b.inner_text().lower() == "apărut recent",
       f"{tag_a.inner_text()!r} / {tag_b.inner_text()!r}")
    ok("the badge tooltip says observed, names the date and source, and denies a launch", all(t in tag_a.get_attribute("title") for t in (
        "Prima urmă observată", "acum 30 de zile", (today - timedelta(days=30)).isoformat(), "prima arhivare Wayback", "Nu este data lansării")), tag_a.get_attribute("title"))
    ok("the 60-day and 183-day tiers keep their two looks", "launch" in tag_a.get_attribute("class") and "launch" not in tag_b.get_attribute("class"))
    head_row = w.locator(".list-head").first
    titles = head_row.locator("span").all_inner_texts()
    helps = head_row.locator("span[title]").evaluate_all("els => els.map(e => e.title)")
    ok("date column headers are Romanian words with tooltips that explain Z, L, A", "PRIMA URMĂ" in [t.upper() for t in titles] and "ACTUALIZAT" in [t.upper() for t in titles]
       and len(helps) == 2 and all("Z = zile, L = luni, A = ani" in t for t in helps) and "Nu este data lansării" in helps[0], " | ".join(helps)[:90])
    cell = row_a.locator(".row-side").nth(1)
    ok("the first-trace cell shows the short span and gives screen readers the words", cell.text_content().startswith("30Z") and "prima urmă observată acum 30 de zile" in cell.text_content(),
       cell.text_content())
    option = w.locator('#sort option[value="nou"]')
    ok("sort label says first trace", option.inner_text() == "Apărute recent (prima urmă)" and "Prima urmă observată" in option.get_attribute("title"), option.inner_text())
    w.select_option("#sort", "nou")
    w.wait_for_timeout(100)
    first = w.locator('[data-slot="results"] [data-open]').first.get_attribute("data-open")
    top = max(i["since"] for i in altered["items"] if i["kind"] == "proiect" and i["status"] not in INACTIVE)
    ok("sorting by first trace puts the newest trace first", by_slug[first]["since"] == top, f"{first} {by_slug[first]['since']} vs {top}")
    w.goto(BASE + "?v=list")
    w.wait_for_selector('[data-slot="results"] .row')
    if w.locator('[data-facet="optiuni"]').get_attribute("open") is None:
        w.click('[data-facet="optiuni"] > summary')
    toggle = w.locator('[data-act="toggle"][data-key="nou"]')
    ok("the new-entries toggle says appeared recently", "Doar proiecte apărute recent" in toggle.locator("xpath=..").text_content(), toggle.locator("xpath=..").text_content().strip())
    toggle.check()
    w.wait_for_selector('[data-slot="toolbar"] .pill')
    pills = w.locator('[data-slot="toolbar"] .pill').all_inner_texts()
    ok("the toggle's pill and count match", "Apărute recent" in pills and count_text(w) == fresh_n, f"{pills}; {count_text(w)} vs {fresh_n}")
    w.goto(BASE + f"proiect/{a_item['slug']}/")
    w.wait_for_selector('[data-slot="drawer"]:not([hidden]) #d-title')
    drawer_text = w.locator('[data-slot="drawer"]').inner_text()
    badge = w.locator('[data-slot="drawer"] .d-badges .new')
    ok("detail row is \"Prima urmă observată\" and says it is not a launch date", "PRIMA URMĂ OBSERVATĂ" in drawer_text.upper() and "VECHIME" not in drawer_text.upper()
       and "nu este data lansării" in drawer_text, "")
    ok("detail badge says apărut recent with the age", badge.count() == 1 and badge.inner_text().startswith("apărut recent · acum 30 de zile"), badge.inner_text() if badge.count() else "none")
    mw = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    mw.on("pageerror", lambda e: errors.append(str(e)))
    mw.route("**/data.json", lambda route: route.fulfill(body=body, content_type="application/json"))
    mw.goto(BASE + "?v=list")
    mw.wait_for_selector('[data-slot="results"] .row')
    meta = mw.locator(f'[data-slot="results"] .row[data-open="{a_item["slug"]}"] .meta-m').inner_text().lower()
    ok("mobile list line says prima urmă, not vechime", "prima urmă acum 30 de zile" in meta and "vechime" not in meta, meta)
    mw.close()
    w.close()
    nojs.close()

    ok("no page errors", not errors, "; ".join(errors[:3]))
    browser.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
