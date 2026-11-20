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
import csv
import json
import re
import sys
import urllib.error
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


def entry_ready(p):
    """The entry view that app.js drew (the tabs are buttons then), not the static markup that build.py wrote."""
    p.wait_for_selector('[data-slot="tabs"] button.tab')
    p.wait_for_selector('[data-slot="entry"]:not([hidden]) #d-title')


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
        page.wait_for_selector('[data-slot="toolbar"] .count', state="attached")

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
    # The child must have a visible entry: an entry that is archived or offline is off the default view, so a child with only such entries proves nothing.
    narrower = [c for c in C.values() if c["scheme"] == "subiect" and any(C[b]["broader"] for b in c["broader"])]
    narrower = [c for c in narrower if any(c["id"] in i["topics"] and i["status"] not in INACTIVE for i in DB["items"])]
    if narrower:
        child = narrower[0]
        parent = next(b for b in child["broader"] if C[b]["broader"])
        kind = next(i["kind"] for i in DB["items"] if child["id"] in i["topics"] and i["status"] not in INACTIVE)
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
    entry_ready(page)
    ok("v1 ?p= moves to the entry address", page.url.rstrip("/").endswith("/proiect/ce-cumpara-primaria"), page.url)

    # 9. Direct links and the detail panel.
    org = next(i for i in DB["items"] if i["kind"] == "organizatie" and i["attributions"] == [] and i["primarySubject"])
    page.goto(BASE + f"organizatie/{org['slug']}/")
    entry_ready(page)
    ok("direct organisation link opens its tab and page", page.locator('.tab[aria-current="page"]').inner_text().startswith("Organizații")
       and page.locator("#d-title").inner_text() == org["name"])
    sheet = page.locator('[data-slot="page"]').inner_text()
    ok("organisation page: Clasificare, Acoperire", "CLASIFICARE" in sheet.upper() and "ACOPERIRE" in sheet.upper())
    proj = next(i for i in DB["items"] if i["kind"] == "proiect" and i["attributions"] and not any(a["accepted"] for a in i["attributions"]) and i["status"] == "activ")
    page.goto(BASE + f"proiect/{proj['slug']}/")
    entry_ready(page)
    sheet = page.locator('[data-slot="page"]').inner_text()
    heads = page.locator(".p-facts dt").all_inner_texts()
    roles = {p["label"] for p in DB["vocabulary"]["predicates"] if p["key"] != "atribuit_in_sursa"}
    ok("unconfirmed attribution is neutral", "rol neconfirmat" in sheet and "Autor" in heads and not roles & set(heads), proj["slug"])
    ok("project page groups", all(g in sheet.upper() for g in ("CLASIFICARE", "ACOPERIRE")) and "SUBIECT" in sheet.upper())
    # A parent entry (`parte_din`) has its own heading. It is never an unconfirmed attribution or an organisation card.
    parents = lambda i: [a["name"] for a in i["attributions"] if a["role"] == "parte_din"]
    child = next((i for i in DB["items"] if parents(i) and not any(a["role"] != "parte_din" and a["name"] in parents(i) for a in i["attributions"])), None)
    if child:
        page.goto(BASE + f"{child['kind']}/{child['slug']}/")
        entry_ready(page)
        sheet = page.locator('[data-slot="page"]').inner_text()
        name = parents(child)[0]
        ok("parent entry has its own heading", "Parte din" in page.locator(".p-facts dt").all_inner_texts() and name in sheet, child["slug"])
        ok("parent entry is not an attribution", not any("rol neconfirmat" in line and name in line for line in sheet.split("\n")), child["slug"])
        ok("parent entry is a link to the parent's page", page.locator('.p-facts dd a[data-open]', has_text=name).count() == 1, child["slug"])
        slug = next(a["org"] for a in child["attributions"] if a["role"] == "parte_din")
        count = sum(any(a["role"] == "parte_din" and a["org"] == slug for a in i["attributions"]) for i in DB["items"])
        parent = next(i for i in DB["items"] if i["slug"] == slug)
        page.goto(BASE + f"{parent['kind']}/{slug}/")
        entry_ready(page)
        sheet = page.locator('[data-slot="page"]').inner_text()
        ok("parent page lists every part", f"CONȚINE ({count})" in sheet.upper() and page.locator('.p-sec:has(h2:text-matches("Conține")) .p-card').count() == count, slug)
    img = next(i for i in DB["items"] if i["img"])
    page.goto(BASE + f"{img['kind']}/{img['slug']}/")
    entry_ready(page)
    every_image = "[...document.querySelectorAll('[data-slot=page] img')].every(i => i.complete && i.naturalWidth > 0)"
    try:  # over a real network the images arrive after the panel opens
        page.wait_for_function(every_image, timeout=10000)
    except PlaywrightTimeout:
        pass
    loaded = page.evaluate(every_image)
    ok("images resolve from an entry page", loaded, img["slug"])
    blank = next((i for i in DB["items"] if not i["primarySubject"]), None)  # an abstention; none once every entry has a subject
    if blank:
        page.goto(BASE + f"{blank['kind']}/{blank['slug']}/")
        entry_ready(page)
        ok("abstention shows an incomplete classification", "nu stabilesc încă subiectul" in page.locator('[data-slot="page"]').inner_text(), blank["slug"])

    # 10. Archives.
    for kind in ("proiect", "organizatie", "resursa", "publicatie"):
        r = page.goto(BASE + f"{kind}/")
        n = page.locator(".arch-item").count()
        ok(f"archive /{kind}/", r.status == 200 and n == sum(i["kind"] == kind for i in DB["items"]), f"{n} items")
    heads = page.goto(BASE + "proiect/") and page.locator(".arch-group h2").all_inner_texts()
    ok("project archive grouped by primary subject", len(heads) > 5 and any("Fără subiect" in h for h in heads) == any(not i["primarySubject"] and i["kind"] == "proiect" for i in DB["items"]), f"{len(heads)} groups")

    # 10b. The section "Analize & investigații": its tab, an entry page under /publicatie/, and the stub at the old /resursa/ address.
    pubs = [i for i in DB["items"] if i["kind"] == "publicatie"]
    if pubs:
        label = next(k["label"] for k in DB["vocabulary"]["kinds"] if k["key"] == "publicatie")
        go("?k=publicatie")
        tab = page.locator('.tab[aria-current="page"]')
        ok("publication tab shows its label and count", tab.inner_text().startswith(label) and count_text(page) == len([i for i in pubs if i["status"] not in ("offline", "arhivat")]),
           f"{tab.inner_text()!r}; {count_text(page)} of {len(pubs)}")
        pub = pubs[0]
        page.goto(BASE + f"publicatie/{pub['slug']}/")
        entry_ready(page)
        ok("publication page opens its tab and page", page.locator('.tab[aria-current="page"]').inner_text().startswith(label)
           and page.locator("#d-title").inner_text() == pub["name"], pub["slug"])
        def has_stub(i):  # a moved entry has a stub at its old address; a new one has none (a 404 raises)
            try:
                return b'http-equiv="refresh"' in urllib.request.urlopen(urllib.request.Request(BASE + f"resursa/{i['slug']}/", headers={"User-Agent": "Mozilla/5.0 (check_preview.py)"})).read()
            except urllib.error.HTTPError:
                return False
        moved = next((i for i in pubs if has_stub(i)), None)
        ok("a moved publication keeps a stub at its old address", moved is not None)
        if moved:
            page.goto(BASE + f"resursa/{moved['slug']}/")
            page.wait_for_url(f"**/publicatie/{moved['slug']}/")
            entry_ready(page)
            ok("old /resursa/ address reaches the new page", page.locator("#d-title").inner_text() == moved["name"], moved["slug"])

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
    # The box suggests filters only; entries of the other tabs list below the active tab, one heading per tab.
    go("?k=organizatie")
    page.fill('[data-slot="q"]', "ce face statul")
    page.wait_for_timeout(400)
    heads = page.locator('[data-slot="results"] .group-head').all_inner_texts()
    ok("no entry suggestions in the box", page.locator('[data-slot="ac"]').is_hidden(), page.locator('[data-slot="ac"]').inner_text()[:80])
    ok("other tabs listed below the active tab", any("Analize & investigații" in h for h in heads), str(heads))
    ok("no count line while other tabs are listed", page.locator('[data-slot="toolbar"] .elsewhere').count() == 0)
    page.locator('[data-slot="tabs"] .tab', has_text="Analize").click()
    page.wait_for_timeout(300)
    ok("a tab keeps the query", "k=publicatie" in page.url and "q=ce+face+statul" in page.url and count_text(page) > 0, page.url)
    # The author view: the same list across tabs, reached from the author's name on an entry page.
    go("?autor=Gabriel+Popa")
    heads = page.locator('[data-slot="results"] .group-head').all_inner_texts()
    ok("author view lists more than one tab", any("din celelalte secțiuni" in h for h in heads) and count_text(page) > 1, str(heads))
    ok("author view has its pill", page.locator('[data-slot="toolbar"] .pill', has_text="Autor: Gabriel Popa").count() == 1)

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
    ok("the page links the source's filtered list and its evidence", page.locator('.p-facts .p-src a[data-nav]', has_text=re.compile('^' + re.escape(source) + '$')).count() == 1
       and page.locator(f'.p-facts .p-src a.ev[href="{evidence}"]').count() >= 1)
    parliament = next(i for i in DB['items'] if any(d['name'] in ('Camera Deputaților', 'Senatul României') for d in i.get('dataSources', [])))
    want = [i for i in visible(parliament['kind']) if any(d['name'] in ('Camera Deputaților', 'Senatul României') for d in i.get('dataSources', []))]
    go('?k=' + parliament['kind'] + '&source=Parlament')
    ok('Parlament combines chambers and counts each entry once', count_text(page) == len(want))
    go('?k=' + parliament['kind'] + '&source=' + urllib.parse.quote('Senatul României'))
    ok('old chamber filter maps to Parlament', count_text(page) == len(want) and 'Parlament' in page.locator('[data-slot="toolbar"] .pill').inner_text())
    go(parliament['kind'] + '/' + parliament['slug'] + '/')
    ok('the page lists the chambers it names', page.locator('.p-facts .p-src a[data-nav]', has_text=re.compile('^(Camera Deputaților|Senatul României|Parlament)$')).count() >= 1)
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
    # The facets `dat` (the relation to data, in two groups) and `st` (the status group), under "Mai multe filtre".
    # The expected sets come from data.json and the rules below, not from the page code. `st=inactiv` shows inactive entries without `ina=1`.
    # The groups (docs/briefs/data-relation.md, section 9): `cu-date` takes date-publice, date-proprii and calcul; `fara-date` takes `fara-date` and an empty value.
    DATA_CODES = {"date-publice", "date-proprii", "calcul", "fara-date"}
    WITH_DATA = {"date-publice", "date-proprii", "calcul"}
    GROUPS = {"cu-date": "Lucrează cu date", "fara-date": "Fără date"}
    relation = lambda i: "cu-date" if i.get("dataRelation") in WITH_DATA else "fara-date"
    everyone = [i for i in DB["items"] if i["kind"] == "proiect"]
    gone = [i for i in everyone if i["status"] in INACTIVE]
    slugs_shown = lambda: set(page.locator('[data-slot="results"] [data-open]').evaluate_all("els => els.map(e => e.dataset.open)"))
    pill_texts = lambda: page.locator('[data-slot="toolbar"] .pill').all_inner_texts()
    ok("the data carries the relation to data, its code list and the two groups", all(i.get("dataRelation", "") in DATA_CODES | {""} for i in DB["items"])
       and {c["key"] for c in DB["vocabulary"]["dataRelations"]} == DATA_CODES
       and {g["key"]: (g["label"], set(g["codes"])) for g in DB["vocabulary"].get("dataGroups", [])}
       == {"cu-date": (GROUPS["cu-date"], WITH_DATA), "fara-date": (GROUPS["fara-date"], {"fara-date", ""})})
    for group in GROUPS:
        want = [i for i in projects if relation(i) == group]
        go("?dat=" + group)
        ok(f"dat={group} shows the visible projects of that group", len(want) > 0 and count_text(page) == len(want) and slugs_shown() == {i["slug"] for i in want}, f"{count_text(page)} vs {len(want)}")
    go("?dat=cu-date")
    ok("a project with the code calcul is in the group cu-date, with date-publice and date-proprii",
       any(i.get("dataRelation") == "calcul" for i in projects)
       and {i["slug"] for i in projects if i.get("dataRelation") in WITH_DATA} == slugs_shown())
    go("?dat=fara-date")
    # The owner may give every visible project a code, so the data need not hold an empty value; the vocabulary check above proves that the group takes it.
    ok("the group fara-date holds the code and the empty value", "fara-date" in {i.get("dataRelation", "") for i in projects}
       and slugs_shown() == {i["slug"] for i in projects if i.get("dataRelation", "") in ("fara-date", "")})
    ok("dat pill names the facet and the value", pill_texts() == ["Date: Fără date"], " | ".join(pill_texts()))
    go("?dat=date-publice")
    ok("the codes are not facet values: a bookmark with one finds nothing", count_text(page) == 0 and slugs_shown() == set())
    go("?dat=neevaluat")
    ok("the old value neevaluat finds nothing either", count_text(page) == 0)
    go("?dat=fara-date")
    ok("dat sits under Mai multe filtre, which is open while a value is selected",
       page.locator('[data-facet="more"][open] .subfacet .kicker', has_text="Date").count() == 1)
    ok("dat keeps inactive entries hidden", not ({i["slug"] for i in gone} & slugs_shown()))
    go("?dat=cu-date,fara-date")
    ok("the two dat values are alternatives, and together they show every visible project", count_text(page) == len(projects))
    go("")
    more = page.locator('[data-facet="more"]')
    if not more.evaluate("e => e.open"):
        more.locator("summary").click()
    dat_counts = {o.get_attribute("data-val"): int(o.locator(".n").text_content()) for o in page.locator('.tag[data-key="dat"]').all()}
    expected_dat = {c: sum(relation(i) == c for i in projects) for c in {relation(i) for i in projects}}
    ok("dat offers the two groups only, with the count of visible projects; an option with three entries or fewer sits behind Mai multe",
       set(dat_counts) <= set(GROUPS) == set(expected_dat) and all(expected_dat[v] == n for v, n in dat_counts.items())
       and all(expected_dat[c] <= 3 for c in expected_dat if c not in dat_counts), f"{dat_counts} vs {expected_dat}")
    ok("the options of dat read Lucrează cu date and Fără date",
       {o.get_attribute("data-val"): o.text_content().rstrip("0123456789") for o in page.locator('.tag[data-key="dat"]').all()}
       == {v: GROUPS.get(v) for v in dat_counts})
    go("?dat=fara-date&q=zzzqx")
    ok("a selected option stays visible although its count is small (here 0)", page.locator('.tag[data-key="dat"][data-val="fara-date"][aria-pressed="true"]').count() == 1
       and page.locator('.tag[data-key="dat"][data-val="cu-date"]').count() == 0)
    go("?dat=fara-date")
    page.locator('[data-slot="toolbar"] .pill', has_text="Date: ").click()
    ok("removing the dat pill clears the filter and the URL", "dat=" not in page.url and count_text(page) == len(projects))
    go("?k=organizatie")
    ok("organisations have no dat facet", page.locator('[data-facet="more"] .subfacet .kicker', has_text="Date").count() == 0)

    for name, query, want in [("st=inactiv", "?st=inactiv", gone),
                              ("st=activ", "?st=activ", [i for i in projects if i["status"] == "activ"]),
                              ("st=neconfirmat", "?st=neconfirmat", [i for i in projects if i["status"] in ("necunoscut", "neverificat")]),
                              ("st=activ,inactiv", "?st=activ,inactiv", [i for i in everyone if i["status"] in ("activ", *INACTIVE)])]:
        go(query)
        ok(f"{name} shows exactly that status group", count_text(page) == len(want) and slugs_shown() == {i["slug"] for i in want}, f"{count_text(page)} vs {len(want)}")
    go("?st=inactiv")
    ok("st=inactiv shows inactive entries without ina=1", "ina=" not in page.url and count_text(page) == len(gone) > 0 and "Stare: Inactiv" in pill_texts())
    toggle = page.locator('[data-act="toggle"][data-key="ina"]')
    ok("with st=inactiv the toggle that hides inactive entries is off and disabled", toggle.count() == 1 and not toggle.is_checked() and toggle.is_disabled())
    for group in GROUPS:
        go(f"?st=inactiv&dat={group}")
        ok(f"st and dat intersect (inactiv, {group})", count_text(page) == sum(i["status"] in INACTIVE and relation(i) == group for i in everyone))
    go("?ina=1")
    ok("old ?ina=1 still shows inactive and active projects", count_text(page) == len(everyone))
    go("?ina=1&s=inactiv")
    ok("old ?s= keeps its meaning next to ina=1", count_text(page) == len(gone))
    go("")
    ok("inactive entries stay hidden by default", count_text(page) == len(projects) and not ({i["slug"] for i in gone} & slugs_shown()))
    if not page.locator('[data-facet="more"]').evaluate("e => e.open"):
        page.locator('[data-facet="more"] summary').click()
    st_counts = {o.get_attribute("data-val"): int(o.locator(".n").text_content()) for o in page.locator('.tag[data-key="st"]').all()}
    ok("st counts the inactive entries although they are hidden", st_counts.get("inactiv") == len(gone) and st_counts.get("activ") == sum(i["status"] == "activ" for i in projects), str(st_counts))
    page.locator('.tag[data-key="st"][data-val="inactiv"]').click()
    ok("choosing Inactiv in the facet lists them and writes st to the URL", "st=inactiv" in page.url and "ina=" not in page.url and count_text(page) == len(gone))
    page.locator('.tag[data-key="st"][data-val="inactiv"]').click()
    ok("choosing it again returns to the default view", "st=" not in page.url and count_text(page) == len(projects))

    # Every provider relation that is not accepted stays out of the public field, unless an accepted row names the same provider.
    with open(Path(__file__).resolve().parent.parent / 'data' / 'taxonomy-v2' / 'integrare' / 'relatii.csv', encoding='utf-8', newline='') as f:
        relations = [r for r in csv.DictReader(f) if r['predicat'] == 'date_din']
    accepted = {(r['subiect'], r['obiect_literal'] or r['obiect']) for r in relations if r['stare'] == 'acceptat'}
    shown = {(i['slug'], d['name']) for i in DB['items'] for d in i.get('dataSources', [])}
    unreviewed = {(r['subiect'], r['obiect_literal'] or r['obiect']) for r in relations if r['stare'] != 'acceptat'} - accepted
    ok('unreviewed sources stay out of the public field', not unreviewed & shown, f'{len(unreviewed)} not accepted')
    go("?v=list")
    hidden = page.locator('[data-slot="results"] .row-kw .vh').first.inner_text()
    ok("result badges name their facet", hidden.rstrip(": ") in ("Subiect", "Format", "Ce poți face"), hidden)
    page.locator('[data-slot="results"] [data-open]').first.click()
    entry_ready(page)
    page.keyboard.press("Control+k")
    ok("search shortcut focuses the search in the entry view", page.evaluate("document.activeElement === document.querySelector('[data-slot=\"q\"]')"))
    page.keyboard.press("Escape")

    # 13. What the v1 site shows must stay: report options, site link, related entries, card types, v1 search words.
    it = next(i for i in DB["items"] if i["kind"] == "organizatie" and i["sheet"])
    go(f"organizatie/{it['slug']}/")
    entry_ready(page)
    flag = page.locator('.p-facts .flag a', has_text="Corectează în tabel")
    ok("report panel opens the entry's Sheet row", flag.count() == 1 and f"gid={DB['site']['tabs'][it['sheet']['tab']]}&range=A{it['sheet']['row']}" in flag.get_attribute("href"),
       str(it["sheet"]))
    link = page.locator('.p-url')
    ok("site link is the plain address", link.count() == 1 and it["domain"] in link.inner_text() and "Deschide" not in link.inner_text(), link.inner_text() if link.count() else "none")
    alone = [i for i in DB["items"] if i["kind"] == "organizatie" and i["primarySubject"] and i["status"] not in INACTIVE
             and not any(j["primarySubject"] == i["primarySubject"] and j["slug"] != i["slug"] for j in DB["items"] if j["kind"] == "organizatie")
             and any(i["primarySubject"] in subj_set(j) and j["slug"] != i["slug"] and j["status"] not in INACTIVE for j in DB["items"] if j["kind"] == "organizatie")]
    if alone:
        go(f"organizatie/{alone[0]['slug']}/")
        entry_ready(page)
        ok("related entries include secondary-subject matches", page.locator('.p-sec:has(h2:text-matches("Tot din")) [data-open]').count() > 0, alone[0]["slug"])
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

    archive_hrefs = [BASE + f"{k}/" for k in ("proiect", "organizatie", "resursa", "publicatie")]
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
    ok("failed data load links the static lists", hrefs_in(f, '[data-slot="results"] [role="alert"] a') == archive_hrefs)
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
    f.wait_for_selector('[data-slot="results"] [data-act="retry"]', state="attached")
    f.wait_for_timeout(300)
    ok("a failed load on an entry page leaves the static entry, with its tabs and left list as plain links",
       f.locator("#d-title").inner_text() == proj["name"] and f.locator("#d-title").is_visible() and f.locator(".p-toc a.toc-it").count() > 0
       and hrefs_in(f, ".tabs a") == archive_hrefs)
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
    ok("without JavaScript an entry page shows the entry and links the archives", n.locator("h1").inner_text() == proj["name"]
       and hrefs_in(n, ".tabs a") == archive_hrefs and not n.locator('[data-slot="list"]').is_visible())
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
    entry_ready(h)
    ok("an entry opened directly keeps its own head", not differs(head(h), x_head), str(differs(head(h), x_head)))
    h.click('.toc-top a[data-nav]')
    h.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    ok("closing a directly opened entry restores the home canonical and share tags", not differs(head(h), home_head), str(differs(head(h), home_head)))
    ok("closing an entry restores the page title", plain["name"] not in h.title())
    h.goto(BASE + f"?k={cover['kind']}&ina=1&o=az")
    h.wait_for_selector('[data-slot="toolbar"] .count')
    ok("the home page keeps its own head", not differs(head(h), home_head), str(differs(head(h), home_head)))
    h.locator(f'[data-slot="results"] [data-open="{cover["slug"]}"] a.stretch').first.click()
    entry_ready(h)
    got = head(h)
    ok("opening an entry in the page sets its canonical and share tags", not differs(got, y_head, TEXTS) and all(got[k].startswith(y_head[k][:30]) for k in TEXTS),
       str(differs(got, y_head, TEXTS)))
    h.go_back()
    h.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    ok("Back restores the home canonical and share tags", not differs(head(h), home_head), str(differs(head(h), home_head)))
    h.locator(f'[data-slot="results"] [data-open="{cover["slug"]}"] a.stretch').first.click()
    entry_ready(h)
    h.keyboard.press("Escape")
    h.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    ok("Escape restores the home canonical and share tags", not differs(head(h), home_head), str(differs(head(h), home_head)))
    h.goto(BASE + f"?p={plain['slug']}")
    entry_ready(h)
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
    entry_ready(w)
    sheet_text = w.locator('[data-slot="page"]').inner_text()
    badge = w.locator('[data-slot="page"] .d-badges .new')
    ok("the page row is \"Prima urmă\", gives the age, and says it is not a launch date", "PRIMA URMĂ" in sheet_text.upper() and "VECHIME" not in sheet_text.upper()
       and "nu este data lansării" in sheet_text and "acum 30 de zile" in sheet_text, "")
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

    # 19. The entry as a full page: no drawer, the left list of the section, keys, Esc and Back, the filters that ride along, a phone.
    fin = "subiect:finante-publice"
    e = browser.new_page(viewport={"width": 1440, "height": 900})
    e.on("pageerror", lambda x: errors.append(str(x)))
    e.on("console", lambda m: m.type == "error" and errors.append(m.text))
    e.goto(BASE + f"?k=proiect&subj={urllib.parse.quote(fin)}&o=az")
    e.wait_for_selector('[data-slot="results"] .row')
    want_rows = [i for i in projects if fin in subj_set(i)]
    e.evaluate("window.scrollTo(0, 700)")
    list_order = e.locator('[data-slot="results"] .row').evaluate_all("els => els.map(x => x.dataset.open)")
    row = e.locator('[data-slot="results"] .row').nth(min(8, len(want_rows) - 1))
    slug = row.get_attribute("data-open")
    row.scroll_into_view_if_needed()
    before = e.evaluate("scrollY")
    row.locator("a.stretch").click()
    entry_ready(e)
    ok("a click on a row opens the full page at the entry's address", e.url.split("?")[0].endswith(f"/proiect/{slug}/") and "subj=" in e.url and "k=" not in e.url, e.url)
    ok("no drawer is left in the page", e.locator('[data-slot="drawer"], .drawer').count() == 0 and e.locator('[data-slot="list"]').is_hidden())
    ok("the focus is on the title, at the top of the page", e.evaluate("document.activeElement?.id") == "d-title" and e.evaluate("scrollY") == 0)
    toc = e.locator(".p-toc .toc-it")
    ok("the left list marks the entry", e.locator('.p-toc .toc-it[aria-current="page"]').get_attribute("data-open") == slug and e.locator('.p-toc [aria-current]').count() == 1)
    ok("a filter in the query narrows the left list", toc.count() == len(want_rows), f"{toc.count()} vs {len(want_rows)}")
    ok("the left list shows the same entries as the list, in the same order", toc.evaluate_all("els => els.map(x => x.dataset.open)") == list_order)
    ok("the tab of the entry is current", e.locator('.tab[aria-current="page"]').inner_text().startswith("Proiecte"))
    ok("the left list has only the link back, no section name", e.locator(".toc-top").inner_text().replace("\n", " ").strip().startswith("← filtre"))
    order = toc.evaluate_all("els => els.map(x => x.dataset.open)")
    at = order.index(slug)
    e.keyboard.press("j")
    e.wait_for_function("s => location.pathname.includes(s)", arg=order[at + 1])
    ok("j opens the next entry of the left list", e.locator('.p-toc [aria-current]').get_attribute("data-open") == order[at + 1] and "subj=" in e.url, e.url)
    e.keyboard.press("ArrowRight")
    e.wait_for_function("s => location.pathname.includes(s)", arg=order[at + 2])
    e.keyboard.press("k")
    e.wait_for_function("s => location.pathname.includes(s)", arg=order[at + 1])
    e.keyboard.press("ArrowLeft")
    e.wait_for_function("s => location.pathname.includes(s)", arg=order[at])
    ok("k and the arrow keys step back through the left list", e.locator("#d-title").inner_text() == next(i["name"] for i in DB["items"] if i["slug"] == slug))
    nxt = e.locator(".p-nav .p-next")
    ok("the link to the next entry follows the left list", nxt.get_attribute("data-open") == order[at + 1])
    e.keyboard.press("Escape")
    e.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    e.wait_for_timeout(100)
    ok("Esc returns to the list with its filters", "subj=" in e.url and "/proiect/" not in e.url.split("?")[0] and count_text(e) == len(want_rows), e.url)
    ok("Esc puts the scroll back", abs(e.evaluate("scrollY") - before) <= 2, f"{e.evaluate('scrollY')} vs {before}")
    ok("Esc puts the focus on the row of the entry", e.evaluate(f"document.activeElement?.closest('[data-open]')?.dataset.open") == slug)
    e.go_back()
    entry_ready(e)
    ok("Back returns from the list to the entry", e.url.split("?")[0].endswith(f"/proiect/{slug}/"))
    e.go_back()
    e.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    e.wait_for_timeout(100)
    ok("Back leaves the entry for the list, with the scroll and the focus", abs(e.evaluate("scrollY") - before) <= 2
       and e.evaluate(f"document.activeElement?.closest('[data-open]')?.dataset.open") == slug)
    e.go_forward()
    entry_ready(e)
    e.locator(".toc-top a[data-nav]").click()
    e.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    ok("the link \"← filtre\" returns to the list, with the filters", "subj=" in e.url and count_text(e) == len(want_rows))
    row = e.locator(f'[data-slot="results"] [data-open="{slug}"] a.stretch')
    row.click()
    entry_ready(e)
    e.fill('[data-slot="q"]', "licitatii")
    e.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    ok("a query typed in the entry view returns to the list with the query", "q=licitatii" in e.url and e.locator('[data-slot="list"]').is_visible())
    e.goto(BASE + f"proiect/{slug}/?subj={urllib.parse.quote(fin)}")
    entry_ready(e)
    sheet_box, main_box, facts_box = (e.locator(s).bounding_box() for s in (".p-sheet", ".p-main", ".p-facts"))
    toc_box = e.locator(".p-toc").bounding_box()
    ok("at 1440 px: the left list, the sheet and the facts box stand side by side", abs(toc_box["x"]) < 2 and sheet_box["x"] >= 255 and facts_box["x"] > main_box["x"] + main_box["width"] - 2
       and abs(e.evaluate("document.documentElement.scrollWidth") - 1440) <= 1, f"{toc_box['x']:.0f} {sheet_box['x']:.0f} {facts_box['x']:.0f}")
    e.set_viewport_size({"width": 1024, "height": 800})
    e.wait_for_timeout(200)
    main_box, facts_box = e.locator(".p-main").bounding_box(), e.locator(".p-facts").bounding_box()
    ok("at 1024 px the facts box goes above the main column and the list stays", facts_box["y"] < main_box["y"] and e.locator(".p-toc").is_visible())
    e.set_viewport_size({"width": 1440, "height": 900})
    first, last = order[0], order[-1]
    ok("the page is the whole section when the filters are removed", e.locator(".toc-filter a").count() == 1)
    e.locator(".toc-filter a").click()
    e.wait_for_function("() => document.querySelectorAll('.p-toc .toc-it').length > 0 && !location.search.includes('subj')")
    ok("\"toată secțiunea\" lists the whole section", e.locator(".p-toc .toc-it").count() >= len(projects), f"{e.locator('.p-toc .toc-it').count()} vs {len(projects)}")
    # The old ?p= link opens the entry, and an entry opened by its address alone opens on its own tab.
    e.goto(BASE + f"?p={slug}")
    entry_ready(e)
    ok("?p=<slug> opens the entry page", e.url.split("?")[0].endswith(f"/proiect/{slug}/") and e.locator('.p-toc [aria-current]').count() == 1)
    # Every label of the classification opens the list filtered by it.
    chip = e.locator(".p-class a.p-chip").first
    label_ = chip.inner_text()
    chip.click()
    e.wait_for_selector('[data-slot="entry"][hidden]', state="attached")
    ok("a label of the classification opens the list filtered by it", "subj=" in e.url and any(label_ in t for t in e.locator('[data-slot="toolbar"] .pill').all_inner_texts()), e.url)
    e.close()
    for scheme in ("light", "dark"):
        t = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme=scheme)
        t.on("pageerror", lambda x: errors.append(str(x)))
        t.on("console", lambda m: m.type == "error" and errors.append(m.text))
        t.goto(BASE + f"proiect/{slug}/")
        entry_ready(t)
        bg = t.evaluate("getComputedStyle(document.querySelector('.p-sheet')).backgroundColor")
        back = t.evaluate("getComputedStyle(document.querySelector('.p-layout')).backgroundColor")
        ok(f"the sheet stands out from the page behind it ({scheme})", bg != back, f"{bg} vs {back}")
        t.close()
    ph = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ph.on("pageerror", lambda x: errors.append(str(x)))
    ph.on("console", lambda m: m.type == "error" and errors.append(m.text))
    ph.goto(BASE + f"proiect/{slug}/")
    entry_ready(ph)
    ok("at 390 px the left list is hidden and there is no horizontal scroll", ph.locator(".p-toc").is_hidden() and ph.evaluate("document.documentElement.scrollWidth") <= 391,
       str(ph.evaluate("document.documentElement.scrollWidth")))
    ph.click(".toc-btn")
    ok("the button opens the left list, full screen", ph.locator(".p-toc.open").is_visible() and ph.locator(".p-toc .toc-it").count() > 10)
    ph.keyboard.press("Escape")
    ok("Esc closes the left list", ph.locator(".p-toc.open").count() == 0)
    ph.click(".toc-btn")
    ph.click(".toc-close")
    ok("the button \"Închide\" closes the left list", ph.locator(".p-toc.open").count() == 0)
    here = ph.locator("#d-title").inner_text()
    ph.evaluate("""() => { const el = document.querySelector('.p-sheet'); const mk = (x) => new Touch({ identifier: 1, target: el, clientX: x, clientY: 400 });
      el.dispatchEvent(new TouchEvent('touchstart', { touches: [mk(300)], changedTouches: [mk(300)], bubbles: true }));
      el.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [mk(120)], bubbles: true })); }""")
    ph.wait_for_function("t => document.querySelector('#d-title').innerText !== t", arg=here)
    ok("a swipe on the sheet steps to the next entry", ph.locator("#d-title").inner_text() != here)
    ph.click(".toc-btn")
    ph.locator(".p-toc .toc-it").nth(3).click()
    ph.wait_for_selector('.p-toc:not(.open)', state="attached")
    ok("a row of the opened left list opens that entry and closes the list", ph.locator(".p-toc.open").count() == 0 and ph.evaluate("document.documentElement.scrollWidth") <= 391)
    ph.close()
    e2 = browser.new_page(viewport={"width": 1440, "height": 900})
    e2.on("pageerror", lambda x: errors.append(str(x)))
    org = next(i for i in DB["items"] if i["kind"] == "organizatie" and any(j["kind"] != "organizatie" and any(a["org"] == i["slug"] and a["role"] != "parte_din" for a in j["attributions"]) for j in DB["items"]))
    e2.goto(BASE + f"organizatie/{org['slug']}/")
    entry_ready(e2)
    ok("an organisation's page lists its projects and resources, with no cap", e2.locator('.p-sec:has(h2:text-matches("Proiecte și resurse")) .p-card').count()
       == len([j for j in DB["items"] if j["kind"] != "organizatie" and any(a["org"] == org["slug"] and a["role"] != "parte_din" for a in j["attributions"]) and not any(a2["org"] == org["slug"] and a2["role"] == "parte_din" for a2 in j["attributions"])]))
    e2.locator(".p-card").first.click()
    e2.wait_for_function("s => !location.pathname.includes(s)", arg=org["slug"])
    ok("a card opens the other entry, and its tab becomes current", e2.locator('.tab[aria-current="page"]').count() == 1 and "k=" not in e2.url)
    e2.close()

    ok("no page errors", not errors, "; ".join(errors[:3]))
    browser.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
