# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Check cross-project inventory discovery in an isolated preview."""
import json
import sys
import urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8770/'
INDEX = json.load(urllib.request.urlopen(BASE + 'inventar/index.json'))
results, errors = [], []


def ok(label, condition):
    results.append(bool(condition))
    print(('PASS ' if condition else 'FAIL ') + label)


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, color_scheme='dark')
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_selector('.tabs a[href="date/"]')
    page.locator('.tabs a[href="date/"]').click()
    page.wait_for_selector('.finder-card')
    ok('explorer navigation opens the dedicated inventory page', '/date/' in page.url)
    ok('dedicated page includes all projects and resources', page.locator('#data-count').inner_text() == '106 proiecte · 21 resurse')
    ok('results load in bounded batches', page.locator('.finder-card').count() == 24)
    page.locator('[data-more]').click()
    ok('more results append and move focus to the next batch', page.locator('.finder-card').count() == 48 and page.locator('.finder-card h2 a').nth(24).evaluate('(e)=>e===document.activeElement'))
    page.goto(BASE + 'date/?variables=cui')
    page.wait_for_selector('.finder-card')
    expected = [e for e in INDEX['entries'] if any(v['id'] == 'cui' for v in e['variables'])]
    ok('shared CUI group finds four entries', len(expected) == 4 and page.locator('.finder-card').count() == 4)
    page.locator('.finder-card').first.locator('.finder-evidence > summary').click()
    ok('group evidence exposes field names and source URLs', page.locator('.finder-evidence[open] code').count() > 0 and page.locator('.finder-evidence[open] a').first.get_attribute('href').startswith('https://'))
    page.locator('.finder-examples [data-value="cpv"]').click()
    ok('multiple variables require a common project', page.locator('.finder-card').count() == 2 and set(page.locator('.finder-card').evaluate_all('els=>els.map(e=>e.dataset.project)')) == {'demoanaf', 'romania-transparenta'})
    saved = page.url
    page.reload(); page.wait_for_selector('.finder-card')
    ok('shareable URL restores the selection', page.locator('.finder-card').count() == 2 and page.url == saved)
    page.locator('#data-active [data-value="cpv"]').click()
    page.go_back(); page.wait_for_function("document.querySelectorAll('.finder-card').length===2")
    ok('browser back restores filters and results', page.locator('#data-active [data-value="cpv"]').count() == 1)
    page.goto(BASE + 'date/?providers=INS')
    page.wait_for_selector('.finder-card')
    ok('provider matches count projects once', page.locator('.finder-card').count() == 9)
    page.locator('#data-resources').uncheck()
    ok('project-only selection excludes resources', page.locator('.finder-card').count() == 3 and 'resurse=0' in page.url)
    page.goto(BASE + 'date/?providers=MDLPA&providers=INS')
    page.wait_for_selector('.finder-card')
    ok('providers are alternatives within their filter', page.locator('.finder-card').count() == 10)
    page.goto(BASE + 'date/?providers=INS&variables=siruta')
    page.wait_for_selector('.finder-card')
    ok('provider and variable filters intersect', page.locator('.finder-card').count() == 1 and page.locator('.finder-card').get_attribute('data-project') == 'orasul-care-se-intinde')
    page.goto(BASE + 'date/?institutions=institutie%3Aparlament')
    page.wait_for_selector('.finder-card')
    expected = sum('institutie:parlament' in e['institutions'] for e in INDEX['entries'])
    ok('institutions concerned are independent of data providers', page.locator('.finder-card').count() == min(24,expected) and expected > 1)
    page.goto(BASE + 'date/?q=REF_AREA')
    page.wait_for_selector('.finder-card')
    ok('technical field search works without opening each project', page.locator('[data-project="ins-gov2"]').count() == 1)
    page.locator('#data-search').fill('nothing_matches_7364')
    page.wait_for_selector('.finder-empty')
    ok('empty results preserve search focus', page.locator('#data-search').evaluate('(e)=>e===document.activeElement'))
    page.locator('[data-clear="all"]').click()
    ok('reset restores all catalogue entries', page.locator('#data-count').inner_text() == '106 proiecte · 21 resurse')
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
