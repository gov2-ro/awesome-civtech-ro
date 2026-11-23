"""Offline tests of the data-set card (docs/specs/data-set-card.md, docs/briefs/data-set-card-build.md).

The real `integrare/fise-date.csv` has a header only. Every test that needs a card uses a temporary package (`data_cards_fixture.make_root`): links to the real
files and a copy of `integrare/`. No test writes into the real data root; `tearDownModule` proves it.
"""
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import common
import data_cards
import data_cards_fixture as fx
import entry_page
import taxonomy_v2
from common import CARD_COLS
from data_cards_fixture import card

SCRIPTS = Path(__file__).parent
REAL_FILE = common.PUBLIC_ROOT / common.CARDS_FILE
REAL_BEFORE = None
TMP = None
CONTEXT = None
TODAY = date(2026, 11, 23)


def setUpModule():
    global REAL_BEFORE, TMP, CONTEXT
    REAL_BEFORE = REAL_FILE.read_bytes()
    TMP = Path(tempfile.mkdtemp(prefix='cards-test-'))
    CONTEXT = data_cards.card_context(fx.make_root(TMP / 'context'))


def tearDownModule():
    shutil.rmtree(TMP, True)
    assert REAL_FILE.read_bytes() == REAL_BEFORE, 'a test changed the real fise-date.csv'


def run(*args):
    done = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=SCRIPTS.parent)
    return done.returncode, done.stdout + done.stderr


def problems(*rows, today=TODAY):
    """(errors, warnings) of `card_problems` for rows made from the fixture card S001 (a good card) with the given changes."""
    errors, warnings = data_cards.card_problems(list(rows), CONTEXT, today)
    return [m for _, m in errors], [m for _, m in warnings]


def good(**changes):
    return {**fx.SICAP, **changes}


class RealFile(unittest.TestCase):
    def test_the_real_file_has_the_header_and_only_proposed_or_accepted_rows(self):
        self.assertEqual(REAL_FILE.read_text(encoding='utf-8').split('\n', 1)[0], ','.join(CARD_COLS))
        self.assertTrue(all(r['stare'] in ('propus', 'acceptat') for r in common.load_cards()))

    def test_the_header_is_declared_in_the_package_and_in_the_constants(self):
        pachet = json.loads((common.PUBLIC_ROOT / 'pachet.json').read_text(encoding='utf-8'))
        self.assertEqual(pachet['headers'][common.CARDS_FILE], CARD_COLS)
        self.assertIn(common.CARDS_FILE, pachet['local_files'])

    def test_the_three_code_lists(self):
        codes = taxonomy_v2.load(common.PUBLIC_ROOT).codes
        self.assertEqual(set(codes['acces_set']), {'web', 'fisier', 'api', 'api-cheie', 'la-cerere'})
        self.assertEqual(set(codes['rol_identificator']),
                         {'autoritate-contractanta', 'furnizor', 'firma', 'institutie', 'uat', 'obiect', 'contribuabil', 'creditor'})
        grains = {c['record_grain'] for p in (common.PUBLIC_ROOT.parent / 'structura/recipes').glob('*.json')
                  for c in json.loads(p.read_text(encoding='utf-8')).get('collections', [])} - {'unknown', None}
        self.assertEqual(len(codes['granularitate_set']), len(grains), 'one code for each record_grain value of the recipes: add the new value to valori.csv')
        for lst in ('acces_set', 'rol_identificator', 'granularitate_set'):
            self.assertTrue(all(r['statut'] == 'propus' and r['eticheta_ro'] and r['definitie_ro'] for r in codes[lst].values()), lst)

    def test_the_real_root_passes_validation_with_no_card_error(self):
        code, out = run('scripts/validate.py', '--publication')
        self.assertEqual(code, 0, out)
        self.assertIn('0 erori', out)


class Checks(unittest.TestCase):
    """One test for each error and each warning of spec section 8."""

    def assertError(self, text, *rows):
        errors, _ = problems(*rows)
        self.assertTrue(any(text in m for m in errors), (text, errors))

    def assertWarning(self, text, *rows):
        errors, warnings = problems(*rows)
        self.assertTrue(any(text in m for m in warnings), (text, warnings))
        self.assertEqual(errors, [])

    def test_the_fixture_cards_are_clean(self):
        errors, warnings = problems(fx.SICAP, fx.NO_FIELDS)
        self.assertEqual((errors, warnings), ([], []))

    def test_the_id_is_invalid_or_repeated(self):
        self.assertError('id invalid', good(id='X1'))
        self.assertError('id duplicat', good(), good(set='Alt set'))

    def test_the_slug_is_unknown(self):
        self.assertError('slug necunoscut', good(slug='nu-exista'))

    def test_the_entry_is_out_of_the_inventory_scope(self):
        organisation = next(s for s, reason in CONTEXT['scope'].items() if reason)
        self.assertError('în afara ariei inventarului', good(slug=organisation))

    def test_the_set_is_missing(self):
        self.assertError('lipsește set', good(set=''))

    def test_the_provider_is_missing_or_not_accepted(self):
        self.assertError('lipsește furnizor', good(furnizor=''))
        self.assertError('nu este un furnizor acceptat', good(furnizor='nu-exista'))
        self.assertEqual(problems(good(furnizor='autor'))[0], [])

    def test_a_code_is_outside_its_list(self):
        self.assertError('granularitate necunoscută', good(granularitate='nu-exista'))
        self.assertError('cod de acces necunoscut', good(acces='web|nu-exista', url_acces=''))
        self.assertError('cod de identificator necunoscut', good(identificatori='isbn:obiect'))
        self.assertError('rol necunoscut', good(identificatori='cui:nu-exista'))
        self.assertError('rol necunoscut sau lipsă', good(identificatori='cui'))
        self.assertError('baza necunoscută', good(baza='ghicit'))
        self.assertError('stare necunoscută', good(stare='gata'))

    def test_the_access_and_its_addresses_differ_in_length(self):
        self.assertError('url_acces are 1 elemente, acces are 2', good(url_acces='https://api.sicap.ai/'))
        self.assertEqual(problems(good(url_acces=''))[0], [])  # an empty cell: no address for any code

    def test_an_address_is_no_url(self):
        self.assertError('adresă invalidă', good(url_acces='|nu-este-adresa'))
        self.assertError('adresă invalidă', good(dovada='nu-este-adresa'))

    def test_a_local_identifier_needs_a_namespace_of_the_recipe(self):
        self.assertEqual(problems(good(identificatori='local:sicap-ai:contracts:id'))[0], [])
        self.assertError('spațiul de nume nu este în rețeta', good(identificatori='local:sicap-ai:nu-exista'))
        no_recipe = next(s for s in sorted(CONTEXT['slugs']) if s not in CONTEXT['recipes'] and not CONTEXT['scope'].get(s) and CONTEXT['fields'].get(s))
        self.assertError('intrarea nu are rețetă de structură', good(slug=no_recipe, furnizor='autor', variabile_cheie='', identificatori='local:x'))

    def test_the_key_variables(self):
        self.assertError('cel mult 6', good(variabile_cheie='|'.join(f'g{n}' for n in range(7))))
        self.assertError('nu este un grup din inventar-concepte.json', good(variabile_cheie='nu-exista'))
        self.assertError('niciun câmp al intrării nu se potrivește', good(slug='textdelege', furnizor='portal-legislativ', variabile_cheie='cpv'))
        field = CONTEXT['fields']['sicap-ai'][0]
        self.assertEqual(problems(good(variabile_cheie=f'{field["source"]}#{field["path"]}'))[0], [])
        self.assertError('nu este un câmp al intrării în campuri.csv', good(variabile_cheie=f'{field["source"]}#nu-exista'))

    def test_an_accepted_card_needs_its_record_evidence_and_date(self):
        self.assertError('nevoie de inregistrare', good(inregistrare=''))
        self.assertError('nevoie de dovada', good(dovada=''))
        self.assertError('nevoie de verificat_la', good(verificat_la=''))
        self.assertEqual(problems(good(stare='propus', inregistrare='', dovada='', verificat_la='', baza=''))[0], [])  # a proposal may be incomplete

    def test_the_date_is_no_iso_date(self):
        self.assertError('nu este o dată ISO', good(verificat_la='20.11.2026'))

    def test_no_relation_to_the_provider(self):
        self.assertWarning('nicio relație date_din', good(furnizor='anaf'))

    def test_only_a_proposed_relation_to_the_provider(self):
        names = {n: p for p, ns in CONTEXT['providers'].items() for n in ns}
        found = next(((s, names[n]) for s, rels in sorted(CONTEXT['relations'].items()) for n, st in rels
                      if n in names and st == 'propus' and not any(m in CONTEXT['providers'][names[n]] and t == 'acceptat' for m, t in rels)
                      and s in CONTEXT['slugs'] and not CONTEXT['scope'].get(s)), None)
        if not found:
            self.skipTest('no entry with only a proposed date_din relation')
        self.assertWarning('doar propusă', good(slug=found[0], furnizor=found[1], variabile_cheie='', identificatori=''))

    def test_a_derived_variable_needs_a_method_note(self):
        derived = next(g for g, c in CONTEXT['concepts'].items() if c.get('categorie') == data_cards.DERIVED)
        slug = next((s for s in sorted(CONTEXT['slugs']) if not CONTEXT['scope'].get(s) and data_cards.group_matches(s, derived, CONTEXT)), None)
        if not slug:
            self.skipTest('no entry reaches a derived group')
        row = good(slug=slug, furnizor='autor', variabile_cheie=derived, identificatori='')
        self.assertWarning('nota_metoda', row)
        self.assertEqual(problems({**row, 'nota_metoda': 'Se calculează din bilanț.'}), ([], []))

    def test_the_check_is_stale_after_a_year(self):
        self.assertWarning('mai vechi de 365', good(verificat_la='2025-11-01'))
        self.assertEqual(problems(good(verificat_la='2025-11-23'))[1], [])

    def test_a_long_set_and_a_free_period(self):
        self.assertWarning('caractere', good(set='x' * 81))
        self.assertWarning('perioada', good(perioada='anii 2000'))
        for period in ('2007–2025', '2019–', '2020', ''):
            self.assertEqual(problems(good(perioada=period)), ([], []), period)


class ValidateScript(unittest.TestCase):
    """validate.py on a temporary package: the exit code and the messages."""

    def validate(self, cards, *flags):
        root = fx.make_root(Path(tempfile.mkdtemp(dir=TMP)), cards)
        return run('scripts/validate.py', '--data-dir', root, *flags)

    def test_the_fixture_cards_pass_the_publication_gate(self):
        code, out = self.validate(fx.FIXTURE, '--publication')
        self.assertEqual(code, 0, out)

    def test_an_error_fails_the_publication_gate_and_names_the_line(self):
        code, out = self.validate([fx.SICAP, {**fx.NO_FIELDS, 'furnizor': 'nu-exista'}], '--publication')
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r'fise-date\.csv:3: error: S002: furnizor')

    def test_a_missing_or_unknown_column_is_an_error(self):
        root = fx.make_root(Path(tempfile.mkdtemp(dir=TMP)), [])
        path = root / common.CARDS_FILE
        path.write_text(','.join(CARD_COLS[:-1] + ['colectie']) + '\n', encoding='utf-8')
        code, out = run('scripts/validate.py', '--data-dir', root)
        self.assertEqual(code, 1, out)
        self.assertIn('fise-date.csv: header differs', out)


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposed = card(id='S003', slug='sicap-ai', set='Un set propus', furnizor='seap-sicap', stare='propus', nota='nu apare')
        cls.root = fx.make_root(Path(tempfile.mkdtemp(dir=TMP)), [fx.SICAP, cls.proposed, fx.NO_FIELDS])
        cls.site = cls.root.parent.parent / 'site'
        code, out = run('scripts/build.py', '--data-dir', cls.root, '--site-dir', cls.site, '--with-inventory')
        assert code == 0, out
        cls.data = json.loads((cls.site / 'data.json').read_text(encoding='utf-8'))
        cls.items = {i['slug']: i for i in cls.data['items']}

    def test_datasets_hold_the_accepted_cards_only(self):
        sets = self.items['sicap-ai']['datasets']
        self.assertEqual([c['id'] for c in sets], ['S001'])
        self.assertNotIn('nota', json.dumps(self.items['sicap-ai']['datasets']))
        self.assertNotIn('nu apare', json.dumps(self.data))

    def test_an_entry_without_a_card_has_an_empty_list(self):
        others = [i for s, i in self.items.items() if s not in ('sicap-ai', 'textdelege')]
        self.assertTrue(others and all(i['datasets'] == [] for i in others))

    def test_a_card_resolves_its_codes(self):
        c = self.items['sicap-ai']['datasets'][0]
        self.assertEqual(c['provider'], {'id': 'seap-sicap', 'name': 'SEAP (e-licitatie)', 'anchor': 'f-seap-sicap'})
        self.assertEqual(c['grain'], {'code': 'achizitie-directa', 'label': 'Achiziție directă'})
        self.assertEqual([(a['code'], a['label'], a['url']) for a in c['access']], [('web', 'web', ''), ('api-cheie', 'API (cheie)', 'https://api.sicap.ai/v1/openapi')])
        self.assertEqual([(x['code'], x['role'], x['roleLabel']) for x in c['identifiers']],
                         [('cui', 'autoritate-contractanta', 'autoritate contractantă'), ('cui', 'furnizor', 'furnizor'), ('cpv', 'obiect', 'obiect')])
        self.assertEqual(c['keyVariables'], [{'id': 'cpv', 'label': 'Cod CPV'}])
        self.assertEqual((c['period'], c['basis'], c['checked']), ('', 'observat', '2026-11-20'))
        self.assertEqual(self.items['textdelege']['datasets'][0]['period'], '1990–')

    def test_the_finder_index_names_the_cards(self):
        index = json.loads((self.site / 'inventar/index.json').read_text(encoding='utf-8'))
        entries = {e['slug']: e for e in index['entries']}
        line = entries['sicap-ai']['datasets'][0]
        self.assertEqual(line['set'], 'Achiziții directe din SEAP')
        self.assertEqual([a['code'] for a in line['access']], ['web', 'api-cheie'])
        self.assertEqual(len(line['identifiers']), 3)
        self.assertTrue(all('datasets' not in e for s, e in entries.items() if s != 'sicap-ai' and s != 'textdelege'))

    def test_the_entry_page_has_the_cards_before_the_technical_link(self):
        page = (self.site / 'proiect/sicap-ai/index.html').read_text(encoding='utf-8')
        panel = page[page.index('class="d-inventory"'):]
        panel = panel[:panel.index('</section>')]
        self.assertLess(panel.index('class="ds-card"'), panel.index('Vedere tehnică: 1263 de câmpuri din 6 documente'))
        self.assertLess(panel.index('Vedere tehnică'), panel.index('class="inv-examples"'))
        self.assertIn('perioada: nedeclarată', panel)
        self.assertIn('href="date/furnizori/#f-seap-sicap"', panel)
        self.assertNotIn('Toate variabilele', panel)

    def test_an_entry_with_a_card_and_no_inventory_shows_the_cards_only(self):
        page = (self.site / 'proiect/textdelege/index.html').read_text(encoding='utf-8')
        panel = page[page.index('class="d-inventory"'):]
        panel = panel[:panel.index('</section>')]
        self.assertIn('class="ds-card"', panel)
        self.assertNotIn('Vedere tehnică', panel)
        self.assertIn('perioada: 1990–', panel)
        self.assertIn('Metodă: Textul vine', panel)

    def test_the_data_page_has_the_cards_then_the_technical_view(self):
        page = (self.site / 'date/sicap-ai/index.html').read_text(encoding='utf-8')
        order = [page.index(f'id="{x}"') for x in ('seturi-de-date', 'vedere-tehnica', 'pe-familii', 'pe-surse')]
        self.assertEqual(order, sorted(order))
        self.assertIn('Câmpurile sunt extrase automat din documentele citite. Ele arată ce se poate extrage, nu ce contează.', page)
        self.assertEqual(page.count('class="ds-card"'), 1)
        levels = [int(n) for n in re.findall(r'<h([1-6])[ >]', page)]
        self.assertTrue(all(b - a <= 1 for a, b in zip(levels, levels[1:])), levels)  # no heading skips a level
        self.assertEqual(page.count('<h2'), 2)  # „Seturi de date” and „Vedere tehnică”

    def test_the_data_page_without_a_card_is_the_page_of_the_public_build(self):
        plain = self.site / 'date/harta-firmelor/index.html'
        self.assertTrue(plain.exists())
        text = plain.read_text(encoding='utf-8')
        self.assertNotIn('vedere-tehnica', text)
        self.assertNotIn('ds-card', text)
        self.assertIn('<h2>Pe familii</h2>', text)
        self.assertIn('<h2>Pe surse</h2>', text)

    def test_the_card_html_is_the_same_on_both_pages(self):
        entry = (self.site / 'proiect/sicap-ai/index.html').read_text(encoding='utf-8')
        data = (self.site / 'date/sicap-ai/index.html').read_text(encoding='utf-8')
        take = lambda page: re.search(r'<article class="ds-card".*?</article>', page, re.S).group(0)
        self.assertEqual(re.sub(r'<h[34]>(.*?)</h[34]>', r'<h>\1</h>', take(entry)), re.sub(r'<h[34]>(.*?)</h[34]>', r'<h>\1</h>', take(data)))


def legacy_data_summary(i):
    """`entry_page.data_summary` as it was before the cards (v0.85.0), kept here to prove that an entry without a card has the same panel."""
    esc = entry_page.esc
    inv = i.get('inventory')
    if not inv or not inv.get('count'):
        return ''
    examples = ''.join(f'<span><code>{esc(e)}</code></span>' for e in (inv.get('examples') or []))
    page = f'<p class="inv-all"><a href="{esc(inv["page"])}">Toate variabilele <span aria-hidden="true">→</span></a></p>' if inv.get('page') else ''
    return (f'<section class="d-inventory" data-inventory-root="{esc(i["slug"])}"><div class="inv-heading"><h3>Date &amp; metodă</h3><span class="inv-status">Inventar parțial</span></div>'
            f'<p class="inv-intro">{inv["count"]} câmpuri și parametri · {inv["sources"]} fișiere consultate</p>'
            f'<p class="inv-note">Extrase automat din sursele de mai jos. Proiectul poate folosi și alte date.</p><div class="inv-examples">{examples}</div>{page}</section>')


class NoCardChangesNothing(unittest.TestCase):
    """The public build, on the current data: no entry has a card, so every panel and every list must be as before."""

    @classmethod
    def setUpClass(cls):
        cls.site = Path(tempfile.mkdtemp(dir=TMP)) / 'site'
        code, out = run('scripts/build.py', '--site-dir', cls.site, '--with-inventory')
        assert code == 0, out
        cls.data = json.loads((cls.site / 'data.json').read_text(encoding='utf-8'))

    def test_no_entry_has_a_card(self):
        self.assertTrue(all(i['datasets'] == [] for i in self.data['items']))

    def test_the_panel_of_every_entry_is_the_old_panel(self):
        self.assertGreater(sum(bool(i.get('inventory', {}).get('count')) for i in self.data['items']), 50)
        for item in self.data['items']:
            self.assertEqual(entry_page.data_summary(item), legacy_data_summary(item), item['slug'])

    def test_no_entry_page_names_a_card(self):
        for page in list(self.site.glob('proiect/*/index.html')) + list((self.site / 'date').glob('*/index.html')):
            text = page.read_text(encoding='utf-8')
            self.assertNotIn('ds-card', text, page)
            self.assertNotIn('vedere-tehnica', text, page)

    def test_the_index_has_no_datasets_key(self):
        index = json.loads((self.site / 'inventar/index.json').read_text(encoding='utf-8'))
        self.assertTrue(all('datasets' not in e for e in index['entries']))


if __name__ == '__main__':
    unittest.main()
