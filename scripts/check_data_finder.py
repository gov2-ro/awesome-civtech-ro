# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Check cross-project inventory discovery in an isolated preview."""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8770/'
INDEX = json.load(urllib.request.urlopen(BASE + 'inventar/index.json'))
DB = json.load(urllib.request.urlopen(BASE + 'data.json'))
# The scope of the variable inventory, written here from the brief (docs/briefs/data-relation.md, sections 3 and 9) and not read from the build:
# a project or a resource, not offline or arhivat, with a relation to data of date-publice, date-proprii or calcul (the group `cu-date`).
# The two reasons to leave an entry out: inactive (counted first), and without data (the code fara-date, or an empty value).
ITEMS = [i for i in DB['items'] if i['kind'] in ('proiect', 'resursa')]
def left_out_reason(item):
    if item['status'] in ('offline', 'arhivat'):
        return 'inactiv'
    return '' if item.get('dataRelation') in ('date-publice', 'date-proprii', 'calcul') else 'fara-date'
OUT = {i['slug']: left_out_reason(i) for i in ITEMS if left_out_reason(i)}
EXPECTED = {i['slug'] for i in ITEMS} - set(OUT)
REASONS = (('fara-date', 'dat=fara-date'), ('inactiv', 'st=inactiv'))  # in the order of the note
COUNTS = {reason: {kind: sum(OUT.get(i['slug']) == reason and i['kind'] == kind for i in ITEMS) for kind in ('proiect', 'resursa')}
          for reason, _ in REASONS}
results, errors = [], []
PROJECTS = sum(e['kind'] == 'proiect' for e in INDEX['entries'])
RESOURCES = sum(e['kind'] != 'proiect' for e in INDEX['entries'])
TOTAL_LABEL = f'{PROJECTS} proiecte · {RESOURCES} resurse'
PAGE = 24


def ok(label, condition):
    results.append(bool(condition))
    print(('PASS ' if condition else 'FAIL ') + label)


def want(variables=(), providers=(), subjects=(), institutions=(), resources=True):
    """The slugs that the filter rules select, computed from the generated index and not from the page code:
    every selected variable is required; the other facets accept any selected value; the facets intersect."""
    found = []
    for e in INDEX['entries']:
        if not resources and e['kind'] != 'proiect':
            continue
        if not all(any(v['id'] == x for v in e['variables']) for x in variables):
            continue
        if providers and not any(p in e['providers'] for p in providers):
            continue
        if subjects and not any(x in e['subjects'] for x in subjects):
            continue
        if institutions and not any(x in e['institutions'] for x in institutions):
            continue
        found.append(e['slug'])
    return found


def shown(page):
    return set(page.locator('.finder-card').evaluate_all('els=>els.map(e=>e.dataset.project)'))


def agrees(page, expected):
    """The page lists the first batch of the expected entries; a small selection is listed completely."""
    got = shown(page)
    return (got == set(expected)) if len(expected) <= PAGE else (len(got) == PAGE and got <= set(expected))


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, color_scheme='dark')
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_selector('.tabs a[href="date/"]')
    page.locator('.tabs a[href="date/"]').click()
    page.wait_for_selector('.finder-card')
    ok('explorer navigation opens the dedicated inventory page', '/date/' in page.url)
    ok('dedicated page includes all projects and resources', page.locator('#data-count').inner_text() == TOTAL_LABEL and PROJECTS + RESOURCES == len(INDEX['entries']))
    ok('results load in bounded batches', page.locator('.finder-card').count() == 24)
    page.locator('[data-more]').click()
    ok('more results append and move focus to the next batch', page.locator('.finder-card').count() == 48 and page.locator('.finder-card h2 a').nth(24).evaluate('(e)=>e===document.activeElement'))
    page.goto(BASE + 'date/?variables=cui')
    page.wait_for_selector('.finder-card')
    expected = want(['cui'])
    ok('shared CUI group lists exactly the entries that the index gives it', agrees(page, expected) and len(expected) >= 4)
    ok('supported CUI members from the first pass survive', {'companii-de-stat', 'demoanaf', 'romania-transparenta', 'transparenta-eu'} <= set(expected))
    ok('entries without a CUI field are not listed', 'europescope' not in shown(page) and 'rezultate-vot' not in shown(page))
    page.locator('.finder-card').first.locator('.finder-evidence > summary').click()
    ok('group evidence exposes field names and source URLs', page.locator('.finder-evidence[open] code').count() > 0 and page.locator('.finder-evidence[open] a').first.get_attribute('href').startswith('https://'))
    ok('group evidence shows the category and what is still unclear', 'Identificator' in page.locator('.finder-evidence[open]').inner_text() and page.locator('.finder-evidence[open] .finder-ambiguity').count() > 0)
    cui = next(v for v in INDEX['variables'] if v['id'] == 'cui')
    badge = page.locator('.finder-evidence[open] .finder-proof', has_text=cui['label']).first.locator('.finder-state')
    labels = {'propus': 'Propus', 'revizuit': 'Revizuit', 'amanat': 'Amânat'}
    ok('group evidence shows the review state of the group as a badge', badge.get_attribute('data-state') == cui['state'] and badge.inner_text() == labels[cui['state']])
    ok('the index lists no rejected group', all(v['state'] != 'respins' for v in INDEX['variables']))
    page.locator('.finder-examples [data-value="cpv"]').click()
    both = want(['cui', 'cpv'])
    ok('multiple variables require a common project', agrees(page, both) and {'demoanaf', 'romania-transparenta'} <= set(both) and 'companii-de-stat' not in both)
    saved = page.url
    page.reload(); page.wait_for_selector('.finder-card')
    ok('shareable URL restores the selection', agrees(page, both) and page.url == saved)
    page.locator('#data-active [data-value="cpv"]').click()
    page.go_back(); page.wait_for_function(f"document.querySelectorAll('.finder-card').length==={len(both)}")
    ok('browser back restores filters and results', page.locator('#data-active [data-value="cpv"]').count() == 1 and agrees(page, both))
    page.goto(BASE + 'date/?variables=judet&variables=perioada-de-referinta')
    page.wait_for_selector('.finder-card')
    ok('county and period intersect on entries that expose both', agrees(page, want(['judet', 'perioada-de-referinta'])) and 'constru-pentru-cine' in shown(page))
    page.goto(BASE + 'date/?variables=voturi-pentru')
    page.wait_for_selector('.finder-card')
    ok('a vote-count group joins two projects of different institutions without claiming a join', shown(page) == {'europescope', 'monitorul-ai'} == set(want(['voturi-pentru'])))
    page.goto(BASE + 'date/?variables=judet')
    page.wait_for_selector('.finder-card')
    ok('an ambiguous name joins a group only through a constrained selector', agrees(page, want(['judet'])) and 'rezultate-vot' not in want(['judet']))
    page.goto(BASE + 'date/?providers=INS')
    page.wait_for_selector('.finder-card')
    ok('provider matches count projects once', agrees(page, want(providers=['INS'])))
    page.locator('#data-resources').uncheck()
    ok('project-only selection excludes resources', agrees(page, want(providers=['INS'], resources=False)) and 'resurse=0' in page.url)
    page.goto(BASE + 'date/?providers=MDLPA&providers=INS')
    page.wait_for_selector('.finder-card')
    ok('providers are alternatives within their filter', agrees(page, want(providers=['MDLPA', 'INS'])))
    page.goto(BASE + 'date/?providers=INS&variables=siruta')
    page.wait_for_selector('.finder-card')
    ok('provider and variable filters intersect', agrees(page, want(['siruta'], ['INS'])) and 'orasul-care-se-intinde' in shown(page))
    page.goto(BASE + 'date/?institutions=institutie%3Aparlament')
    page.wait_for_selector('.finder-card')
    expected = want(institutions=['institutie:parlament'])
    ok('institutions concerned are independent of data providers', agrees(page, expected) and len(expected) > 1)
    page.goto(BASE + 'date/?q=REF_AREA')
    page.wait_for_selector('.finder-card')
    searchable = [e['slug'] for e in INDEX['entries'] if 'ref_area' in e['keywords'].lower()]
    ok('technical field search works without opening each project', agrees(page, searchable) and 'ins-gov2' in searchable and 'constru-pentru-cine' in searchable)
    page.locator('#data-search').fill('nothing_matches_7364')
    page.wait_for_selector('.finder-empty')
    ok('empty results preserve search focus', page.locator('#data-search').evaluate('(e)=>e===document.activeElement'))
    page.locator('[data-clear="all"]').click()
    ok('reset restores all catalogue entries', page.locator('#data-count').inner_text() == TOTAL_LABEL)
    ok('uninventoried projects remain reachable', any(not e['inventory'].get('count') for e in INDEX['entries']) and 'Câmpuri încă neinventariate' in page.locator('#data-cards').inner_text())
    page.screenshot(path='/tmp/civtech-data-finder-desktop.png', full_page=False)
    for width in (390,320):
        page.set_viewport_size({'width':width,'height':900})
        page.goto(BASE + 'date/?variables=cui')
        page.wait_for_selector('.finder-card')
        ok(f'{width}px page fits the viewport', page.evaluate('document.documentElement.scrollWidth===innerWidth'))
        page.locator('.finder-card').first.locator('.finder-evidence > summary').click()
        ok(f'{width}px evidence fits the viewport', page.evaluate('document.documentElement.scrollWidth===innerWidth'))
        page.screenshot(path=f'/tmp/civtech-data-finder-{width}.png',full_page=False)
    # Variables are grouped by family; a family that holds a selected variable is open.
    page.set_viewport_size({'width':1440,'height':1100})
    page.goto(BASE + 'date/?variables=cpv')
    page.wait_for_selector('.finder-card')
    fams = [f['id'] for f in INDEX.get('families', []) if any(v.get('family') == f['id'] for v in INDEX['variables'])]
    ok('variables are grouped by family in the index order', page.locator('.finder-family').evaluate_all('els=>els.map(e=>e.dataset.family)')[:len(fams)] == fams)
    cpv_family = next(v['family'] for v in INDEX['variables'] if v['id'] == 'cpv')
    ok('the family of a selected variable is open', page.locator(f'.finder-family[data-family="{cpv_family}"]').evaluate('e=>e.open'))
    # The per-project list: one row per entry with extracted fields, the others named once.
    page.goto(BASE + 'date/lista/')
    with_fields = sum(bool(e['inventory'].get('count')) for e in INDEX['entries'])
    ok('the list has one row per entry with fields', page.locator('.ov-table tbody tr').count() == with_fields)
    ok('the list names every entry without fields', page.locator('.ov-bare a').count() == len(INDEX['entries']) - with_fields)
    columns = page.locator('.ov-table thead th').evaluate_all('els=>els.map(e=>e.firstChild.textContent)')
    ok('the list has one column per family, then Altele', columns[1:-1] == [f['label'] for f in INDEX.get('families', [])] and columns[-1] == 'Altele')
    cui = next(v for v in INDEX['variables'] if v['id'] == 'cui')
    cui_rows = {e['slug'] for e in INDEX['entries'] if any(v['id'] == 'cui' for v in e['variables'])}
    shown_cui = set(page.locator('.ov-table tbody tr').evaluate_all('(els, label)=>els.filter(e=>[...e.querySelectorAll("li")].some(li=>li.textContent===label)).map(e=>e.id)', cui['label']))
    ok('a normalised name appears in exactly the rows whose entries have the group', shown_cui == cui_rows)
    ok('the table scrolls inside its frame, not the page', page.evaluate('document.documentElement.scrollWidth===innerWidth'))
    # The scope: the entries that the inventory leaves out are absent from the index, the list and the finder, and counted by reason.
    ok('the index lists exactly the projects and resources that are in scope', {e['slug'] for e in INDEX['entries']} == EXPECTED and len(OUT) > 0)
    ok('the index counts what it leaves out, by the two reasons and kind', INDEX.get('leftOut') == COUNTS and list(COUNTS) == ['fara-date', 'inactiv'])
    # The explorer is not limited by the scope (owner, 2026-10-27): an entry out of scope keeps its documentation links.
    ok('an entry out of scope keeps its documentation links in the explorer data', any(i.get('inventory', {}).get('docs') for i in DB['items'] if i['slug'] in OUT))
    page.goto(BASE + 'date/')
    page.wait_for_selector('.finder-card')
    note = page.locator('#data-left-out')
    ok('the finder says what it leaves out, with a link for each reason', note.is_visible() and all(
        (note.locator(f'a[href*="{query}"]').count() > 0) == bool(sum(COUNTS[reason].values()))
        for reason, query in REASONS))
    ok('the finder names no third reason: an empty value is without data', 'neevaluat' not in note.inner_html().lower() and note.locator('a[href*="neevaluat"]').count() == 0)
    ok('the links of the finder carry the counts of the index', sorted(int(re.match(r'\d+', t).group()) for t in note.locator('a').all_inner_texts())
       == sorted(n for reason in COUNTS.values() for n in reason.values() if n))
    for name in [next(i['name'] for i in ITEMS if OUT.get(i['slug']) == reason) for reason in ('inactiv', 'fara-date') if reason in OUT.values()]:
        page.goto(BASE + 'date/?q=' + urllib.parse.quote(name) + '&resurse=1')
        page.wait_for_selector('#data-count')
        ok('the finder does not find an entry out of scope: ' + name, not ({i['slug'] for i in ITEMS if i['name'] == name} & shown(page)))
    # The facet `cu-date` of the explorer is the scope of the finder: the same entries on each tab (the explorer hides inactive entries by default, as the finder does).
    for kind, prefix in (('proiect', ''), ('resursa', 'k=resursa&')):
        page.goto(BASE + f'?{prefix}dat=cu-date')
        page.wait_for_selector('[data-slot="toolbar"] .count')
        listed = set(page.locator('[data-slot="results"] [data-open]').evaluate_all('els => els.map(e => e.dataset.open)'))
        ok(f'the explorer group cu-date lists the {kind} entries of the finder, no more and no fewer', listed == {e['slug'] for e in INDEX['entries'] if e['kind'] == kind} and len(listed) > 0)
    def follow(link, expected):
        """Click a link to the explorer: it opens with the selection of the link and lists as many entries as the link says."""
        text = link.inner_text()
        href = link.get_attribute('href')
        link.click()
        page.wait_for_selector('[data-slot="toolbar"] .count')
        listed = int(page.locator('[data-slot="toolbar"] .count b').inner_text())
        return listed == expected == int(re.match(r'\d+', text).group()) and urllib.parse.urlsplit(page.url).query == urllib.parse.urlsplit(href).query
    for path, label in (('date/', 'finder'), ('date/lista/', 'list')):
        for reason, query in REASONS:
            for kind, extra in (('proiect', ''), ('resursa', 'k=resursa&')):
                if not COUNTS[reason][kind]:
                    continue
                page.goto(BASE + path)
                page.wait_for_selector('#data-left-out:not([hidden]), .ov-left')
                link = page.locator(f'a[href="./?{extra}{query}"]')
                ok(f'the {label} link for {reason} ({kind}) opens the explorer with the same count', link.count() == 1 and follow(link, COUNTS[reason][kind]))
    page.goto(BASE + 'date/lista/')
    ok('the list counts the entries it leaves out', page.locator('.ov-left h2').inner_text() == f'Lăsate pe dinafară ({len(OUT)})')
    reasons = page.locator('.ov-left li[data-reason]').evaluate_all('els=>els.map(e=>e.dataset.reason)')
    ok('the list gives one line for each reason that has entries, in the order of the note', reasons == [r for r, _ in REASONS if sum(COUNTS[r].values())])
    ok('the list names no third reason: an empty value is without data', 'neevaluat' not in page.content().lower() and 'neevaluate' not in page.content().lower())
    named = set(page.locator('.ov-table tbody tr').evaluate_all('els=>els.map(e=>e.id)')) | {
        h.rstrip('/').split('/')[-1] for h in page.locator('.ov-bare a').evaluate_all('els=>els.map(e=>e.getAttribute("href"))')}
    ok('the list names no entry out of scope', named == EXPECTED)
    ok('the note about missing fields stays with the entries that are in scope', 'Lipsa câmpurilor nu înseamnă lipsa datelor' in page.locator('.ov-bare').inner_text()
       and 'Lipsa câmpurilor' not in page.locator('.ov-left').inner_text())
    failed = browser.new_page()
    failed.route('**/inventar/index.json', lambda route: route.fulfill(status=503,body='{}'))
    failed.goto(BASE + 'date/')
    failed.wait_for_selector('.finder-empty')
    ok('failed load offers retry and the explorer', failed.locator('.finder-empty a').count() == 2)
    # A malicious source description remains text.
    unsafe = json.loads(json.dumps(INDEX)); unsafe['entries'][0]['description'] = '<img src=x onerror="window.__unsafe=1">'
    safe = browser.new_page()
    safe.route('**/inventar/index.json', lambda route: route.fulfill(content_type='application/json',body=json.dumps(unsafe)))
    safe.goto(BASE + 'date/?q=' + unsafe['entries'][0]['slug'])
    safe.wait_for_selector('.finder-card')
    ok('source descriptions cannot execute HTML', safe.evaluate('window.__unsafe !== 1') and safe.locator('.finder-card img').count() == 0)
    ok('no browser errors', not errors)
    browser.close()

print(f'{sum(results)}/{len(results)} checks passed')
raise SystemExit(0 if all(results) else 1)
