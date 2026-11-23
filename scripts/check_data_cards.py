# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Browser checks of the data-set card (docs/briefs/data-set-card-build.md, part D and E).

The real `integrare/fise-date.csv` has no row, so this script builds its own preview: a temporary package with two fixture cards (scripts/data_cards_fixture.py),
an isolated build with the inventory, and a local server. It makes no request outside localhost.

    uv run scripts/check_data_cards.py [folder for screenshots]
"""
import functools
import http.server
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
import data_cards_fixture as fx  # noqa: E402

SHOTS = sys.argv[1] if len(sys.argv) > 1 else ''
results, errors = [], []


def ok(label, condition):
    results.append(bool(condition))
    print(('PASS ' if condition else 'FAIL ') + label)


def build(tmp):
    root = fx.make_root(tmp)
    site = tmp / 'site'
    done = subprocess.run([sys.executable, str(SCRIPTS / 'build.py'), '--data-dir', str(root), '--site-dir', str(site), '--with-inventory'], capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(done.stdout + done.stderr)
    return site


def serve(site):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(Quiet, directory=str(site))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_address[1]}/'


def no_sideways_scroll(page):
    return page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')


def cards_text(page):
    return page.locator('.ds-card').evaluate_all('els => els.map(e => e.textContent.replace(/\\s+/g, " ").trim())')


with tempfile.TemporaryDirectory(prefix='cards-check-') as tmp:
    site = build(Path(tmp))
    server, BASE = serve(site)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # The entry page without JavaScript: the static form.
        plain = browser.new_context(java_script_enabled=False, viewport={'width': 1280, 'height': 1000})
        page = plain.new_page()
        page.goto(BASE + 'proiect/sicap-ai/')
        static_text = cards_text(page)
        ok('no JavaScript: the entry page has one card, with the set as a heading', page.locator('.d-inventory .ds-card').count() == 1 and page.locator('.ds-card h4').inner_text() == 'Achiziții directe din SEAP')
        card = page.locator('.ds-card').inner_text()
        ok('no JavaScript: the card says provider, record, undeclared period and access', all(x in card for x in ('furnizor: SEAP (e-licitatie)', 'o înregistrare: o achiziție directă', 'perioada: nedeclarată', 'acces: web, API (cheie)')))
        ok('no JavaScript: the card names the identifiers with their role and the key variable', 'CUI (autoritate contractantă) · CUI (furnizor) · cod CPV (obiect)' in card and 'Variabile principale: Cod CPV' in card)
        ok('no JavaScript: the provider links to its anchor on the provider view', page.locator('.ds-card a[href="date/furnizori/#f-seap-sicap"]').count() == 1)
        tech = page.locator('.inv-tech a')
        ok('no JavaScript: the link "Vedere tehnică" leads to the data page and comes after the cards',
           tech.count() == 1 and tech.get_attribute('href') == 'date/sicap-ai/' and tech.inner_text().startswith('Vedere tehnică: 1263 de câmpuri din 6 documente')
           and page.evaluate("document.querySelector('.ds-cards').compareDocumentPosition(document.querySelector('.inv-tech')) & Node.DOCUMENT_POSITION_FOLLOWING") != 0)
        ok('no JavaScript: the count and the examples stay under the link', page.locator('.d-inventory .inv-examples code').count() == 5 and page.locator('.d-inventory .inv-all a:has-text("Toate variabilele")').count() == 0)
        page.goto(BASE + 'proiect/textdelege/')
        ok('no JavaScript: an entry with a card and no inventory shows the card and no technical link', page.locator('.ds-card').count() == 1 and page.locator('.inv-tech').count() == 0
           and 'perioada: 1990–' in page.locator('.ds-card').inner_text() and 'Metodă: Textul vine' in page.locator('.ds-card').inner_text())
        page.goto(BASE + 'proiect/harta-firmelor/')
        ok('no JavaScript: an entry without a card keeps its panel', page.locator('.ds-card').count() == 0 and page.locator('.d-inventory .inv-all a:has-text("Toate variabilele")').count() == 1)
        plain.close()

        # The entry page with JavaScript: the same card.
        page = browser.new_page(viewport={'width': 1280, 'height': 1000})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(BASE + 'proiect/sicap-ai/')
        page.wait_for_selector('#inventory-title')
        ok('JavaScript: the card has the same text as the static card', cards_text(page) == static_text and len(static_text) == 1)
        ok('JavaScript: the provider link keeps its target', page.locator('.ds-card a[href$="date/furnizori/#f-seap-sicap"]').count() == 1)
        ok('JavaScript: the cards come first and the examples and the field explorer stay below the link',
           page.evaluate("""() => { const q = s => document.querySelector(s), after = (a, b) => (q(a).compareDocumentPosition(q(b)) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
              return after('.ds-cards', '.inv-tech') && after('.inv-tech', '.inv-examples') && after('.inv-examples', '.inv-details'); }"""))
        ok('JavaScript: "Toate variabilele" is replaced by "Vedere tehnică"', page.locator('.inv-all a:has-text("Toate variabilele")').count() == 0 and page.locator('.inv-tech a').count() == 1)
        page.locator('.inv-tech a').click()
        page.wait_for_selector('#seturi-de-date')
        ok('the link "Vedere tehnică" opens the data page of the entry', page.url.endswith('/date/sicap-ai/'))
        page.goto(BASE + 'proiect/textdelege/')
        page.wait_for_selector('#inventory-title')
        ok('JavaScript: an entry with a card and no inventory shows the card and no technical link', page.locator('.ds-card').count() == 1 and page.locator('.inv-tech').count() == 0)
        page.goto(BASE + 'proiect/harta-firmelor/')
        page.wait_for_selector('#inventory-title')
        ok('JavaScript: an entry without a card has no card', page.locator('.ds-card').count() == 0 and page.locator('.inv-all a:has-text("Toate variabilele")').count() == 1)

        # The data page: the order of the parts.
        page.goto(BASE + 'date/sicap-ai/')
        ids = page.evaluate("""() => ['seturi-de-date', 'vedere-tehnica', 'pe-familii', 'pe-surse'].map(id => document.getElementById(id)?.getBoundingClientRect().top ?? -1)""")
        ok('data page: "Seturi de date", then "Vedere tehnică", with "Pe familii" and "Pe surse" below it', all(t >= 0 for t in ids) and ids == sorted(ids))
        ok('data page: "Pe familii" and "Pe surse" sit under "Vedere tehnică"', page.locator('#vedere-tehnica #pe-familii').count() == 1 and page.locator('#vedere-tehnica #pe-surse').count() == 1)
        ok('data page: the same card, with the sentence of the spec', page.locator('#seturi-de-date .ds-card').count() == 1 and cards_text(page)[0] == static_text[0]
           and 'Câmpurile sunt extrase automat din documentele citite. Ele arată ce se poate extrage, nu ce contează.' in page.locator('#vedere-tehnica').inner_text())
        ok('data page: the headings keep their order', page.evaluate("""() => { const l = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => +h.tagName[1]); return l.every((n, i) => !i || n - l[i - 1] <= 1); }"""))
        page.goto(BASE + 'date/harta-firmelor/')
        ok('data page: an entry without a card keeps „Pe familii” and „Pe surse” as sections of the page', page.locator('.ds-card, #vedere-tehnica, #seturi-de-date').count() == 0 and page.locator('#pe-familii > h2').count() == 1)

        # The finder.
        page.goto(BASE + 'date/')
        page.wait_for_selector('.finder-card')
        page.locator('#data-search').fill('Achiziții directe din SEAP')
        page.wait_for_selector('.finder-card[data-project="sicap-ai"]')
        line = page.locator('.finder-card[data-project="sicap-ai"] .finder-sets li')
        ok('finder: a result with a card shows one line for the card', line.count() == 1)
        text = line.inner_text()
        ok('finder: the line names the set, the provider, the access and the identifiers', all(x in text for x in ('Achiziții directe din SEAP', 'SEAP (e-licitatie)', 'web, API (cheie)', 'CUI (autoritate contractantă), CUI (furnizor), cod CPV (obiect)')))
        ok('finder: the line comes above the field examples', page.evaluate("""() => { const c = document.querySelector('.finder-card[data-project="sicap-ai"]'); return (c.querySelector('.finder-sets').compareDocumentPosition(c.querySelector('dl')) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0; }"""))
        page.locator('#data-search').fill('')
        page.goto(BASE + 'date/?q=harta')
        page.wait_for_selector('.finder-card')
        ok('finder: a result without a card has no line', page.locator('.finder-card .finder-sets').count() == 0 or page.locator('.finder-card[data-project="harta-firmelor"] .finder-sets').count() == 0)
        page.close()

        # A narrow screen: no sideways scroll.
        phone = browser.new_context(viewport={'width': 375, 'height': 800})
        page = phone.new_page()
        for path, wait in (('proiect/sicap-ai/', '#inventory-title'), ('proiect/textdelege/', '#inventory-title'), ('date/sicap-ai/', '#seturi-de-date'), ('date/?q=SEAP', '.finder-card')):
            page.goto(BASE + path)
            page.wait_for_selector(wait)
            ok(f'375 px: no sideways scroll on {path}', no_sideways_scroll(page))
            if SHOTS:
                page.screenshot(path=str(Path(SHOTS) / (path.strip('/').replace('/', '-').replace('?q=', '-') + '-375.png')), full_page=True)
        phone.close()
        browser.close()
    server.shutdown()

ok('no browser errors', not errors)
print(f'{sum(results)}/{len(results)} checks passed')
raise SystemExit(0 if all(results) else 1)
