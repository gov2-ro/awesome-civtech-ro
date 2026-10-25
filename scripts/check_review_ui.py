# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Browser checks of the local review interface (scripts/review_ui.py).

    uv run scripts/check_review_ui.py [--screenshots DIR]

The check copies the taxonomy v2 package to a temporary folder (with the ignored retained bodies when they exist), makes the copy a git
repository, starts the real command on it (`python3 scripts/review_ui.py --data-dir ... --port 0`) and drives the page with Chromium.
It decides items in the copy only. It refuses to run on the real data root and proves at the end that the real review files did not change.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
REAL = ROOT / 'data/taxonomy-v2'
REAL_FILES = [REAL / 'integrare/revizuire.csv', REAL / 'integrare/relatii.csv', REAL / 'inventar-concepte.json']
PINNED = 'v0.23.0'  # 31 open provider items and 30 proposed groups
GIT_ENV = {**os.environ, 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_SYSTEM': '/dev/null'}
results, errors, external = [], [], []


def ok(label, condition):
    results.append(bool(condition))
    print(('PASS ' if condition else 'FAIL ') + label)


def git(cwd, *args):
    done = subprocess.run(['git', '-c', 'user.name=check', '-c', 'user.email=check@example.org', '-c', 'commit.gpgsign=false',
                           '-c', 'core.hooksPath=/dev/null', *args], cwd=cwd, capture_output=True, text=True, env=GIT_ENV)
    assert done.returncode == 0, done.stderr
    return done.stdout


def until(page, condition, timeout=20):
    """Poll a Python condition. The page's CSP forbids eval, so Playwright's wait_for_function (a string predicate) cannot run."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        page.wait_for_timeout(100)
    raise AssertionError('timed out waiting for a condition')


def start_server(data_dir):
    process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'scripts/review_ui.py'), '--data-dir', str(data_dir), '--port', '0'],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT)
    deadline = time.time() + 30
    while time.time() < deadline:
        line = process.stdout.readline()
        found = re.search(r'(http://127\.0\.0\.1:\d+/)', line)
        if found:
            return process, found.group(1)
    process.kill()
    raise SystemExit('The review server did not start.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in REAL_FILES]
    tmp = Path(tempfile.mkdtemp(prefix='review-ui-browser-'))
    repo = tmp / 'repo'
    repo.mkdir()
    shutil.copytree(REAL, repo / 'taxonomy-v2', ignore=shutil.ignore_patterns('runs', '__pycache__', 'catalogue.json'))
    # The review files come from a commit where nothing was decided, so editorial progress never changes the expected counts.
    for real in REAL_FILES:
        pinned = subprocess.run(['git', 'show', f'{PINNED}:{real.relative_to(ROOT).as_posix()}'], cwd=ROOT, capture_output=True, env=GIT_ENV, check=True)
        (repo / 'taxonomy-v2' / real.relative_to(REAL)).write_bytes(pinned.stdout)
    git(repo, 'init', '-q')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'baseline')
    data = repo / 'taxonomy-v2'
    assert data.resolve() != REAL.resolve(), 'the check runs on a copy, never on the real data root'
    files = {'revizuire': data / 'integrare/revizuire.csv', 'relatii': data / 'integrare/relatii.csv', 'concepte': data / 'inventar-concepte.json'}
    process, base = start_server(data / 'integrare')
    try:
        run(base, files, args.screenshots)
    finally:
        process.terminate()
        process.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)
    after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in REAL_FILES]
    ok('the real review files did not change', before == after)
    print(f'{sum(results)}/{len(results)} checks passed')
    raise SystemExit(0 if all(results) else 1)


def run(base, files, shots):
    host = base.rstrip('/')
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 900}, color_scheme='light')
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('request', lambda r: external.append(r.url) if not r.url.startswith(host) else None)

        def snap(name, selector=None):
            if shots:
                shots.mkdir(parents=True, exist_ok=True)
                if selector:
                    page.locator(selector).first.screenshot(path=str(shots / f'{name}.png'))
                else:
                    page.screenshot(path=str(shots / f'{name}.png'), full_page=False)

        def rows():
            return page.locator('#list .row').evaluate_all('els=>els.map(e=>e.querySelector(".id").textContent)')

        def chip(item_id):
            return page.locator(f'#list .row:has(.id:text-is("{item_id}")) .chip').inner_text()

        def wait_detail(title):
            until(page, lambda: page.locator('#detail h2').count() and page.locator('#detail h2').first.inner_text().startswith(title))

        def progress_has(text):
            until(page, lambda: text in page.locator('#progress').inner_text())

        def open_item(kind, item_id, title):
            page.evaluate(f'location.hash="#{kind}/{item_id}"')
            wait_detail(title)

        def decide(action, note=None, **fields):
            page.locator(f'.actions button[data-action="{action}"]').click()
            for key, value in fields.items():
                if key == 'other':
                    page.locator('#f-other').select_option(value)
                else:
                    page.locator(f'#f-{key}').fill(value)
            if note is not None:
                page.locator('#f-note').fill(note)

        def row_of(path, item_id):
            return next(r for r in path.read_text().splitlines() if r.startswith(item_id + ','))

        state = json.loads(page.request.get(host + '/api/state').text())
        open_total = state['progress']['providers']['total']

        # -- load, progress, list, selection in the URL -----------------------------------------------------------------------------------
        page.goto(base)
        page.wait_for_selector('#list .row')
        ok('the page loads with the progress of both queues', page.locator('#progress').inner_text().startswith('Furnizori: 0 / 31 decise') and 'Grupuri: 0 / 30 revizuite' in page.locator('#progress').inner_text())
        ok('the validation state is visible', page.locator('#validation').inner_text() == 'Validare: fără erori')
        ok('the default filter is Deschise and lists every open provider item', page.locator('#filter button[aria-pressed="true"]').inner_text() == 'Deschise' and len(rows()) == open_total == 31)
        ok('a row shows the id, the project and a short proposal', 'DemoANAF' in page.locator('#list .row').first.inner_text() and 'ANAF' in page.locator('#list .row').first.inner_text())
        ok('the first item is selected and its id is in the URL hash', page.url.endswith('#furnizor/D132') and 'D132 · DemoANAF' in page.locator('#detail h2').inner_text())
        open_item('furnizor', 'D140', 'D140')
        ok('selecting an item puts it in the hash', page.url.endswith('#furnizor/D140'))
        page.reload()
        wait_detail('D140')
        ok('reload keeps the selection', page.url.endswith('#furnizor/D140') and page.locator('#list .row[aria-current="true"] .id').inner_text() == 'D140')
        page.locator('#list .row:has(.id:text-is("D141"))').click()
        wait_detail('D141')
        page.go_back()
        wait_detail('D140')
        ok('back returns to the earlier item', page.url.endswith('#furnizor/D140'))
        page.locator('body').click(position={'x': 5, 'y': 5})
        page.keyboard.press('j')
        wait_detail('D141')
        page.keyboard.press('k')
        wait_detail('D140')
        ok('j and k move between items', page.url.endswith('#furnizor/D140'))
        for key in ('a', 'r', 'd', 'x', 'Enter'):
            page.keyboard.press(key)
        ok('no single key decides an item', json.loads(page.request.get(host + '/api/state').text())['progress']['providers']['decided'] == 0)

        # -- provider item: proposal, evidence, relation, related items, warnings ---------------------------------------------------------------
        open_item('furnizor', 'D153', 'D153')
        detail = page.locator('#detail').inner_text()
        ok('a provider item shows the original value, the proposal and the reason', 'Valoare originală' in detail and 'Propunere' in detail and 'Motiv' in detail and 'Oficiul Național al Registrului Comerțului' in detail)
        ok('a related item for the same project and provider is listed with its state', page.locator('#detail li:has(a:text-is("D140")) .tag').count() == 1 and 'Deschis' in page.locator('#detail li:has(a:text-is("D140"))').inner_text())
        ok('the catalogue link opens in a new tab', page.locator('#detail .links a').first.get_attribute('target') == '_blank' and page.locator('#detail .links a').first.get_attribute('href').startswith('https://civtech.gov2.ro/proiect/'))
        evidence_state = page.locator('#detail .evidence .chip').first.inner_text()
        marks = page.locator('#detail .evidence mark').all_inner_texts()
        ok('the evidence panel shows a verification state and highlights the fragment only when it has the retained text',
           (evidence_state == 'verificat' and marks == ['Oficiul Național al Registrului Comerțului · data.gov.ro']) or (evidence_state == 'indisponibil local' and not marks))
        open_item('furnizor', 'D132', 'D132')
        first_state = page.locator('#detail .evidence .chip').first.inner_text()
        ok('an item with no recorded hash is never called verified', first_state in ('fără amprentă', 'indisponibil local'))
        open_item('furnizor', 'D160', 'D160')
        ok('a proposal limited to one dataset shows a warning', 'un singur set' in page.locator('#detail .warn').inner_text())
        open_item('furnizor', 'D147', 'D147')
        ok('an item with no relation row says which row it would add', 'Rând nou L147' in page.locator('#detail').inner_text())
        snap('provider')

        # -- one decision of each kind ----------------------------------------------------------------------------------------------------------
        open_item('furnizor', 'D132', 'D132')
        decide('accept', note='Furnizor confirmat pe pagina proiectului.')
        ok('the consequence sentence names the provider and the project before saving',
           'Acceptarea adaugă «ANAF» ca sursă de date pentru DemoANAF pe site-ul public.' in page.locator('#consequence').inner_text())
        page.locator('#f-name').fill('Agenția Națională de Administrare Fiscală (ANAF)')
        ok('the consequence follows the edited name', '«Agenția Națională de Administrare Fiscală (ANAF)»' in page.locator('#consequence').inner_text())
        page.locator('#f-note').fill('')
        page.locator('#f-save').click()
        until(page, lambda: page.locator('#p-status').inner_text() != '')
        ok('a missing note is refused and nothing is written', 'Notă' in page.locator('#p-status').inner_text() and row_of(files['revizuire'], 'D132').endswith(',deschis,'))
        page.locator('#f-note').fill('Furnizor confirmat pe pagina proiectului.')
        page.locator('#f-save').click()
        until(page, lambda: page.locator('#progress').inner_text().startswith("Furnizori: 1 / 31"))
        ok('accept: the progress, the chip and the files change', chip('D132') == 'Acceptat' and re.search(r'^L132,demoanaf,date_din,,Agenția Națională de Administrare Fiscală \(ANAF\),surse_date,https://demoanaf.ro/,acceptat$', files['relatii'].read_text(), re.M)
           and ',acceptat,Acceptat 2026' in row_of(files['revizuire'], 'D132'))
        ok('the saved decision is shown on the item', 'Decizia curentă' in page.locator('#detail').inner_text() and page.locator('#p-status').inner_text().startswith('D132 acceptat'))
        ok('a decided item stays visible under the Deschise filter until you leave it', 'D132' in rows())

        open_item('furnizor', 'D133', 'D133')
        decide('reject', note='Doar o referință metodologică, nu date.')
        ok('reject: the consequence sentence says the row is rejected', 'Respingerea nu adaugă nimic' in page.locator('#consequence').inner_text() and 'L133' in page.locator('#consequence').inner_text())
        page.locator('#f-save').click()
        until(page, lambda: page.locator('#progress').inner_text().startswith("Furnizori: 2 / 31"))
        ok('reject: the relation row becomes respins', chip('D133') == 'Respins' and re.search(r'^L133,.*,respins$', files['relatii'].read_text(), re.M))

        open_item('furnizor', 'D134', 'D134')
        decide('defer', note='Aștept răspunsul proiectului.')
        page.locator('#f-save').click()
        until(page, lambda: 'amânat' in page.locator('#p-status').inner_text())
        ok('defer: the item is deferred, counts as open, and the relation row stays propus', chip('D134') == 'Amânat' and page.locator('#progress').inner_text().startswith('Furnizori: 2 / 31 decise (1 amânate)')
           and re.search(r'^L134,.*,propus$', files['relatii'].read_text(), re.M))

        open_item('furnizor', 'D153', 'D153')
        decide('duplicate', note='Aceeași sursă ca D140.', other='D140')
        ok('duplicate: the consequence names the other item', 'duplicat al lui D140' in page.locator('#consequence').inner_text())
        page.locator('#f-save').click()
        until(page, lambda: page.locator('#progress').inner_text().startswith("Furnizori: 3 / 31"))
        row = [r for r in files['revizuire'].read_text().splitlines() if r.startswith('D153,')][0]
        ok('duplicate: the item is tehnic with a motiv that names the other item and no editor decision', row.endswith(',tehnic,') and 'Duplicat: D140. Aceeași sursă ca D140.' in row)

        open_item('furnizor', 'D147', 'D147')
        decide('accept', note='Pagina cere atribuirea sursei.')
        ok('a new row: the consequence names the next free id', 'Rândul nou L147' in page.locator('#consequence').inner_text() and page.locator('#f-name').input_value().startswith('Parlamentul European'))
        page.locator('#f-save').click()
        until(page, lambda: page.locator('#progress').inner_text().startswith("Furnizori: 4 / 31"))
        ok('a new row is appended with the next free id', files['relatii'].read_text().splitlines()[-1].startswith('L147,europescope,date_din,,Parlamentul European') and files['relatii'].read_text().endswith('\n'))

        open_item('furnizor', 'D133', 'D133')
        ok('reset is offered for a changed item', page.locator('.actions button[data-action="reset"]').is_enabled())
        decide('reset')
        ok('reset needs no note and says what it restores', 'HEAD' in page.locator('#consequence').inner_text() and page.locator('#f-note').count() == 0)
        page.locator('#f-save').click()
        until(page, lambda: page.locator('#progress').inner_text().startswith("Furnizori: 3 / 31"))
        ok('reset: the item and its row are back at HEAD values', chip('D133') == 'Deschis' and re.search(r'^L133,.*,propus$', files['relatii'].read_text(), re.M) and row_of(files['revizuire'], 'D133').endswith(',deschis,'))
        page.locator('#filter button[data-filter="decided"]').click()
        decided = rows()
        page.locator('#filter button[data-filter="open"]').click()
        page.locator('#filter button[data-filter="all"]').click()
        ok('the filters list decided, open and all items', set(decided) >= {'D132', 'D153', 'D147'} and 'D141' not in decided and len(rows()) == 31)
        page.locator('#filter button[data-filter="open"]').click()
        ok('the open filter hides decided items and keeps deferred ones', 'D134' in rows() and 'D140' in rows() and 'D147' not in rows())

        # -- the note is text: markup in it never runs ------------------------------------------------------------------------------------------
        open_item('furnizor', 'D135', 'D135')
        decide('defer', note='<img src=x onerror="window.__injected=1"> <b>negru</b>')
        page.locator('#f-save').click()
        progress_has("(2 amânate)")
        ok('markup in a note is shown as text', '<img src=x' in page.locator('#detail').inner_text() and page.locator('#detail img').count() == 0 and page.evaluate('window.__injected') is None)

        # -- a stale file: the page refuses and asks for a reload -------------------------------------------------------------------------------
        open_item('furnizor', 'D136', 'D136')
        decide('defer', note='Încerc după o editare externă.')
        edited = files['revizuire'].read_text().replace('Recomandare: păstrați subiect:guvernare-democratie', 'Recomandare (editată): păstrați subiect:guvernare-democratie', 1)
        files['revizuire'].write_text(edited)
        page.locator('#f-save').click()
        page.wait_for_selector('#banner:not([hidden])')
        ok('a file edited since the page loaded refuses the write and offers a reload', 'Reîncărcați' in page.locator('#banner').inner_text() and 'Reîncarcă' in page.locator('#banner button').inner_text())
        ok('the refused write left the edited file as it was', files['revizuire'].read_text() == edited)
        page.locator('#banner button').click()
        page.wait_for_selector('#banner[hidden]', state='attached')
        ok('reloading brings the page up to date', page.locator('#progress').inner_text().startswith('Furnizori: 3 / 31'))
        files['revizuire'].write_text(files['revizuire'].read_text().replace('Recomandare (editată):', 'Recomandare:', 1))

        # -- groups -------------------------------------------------------------------------------------------------------------------------------
        page.locator('#tab-groups').click()
        until(page, lambda: page.locator('#list .row .id').first.inner_text() == 'cui')
        group_rows = rows()
        ok('the group queue lists the 30 groups, all proposed', len(group_rows) == 30 and page.locator('#list .row .chip').all_inner_texts().count('Propus') == 30)
        ok('the first group is selected in the hash', page.url.endswith('#grup/' + group_rows[0]))
        open_item('grup', 'cui', 'CUI')
        ok('a group shows its definition with the basis label', 'parafrază editorială' in page.locator('#detail').inner_text() and 'Identificatorul fiscal' in page.locator('#detail').inner_text())
        ok('members show the project, the field, the source and examples', page.locator('.member').count() == 12 and 'afn' in page.locator('.member').nth(5).inner_text() and page.locator('.member').nth(5).locator('a[target="_blank"]').count() >= 1
           and page.locator('.member').nth(5).locator('table.examples tbody tr').count() >= 1)
        ok('deductions have a distinct style and a basis label', page.locator('.member .deduction').count() == 4 and 'deducție din dovezi' in page.locator('.member .deduction').first.inner_text())
        group_evidence = page.locator('#detail .evidence .chip').all_inner_texts()
        ok('group evidence states come from the hash check', group_evidence and set(group_evidence) <= {'verificat', 'indisponibil local'})
        ok('Revizuit is disabled and the page says why', page.locator('#g-revizuit').is_disabled() and 'membri sunt încă «propuși»' in page.locator('#g-reason').inner_text())
        snap('group')
        page.locator('.member').first.locator('input[type="text"]').fill('')
        page.locator('.member').first.locator('button[data-act="exclude"]').click()
        page.wait_for_selector('#banner:not([hidden])')
        ok('excluding a member without a note is refused', 'Notă' in page.locator('#banner').inner_text())
        for number in range(1, 13):
            member = page.locator(f'.member[data-member="{number}"]')
            if number == 1:
                member.locator('input[type="text"]').fill('Nu este CUI: este un cod intern.')
                member.locator('button[data-act="exclude"]').click()
            else:
                member.locator('button[data-act="confirm"]').click()
            until(page, lambda n=number: page.locator(f'.member[data-member="{n}"]').get_attribute('data-state') != 'propus')
        ok('members are confirmed or excluded one by one', page.locator('.member[data-state="confirmat"]').count() == 11 and page.locator('.member[data-state="exclus"]').count() == 1)
        ok('an excluded member keeps its note and stays in the file', '"nota_editor": "Nu este CUI: este un cod intern."' in files['concepte'].read_text())
        ok('Revizuit stays disabled while a deduction is not ticked', page.locator('#g-revizuit').is_disabled() and '4 deducții' in page.locator('#g-reason').inner_text())
        for box in page.locator('input[data-tick]').all():
            box.check()
        snap('group-member', '.member[data-member="6"]')
        ok('ticking every deduction enables Revizuit', page.locator('#g-revizuit').is_enabled() and page.locator('#g-reason').inner_text() == '')
        page.locator('#g-note').fill('Membrii, dovezile și formularea sunt verificate.')
        snap('group-decision', '#decision')
        page.locator('#g-revizuit').click()
        progress_has("Grupuri: 1 / 30 revizuite")
        saved = json.loads(files['concepte'].read_text())['concepte'][0]
        ok('revizuit: the group state, the decision and the date are written after the existing keys', saved['stare'] == 'revizuit' and saved['decizie_editor'].startswith('Membrii') and re.fullmatch(r'\d{4}-\d{2}-\d{2}', saved['data_revizie'])
           and list(saved)[-3:] == ['stare', 'decizie_editor', 'data_revizie'])
        ok('a reviewed group locks its members until it is reset', page.locator('.member .actions button').count() == 0)
        page.locator('#g-reset').click()
        progress_has("Grupuri: 0 / 30 revizuite")
        ok('reset: the group is back at HEAD', 'stare' not in json.loads(files['concepte'].read_text())['concepte'][0] and files['concepte'].read_bytes() == subprocess.run(
            ['git', 'show', 'HEAD:taxonomy-v2/inventar-concepte.json'], cwd=files['concepte'].parent.parent, capture_output=True, env=GIT_ENV).stdout)
        open_item('grup', 'siruta', 'Cod SIRUTA')
        page.locator('.member[data-member="1"] button[data-act="confirm"]').click()
        until(page, lambda: page.locator('.member[data-member="1"]').get_attribute('data-state') == 'confirmat')
        ok('a group without deductions can be reviewed once its members are decided', page.locator('#g-revizuit').is_enabled())
        page.locator('#g-note').fill('Verificat.')
        page.locator('#g-respins').click()
        progress_has("Grupuri: 1 / 30 revizuite")
        ok('resping: the group is rejected', chip('siruta') == 'Respins' and json.loads(files['concepte'].read_text())['concepte'][2]['stare'] == 'respins')
        page.locator('#tab-groups').click()
        until(page, lambda: page.locator('#tab-groups').get_attribute('aria-current') == 'page')
        page.locator('#filter button[data-filter="decided"]').click()
        ok('the decided filter lists reviewed groups', 'siruta' in rows() and 'judet' not in rows())
        page.locator('#filter button[data-filter="open"]').click()

        # -- the check panel -----------------------------------------------------------------------------------------------------------------------
        page.locator('#tab-checks').click()
        page.wait_for_selector('#run-checks')
        page.wait_for_selector('#public-diff')
        ok('the public consequence lists added providers against HEAD', page.locator('#public-diff .diff-add').all_inner_texts()[:2] == [
            '+ demoanaf: Agenția Națională de Administrare Fiscală (ANAF) (https://demoanaf.ro/)', '+ europescope: Parlamentul European (portalul de date deschise) (https://www.europescope.eu/data)'])
        ok('changed files and the suggested commands are shown', 'revizuire.csv' in page.locator('#git-panel').inner_text() and 'inventar-concepte.json' in page.locator('#git-panel').inner_text()
           and 'git add' in page.locator('#commands').inner_text() and 'python3 scripts/inventory_report.py' in page.locator('#commands').inner_text() and 'git push' not in page.locator('#commands').inner_text())
        page.locator('#run-checks').click()
        until(page, lambda: page.locator('#check-results .check').count() == 3, timeout=120)
        cards = page.locator('#check-results .check')
        ok('each check shows its exit code and the end of its output', cards.count() == 3 and all('cod de ieșire' in cards.nth(i).inner_text() for i in range(3)))
        ok('validate.py --publication passes on the edited copy', cards.nth(0).get_attribute('data-ok') == 'true' and 'erori' in cards.nth(0).inner_text())
        snap('checks')

        # -- layout, requests, errors -------------------------------------------------------------------------------------------------------------------
        for width in (1280, 390):
            page.set_viewport_size({'width': width, 'height': 900})
            for label, hash_ in (('list', '#furnizori'), ('provider', '#furnizor/D153'), ('group', '#grup/cui'), ('checks', '#verificari')):
                page.evaluate(f'location.hash="{hash_}"')
                page.wait_for_timeout(600)
                if label == 'group':
                    page.wait_for_selector('.member')
                fits = page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                ok(f'{width}px: the {label} view fits the viewport (no horizontal scroll)', fits)
        page.evaluate('location.hash="#furnizori"')
        page.wait_for_timeout(300)
        ok('390px: the list and the detail are shown one at a time', page.locator('#list').is_visible() and not page.locator('#detail').is_visible())
        page.locator('#list .row').first.click()
        page.wait_for_selector('#detail h2')
        ok('390px: selecting an item shows the detail with a way back', page.locator('#detail').is_visible() and not page.locator('#list').is_visible() and page.locator('.back').is_visible())
        snap('mobile')
        ok('the page made no request outside the local server', external == [])
        refused = [e for e in errors if re.fullmatch(r'Failed to load resource: the server responded with a status of (400|409) \(.*\)', e)]
        ok('the only console errors are the three refused requests that this check provokes (a missing note twice, a stale file)',
           len(refused) == 3 and refused == errors[:0] + [e for e in errors if e in refused])
        ok('no other browser error', [e for e in errors if e not in refused] == [])
        browser.close()


if __name__ == '__main__':
    main()
