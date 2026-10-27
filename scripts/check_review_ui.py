# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Browser checks of the local review interface (scripts/review_ui.py).

    uv run scripts/check_review_ui.py [--screenshots DIR]

The check copies the taxonomy v2 package to a temporary folder (with the ignored retained bodies when they exist), makes the copy a git
repository, starts the real command on it (`python3 scripts/review_ui.py --data-dir ... --port 0`) and drives the page with Chromium.
A second copy holds candidate members that the check makes itself (the real notes hold none): it confirms, excludes and resets them.
It decides items in the copies only. It refuses to run on the real data root and proves at the end that the real review files did not change.
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
REAL_FILES = [REAL / 'integrare/revizuire.csv', REAL / 'integrare/relatii.csv', REAL / 'inventar-concepte.json', REAL / 'inventar-note.json']
PINNED_FILES = REAL_FILES[:3]  # the files that carry the decisions; the notes of the working tree hold no candidate
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


def make_copy(tmp, name):
    """A copy of the taxonomy v2 package in a repository of its own, with the review files of a commit where nothing was decided
    (so that editorial progress never changes the expected counts). Returns the data folder of the copy."""
    repo = tmp / name
    repo.mkdir()
    shutil.copytree(REAL, repo / 'taxonomy-v2', ignore=shutil.ignore_patterns('runs', '__pycache__', 'catalogue.json'))
    for real in PINNED_FILES:
        pinned = subprocess.run(['git', 'show', f'{PINNED}:{real.relative_to(ROOT).as_posix()}'], cwd=ROOT, capture_output=True, env=GIT_ENV, check=True)
        (repo / 'taxonomy-v2' / real.relative_to(REAL)).write_bytes(pinned.stdout)
    data = repo / 'taxonomy-v2'
    assert data.resolve() != REAL.resolve(), 'the check runs on a copy, never on the real data root'
    return data


def commit_all(data):
    git(data.parent, 'init', '-q')
    git(data.parent, 'add', '-A')
    git(data.parent, 'commit', '-qm', 'baseline')


def write_like(path, value):
    """JSON as the review tool writes it: two spaces, readable characters, and the final newline that the file has (or has not)."""
    like = path.read_bytes()
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + ('\n' if like.endswith(b'\n') else ''))


CANDIDATE_GROUPS = ('cui', 'judet', 'localitate')  # reviewed in the second copy, with every member confirmed; `siruta` stays proposed


def seed_candidates(data):
    """Make the candidates of the check in a copy: three reviewed groups, and candidates that a batch could have proposed (selectors of other groups).
    A: cui, with pinned facts; B: judet; C: localitate; D: siruta (a proposed group: an error); E: excluded earlier; F: E proposed again."""
    concepts = json.loads((data / 'inventar-concepte.json').read_text())
    by_id = {c['id']: c for c in concepts['concepte']}
    with_facts = next(sel for sel in by_id['populatie']['selectors'] if sel.get('fapte'))
    chosen = {'A': ('cui', with_facts), 'B': ('judet', by_id['localitate']['selectors'][0]), 'C': ('localitate', by_id['cui']['selectors'][0]),
              'D': ('siruta', {'projects': ['banii-nostri'], 'names': ['siruta_nou']}), 'E': ('cui', {'projects': ['banii-nostri'], 'names': ['cui_vechi'], 'context': 'Primul context.'})}
    for gid in CANDIDATE_GROUPS:
        for selector in by_id[gid]['selectors']:
            selector['stare'] = 'confirmat'
        by_id[gid].update(stare='revizuit', decizie_editor='Verificat.', data_revizie='2026-10-24')
    write_like(data / 'inventar-concepte.json', concepts)
    items = [{'grup': g, 'selector': sel} for g, sel in (chosen['A'], chosen['B'], chosen['C'], chosen['D'])]
    items.append({'grup': 'cui', 'selector': chosen['E'][1], 'stare': 'exclus', 'nota_editor': 'Este un cod intern.'})
    items.append({'grup': 'cui', 'selector': {**chosen['E'][1], 'context': 'Alt context, același câmp.'}})
    notes = json.loads((data / 'inventar-note.json').read_text())
    anchor, out = list(notes)[len(notes) // 2], {}
    for key, value in notes.items():
        out[key] = value
        if key == anchor:
            out['selectori_candidati'] = items
    write_like(data / 'inventar-note.json', out)
    return concepts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in REAL_FILES]
    tmp = Path(tempfile.mkdtemp(prefix='review-ui-browser-'))
    try:
        data = make_copy(tmp, 'repo')
        commit_all(data)
        files = {'revizuire': data / 'integrare/revizuire.csv', 'relatii': data / 'integrare/relatii.csv', 'concepte': data / 'inventar-concepte.json'}
        process, base = start_server(data / 'integrare')
        try:
            run(base, files, args.screenshots)
        finally:
            process.terminate()
            process.wait(timeout=10)
        data = make_copy(tmp, 'repo-candidates')
        seed_candidates(data)
        commit_all(data)
        files = {'concepte': data / 'inventar-concepte.json', 'note': data / 'inventar-note.json'}
        process, base = start_server(data / 'integrare')
        try:
            run_candidates(base, files, args.screenshots)
        finally:
            process.terminate()
            process.wait(timeout=10)
    finally:
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


def run_candidates(base, files, shots):
    """The candidate queue, on a copy that holds six candidates (A..F, see seed_candidates). Each step reads the files of the copy."""
    host = base.rstrip('/')
    repo = files['concepte'].parent.parent
    problems, outside = [], []

    def head(path):
        return subprocess.run(['git', 'show', 'HEAD:' + path.relative_to(repo).as_posix()], cwd=repo, capture_output=True, env=GIT_ENV, check=True).stdout

    def both():
        return files['concepte'].read_bytes(), files['note'].read_bytes()

    def group(gid):
        return next(c for c in json.loads(files['concepte'].read_text())['concepte'] if c['id'] == gid)

    def items():
        return json.loads(files['note'].read_text()).get('selectori_candidati', [])

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 900}, color_scheme='light')
        page = context.new_page()
        page.on('pageerror', lambda e: problems.append(str(e)))
        page.on('console', lambda m: problems.append(m.text) if m.type == 'error' else None)
        page.on('request', lambda r: outside.append(r.url) if not r.url.startswith(host) else None)

        def api_get(path):
            return json.loads(page.request.get(host + path).text())

        def snap(name, selector=None):
            if shots:
                shots.mkdir(parents=True, exist_ok=True)
                if selector:
                    page.locator(selector).first.screenshot(path=str(shots / f'{name}.png'))
                else:
                    page.screenshot(path=str(shots / f'{name}.png'), full_page=False)

        def queue():
            return api_get('/api/state')['candidates']

        def rows():
            return page.locator('#list .row').evaluate_all('els=>els.map(e=>e.querySelector(".id").textContent)')

        def cid(letter):
            return next(c['id'] for c in queue() if c['key'] == keys[letter])

        def goto(letter):
            wanted = cid(letter)
            page.evaluate(f'location.hash="#candidat/{wanted}"')
            until(page, lambda: page.locator('#detail [data-candidate]').count() and page.locator('#detail [data-candidate]').first.get_attribute('data-candidate') == wanted)
            return wanted

        def row_chip(letter):
            return page.locator(f'#list a.row[href="#candidat/{cid(letter)}"] .chip').inner_text()

        def status_has(text):
            until(page, lambda: text in page.locator('#c-status').inner_text())

        def progress_has(text):
            until(page, lambda: text in page.locator('#progress').inner_text())

        def decide(button, note=None):
            if note is not None:
                page.locator('#c-note').fill(note)
            page.locator(button).click()

        # -- the queue ---------------------------------------------------------------------------------------------------------------------------
        state = api_get('/api/state')
        keys = dict(zip('ABCDEF', [c['key'] for c in state['candidates']]))
        labels = {c['group']: c['label'] for c in state['candidates']}
        page.goto(base)
        page.wait_for_selector('#list .row')
        ok('the navigation counts the open candidates', page.locator('#tab-candidates').inner_text() == 'Candidați (5)')
        ok('the header counts them too', page.locator('#progress').inner_text().endswith('· Candidați: 5 deschiși'))
        ok('the candidate of a proposed group is the one validation error', page.locator('#validation').inner_text() == 'Validare: 1 erori')
        page.locator('#tab-candidates').click()
        until(page, lambda: len(rows()) == 5)
        ok('the queue lists the open candidates in the order of the notes, by their place', rows() == ['#1', '#2', '#3', '#4', '#6'])
        ok('a row names the group and the selector', labels['cui'] in page.locator('#list .row').first.inner_text() and ' · ' in page.locator('#list .row').first.inner_text())
        until(page, lambda: page.url.endswith('#candidat/' + cid('A')))
        ok('the first open candidate is selected and its id is in the URL', page.url.endswith('#candidat/' + cid('A')))
        page.locator('#filter button[data-filter="all"]').click()
        ok('all candidates are listed under the filter Toate', len(rows()) == 6)
        page.locator('#filter button[data-filter="decided"]').click()
        ok('the excluded candidate is listed under Decise, with its state (the selected one stays visible)', rows() == ['#1', '#5'] and row_chip('E') == 'Exclus')
        page.locator('#filter button[data-filter="open"]').click()

        # -- the detail --------------------------------------------------------------------------------------------------------------------------
        goto('A')
        view = api_get('/api/candidate/' + cid('A'))
        detail = page.locator('#detail').inner_text()
        ok('the detail names the group, its definition and the candidate', page.locator('#detail h2').inner_text().startswith('Candidat #1 · ' + labels['cui']) and view['group']['definition'][:40] in detail)
        ok('the detail shows the names, the path, the source and the reach of the selector', 'Câmpuri atinse' in detail and all(n in detail for n in view['member']['names'] + view['member']['path']))
        ok('the examples of the reach are listed', page.locator('#candidate-member table.examples tbody tr').count() == len(view['member']['reach']['examples']))
        pinned = view['member']['facts']
        ok('the pinned facts show their basis and the state of their evidence', len(pinned) >= 1 and page.locator('#candidate-member .evidence .chip').count() == len([f for f in pinned if f['evidence']])
           and set(page.locator('#candidate-member .evidence .chip').all_inner_texts()) <= {'verificat', 'indisponibil local', 'fără amprentă', 'schimbat', 'fragment lipsă'} and all(f['basis_label'] in page.locator('#candidate-member').inner_text() for f in pinned))
        ok('the detail lists the confirmed members of the group', page.locator('#confirmed-members li').count() == len(group('cui')['selectors']) and f'membri confirmați ai grupului ({len(group("cui")["selectors"])})' in detail.lower())
        ok('the members of the same project are tagged', page.locator('#confirmed-members .tag').count() == len([m for m in view['confirmed'] if m['same_project']]))
        ok('the three actions are there and the consequence of each is stated', page.locator('#c-confirm').is_enabled() and page.locator('#c-exclude').is_enabled() and page.locator('#c-reset').is_disabled()
           and 'Confirm:' in page.locator('#c-consequences').inner_text() and 'Exclud:' in page.locator('#c-consequences').inner_text() and 'inventar-note.json' in page.locator('#c-consequences').inner_text())
        page.evaluate('window.scrollTo(0, 0)')
        snap('candidates-queue')
        snap('candidate-detail', '#detail')
        goto('F')
        ok('a candidate that equals an excluded one shows the refusal', 'a fost exclus înainte' in page.locator('#detail .warn').inner_text() and 'Este un cod intern.' in page.locator('#detail .warn').inner_text())
        goto('D')
        ok('a candidate of a proposed group shows why it cannot be confirmed, and Confirm is disabled',
           'este «propus»' in page.locator('#detail .warn[data-blocker]').inner_text() and page.locator('#c-confirm').is_disabled() and page.locator('#c-exclude').is_enabled())
        goto('A')
        page.locator('body').click(position={'x': 5, 'y': 5})
        page.keyboard.press('j')
        until(page, lambda: page.url.endswith(cid('B')))
        page.keyboard.press('k')
        until(page, lambda: page.url.endswith(cid('A')))
        ok('j and k move between candidates', page.url.endswith('#candidat/' + cid('A')))
        ok('no key decided a candidate', both() == (head(files['concepte']), head(files['note'])))

        # -- confirm -----------------------------------------------------------------------------------------------------------------------------
        goto('A')
        members_before = len(group('cui')['selectors'])
        decide('#c-confirm', 'Poartă CUI-ul întreprinderii.')
        status_has('confirmat')
        progress_has('Candidați: 4 deschiși')
        saved = group('cui')
        ok('confirm: the selector is the last member of its group, confirmed, with the note', len(saved['selectors']) == members_before + 1 and saved['selectors'][-1]['stare'] == 'confirmat'
           and saved['selectors'][-1]['nota_editor'] == 'Poartă CUI-ul întreprinderii.' and list(saved['selectors'][-1])[-2:] == ['stare', 'nota_editor'])
        ok('confirm: the group keeps its state and its review date', saved['stare'] == 'revizuit' and saved['data_revizie'] == '2026-10-24')
        ok('confirm: the candidate left the notes', len(items()) == 5 and items()[0]['grup'] == 'judet')
        ok('confirm: the navigation and the header count four open candidates', page.locator('#tab-candidates').inner_text() == 'Candidați (4)')
        ok('confirm: the candidate stays in the queue as confirmed, with Reset only', row_chip('A') == 'Confirmat' and page.locator('#c-reset').is_enabled()
           and page.locator('#c-confirm').is_disabled() and page.locator('#c-exclude').is_disabled())
        ok('confirm: the member is marked in the list of the confirmed members', page.locator('#confirmed-members li[data-this="1"]').count() == 1)
        ok('confirm: the message says which member it became', 'membrul' in page.locator('#c-status').inner_text())

        # -- exclude -----------------------------------------------------------------------------------------------------------------------------
        goto('B')
        before = both()
        decide('#c-exclude', '')
        until(page, lambda: page.locator('#c-status').inner_text() != '')
        ok('exclude without a note is refused and nothing is written', 'Notă' in page.locator('#c-status').inner_text() and both() == before)
        decide('#c-exclude', 'Nu poartă județul.')
        status_has('exclus')
        excluded = next(i for i in items() if i['grup'] == 'judet')
        ok('exclude: the candidate stays in the notes with its state and its note', excluded['stare'] == 'exclus' and excluded['nota_editor'] == 'Nu poartă județul.'
           and list(excluded) == ['grup', 'selector', 'stare', 'nota_editor'] and len(items()) == 5)
        ok('exclude: no member was added and the queue says so', files['concepte'].read_bytes() == before[0] and row_chip('B') == 'Exclus' and 'Nu poartă județul.' in page.locator('#detail').inner_text())
        progress_has('Candidați: 3 deschiși')

        # -- reset an excluded candidate; confirm another one while A is confirmed (the places of the working list shift) ------------------------------------
        ok('reset is offered for a changed candidate', page.locator('#c-reset').is_enabled())
        page.locator('#c-reset').click()
        status_has('a revenit')
        ok('reset: an excluded candidate is open again, as at HEAD', row_chip('B') == 'Propus' and 'stare' not in next(i for i in items() if i['grup'] == 'judet'))
        progress_has('Candidați: 4 deschiși')
        before_c = cid('C')
        goto('C')
        decide('#c-confirm')
        status_has('confirmat')
        ok('confirm without a note writes no note', 'nota_editor' not in group('localitate')['selectors'][-1] and group('localitate')['selectors'][-1]['stare'] == 'confirmat')
        ok('the place of a candidate shifts when an earlier one is confirmed, and the page follows it', cid('C') != before_c and page.url.endswith('#candidat/' + cid('C')) and row_chip('C') == 'Confirmat')

        goto('A')
        page.locator('#c-reset').click()
        status_has('a revenit')
        head_cui = next(c for c in json.loads(head(files['concepte']))['concepte'] if c['id'] == 'cui')
        ok('reset: a confirmed candidate leaves its group and returns to its place in the list', group('cui') == head_cui and row_chip('A') == 'Propus' and items()[0]['grup'] == 'cui'
           and 'stare' not in items()[0] and group('localitate')['selectors'][-1]['stare'] == 'confirmat')
        ok('reset: the candidate is back in the list in its place (the places are those of the notes)', rows() == ['#1', '#2', '#3', '#5'] and page.locator('#c-reset').is_disabled())
        progress_has('Candidați: 4 deschiși')

        # -- D excluded: the error goes ------------------------------------------------------------------------------------------------------------------
        goto('D')
        decide('#c-exclude', 'Grupul nu este revizuit.')
        status_has('exclus')
        until(page, lambda: page.locator('#validation').inner_text() == 'Validare: fără erori')
        ok('excluding the candidate of a proposed group clears the validation error', page.locator('#validation').inner_text() == 'Validare: fără erori')
        page.reload()
        until(page, lambda: page.locator('#detail [data-candidate]').count() == 1)
        goto('C')
        ok('a confirmed candidate survives a reload (it is read from HEAD and the group)', row_chip('C') == 'Confirmat' and page.locator('#c-reset').is_enabled())

        # -- the check panel ---------------------------------------------------------------------------------------------------------------------
        page.locator('#tab-checks').click()
        page.wait_for_selector('#candidate-counts')
        ok('the check panel counts the open candidates', page.locator('#candidate-counts').inner_text() == 'Candidați deschiși: 3. Excluși: 2. Confirmați după HEAD: 1.')
        page.wait_for_selector('#git-panel h3:text-is("Consecința publică")')
        ok('a candidate does not change the public build', 'Nicio schimbare a surselor de date acceptate' in page.locator('#git-panel').inner_text())
        ok('the check panel lists the notes file and suggests committing it', 'inventar-note.json' in page.locator('#git-panel').inner_text() and 'inventar-note.json' in page.locator('#commands').inner_text())
        snap('candidates-checks')

        # -- everything back to HEAD -------------------------------------------------------------------------------------------------------------------
        goto('C')
        page.locator('#c-reset').click()
        status_has('a revenit')
        goto('D')
        page.locator('#c-reset').click()
        until(page, lambda: page.locator('#c-status').inner_text() != '')
        ok('reset: a candidate whose HEAD version is an error stays excluded (the write would bring the error back)', 'nu s-a scris nimic' in page.locator('#c-status').inner_text()
           and next(i for i in items() if i['grup'] == 'siruta')['stare'] == 'exclus')
        head_items = json.loads(head(files['note']))['selectori_candidati']
        ok('reset: the dictionary is the file of HEAD again, and the notes differ from HEAD by the one excluded candidate of the proposed group',
           files['concepte'].read_bytes() == head(files['concepte']) and [i for i in items() if i['grup'] != 'siruta'] == [i for i in head_items if i['grup'] != 'siruta'])

        # -- a stale file ------------------------------------------------------------------------------------------------------------------------
        goto('F')
        notes = json.loads(files['note'].read_text())
        notes['editat'] = 'de mână'
        write_like(files['note'], notes)
        before = both()
        decide('#c-exclude', 'Încerc după o editare externă.')
        page.wait_for_selector('#banner:not([hidden])')
        ok('a file edited since the page loaded refuses the decision and offers a reload', 'Reîncărcați' in page.locator('#banner').inner_text() and 'Reîncarcă' in page.locator('#banner button').inner_text() and both() == before)
        page.locator('#banner button').click()
        page.wait_for_selector('#banner[hidden]', state='attached')
        notes.pop('editat')
        write_like(files['note'], notes)

        # -- layout, requests, errors --------------------------------------------------------------------------------------------------------------
        page.reload()
        for width in (1280, 390):
            page.set_viewport_size({'width': width, 'height': 900})
            for label, wanted in (('queue', '#candidati'), ('candidate', '#candidat/' + cid('A')), ('candidate of a proposed group', '#candidat/' + cid('F'))):
                page.evaluate(f'location.hash="{wanted}"')
                page.wait_for_timeout(600)
                if label != 'queue':
                    page.wait_for_selector('#detail [data-candidate]')
                ok(f'{width}px: the {label} view fits the viewport (no horizontal scroll)', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        goto('A')
        snap('candidates-mobile')
        ok('the candidate pages made no request outside the local server', outside == [])
        refused = [e for e in problems if re.fullmatch(r'Failed to load resource: the server responded with a status of (400|409|422) \(.*\)', e)]
        ok('the only console errors are the three refused requests that this check provokes (a missing note, a reset that brings an error back, a stale file)', len(refused) == 3)
        ok('no other browser error on the candidate pages', [e for e in problems if e not in refused] == [])
        browser.close()


if __name__ == '__main__':
    main()
