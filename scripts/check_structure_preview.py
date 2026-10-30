# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Browser acceptance checks for an isolated --with-structure preview."""
import json
import copy
import sys
import urllib.request
from playwright.sync_api import sync_playwright

BASE=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8784/').rstrip('/')+'/'
DB=json.load(urllib.request.urlopen(BASE+'entitati/data.json'))
checks=[]


def observed(namespace,value):
    return [r for r in DB['records'] if any(i['namespace']==namespace and i['value']==value for i in r['identifiers'])]


def direct_counterparts(record):
    ids={record['id']}
    for link in DB['links']:
        if record['id'] in link['records']:ids.update(link['records'])
    return ids


ANTIBIOTICE=observed('ro:cui','1973096')
MAE=observed('ro:cui','4266863')
BUCURESTI=observed('ro:siruta','179132')
IGOV=next(r for r in ANTIBIOTICE if r['project']=='igov')
LOCAL_IDS=direct_counterparts(IGOV)


def ok(label,condition):
    checks.append(bool(condition));print(('PASS ' if condition else 'FAIL ')+label)


with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1280,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    # The preview must work without requesting any project host.
    page.route('**/*',lambda route: route.continue_() if route.request.url.startswith(BASE) else route.abort())
    page.goto(BASE+'entitati/?namespace=ro:cui&value=1973096')
    page.wait_for_selector('.entity-card')
    cards=page.locator('.entity-card')
    ok('Antibiotice shows the observed records',cards.count()==len(ANTIBIOTICE) and 'Antibiotice' in page.locator('#entity-results').inner_text())
    ok('confirmation follows the accepted links',page.locator('.entity-card .kicker').filter(has_text='Corespondență confirmată').count()==len({rid for link in DB['links'] for rid in link['records']} & {r['id'] for r in ANTIBIOTICE}))
    ok('igov local ID remains visible','inst_cui-1973096_89f11b5bc5' in page.locator('#entity-results').inner_text())
    ok('template-derived URLs carry an availability qualifier','URL construit din tipar; disponibilitate neverificată' in page.locator('#entity-results').inner_text())
    ok('igov has no invented company page',cards.filter(has_text='igov · fișa proiectului').get_by_text('Nu avem un URL distinct').count()==1)
    page.get_by_role('button',name='MAE · CUI 4266863',exact=True).click()
    ok('example updates query and results','4266863' in page.url and page.locator('.entity-card').count()==len(MAE))
    page.go_back();page.wait_for_selector('.entity-card')
    ok('back restores the input and results',page.locator('#entity-value').input_value()=='1973096' and 'Antibiotice' in page.locator('#entity-results').inner_text())
    page.get_by_role('button',name='București · SIRUTA 179132',exact=True).click()
    ok('territory search does not equate its fiscal institution',page.locator('.entity-card').count()==len(BUCURESTI) and '4267117' not in page.locator('#entity-results').inner_text() and 'TERITORIU' in page.locator('#entity-results').inner_text().upper())
    page.locator('#entity-value').fill('0179132');page.get_by_role('button',name='Caută',exact=True).click()
    ok('leading zero is not silently removed',page.locator('.entity-card').count()==0 and 'Nicio înregistrare observată' in page.locator('#entity-count').inner_text())
    local=next(n for n in DB['namespaces'] if n['namespace']=='igov:companies:id')
    page.locator('#entity-namespace').select_option(local['id'])
    page.locator('#entity-value').fill('inst_cui-1973096_89f11b5bc5');page.get_by_role('button',name='Caută',exact=True).click()
    ok('local identifier returns direct accepted counterparts',page.locator('.entity-card').count()==len(LOCAL_IDS))
    page.reload();page.wait_for_selector('.entity-card')
    ok('a shared local-ID URL survives reload',page.locator('#entity-namespace').input_value()==local['id'] and page.locator('.entity-card').count()==len(LOCAL_IDS))
    page.goto(BASE+'proiect/romania-transparenta/')
    page.wait_for_selector('[data-structure-profile]')
    profile=page.locator('[data-structure-profile]')
    ok('direct project URL opens its site structure','Secțiuni și colecții' in profile.inner_text() and 'Instituții centrale' in profile.inner_text())
    profile.locator('[data-structure-patterns] > summary').click()
    ok('URL patterns retain typed placeholders','/registre/administratia-centrala/{cui}' in profile.inner_text())
    ok('placeholder templates are text rather than false working links',profile.locator('a[href*="{cui}"]').count()==0)
    profile.locator('[data-structure-apis] > summary').click()
    ok('API endpoints keep method and access claims','GET https://api.romaniatransparenta.eu/v1/companii' in profile.inner_text() and 'Acces declarat:' in profile.inner_text() and 'Acces observat:' in profile.inner_text())
    profile.locator('details > summary').filter(has_text='Surse și data observației').first.click()
    ok('source receipts retain observation dates and hashes','SHA-256' in profile.inner_text() and '2026-' in profile.inner_text())
    ok('lookup is discoverable from profile',profile.get_by_role('link',name='Caută o entitate între proiecte →').get_attribute('href').endswith('/entitati/'))
    page.set_viewport_size({'width':390,'height':844})
    page.goto(BASE+'proiect/romania-transparenta/');page.wait_for_selector('[data-structure-profile]')
    ok('mobile drawer has no horizontal overflow',page.locator('[data-slot="drawer"]').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'))
    profile=page.locator('[data-structure-profile]');profile.scroll_into_view_if_needed()
    page.screenshot(path='/tmp/civtech-structure-profile-mobile.png')
    page.goto(BASE+'entitati/?namespace=ro:cui&value=1973096');page.wait_for_selector('.entity-card')
    ok('mobile lookup has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.screenshot(path='/tmp/civtech-entity-lookup-mobile.png',full_page=True)
    # Exercise the error path without changing the build or reaching an external host.
    page.route('**/entitati/data.json',lambda route:route.fulfill(status=503,body='unavailable'))
    page.reload();page.wait_for_selector('#entity-retry')
    ok('failed payload offers a retry','nu au putut fi încărcate' in page.locator('#entity-count').inner_text())
    page.unroute('**/entitati/data.json');page.locator('#entity-retry').click();page.wait_for_selector('.entity-card')
    ok('retry restores the deep-linked lookup',page.locator('.entity-card').count()==len(ANTIBIOTICE))
    page.goto(BASE+'entitati/?namespace=unrecognised&value=1973096');page.wait_for_function("document.querySelector('#entity-count').textContent.includes('ambiguu')")
    ok('unknown namespace does not fall back to a CUI match',page.locator('.entity-card').count()==0)
    trial=copy.deepcopy(DB)
    original=next(r for r in trial['records'] if r['project']=='registrul-firmelor' and any(i['value']=='1973096' for i in r['identifiers']))
    third=copy.deepcopy(original);third['id']='synthetic-third';third['label']='Synthetic chained record';third['identifiers']=[dict(original['identifiers'][0],value='different')]
    trial['records'].append(third);trial['links'].append(dict(id='synthetic-chain',records=[original['id'],third['id']],state='accepted'))
    page.route('**/entitati/data.json',lambda route:route.fulfill(json=trial))
    page.goto(BASE+'entitati/?namespace='+local['id']+'&value=inst_cui-1973096_89f11b5bc5');page.wait_for_selector('.entity-card')
    ok('accepted links expand one hop without inventing a transitive cluster',page.locator('.entity-card').count()==len(LOCAL_IDS) and page.locator('[data-record="synthetic-third"]').count()==0)
    for slug in ['lista-firme','demoanaf','companii-de-stat','companii-publice-ro','orasul-care-se-intinde',
                 'executii-bugetare','banii-nostri','data-expertforum','ce-cumpara-primaria','cat-de-tare']:
        if slug not in DB['projects']:continue
        expected=DB['projects'][slug]
        page.goto(BASE+expected['profile']);page.wait_for_selector('[data-structure-profile]')
        panel=page.locator('[data-structure-profile]')
        ok('expansion site profile: '+slug,all(c['label'] in panel.inner_text() for c in expected['collections'])
           and f"Tipare URL ({len(expected['patterns'])})" in panel.inner_text()
           and f"Endpointuri API ({len(expected['operations'])})" in panel.inner_text())
        if slug=='demoanaf':
            panel.locator('[data-structure-apis] > summary').click()
            ok('DemoANAF API authentication stays distinct from public frontend records','Autentificare declarată' in panel.inner_text() and 'Acces observat: Neverificat' in panel.inner_text())
    if 'cat-de-tare' in DB['projects']:
        page.unroute('**/entitati/data.json')
        scope=next(n for n in DB['namespaces'] if n['namespace']=='cat-de-tare:locality-slug')
        page.goto(BASE+'entitati/?namespace='+scope['id']+'&value=bucuresti');page.wait_for_selector('.entity-card')
        ok('a local locality slug does not match other sites by name',page.locator('.entity-card').count()==1
           and 'cat-de-tare' in page.locator('.entity-card a').first.get_attribute('href'))
        ok('long local identifier labels fit the mobile lookup',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    ok('no browser script errors',not errors)
    browser.close()
print(f'{sum(checks)}/{len(checks)} browser checks pass')
raise SystemExit(0 if all(checks) else 1)
