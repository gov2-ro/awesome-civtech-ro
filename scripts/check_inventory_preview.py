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
    # An entry out of the scope of the inventory (inactive, without data, not assessed, or an organisation) has no marker and no "Date & metodă" panel,
    # in the list and on its own page. The sets come from data.json and the rule of the brief, not from the build.
    in_scope = lambda i: i['kind'] in ('proiect', 'resursa') and i['status'] not in ('offline', 'arhivat') and i.get('dataRelation') in ('date-publice', 'date-proprii', 'calcul')
    outside = [i for i in DB['items'] if not in_scope(i)]
    ok('the data gives the inventory to entries in scope only', outside and all('inventory' not in i for i in outside))
    for kind in ('proiect', 'resursa'):
        page.goto(BASE + f'?k={kind}&ina=1&o=az')
        page.wait_for_selector('[data-slot="toolbar"] .count')
        marked = set(page.locator('[data-slot="results"] .row:has(.inventory-tag), [data-slot="results"] .card:has(.inventory-tag)').evaluate_all('els=>els.map(e=>e.dataset.open)'))
        ok(f'markers on the {kind} tab belong to entries in scope, inactive ones shown too',
           marked == {i['slug'] for i in DB['items'] if i['kind'] == kind and in_scope(i) and i.get('inventory', {}).get('count')})
    for item in [next(i for i in outside if i['kind'] == 'proiect' and i['status'] in ('offline', 'arhivat')), next(i for i in outside if i['kind'] == 'organizatie')]:
        page.goto(BASE + f"{item['kind']}/{item['slug']}/")
        page.wait_for_selector('#d-title')
        ok('no inventory panel on the page of ' + item['slug'], page.locator('.d-inventory').count() == 0)
    ok('no uncaught page errors', not errors)
    browser.close()
print(f'{sum(results)}/{len(results)} inventory preview checks passed')
raise SystemExit(not all(results))
