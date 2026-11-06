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
EXPECTED_WITH_PROVIDER = sum(1 for i in ITEMS if i['slug'] in EXPECTED and i.get('dataSources'))
SHOTS = sys.argv[2] if len(sys.argv) > 2 else ''
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
    # The cards with evidence come first and 24 are shown at a time, so an uninventoried project is on a later page: open them all.
    while page.locator('[data-more]').count():
        page.locator('[data-more]').click()
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
    # The page of each entry with fields (`/date/<slug>/`): linked from its row; one block for each source and for each family that the entry's own data names.
    rows = page.locator('.ov-table tbody tr').evaluate_all('els=>els.map(e=>({slug:e.id, href:e.querySelector("th small a")?.getAttribute("href")}))')
    ok('every row of the list links to the page of its entry', len(rows) == with_fields and all(r['href'] == f'date/{r["slug"]}/' for r in rows))
    family_of = {v['id']: v.get('family') for v in INDEX['variables']}
    family_ids = {f['id'] for f in INDEX.get('families', [])}
    by_slug = {i['slug']: i for i in ITEMS}
    missing, wrong_sources, wrong_families, wrong_rows, wrong_head, sideways, anchors, wrong_facts, not_loaded = [], [], [], [], [], [], [], [], []
    page.on('response', lambda r: not_loaded.append(f'{r.status} {r.url}') if r.status >= 400 else None)
    for row in rows:
        slug = row['slug']
        try:
            # A static server answers a folder without a page with a listing, so the page is recognised by its header.
            exists = bool(row['href']) and 'class="vp-head"' in urllib.request.urlopen(BASE + row['href']).read().decode()
        except urllib.error.HTTPError:
            exists = False
        if not exists:
            missing.append(slug)
            continue
        entry = next(e for e in INDEX['entries'] if e['slug'] == slug)
        payload = json.load(urllib.request.urlopen(BASE + entry['inventory']['url']))
        for width in (1280, 375):
            page.set_viewport_size({'width': width, 'height': 900})
            page.goto(BASE + row['href'])
            page.wait_for_selector('.vp-head h1')
            if page.evaluate('document.documentElement.scrollWidth!==innerWidth'):
                sideways.append(f'{slug}@{width}')
        item = by_slug[slug]
        if page.locator('.vp-head h1').inner_text() != item['name'] or page.locator('.vp-open').get_attribute('href') != f'{item["kind"]}/{slug}/':
            wrong_head.append(slug)
        counts = [int(n) for n in re.findall(r'\d+', page.locator('.vp-meta').inner_text())]
        if counts[:2] != [len(payload['sources']), len(payload['fields'])]:
            wrong_head.append(slug + ' counts')
        if page.locator('.vp-source').evaluate_all('els=>els.map(e=>e.dataset.source)') != [s['id'] for s in payload['sources']]:
            wrong_sources.append(slug)
        shown_families = set(page.locator('.vp-family:not(.vp-other)').evaluate_all('els=>els.map(e=>e.dataset.family)'))
        if shown_families != {family_of.get(v['id']) if family_of.get(v['id']) in family_ids else '' for v in entry['variables']}:
            wrong_families.append(slug)
        if page.locator('.vp-table tbody tr').count() != len(payload['fields']):
            wrong_rows.append(slug)
        # The data set facts that a source declares (and the INS metadata) are listed under that source, each with its basis, and under no other.
        for source in payload['sources']:
            facts = source.get('facts') or {}
            block = page.locator(f'.vp-source[data-source="{source["id"]}"]')
            titles = [x['title'] for x in facts.get('sets', [])] + [x.get('name') or 'Set de date' for x in facts.get('schema', [])] + ([source['dataset']['code']] if source.get('dataset') else [])
            on_page = block.locator('.vp-set > strong').all_inner_texts()
            if on_page != titles or (titles and not all(b == (facts.get('basis') or source['dataset']['basis']) == INDEX['factBasis']['declaratie-directa']
                                                         for b in block.locator('.vp-datasets .inv-basis').all_inner_texts())):
                wrong_facts.append(f'{slug}:{source["id"]}')
        page.set_viewport_size({'width': 1280, 'height': 900})
        page.locator('.vp-nav a', has_text='Pe surse').click()
        if not page.url.endswith(f'/date/{slug}/#pe-surse'):
            anchors.append(slug)
    ok('every page of the list exists', not missing)
    ok('every page names its entry and links to it in the explorer, with the counts of its own data', not wrong_head)
    ok('every page has one block for each source of its own data, in its order', not wrong_sources)
    ok('every page has a block for each family that its own data names, and no other', not wrong_families)
    ok('every page has one row for each field of its own data', not wrong_rows)
    ok('every page lists the data set facts of each source of its own data under that source, with the basis', not wrong_facts)
    words = INDEX.get('factBasis', {})
    ok('the index carries the public words for the bases, and no basis is left without one', set(words) == {'declaratie-directa', 'observatie-esantion', 'deductie-din-dovezi', 'parafraza-editoriala'} and all(words.values()))
    ok('no page scrolls sideways at 1280 px or at 375 px', not sideways)
    ok('the links inside a page stay on the page', not anchors)
    ok('every file that a page loads (styles, fonts, images) resolves from the address of the page', not not_loaded)
    if missing + wrong_head + wrong_sources + wrong_families + wrong_rows + sideways + anchors + wrong_facts + not_loaded:
        print('  ', missing, wrong_head, wrong_sources, wrong_families, wrong_rows, sideways, anchors, wrong_facts, not_loaded[:5])
    page.set_viewport_size({'width': 1440, 'height': 1100})
    # The three pages have `<base href>`, which resolves `#id` against the base: a skip link or an anchor must name its page (`date/#data-results`), or a click leaves for the explorer.
    sample = next(r['slug'] for r in rows)
    for path in ('date/', 'date/lista/', f'date/{sample}/'):
        page.goto(BASE + path)
        page.wait_for_selector('.finder-card, .ov-table, .vp-head')
        ok(f'{path} has no link to a bare anchor', page.locator('a[href^="#"]').count() == 0)
        skips = page.locator('a.skip')
        stays = True
        for n in range(skips.count()):
            skips.nth(n).focus()
            skips.nth(n).click()
            stays = stays and urllib.parse.urlsplit(page.url).path == '/' + path and page.url.endswith('#' + skips.nth(n).get_attribute('href').split('#')[1])
            page.goto(BASE + path)
            page.wait_for_selector('.finder-card, .ov-table, .vp-head')
        ok(f'{path}: every skip link stays on the page and reaches its target ({skips.count()} found)', stays and (path != 'date/' or skips.count() == 1))
    page.goto(BASE + 'date/')
    page.wait_for_selector('.finder-card')
    page.locator('a.skip').focus()
    page.locator('a.skip').click()
    ok('the skip link of the finder moves to the results', page.evaluate("location.hash==='#data-results' && location.pathname.endsWith('/date/')") and page.locator('#data-results').count() == 1)
    # One word for one basis: the finder shows the word that the index gives to the basis of a fact of a group member.
    found = next(((e, v, f) for e in INDEX['entries'] for v in e['variables'] for ev in v['evidence'] for f in ev.get('facts', [])), None)
    ok('a fact of a group member exists to check the word of its basis', found is not None)
    if found:
        e, v, f = found
        page.goto(BASE + 'date/?q=' + urllib.parse.quote(e['name']) + '&variables=' + urllib.parse.quote(v['id']))
        page.wait_for_selector(f'.finder-card[data-project="{e["slug"]}"]')
        card = page.locator(f'.finder-card[data-project="{e["slug"]}"]')
        card.locator('.finder-evidence > summary').click()
        ok('the finder says the basis of a fact with the word of the index', f'({INDEX["factBasis"][f["basis"]]})' in card.locator('.finder-evidence').inner_text())
    page.goto(BASE + 'date/lista/')
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
    # The views by source (docs/briefs/source-views.md): the same entries as the list, grouped by a property of their sources. Each expectation is computed here from
    # the generated data (`data.json`, the payloads `inventar/<slug>.json`), not read from the page code.
    VIEWS = [('lista', 'Pe familii de variabile'), ('furnizori', 'Pe furnizori'), ('formate', 'Pe formate'), ('licente', 'Pe licențe'), ('gazde', 'Pe gazde')]
    PAYLOADS = {e['slug']: json.load(urllib.request.urlopen(BASE + e['inventory']['url'])) for e in INDEX['entries'] if e['inventory'].get('url')}
    def fetch(path):
        try:
            return urllib.request.urlopen(BASE + path).read().decode()
        except urllib.error.HTTPError:
            return ''
    texts = {name: fetch(f'date/{name}/') for name, _ in VIEWS}
    seen_pages = {}
    def cached(path):
        if path not in seen_pages:
            seen_pages[path] = fetch(path)
        return seen_pages[path]
    for name, label in VIEWS:
        page.set_viewport_size({'width': 1280, 'height': 900})
        page.goto(BASE + f'date/{name}/')
        page.wait_for_selector('.ov-views')
        links = page.locator('.ov-views a').evaluate_all('els=>els.map(e=>[e.getAttribute("href"),e.textContent,e.getAttribute("aria-current")])')
        ok(f'date/{name}/ has the switcher of the five views with this page marked',
           [(h, t) for h, t, _ in links] == [(f'date/{n}/', l) for n, l in VIEWS] and [h for h, _, c in links if c == 'page'] == [f'date/{name}/'] and page.locator('.ov-views [aria-current]').count() == 1)
        hrefs = set(page.locator('main a').evaluate_all('els=>els.map(e=>e.getAttribute("href"))'))
        entry_hrefs = {h for h in hrefs if re.match(r'^(proiect|resursa)/[\w-]+/$', h or '')}
        missing_entries = [h for h in entry_hrefs if 'class="' not in fetch(h + 'index.html')]
        ok(f'date/{name}/: every entry link resolves, and names an entry in scope', not missing_entries and {h.split('/')[1] for h in entry_hrefs} <= EXPECTED)
        broken = [h for h in hrefs if h and h.startswith('date/') and '#' in h and f'id="{h.split("#")[1]}"' not in cached(h.split('#')[0])]
        ok(f'date/{name}/: every anchor of a link to a view exists on that view', not broken)
        ok(f'date/{name}/ has no link to a bare anchor', page.locator('a[href^="#"]').count() == 0)
        ok(f'date/{name}/ ends with the entries that the inventory leaves out', page.locator('.ov-left h2').inner_text() == f'Lăsate pe dinafară ({len(OUT)})')
        sideways = []
        for width in (1280, 375):
            page.set_viewport_size({'width': width, 'height': 900})
            page.goto(BASE + f'date/{name}/')
            page.wait_for_selector('.ov-views')
            if page.evaluate('document.documentElement.scrollWidth!==innerWidth'):
                sideways.append(width)
        ok(f'date/{name}/ does not scroll sideways at 1280 px or at 375 px', not sideways)
    # Providers: every name of a relation `date_din` of an entry in scope is on the page, and the entries without one are named in their own part.
    page.set_viewport_size({'width': 1280, 'height': 900})
    page.goto(BASE + 'date/furnizori/')
    names = {d['name'] for i in ITEMS if i['slug'] in EXPECTED for d in i.get('dataSources', [])}
    body = page.locator('main').text_content()
    ok('furnizori: every provider name of an entry in scope is on the page', all(n in body for n in names) and len(names) > 0)
    without = {i['slug'] for i in ITEMS if i['slug'] in EXPECTED and not i.get('dataSources')}
    named = {h.rstrip('/').split('/')[-1] for h in page.locator('#fara-furnizor a').evaluate_all('els=>els.map(e=>e.getAttribute("href"))')}
    ok('furnizori: the entries without a provider are named, and only they', named == without)
    listed = {h.rstrip('/').split('/')[-1] for h in page.locator('.ov-providers a[href^="proiect/"], .ov-providers a[href^="resursa/"]').evaluate_all('els=>els.map(e=>e.getAttribute("href"))')}
    ok('furnizori: the providers list the entries that have one, and only them', listed == EXPECTED - without)
    # The matrix: every provider in both orientations, short names with titles, a background on the checked cells, the toggle, the sort, no sideways scroll.
    page.goto(BASE + 'date/furnizori/')
    page.wait_for_selector('[data-orient-toggle]:not([hidden])')
    provider_ids = page.locator('.ov-providers > li.ov-provider').evaluate_all('els=>els.map(e=>e.id.slice(2))')
    matrix_ids = page.locator('table[data-matrix="entries"] thead a[href*="#f-"]').evaluate_all('els=>els.map(e=>e.getAttribute("href").split("#f-")[1])')
    pivot_ids = page.locator('table[data-matrix="providers"] tbody tr').evaluate_all('els=>els.map(e=>e.id.slice(3))')
    ok('furnizori: the matrix has every provider of the list, not only twelve', len(provider_ids) > 12 and set(matrix_ids) == set(provider_ids) == set(pivot_ids) and len(matrix_ids) == len(provider_ids))
    counts = page.locator('table[data-matrix="entries"] thead th small').evaluate_all('els=>els.slice(1).map(e=>Number(e.textContent))')
    ok('furnizori: the providers are sorted by entry count, then by name', counts == sorted(counts, reverse=True) and pivot_ids == matrix_ids)
    titled = page.locator('table[data-matrix] a[title]:has(.sr)').evaluate_all('els=>els.map(e=>[e.title,e.querySelector("[aria-hidden]").textContent,e.querySelector(".sr").textContent])')
    ok('furnizori: a short name has the full name in title and in hidden text', titled and all(t == sr and 0 < len(short) < len(t) for t, short, sr in titled))
    widths = page.locator('table[data-matrix="entries"] tbody tr').evaluate_all('els=>els.map(r=>Number(r.cells[1].textContent))')
    ok('furnizori: the entries start grouped, the ones with more providers first', widths == sorted(widths, reverse=True) and widths[0] > widths[-1])
    trimmed = page.locator('table[data-matrix="entries"] tbody th a').evaluate_all('els=>els.map(a=>[a.title===a.textContent, getComputedStyle(a).whiteSpace, a.getBoundingClientRect().height])')
    ok('furnizori: an entry name stays on one line, trimmed, with the full name in title', all(t and ws == 'nowrap' and h < 30 for t, ws, h in trimmed))
    visible = lambda: page.locator('#matrice, .ov-group, #fara-furnizor').evaluate_all('els=>els.filter(e=>!e.hidden).map(e=>e.id)')
    ok('furnizori: the tabs show the matrix only at the start', visible() == ['matrice'])
    page.locator('nav.ov-toc a[href$="#tip-institutie-publica"]').click()
    page.wait_for_timeout(100)
    ok('furnizori: a tab shows its provider type only, and marks itself', visible() == ['tip-institutie-publica']
       and page.locator('nav.ov-toc a[aria-current]').get_attribute('href').endswith('#tip-institutie-publica'))
    page.goto(BASE + 'date/furnizori/#f-ins'); page.wait_for_timeout(100)
    ok('furnizori: the address of a provider opens the tab of its type', visible() == ['tip-institutie-publica'] or page.locator('#f-ins').count() == 0)
    page.goto(BASE + 'date/furnizori/'); page.wait_for_selector('[data-orient-toggle]:not([hidden])')
    ok('furnizori: the headers use the short names (no header longer than 24 characters unless it is the name itself)',
       all(len(t) <= 24 for t in page.locator('table[data-matrix="entries"] thead a[href*="#f-"] > [aria-hidden]').all_inner_texts()))
    ok('furnizori: the list below keeps the full name', any(t.startswith('Monitorul Oficial al României') for t in page.locator('.ov-provider h3').all_inner_texts()))
    mark = page.locator('table[data-matrix="entries"] td.ov-mark').first
    plain = page.locator('table[data-matrix="entries"] td:not(.ov-mark)').first
    bg = lambda loc: loc.evaluate('e=>getComputedStyle(e).backgroundColor')
    ok('furnizori: a checked cell has a background of its own, and the screen-reader text stays', bg(mark) != bg(plain) and mark.locator('.sr').inner_text() == 'da')
    ok('furnizori: the toggle shows the entries in rows first and switches to the providers in rows',
       page.locator('table[data-matrix="entries"]').is_visible() and not page.locator('table[data-matrix="providers"]').is_visible())
    page.get_by_role('button', name='Furnizori pe rânduri').click()
    ok('furnizori: after the toggle only the pivot shows, and the button is pressed',
       page.locator('table[data-matrix="providers"]').is_visible() and not page.locator('table[data-matrix="entries"]').is_visible()
       and page.get_by_role('button', name='Furnizori pe rânduri').get_attribute('aria-pressed') == 'true')
    ok('furnizori: the pivot has one row for each provider and one column for each entry with a provider',
       page.locator('table[data-matrix="providers"] tbody tr').count() == len(provider_ids)
       and page.locator('table[data-matrix="providers"] thead th.ov-vert').count() == EXPECTED_WITH_PROVIDER)
    sticky = page.locator('table[data-matrix="providers"] tbody th').first.evaluate('e=>getComputedStyle(e).position')
    ok('furnizori: the first column is sticky, and the frame is as wide as the window', sticky == 'sticky'
       and page.locator('[data-orient="providers"] .ov-scroll').evaluate('e=>e.getBoundingClientRect().width') >= page.evaluate('document.documentElement.clientWidth') - 1)
    first = page.locator('table[data-matrix="providers"] thead th.ov-vert').first
    first.locator('button.ov-sort').click()
    users_first = page.locator('table[data-matrix="providers"] tbody tr').evaluate_all('(rows)=>rows.map(r=>r.cells[2].classList.contains("ov-mark"))')
    ok('furnizori: sorting an entry column puts the providers that it uses first, and sets aria-sort',
       first.get_attribute('aria-sort') == 'descending' and users_first == sorted(users_first, reverse=True) and users_first[0])
    page.get_by_role('button', name='Intrări pe rânduri').click()
    head = page.locator('table[data-matrix="entries"] thead th').nth(2)
    head.locator('button.ov-sort').click()
    marked = page.locator('table[data-matrix="entries"] tbody tr').evaluate_all('(rows)=>rows.map(r=>r.cells[2].classList.contains("ov-mark"))')
    ok('furnizori: sorting a provider column puts the entries that use it first', head.get_attribute('aria-sort') == 'descending' and marked == sorted(marked, reverse=True) and marked[0])
    head.locator('button.ov-sort').click()
    marked = page.locator('table[data-matrix="entries"] tbody tr').evaluate_all('(rows)=>rows.map(r=>r.cells[1].classList.contains("ov-mark"))')
    ok('furnizori: a second click reverses the order', head.get_attribute('aria-sort') == 'ascending' and marked == sorted(marked) and page.locator('table[data-matrix="entries"] [aria-sort]').count() == 1)
    name_head = page.locator('table[data-matrix="entries"] thead th').first
    name_head.locator('button.ov-sort').click()
    names = page.locator('table[data-matrix="entries"] tbody th').evaluate_all('els=>els.map(e=>e.dataset.sort)')
    collator = sorted(names, key=lambda n: n.casefold().replace('ă', 'a~').replace('â', 'a~').replace('î', 'i~').replace('ș', 's~').replace('ț', 't~'))
    ok('furnizori: the name column sorts by name, ascending first', name_head.get_attribute('aria-sort') == 'ascending' and names == collator)
    page.keyboard.press('Tab')
    ok('furnizori: a sort control is a button that the keyboard reaches', page.locator('table.ov-sortable thead button.ov-sort').first.evaluate('e=>e.tagName') == 'BUTTON')
    for width in (1440, 375):
        for mode in ('Intrări pe rânduri', 'Furnizori pe rânduri'):
            page.set_viewport_size({'width': width, 'height': 900})
            page.goto(BASE + 'date/furnizori/')
            page.get_by_role('button', name=mode).click()
            if width == 375 and mode == 'Intrări pe rânduri':
                ok('furnizori: no sideways scroll of the page at 375 px, in both orientations', not page.evaluate('document.documentElement.scrollWidth!==innerWidth'))
            if width == 375 and mode == 'Furnizori pe rânduri':
                ok('furnizori: the same for the pivot at 375 px', not page.evaluate('document.documentElement.scrollWidth!==innerWidth'))
            if SHOTS:
                page.screenshot(path=f'{SHOTS}/furnizori-{"intrari" if mode.startswith("Intr") else "furnizori"}-{width}.png')
    page.set_viewport_size({'width': 1280, 'height': 900})
    noscript = browser.new_context(java_script_enabled=False, viewport={'width': 1280, 'height': 900}).new_page()
    noscript.goto(BASE + 'date/furnizori/')
    ok('furnizori: without JavaScript both orientations show and the toggle does not',
       noscript.locator('table[data-matrix]').count() == 2 and noscript.locator('table[data-matrix]:visible').count() == 2 and not noscript.locator('[data-orient-toggle]').is_visible())
    noscript.close()
    # Sortable tables of the list and the formats: a click sorts, aria-sort follows, a count sorts largest first.
    for view in ('lista', 'formate'):
        page.goto(BASE + f'date/{view}/')
        table = page.locator('table.ov-sortable')
        ok(f'{view}: the table has a sort button in every column header', table.locator('thead th').count() == table.locator('thead button.ov-sort').count() > 1)
        col = 1
        th = table.locator('thead th').nth(col)
        th.locator('button.ov-sort').click()
        sizes = table.locator('tbody tr').evaluate_all(f'(rows)=>rows.map(r=>Number(r.cells[{col}].dataset.sort))')
        ok(f'{view}: a count column sorts largest first, with aria-sort', th.get_attribute('aria-sort') == 'descending' and sizes == sorted(sizes, reverse=True))
        first_name = table.locator('tbody tr').first.locator('th').get_attribute('data-sort')
        table.locator('thead th').first.locator('button.ov-sort').click()
        names = table.locator('tbody th').evaluate_all('els=>els.map(e=>e.dataset.sort)')
        ok(f'{view}: the first column sorts by name', table.locator('thead th').first.get_attribute('aria-sort') == 'ascending' and names == sorted(names, key=lambda n: n.casefold().replace('ă', 'a~').replace('â', 'a~').replace('î', 'i~').replace('ș', 's~').replace('ț', 't~')) and th.get_attribute('aria-sort') is None)
        if view == 'formate' and SHOTS:
            table.locator('thead th').nth(1).locator('button.ov-sort').click()
            page.screenshot(path=f'{SHOTS}/formate-sorted.png')
    # Formats: one row for each entry that has a source, five columns.
    page.goto(BASE + 'date/formate/')
    ok('formate: five columns of kinds', page.locator('.ov-formats thead th').evaluate_all('els=>els.map(e=>e.firstChild.textContent)')[1:] ==
       ['API și JSON', 'Fișiere și seturi descrise', 'Tabele în pagină', 'Scriptul paginii', 'Cod sursă'])
    ok('formate: one row for each entry that has a source', set(page.locator('.ov-formats tbody tr').evaluate_all('els=>els.map(e=>e.id)')) == {s for s, p in PAYLOADS.items() if p['sources'] and s in EXPECTED})
    kinds_seen = {f for p in PAYLOADS.values() for f in (s['format'] for s in p['sources'])}
    ok('formate: every format of the sources has its anchor', all(f'id="fmt-{f}"' in texts['formate'] for f in kinds_seen))
    # Licences: the names that the sources declare, and the undeclared sources last.
    page.goto(BASE + 'date/licente/')
    declared = {x for p in PAYLOADS.values() for s in p['sources'] for x in ([s['licence']['name']] if s.get('licence') else []) + [y['licence']['name'] for y in (s.get('facts') or {}).get('schema', []) if y.get('licence')]}
    shown = page.locator('.ov-licence').evaluate_all('els=>els.map(e=>e.dataset.licence)')
    ok('licente: the licences are those that the sources declare, and the undeclared ones come last',
       set(shown[:-1] if shown and shown[-1] == 'Licență nedeclarată' else shown) == declared and (not shown or shown[-1] == 'Licență nedeclarată' or not shown))
    # Hosts: a host that two entries use is on the page; a host on the page is a host of a source.
    page.goto(BASE + 'date/gazde/')
    used = {}
    for slug, payload in PAYLOADS.items():
        for s in payload['sources']:
            used.setdefault(re.sub(r'^www\.', '', (urllib.parse.urlsplit(s['url']).hostname or '').lower()), set()).add(slug)
    on_page = set(page.locator('.ov-host code').all_inner_texts())
    domains = set(page.locator('.ov-host').evaluate_all('els=>els.map(e=>e.dataset.host)'))
    ok('gazde: every host used by two entries is on the page', {h for h, e in used.items() if len(e) >= 2 and e & EXPECTED} <= on_page | domains)
    ok('gazde: every host on the page is the host of a source', (on_page - domains) <= set(used) and domains <= set(used) | {re.sub(r'^[^.]+\.', '', h) for h in used})
    ok('gazde: the line of the entries on their own domain is there', page.locator('#domeniu-propriu strong').count() == 1)
    # Part F: the page of an entry links its providers and formats to anchors that exist.
    bad_links = []
    for row in rows:
        html_text = fetch(row['href'])
        for target, fragment in re.findall(r'href="date/(furnizori|formate)/#([^"]+)"', html_text):
            if f'id="{fragment}"' not in texts[target]:
                bad_links.append(f'{row["slug"]}->{target}#{fragment}')
    ok('every provider and format link on the page of an entry reaches an anchor that exists', not bad_links)
    ok('the pages of the entries with a provider link it', any('date/furnizori/#f-' in fetch(r['href']) for r in rows))
    page.goto(BASE + 'date/')
    page.wait_for_selector('.finder-card')
    ok('the finder header links the four views', all(page.locator(f'.finder-bar a[href="date/{n}/"]').count() == 1 for n in ('furnizori', 'formate', 'licente', 'gazde')))
    page.set_viewport_size({'width': 1440, 'height': 1100})
    failed = browser.new_page()
    failed.route('**/inventar/index.json', lambda route: route.fulfill(status=503,body='{}'))
    failed.goto(BASE + 'date/')
    failed.wait_for_selector('.finder-empty')
    ok('failed load offers retry and the explorer', failed.locator('.finder-empty a').count() == 2)
    # A malicious source description remains text.
    unsafe = json.loads(json.dumps(INDEX)); unsafe['entries'][0]['description'] = '<img src=x onerror="window.__unsafe=1">'
    safe = browser.new_page()
    safe.route('**/inventar/index.json', lambda route: route.fulfill(content_type='application/json',body=json.dumps(unsafe)))
    # The search matches the name, not the slug.
    safe.goto(BASE + 'date/?q=' + urllib.parse.quote(unsafe['entries'][0]['name']))
    safe.wait_for_selector('.finder-card')
    ok('source descriptions cannot execute HTML', safe.evaluate('window.__unsafe !== 1') and safe.locator('.finder-card img').count() == 0)
    ok('no browser errors', not errors)
    browser.close()

print(f'{sum(results)}/{len(results)} checks passed')
raise SystemExit(0 if all(results) else 1)
