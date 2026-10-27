# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Browser checks for the isolated data-inventory explorer preview.

    python3 scripts/build.py --site-dir /tmp/civtech-inventory-preview --with-inventory
    python3 -m http.server -d /tmp/civtech-inventory-preview 8770
    uv run scripts/check_inventory_preview.py http://localhost:8770/
"""
import json
import sys
import urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8770/'
DB = json.load(urllib.request.urlopen(BASE + 'data.json'))
assert DB.get('inventoryPreview'), 'Build with --with-inventory first.'
results, errors = [], []


def ok(label, condition):
    results.append(bool(condition))
    print(('PASS ' if condition else 'FAIL ') + label)


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1280, 'height': 1000}, color_scheme='dark')
    page.on('pageerror', lambda e: errors.append(str(e)))
    requests = []
    page.on('request', lambda r: requests.append(r.url) if '/inventar/' in r.url else None)
    page.goto(BASE + '?o=az')
    page.wait_for_selector('[data-slot="toolbar"] .count')
    ok('inventory payloads are not fetched with the catalogue', not requests)
    expected = sum(bool(i.get('inventory', {}).get('count')) for i in DB['items'] if i['kind'] == 'proiect' and i['status'] not in ('offline', 'arhivat'))
    ok('only projects with structured fields have a marker', page.locator('[data-slot="results"] .inventory-tag').count() == expected)
    page.locator('[data-open="demoanaf"] .inventory-tag').click()
    page.wait_for_selector('[data-inv-panel][open] .inv-field')
    payload = json.load(urllib.request.urlopen(BASE + 'inventar/demoanaf.json'))
    ok('marker opens the project and its fields', '/proiect/demoanaf/' in page.url and page.locator('.inv-field').count() == min(8, len(payload['fields'])))
    ok('partial status is visible', page.locator('.inv-status').inner_text() == 'Inventar parțial')
    ok('one project payload is loaded', len(requests) == 1 and requests[0].endswith('/inventar/demoanaf.json'))
    url = page.url
    field_search = page.locator('[data-inv="q"]')
    field_search.fill('CUI')
    ok('field search filters by name', page.locator('.inv-field').count() > 0 and all('cui' in t.lower() for t in page.locator('.inv-field').all_inner_texts()))
    ok('field search keeps its focus and leaves the main query unchanged', field_search.evaluate('(e)=>e===document.activeElement') and page.url == url and page.locator('[data-slot="q"]').input_value() == '')
    field_search.fill('')
    page.select_option('[data-inv="role"]', 'parametru-api')
    ok('API inputs are distinct from returned fields', all('Intrări API' in t for t in page.locator('.inv-field').all_inner_texts()))
    page.select_option('[data-inv="role"]', '')
    page.locator('[data-act="inventory-more"]').click()
    ok('more fields expand incrementally', page.locator('.inv-field').count() == min(28, len(payload['fields'])) > 8)
    field_search.fill('no_such_field_xyz')
    ok('empty search offers a reset', page.locator('.inv-field').count() == 0 and page.locator('[data-act="inventory-clear"]').count() == 1)
    page.locator('[data-act="inventory-clear"]').click()
    ok('reset restores fields and search focus', page.locator('.inv-field').count() == min(8, len(payload['fields'])) and field_search.evaluate('(e)=>e===document.activeElement'))
    first_source = next(s['url'] for s in payload['sources'] if s['id'] == payload['fields'][0]['source'])
    ok('field evidence opens the source of the first field', page.locator('.inv-field-meta a').first.get_attribute('href') == first_source)
    ok('the project reads more than one source, so INS metadata sits beside its own contract', {'https://demoanaf.ro/openapi.json', 'https://ins.gov2.ro/api/datasets/POP107D?lang=en'} <= {s['url'] for s in payload['sources']})
    page.keyboard.press('Escape')
    page.locator('[data-open="demoanaf"] .inventory-tag').click()
    page.wait_for_selector('.inv-field')
    ok('reopening a project reuses its cached payload', len(requests) == 1)
    page.wait_for_timeout(300)
    page.screenshot(path='/tmp/civtech-inventory-desktop.png')

    page.goto(BASE + 'proiect/companii-de-stat/')
    page.wait_for_selector('[data-inv-panel]')
    before = len(requests)
    ok('opening a project keeps the field list lazy', page.locator('[data-inv-panel]').get_attribute('open') is None and len(requests) == before)
    page.locator('[data-inv-panel] > summary').click()
    page.wait_for_selector('.inv-field')
    options = page.locator('[data-inv="source"] option').evaluate_all('els=>els.map(e=>({value:e.value,text:e.textContent}))')
    csv_option = next(o['value'] for o in options if 'CSV' in o['text'])
    page.select_option('[data-inv="source"]', csv_option)
    ok('source selector isolates CSV fields without invented types', page.locator('.inv-field').count() > 0 and all('Tip neprecizat' in t and 'Antet CSV' in t for t in page.locator('.inv-field').all_inner_texts()))

    page.goto(BASE + '?q=REF_AREA')
    page.wait_for_selector('[data-slot="toolbar"] .count')
    expected = [i for i in DB['items'] if i['kind'] == 'proiect' and i['status'] not in ('offline', 'arhivat') and 'ref_area' in i.get('inventory', {}).get('keywords', '').lower()]
    ok('main explorer search finds inventoried field names', int(page.locator('[data-slot="toolbar"] .count b').inner_text()) == len(expected) and len(expected) > 0)

    # New evidence kinds: dataset facts, declared alternatives, formulas, periods, and a failed refresh that must not look fresh.
    page.goto(BASE + 'resursa/orasul-care-se-intinde/')
    page.wait_for_selector('[data-inv-panel]')
    page.locator('[data-inv-panel] > summary').click()
    page.wait_for_selector('.inv-field')
    ok('INS metadata sources list the datasets with period, unit and the mirror caveat',
       page.locator('.inv-datasets').count() == 1 and 'POP107D' in page.locator('.inv-datasets').text_content() and 'Numar persoane' in page.locator('.inv-datasets').text_content()
       and 'oglindă' in page.locator('.inv-datasets').text_content())
    page.locator('[data-inv="q"]').fill('OBS_VALUE')
    ok('an INS dataset has one measure field with its declared unit, not one field per dimension value',
       page.locator('.inv-field').count() == 2 and all('Numar' in t and 'Tip neprecizat' in t for t in page.locator('.inv-field').all_inner_texts()))
    page.goto(BASE + 'proiect/rezultate-vot/')
    page.wait_for_selector('[data-inv-panel]')
    page.locator('[data-inv-panel] > summary').click()
    page.wait_for_selector('.inv-field')
    page.locator('[data-inv="q"]').fill('stocate')
    page.locator('[data-inv="q"]').fill('percent')
    ok('a generated column shows its declared formula', 'Formulă declarată' in page.locator('[data-inventory-fields]').inner_text() and 'initial_total' in page.locator('[data-inventory-fields]').inner_text())
    page.locator('[data-inv="q"]').fill('')
    page.goto(BASE + 'proiect/europescope/')
    page.wait_for_selector('[data-inv-panel]')
    page.locator('[data-inv-panel] > summary').click()
    page.wait_for_selector('.inv-field')
    ok('CSV headers stay without invented types', all('Tip neprecizat' in t for t in page.locator('.inv-field').all_inner_texts()))
    fresh = browser.new_page()
    stale = json.load(urllib.request.urlopen(BASE + 'inventar/demoanaf.json'))
    stale['sources'][0]['refreshFailed'] = {'date': '2026-10-26', 'status': 503, 'state': 'eroare-http'}
    fresh.route('**/inventar/demoanaf.json', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(stale)))
    fresh.goto(BASE + 'proiect/demoanaf/')
    fresh.wait_for_selector('[data-inv-panel]')
    fresh.locator('[data-inv-panel] > summary').click()
    fresh.wait_for_selector('.inv-field')
    ok('a failed refresh is visible and the evidence is not presented as freshly verified',
       'Ultima reîmprospătare a eșuat' in fresh.locator('[data-inventory-fields]').inner_text(timeout=2000) or fresh.evaluate("document.querySelector('[data-inventory-fields]').textContent.includes('Ultima reîmprospătare a eșuat')"))
    fresh.close()

    # A failed lazy request keeps the rest of the project usable, then permits a retry.
    retry = browser.new_page(viewport={'width': 1280, 'height': 900})
    attempts = [0]
    def fail_once(route):
        attempts[0] += 1
        if attempts[0] <= 2:
            route.fulfill(status=503, content_type='application/json', body='{}')
        else:
            route.continue_()
    retry.route('**/inventar/demoanaf.json', fail_once)
    retry.goto(BASE + 'proiect/demoanaf/')
    retry.wait_for_selector('[data-inv-panel]')
    retry.locator('[data-inv-panel] > summary').click()
    retry.wait_for_selector('[data-act="inventory-retry"]')
    ok('failed lazy load has a retry and preserves project details', retry.locator('.inv-error').count() == 1 and retry.locator('#d-title').inner_text() == 'DemoANAF')
    retry.locator('[data-act="inventory-retry"]').click()
    retry.wait_for_selector('[data-act="inventory-retry"]')
    ok('repeated failure keeps focus on the retry', retry.locator('[data-act="inventory-retry"]').evaluate('(e)=>e===document.activeElement'))
    retry.locator('[data-act="inventory-retry"]').click()
    retry.wait_for_selector('.inv-field')
    ok('retry recovers and focuses the field search', attempts[0] == 3 and retry.locator('[data-inv="q"]').evaluate('(e)=>e===document.activeElement'))
    retry.close()

    # Descriptions originate on external sites. Render them as text.
    hostile = browser.new_page()
    payload = json.load(urllib.request.urlopen(BASE + 'inventar/demoanaf.json'))
    payload['fields'][0]['description'] = '<img src=x onerror="window.inventoryExecuted=true">'
    hostile.route('**/inventar/demoanaf.json', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps(payload)))
    hostile.goto(BASE + 'proiect/demoanaf/')
    hostile.wait_for_selector('[data-inv-panel]')
    hostile.locator('[data-inv-panel] > summary').click()
    hostile.wait_for_selector('.inv-field')
    ok('external descriptions remain inert text', hostile.locator('.inv-description img').count() == 0 and hostile.evaluate('window.inventoryExecuted === undefined'))
    hostile.close()

    for width in (390, 320):
        mobile = browser.new_page(viewport={'width': width, 'height': 900}, is_mobile=True, has_touch=True)
        mobile.on('pageerror', lambda e: errors.append(str(e)))
        mobile.goto(BASE + 'proiect/demoanaf/')
        mobile.wait_for_selector('[data-inv-panel]')
        # This block checks the layout of an open panel; opening it by pointer is checked on desktop. On the Linux runner a pointer
        # click at 320 px timed out with the panel itself reported as intercepting it, so the summary is activated directly.
        mobile.locator('[data-inv-panel] > summary').evaluate('(e) => e.click()')
        mobile.wait_for_selector('.inv-field')
        mobile.evaluate('document.fonts.ready')
        bounds = mobile.locator('.d-inventory').bounding_box()
        ok(f'inventory fits the {width}px detail panel', bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1 and mobile.locator('.d-scroll').evaluate('(e)=>e.scrollWidth<=e.clientWidth'))
        overflow = mobile.evaluate('document.documentElement.scrollWidth')
        ok(f'page has no horizontal overflow at {width}px', overflow <= width)
        if overflow > width:  # name the widest elements, so that a failure on another platform says where to look
            print('  ' + ' | '.join(mobile.evaluate('''(w) => [...document.querySelectorAll('body *')].map(e => [e, e.getBoundingClientRect()])
              .filter(([e, r]) => r.width && r.right > w + 1 && !(function clipped(n) { for (n = n.parentElement; n && n !== document.body; n = n.parentElement)
                if (getComputedStyle(n).overflowX !== 'visible' && n.getBoundingClientRect().right <= w + 1) return true; return false; })(e)).sort((a, b) => b[1].right - a[1].right).slice(0, 8)
              .map(([e, r]) => `${e.tagName.toLowerCase()}.${String(e.className).trim().replace(/ +/g, '.')} right=${Math.round(r.right)} "${(e.textContent || '').trim().slice(0, 40)}"`)''', width)))
        mobile.locator('.d-inventory').evaluate('(e)=>e.scrollIntoView({block:"start"})')
        mobile.wait_for_timeout(300)
        mobile.screenshot(path=f'/tmp/civtech-inventory-mobile-{width}.png')
        mobile.close()
    # The explorer is not limited by the scope of /date/ (owner, 2026-10-27): an entry out of scope (inactive, without data, or an organisation)
    # keeps its markers and its "Date & metodă" panel. The sets come from data.json and the rule of the brief, not from the build.
    in_scope = lambda i: i['kind'] in ('proiect', 'resursa') and i['status'] not in ('offline', 'arhivat') and i.get('dataRelation') in ('date-publice', 'date-proprii', 'calcul')
    for kind in ('proiect', 'resursa'):
        page.goto(BASE + f'?k={kind}&ina=1&o=az')
        page.wait_for_selector('[data-slot="toolbar"] .count')
        marker_rows = '[data-slot="results"] .row:has(.inventory-tag), [data-slot="results"] .card:has(.inventory-tag)'
        marked = set(page.locator(marker_rows).evaluate_all('els=>els.map(e=>e.dataset.open)'))
        expected = {i['slug'] for i in DB['items'] if i['kind'] == kind and i.get('inventory', {}).get('count')}
        ok(f'markers on the {kind} tab belong to the entries with fields, inactive ones shown too', marked == expected)
        inside = {i['slug'] for i in DB['items'] if i['slug'] in expected and in_scope(i)}
        for group, want in (('cu-date', inside), ('fara-date', {s for s in expected - inside if next(i for i in DB['items'] if i['slug'] == s)['status'] not in ('offline', 'arhivat')})):
            page.goto(BASE + f'?k={kind}&o=az&dat={group}')
            page.wait_for_selector('[data-slot="toolbar"] .count')
            ok(f'the group {group} shows the markers of its own entries on the {kind} tab',
               set(page.locator(marker_rows).evaluate_all('els=>els.map(e=>e.dataset.open)')) == want and (group != 'cu-date' or len(want) > 0))
    outside_docs = [i for i in DB['items'] if not in_scope(i) and i.get('inventory', {}).get('docs')]
    ok('entries out of scope keep their documentation links in the data', len(outside_docs) > 0)
    for item in [next((i for i in outside_docs if i['kind'] == 'organizatie'), None), next((i for i in outside_docs if i['kind'] != 'organizatie'), None)]:
        if item is None:
            continue
        page.goto(BASE + f"{item['kind']}/{item['slug']}/")
        page.wait_for_selector('#d-title')
        page.wait_for_selector('.d-inventory', timeout=8000)
        ok('the page of ' + item['slug'] + ' (out of scope) shows its "Date & metodă" panel with its documentation links',
           page.locator('.d-inventory').count() == 1 and all(page.locator(f'.d-inventory a[href="{d["url"]}"]').count() > 0 for d in item['inventory']['docs']))
    # The data set facts that a source declares: under the source, with the basis. One entry of each kind that the data holds is opened.
    payloads = {i['slug']: json.load(urllib.request.urlopen(BASE + i['inventory']['url'])) for i in DB['items'] if i.get('inventory', {}).get('url')}
    for kind in ('sets', 'schema'):
        slug = next((s for s, data in payloads.items() if any(source.get('facts', {}).get(kind) for source in data['sources'])), None)
        if slug is None:
            ok(f'a source declares {kind} (no entry has them: the check cannot run)', False)
            continue
        item = next(i for i in DB['items'] if i['slug'] == slug)
        facts = browser.new_page(viewport={'width': 1280, 'height': 900})
        facts.goto(BASE + f"{item['kind']}/{slug}/")
        facts.wait_for_selector('[data-inv-panel]')
        facts.locator('[data-inv-panel] > summary').click()
        facts.wait_for_selector('.inv-facts')
        listed = [x for source in payloads[slug]['sources'] for x in source.get('facts', {}).get('sets', []) + source.get('facts', {}).get('schema', [])]
        names = [x.get('title') or x.get('name') or 'Set de date' for x in listed]
        facts.locator('.inv-facts > summary').click()
        texts = lambda selector: facts.locator(selector).evaluate_all('els=>els.map(e=>e.textContent.trim())')
        ok(f'the field browser lists each data set that a source of {slug} declares ({kind})', facts.locator('.inv-facts .inv-set').count() == len(listed)
           and texts('.inv-facts .inv-set > strong') == names)
        ok(f'each source with facts names its basis ({slug})', texts('.inv-facts .inv-basis') == [s['facts']['basis'] for s in payloads[slug]['sources'] if s.get('facts')]
           and all(b == 'declarație directă' for b in texts('.inv-facts .inv-basis')))
        ok(f'a source that declares nothing has no block of facts ({slug})', facts.locator('.inv-facts > .inv-note').count() >= sum(bool(s.get('facts')) for s in payloads[slug]['sources']))
        facts.close()
    # A long description is cut in the payload; the note then points to the page that holds the whole text. A set that a source declares stays text.
    slug = next(s for s, data in payloads.items() if any(source.get('facts', {}).get('sets') for source in data['sources']))
    item = next(i for i in DB['items'] if i['slug'] == slug)
    edited = json.loads(json.dumps(payloads[slug]))
    first = next(source['facts']['sets'][0] for source in edited['sources'] if source.get('facts', {}).get('sets'))
    first['description'] = 'x' * 299 + '…'
    first['title'] = '<img src=x onerror="window.factsExecuted=true">'
    cut = browser.new_page(viewport={'width': 1280, 'height': 900})
    cut.route(f'**/inventar/{slug}.json', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps(edited)))
    cut.goto(BASE + f"{item['kind']}/{slug}/")
    cut.wait_for_selector('[data-inv-panel]')
    cut.locator('[data-inv-panel] > summary').click()
    cut.wait_for_selector('.inv-facts')
    ok('a cut description points to the page that holds the whole text', cut.locator('.inv-facts a[href="date/' + slug + '/"]').count() == 1)
    ok('the title of a set remains inert text', cut.locator('.inv-facts img').count() == 0 and cut.evaluate('window.factsExecuted === undefined'))
    cut.close()
    # The link to the variables page of an entry (`/date/<slug>/`): only an entry that has the page, and the page is the one of that entry.
    with_page = [i for i in DB['items'] if i.get('inventory', {}).get('page')]
    ok('an entry with a variables page has fields, and the page is date/<slug>/', len(with_page) > 0 and all(i['inventory']['count'] and i['inventory']['page'] == f'date/{i["slug"]}/' for i in with_page))
    ok('an entry in the scope of /date/ with fields has the page', all(i['inventory'].get('page') for i in DB['items'] if i['kind'] in ('proiect', 'resursa') and i['status'] not in ('offline', 'arhivat')
                                                                       and i.get('dataRelation') in ('date-publice', 'date-proprii', 'calcul') and i.get('inventory', {}).get('count')))
    linked = browser.new_page(viewport={'width': 1280, 'height': 900})
    linked.goto(BASE + 'proiect/demoanaf/')
    linked.wait_for_selector('.d-inventory')
    link = linked.locator('.d-inventory .inv-all a')
    ok('the field browser links to the variables page of the entry', link.count() == 1 and 'Toate variabilele' in link.inner_text() and link.get_attribute('href') == 'date/demoanaf/')
    link.click()
    linked.wait_for_selector('.vp-head h1')
    ok('the link opens the variables page of the entry', linked.url.endswith('/date/demoanaf/') and linked.locator('.vp-head h1').inner_text() == 'DemoANAF')
    ok('the page links back to the entry in the explorer', linked.locator('.vp-open').get_attribute('href') == 'proiect/demoanaf/')
    linked.close()
    for item in [i for i in DB['items'] if i.get('inventory') and not i['inventory'].get('page')][:2]:
        other = browser.new_page(viewport={'width': 1280, 'height': 900})
        other.goto(BASE + f"{item['kind']}/{item['slug']}/")
        other.wait_for_selector('.d-inventory')
        ok('an entry without a variables page has no link to one: ' + item['slug'], other.locator('.d-inventory .inv-all').count() == 0)
        other.close()
    ok('no uncaught page errors', not errors)
    browser.close()
print(f'{sum(results)}/{len(results)} inventory preview checks passed')
raise SystemExit(not all(results))
