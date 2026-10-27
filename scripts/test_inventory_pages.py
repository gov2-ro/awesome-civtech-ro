"""Offline checks for the variables page of an entry (`/date/<slug>/`) and for the data set facts that a source declares.

The fixtures build their own inventory, concepts and items. The one test that reads the tracked inventory compares each page with its own `inventar/<slug>.json`:
no test here pins the number of entries with a page, the number of fields of an entry or a review state that the owner edits.
"""
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit

from inventory_site import (FIELD_BASIS_LABELS, GROUP_STATE_LABELS, ROLE_LABELS, TYPE_LABELS, clip, family_columns, field_groups, group_hits, has_page,
                            publish_finder, publish_preview, publish_variable_pages, type_label, variable_matches)

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = [{'id': 'ids', 'label': 'Identificatori'}, {'id': 'timp', 'label': 'Timp'}, {'id': 'geo', 'label': 'Geografie'}]
CONCEPTS = [
    {'id': 'cui', 'label': 'CUI', 'familie': 'ids', 'definition': 'd', 'stare': 'revizuit', 'selectors': [{'projects': ['p'], 'names': ['cui', 'cui_firma']}]},
    {'id': 'cod', 'label': 'Cod', 'familie': 'ids', 'definition': 'd', 'selectors': [{'projects': ['p'], 'names': ['cui']}]},
    {'id': 'an', 'label': 'An <b>', 'familie': 'timp', 'definition': 'd', 'selectors': [{'projects': ['p'], 'names': ['year']}]},
    {'id': 'gone', 'label': 'Gone', 'familie': 'ids', 'definition': 'd', 'stare': 'respins', 'selectors': [{'projects': ['p'], 'names': ['total']}]},
]


def built(slug, **fields):
    return {'slug': slug, 'name': slug, 'kind': 'proiect', 'status': 'activ', 'dataRelation': 'date-publice', **fields}


def record(name, path=None, **more):
    return {'nume': name, 'cale': path or '$.' + name, 'rol': 'camp-raspuns', 'stare_tip': 'declarat-in-schema', 'pointer': '/p/' + name, 'tip_declarat': 'string', **more}


def site_of(tmp, sources, profiles, items, concepts=CONCEPTS, families=FAMILIES, vocabulary=None):
    """Write an inventory fixture, publish the preview and the finder, and return the site folder."""
    base = Path(tmp)
    root = base / 'integrare'
    inv = base / 'observatii' / 'inventare'
    inv.mkdir(parents=True)
    (base / 'observatii' / 'documentare').mkdir()
    (base / 'observatii' / 'documentare/index.json').write_text(json.dumps({'entries': []}))
    (base / 'inventar-concepte.json').write_text(json.dumps({'concepte': concepts, 'familii': families}))
    (inv / 'proiecte.json').write_text(json.dumps({'proiecte': profiles}))
    (inv / 'seturi-date.json').write_text(json.dumps({'surse': sources}))
    site = base / 'site'
    (site / 'inventar').mkdir(parents=True)
    for name in ('style.css', 'inventory.css', 'inventory.js'):
        (site / name).write_text('/* fixture */')
    with patch('inventory_site.observation_paths', return_value={'profile': base / 'observatii/profil.csv'}):
        projections = publish_preview(items, root, site)
    publish_finder(items, root, site, projections, vocabulary or {'concepts': [], 'dataRelations': [{'key': 'date-publice', 'label': 'Date publice'}]})
    return site, projections


def site_fixture(tmp, concepts):
    """The standard fixture with other concepts: the site folder only."""
    (site, _), _ = fixture(tmp, concepts=concepts)
    return site


def fixture(tmp, **extra):
    sources = [{'id': 's1', 'url': 'https://example.org/api/openapi.json', 'format': 'openapi', 'fetched_at': '2026-10-24T10:00:00+00:00',
                'campuri': [record('cui'), record('cui_firma', '$.firma.cui_firma', descriere='Codul <unic>', unitate='cifre'), record('year', tip_declarat=None, tipuri_observate=['integer']),
                            record('total'), record('q', 'q', rol='parametru-api', loc='query')]},
               {'id': 's2', 'url': 'https://example.org/lista.csv', 'format': 'csv', 'checked': 'x', 'fetched_at': '2026-10-25T10:00:00+00:00',
                'campuri': [record('cui', 'cui', rol='camp-date', stare_tip='neprecizat-in-antet-csv', tip_declarat=None), record('altceva', 'altceva', rol='camp-date', stare_tip='neprecizat-in-antet-csv', tip_declarat=None)]}]
    profiles = [{'slug': 'p', 'surse_structurate': ['s1', 's2']}, {'slug': 'bare', 'surse_structurate': []}]
    items = [built('p', name='Proiect <P> & co'), built('bare'), built('gone', status='offline'), built('nodata', dataRelation='fara-date'),
             built('org', kind='organizatie', dataRelation='')]
    return site_of(tmp, extra.get('sources', sources), extra.get('profiles', profiles), extra.get('items', items), concepts=extra.get('concepts', CONCEPTS)), items


class Parser(HTMLParser):
    """The links and the text of a page."""

    def __init__(self):
        super().__init__()
        self.links, self.text = [], []

    def handle_starttag(self, tag, attrs):
        self.links += [(tag, name, value) for name, value in attrs if name in ('href', 'src') and value is not None]

    def handle_data(self, data):
        self.text.append(data)


def parse(page):
    parser = Parser()
    parser.feed(page)
    return parser


def text_of(page):
    return ' '.join(' '.join(parse(page).text).split())


class Pages(unittest.TestCase):
    def test_an_entry_in_scope_with_fields_gets_a_page_and_no_other_entry_does(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, projections), items = fixture(tmp)
            self.assertEqual(sorted(p.name for p in (site / 'date').iterdir() if p.is_dir()), ['lista', 'p'])
            self.assertEqual([i['slug'] for i in items if has_page(i, projections)], ['p'])
            self.assertEqual(items[0]['inventory']['page'], 'date/p/', 'the explorer data names the page that exists')
            self.assertTrue(all('page' not in i.get('inventory', {}) for i in items[1:]))

    def test_an_organisation_and_an_entry_out_of_scope_get_no_page_although_they_have_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = [{'id': 's', 'url': 'https://example.org/a.csv', 'format': 'csv', 'campuri': [record('a')]}]
            profiles = [{'slug': slug, 'surse_structurate': ['s']} for slug in ('org', 'off', 'free', 'fine')]
            items = [built('org', kind='organizatie', dataRelation=''), built('off', status='offline'), built('free', dataRelation='fara-date'), built('fine')]
            (site, projections), _ = fixture(tmp, sources=sources, profiles=profiles, items=items)
            self.assertEqual(sorted(p.name for p in (site / 'date').iterdir() if p.is_dir()), ['fine', 'lista'])
            self.assertTrue(all((site / 'inventar' / f'{slug}.json').exists() for slug in ('org', 'off', 'free', 'fine')), 'the explorer keeps every panel')

    def test_the_header_names_the_entry_with_its_link_the_relation_and_the_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, projections), items = fixture(tmp)
            page = (site / 'date/p/index.html').read_text()
        head = page[page.index('<section class="vp-head">'):page.index('</section>')]
        self.assertIn('<h1>Proiect &lt;P&gt; &amp; co</h1>', head)
        self.assertIn('<a class="vp-open" href="proiect/p/">', head, 'a link to the entry of the explorer, from the base of the site')
        self.assertIn('Relația cu datele: Date publice', head)
        fields, sources = projections['p']
        self.assertIn(f'<span>{len(sources)} surse</span>', head)
        self.assertIn(f'<span>{len(fields)} câmpuri</span>', head)
        self.assertIn('Inventar parțial', head)
        self.assertIn('<title>Variabile · Proiect &lt;P&gt; &amp; co · CivTech România</title>', page)
        self.assertNotIn('<!--', page)
        self.assertNotIn('v=BUILD', page)

    def test_a_resource_is_named_as_one_and_an_unknown_relation_shows_its_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = [{'id': 's', 'url': 'https://example.org/a.csv', 'format': 'csv', 'campuri': [record('a')]}]
            (site, _), _ = fixture(tmp, sources=sources, profiles=[{'slug': 'r', 'surse_structurate': ['s']}], items=[built('r', kind='resursa', dataRelation='calcul')])
            page = (site / 'date/r/index.html').read_text()
        self.assertIn('<p class="vp-kind">Resursă</p>', page)
        self.assertIn('href="resursa/r/"', page)
        self.assertIn('Relația cu datele: calcul', page, 'a code that the vocabulary does not list is shown as it is')

    def test_the_families_come_in_the_order_of_the_list_and_a_family_without_a_field_has_no_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, _), _ = fixture(tmp)
            page = (site / 'date/p/index.html').read_text()
        blocks = re.findall(r'<section class="vp-family[^"]*" data-family="([^"]*)"', page)
        self.assertEqual(blocks, ['ids', 'timp', 'altele'], 'Geografie has no field; the order is the one of the families and then „Altele”')
        self.assertEqual([i for i, _ in family_columns(CONCEPTS, FAMILIES)], ['ids', 'timp', 'geo'])
        self.assertIn('data-state="revizuit">Revizuit</small>', page)
        self.assertIn('data-state="propus">Propus</small>', page, 'a group without a state is proposed')
        self.assertNotIn('Gone', page, 'a rejected group shows nothing')
        self.assertIn('<a href="date/?variables=cui">CUI</a>', page, 'the group links to the finder from the base of the site')
        self.assertIn('An &lt;b&gt;', page)

    def test_a_field_that_two_groups_match_is_listed_under_both_and_a_field_in_no_group_goes_to_altele(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, projections), _ = fixture(tmp)
            page = (site / 'date/p/index.html').read_text()
        def group(gid):
            start = page.index(f'<div class="vp-group" data-group="{gid}">')
            return page[start:page.index('</ul>', start)]
        # The rows keep the order of the field browser (its ranking puts a field with a description before one without).
        self.assertEqual(re.findall(r'<code>([^<]+)</code>', group('cui')), ['$.firma.cui_firma', 'cui', '$.cui'])
        self.assertEqual(re.findall(r'<code>([^<]+)</code>', group('cod')), ['cui', '$.cui'], 'the second group takes the fields that it matches, the first group does not hide them')
        other = page[page.index('data-family="altele"'):page.index('id="pe-surse"')]
        self.assertEqual(sorted(re.findall(r'<code>([^<]+)</code>', other)), ['$.total', 'altceva', 'q'], 'total belongs to a rejected group, so it matches none')
        self.assertIn('Fișier CSV · lista.csv', group('cui'), 'each row names its source by the title of the field browser, then the path')
        fields, sources = projections['p']
        self.assertEqual(set(field_groups('p', fields, sources, CONCEPTS).values()), {'cui', 'an'}, 'the list keeps first-group-wins: its counts are unchanged')

    def test_the_part_by_sources_gives_the_address_the_format_the_licence_and_one_row_per_field(self):
        licence = {'valoare': 'CC BY 4.0', 'url': {'valoare': 'https://creativecommons.org/licenses/by/4.0/'}, 'atribuire': {'valoare': 'Sursa: example.org'}}
        with tempfile.TemporaryDirectory() as tmp:
            sources = [{'id': 's1', 'url': 'https://example.org/api/openapi.json', 'format': 'openapi', 'fetched_at': '2026-10-24T10:00:00+00:00',
                        'campuri': [record('cui', descriere='Codul <unic>', unitate='cifre'), record('year', tip_declarat=None, tipuri_observate=['integer'], grup='Tabel', randuri_tabel=40)],
                        'seturi': [{'licenta': licence}], 'ultima_incercare': {'la': '2026-10-26T09:00:00+00:00', 'stare': 'eroare-http', 'http_status': 503}}]
            (site, projections), _ = fixture(tmp, sources=sources, profiles=[{'slug': 'p', 'surse_structurate': ['s1']}])
            page = (site / 'date/p/index.html').read_text()
            payload = json.loads((site / 'inventar/p.json').read_text())
        part = page[page.index('id="pe-surse"'):]
        self.assertEqual(part.count('<section class="vp-source"'), len(payload['sources']))
        self.assertIn('<h3>Schemă API · openapi.json</h3>', part)
        self.assertIn('<dt>Adresă</dt><dd><a href="https://example.org/api/openapi.json" target="_blank" rel="noopener">https://example.org/api/openapi.json</a></dd>', part)
        self.assertIn('<dt>Format</dt><dd>Schemă API</dd>', part)
        self.assertIn('<dt>Licență</dt><dd><a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a> · Sursa: example.org</dd>', part)
        self.assertIn('consultat la 2026-10-24', part)
        self.assertIn('ultima reîmprospătare a eșuat la 2026-10-26 (HTTP 503); informațiile pot fi vechi', part, 'a failed refresh is never hidden')
        rows = re.findall(r'<tr><th scope="row"><code>(.*?)</code><small>(.*?)</small></th><td><code>(.*?)</code>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>', part)
        self.assertEqual([(r[0], r[1], r[2], r[4], r[5], r[6], r[7]) for r in rows],
                         [('cui', 'Răspunsuri API · Descris în schemă', '$.cui', 'Text', 'cifre', 'Codul &lt;unic&gt;', 'CUI, Cod'),
                          ('year', 'Răspunsuri API · Descris în schemă', '$.year', 'Număr întreg', '', '', 'An &lt;b&gt;')])
        self.assertEqual(rows[1][3], '<small>Tabel · 40 de rânduri</small>', 'the table of the source and its row count sit under the path')

    def test_a_copy_that_the_owner_saved_is_not_called_a_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = [{'id': 's', 'url': 'https://example.org/a.csv', 'format': 'csv', 'origine': 'copie-salvata-de-proprietar', 'fetched_at': '2026-10-25T20:39:00+02:00',
                        'campuri': [record('a')]}]
            (site, _), _ = fixture(tmp, sources=sources, profiles=[{'slug': 'p', 'surse_structurate': ['s']}])
            page = (site / 'date/p/index.html').read_text()
        self.assertIn('copie salvată de proprietar la 2026-10-25', page)
        self.assertNotIn('consultat la', page)

    def test_a_group_without_a_known_family_goes_to_the_last_block_of_the_list(self):
        concepts = [{**CONCEPTS[0], 'familie': 'nu-exista'}, {**CONCEPTS[2]}]
        self.assertEqual(family_columns(concepts, FAMILIES)[-1], (None, 'Fără familie'))
        self.assertEqual(family_columns(CONCEPTS[2:3], FAMILIES), [(f['id'], f['label']) for f in FAMILIES], 'no such block when every group has a family')
        with tempfile.TemporaryDirectory() as tmp:
            site = site_fixture(tmp, concepts)
            page = (site / 'date/p/index.html').read_text()
        self.assertEqual(re.findall(r'<section class="vp-family[^"]*" data-family="([^"]*)"', page), ['timp', '', 'altele'])
        self.assertIn('<h3>Fără familie<small>', page)

    def test_a_licence_that_the_source_does_not_declare_is_not_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, _), _ = fixture(tmp)
            page = (site / 'date/p/index.html').read_text()
        self.assertNotIn('Licență', page)

    def test_a_source_that_has_no_field_of_its_own_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract = {'id': 'c', 'url': 'https://example.org/openapi.json', 'format': 'openapi', 'campuri': [record('cui', pointer='/p/0')]}
            docs = {'id': 'd', 'url': 'https://example.org/api-docs', 'format': 'html-api-docs',
                    'campuri': [{**record('cui'), 'stare_tip': 'declarat-in-documentatie-api', 'in_contract': {'sursa_id': 'c', 'pointer': '/p/0'}}]}
            (site, _), _ = fixture(tmp, sources=[contract, docs], profiles=[{'slug': 'p', 'surse_structurate': ['c', 'd']}])
            page = (site / 'date/p/index.html').read_text()
            payload = json.loads((site / 'inventar/p.json').read_text())
        self.assertEqual([f['source'] for f in payload['fields']], ['c'], 'the browser folds the restatement into the contract record')
        self.assertEqual(page.count('<tbody>'), 1)
        self.assertIn('Niciun câmp propriu', page)
        self.assertEqual(page.count('<section class="vp-source"'), 2, 'the source stays named, as it does in the selector of the browser')

    def test_the_rows_follow_the_order_and_the_folding_of_the_field_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            fields = [record('zeta'), record('q', 'q', rol='parametru-api', loc='query', pointer='/a'), record('cui', descriere='Cod'), record('q', 'q', rol='parametru-api', loc='query', pointer='/b'),
                      record('alfa', '$.a.b.c.alfa')]
            (site, _), _ = fixture(tmp, sources=[{'id': 's', 'url': 'https://example.org/a.json', 'format': 'json', 'campuri': fields}], profiles=[{'slug': 'p', 'surse_structurate': ['s']}])
            page = (site / 'date/p/index.html').read_text()
            payload = json.loads((site / 'inventar/p.json').read_text())
        table = page[page.index('<tbody>'):page.index('</tbody>')]
        names = re.findall(r'<th scope="row"><code>([^<]*)</code>', table)
        self.assertEqual(names, [f['name'] for f in payload['fields']], 'the page uses the ranking of the browser')
        self.assertEqual(names.count('q'), 1, 'two declarations of one API parameter are one row, as in the browser')
        self.assertNotEqual(names, ['zeta', 'q', 'cui', 'q', 'alfa'])

    def test_no_value_of_a_data_body_and_no_evidence_reaches_the_page(self):
        secret = {'valoare': 'VALOARE-SECRETA', 'exemplu': 'EXEMPLU-SECRET', 'valori_enum': ['ENUM-SECRET'], 'formula_declarata': 'FORMULA-SECRETA',
                  'perioada_declarata': 'PERIOADA-SECRETA', 'chei_exemplu': ['CHEIE-SECRETA'], 'dovada_externa': {'url': 'https://x.example/', 'fragment': 'FRAGMENT-SECRET'},
                  'expresie': 'EXPRESIE-SECRETA', 'linie': 7}
        with tempfile.TemporaryDirectory() as tmp:
            sources = [{'id': 's', 'url': 'https://example.org/a.json', 'format': 'json', 'snapshot': 'surse/SNAPSHOT.json', 'sha256': 'HASH-SECRET',
                        'esantion': {'x': 'ESANTION-SECRET'}, 'campuri': [record('cui', **secret)]}]
            (site, _), _ = fixture(tmp, sources=sources, profiles=[{'slug': 'p', 'surse_structurate': ['s']}])
            page = (site / 'date/p/index.html').read_text()
            payload = (site / 'inventar/p.json').read_text()
        self.assertIn('ENUM-SECRET', payload, 'the fixture does carry the values to the payload of the browser')
        for word in ('SECRET', 'SECRETA', 'SNAPSHOT', 'FRAGMENT'):
            self.assertNotIn(word, page)

    def test_a_text_that_a_source_wrote_stays_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            hostile = '<img src=x onerror="alert(1)">'
            sources = [{'id': 's', 'url': 'https://example.org/a.json', 'format': 'json', 'campuri': [record('cui', descriere=hostile, unitate=hostile, grup=hostile)]}]
            (site, _), _ = fixture(tmp, sources=sources, profiles=[{'slug': 'p', 'surse_structurate': ['s']}])
            page = (site / 'date/p/index.html').read_text()
        self.assertNotIn('<img', page)
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;', page)

    def test_every_link_and_file_of_the_page_resolves_from_its_own_address_and_no_anchor_is_bare(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, _), _ = fixture(tmp)
            page = (site / 'date/p/index.html').read_text()
            self.assertIn('<base href="../../">', page)
            here = 'https://civtech.example/date/p/'
            base = urljoin(here, '../../')
            self.assertEqual(base, 'https://civtech.example/')
            for tag, name, value in parse(page).links:
                if value.startswith('https://') and tag == 'a':
                    continue
                self.assertFalse(value.startswith('#'), f'a bare anchor {value} would leave the page through the base')
                self.assertFalse(value.startswith('/'), f'{value}: a link that starts at the root would ignore the folder of the site')
                target = urlsplit(urljoin(base, value))
                self.assertEqual(target.netloc, 'civtech.example')
                if tag == 'link' or name == 'src':
                    # A file of the site: the fixture holds the two style sheets; the font and image files belong to the template and are checked in the real site.
                    self.assertTrue((site / target.path.lstrip('/')).exists() or value.startswith(('img/', 'fonts/')), value)
                elif target.fragment:
                    self.assertEqual(target.path, '/date/p/', 'an anchor of the page goes to the page, not to the explorer')
        hrefs = {v for _, n, v in parse(page).links if n == 'href'}
        self.assertTrue({'./', 'date/', 'date/lista/', 'proiect/p/', 'date/p/#pe-familii', 'date/p/#pe-surse'} <= hrefs)
        self.assertIn('id="pe-familii"', page)
        self.assertIn('id="pe-surse"', page)

    def test_the_list_links_each_row_to_its_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, _), _ = fixture(tmp)
            page = (site / 'date/lista/index.html').read_text()
        row = page[page.index('<tr id="p">'):page.index('</tr>', page.index('<tr id="p">'))]
        self.assertIn('<a href="proiect/p/">', row, 'the link to the entry stays')
        self.assertIn('<a href="date/p/">Toate variabilele</a>', row)
        self.assertEqual(page.count('Toate variabilele'), len(re.findall(r'<tr id="', page)), 'one link for each row')

    def test_a_page_that_no_entry_has_any_more_is_removed_and_the_reserved_slug_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (site, projections), items = fixture(tmp)
            (site / 'date/old').mkdir()
            (site / 'date/old/index.html').write_text('stale')
            publish_variable_pages(items, site, projections, CONCEPTS, FAMILIES)
            self.assertEqual(sorted(p.name for p in (site / 'date').iterdir() if p.is_dir()), ['lista', 'p'])
            self.assertTrue((site / 'date/lista/index.html').exists(), 'the list is not a page of an entry')
            clash = {'lista': projections['p']}
            with self.assertRaises(ValueError):
                publish_variable_pages([built('lista')], site, clash, CONCEPTS, FAMILIES)
            with self.assertRaises(ValueError):
                publish_variable_pages([built('Not_A_Slug')], site, {'Not_A_Slug': projections['p']}, CONCEPTS, FAMILIES)

    def test_one_matching_rule_serves_the_finder_the_list_and_the_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            (_, projections), _ = fixture(tmp)
        fields, sources = projections['p']
        hits = group_hits('p', fields, sources, CONCEPTS)
        self.assertEqual([c['id'] for c, _ in hits], ['cui', 'cod', 'an'])
        self.assertEqual([m['id'] for m in variable_matches('p', fields, sources, CONCEPTS)], [c['id'] for c, _ in hits])
        self.assertEqual([m['count'] for m in variable_matches('p', fields, sources, CONCEPTS)], [len(found) for _, found in hits])
        self.assertEqual(group_hits('other', fields, sources, CONCEPTS), [])


def js_object(source, name):
    """The `{key: 'text'}` pairs of a JavaScript object literal `const <name> = { ... };`."""
    body = re.search(r'const ' + name + r'\s*=\s*\{(.*?)\};', source, re.S).group(1)
    return {a or b: c for a, b, c in re.findall(r"""(?:'([^']+)'|([A-Za-z_]\w*))\s*:\s*'([^']*)'""", body)}


class Labels(unittest.TestCase):
    def test_the_labels_of_the_static_page_equal_the_labels_of_the_field_browser(self):
        app = (ROOT / 'site/app.js').read_text()
        self.assertEqual(TYPE_LABELS, js_object(app, 'INV_TYPES'))
        self.assertEqual(ROLE_LABELS, js_object(app, 'INV_ROLES'))
        self.assertEqual(FIELD_BASIS_LABELS, js_object(app, 'INV_BASIS'))
        self.assertEqual(GROUP_STATE_LABELS, js_object((ROOT / 'site/inventory.js').read_text(), 'stateLabels'))

    def test_the_type_of_a_field_is_worded_as_the_field_browser_words_it(self):
        self.assertEqual(type_label({'declaredType': 'string', 'observedTypes': ['integer']}), 'Text')
        self.assertEqual(type_label({'declaredType': ['string', 'null'], 'observedTypes': []}), 'Text / Valoare nulă')
        self.assertEqual(type_label({'declaredType': None, 'observedTypes': ['integer', 'null']}), 'Număr întreg / Valoare nulă')
        self.assertEqual(type_label({'declaredType': None, 'observedTypes': [], 'semanticType': 'geo'}), 'Arie geografică')
        self.assertEqual(type_label({'declaredType': None, 'observedTypes': []}), 'Tip neprecizat')
        self.assertEqual(type_label({'declaredType': 'varchar(255)', 'observedTypes': []}), 'varchar(255)', 'a type without a label is shown as written')
        self.assertEqual(type_label({'declaredType': [], 'observedTypes': ['integer']}), 'Tip neprecizat', 'an empty list is true in JavaScript, so it hides the observed types there too')

    def test_a_long_text_is_cut_at_a_word_with_an_ellipsis(self):
        self.assertEqual(clip('scurt', 300), 'scurt')
        text = 'cuvânt ' * 100
        cut = clip(text, 300)
        self.assertTrue(cut.endswith('…') and len(cut) <= 301 and not cut[:-1].endswith(' '))
        self.assertEqual(clip('x' * 400, 300), 'x' * 300 + '…', 'a text without a space is cut at the limit')
        self.assertEqual(clip('uno doi trei patru', 14), 'uno doi trei…', 'the cut falls at the last space before the limit, not inside a word')
        self.assertEqual(clip('uno doi, trei patru', 9), 'uno doi…', 'a comma or a space before the cut goes too')


class RealInventory(unittest.TestCase):
    def test_each_page_of_the_tracked_inventory_agrees_with_its_own_payload(self):
        """Compared with the data and not with a number: the pages, their sources and their rows are those of `inventar/<slug>.json`."""
        taxonomy = ROOT / 'data/taxonomy-v2'
        profiles = json.loads((taxonomy / 'observatii/inventare/proiecte.json').read_text())['proiecte']
        document = json.loads((taxonomy / 'inventar-concepte.json').read_text())
        items = [built(p['slug']) for p in profiles if p['surse_structurate']]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / 'site'
            (site / 'inventar').mkdir(parents=True)
            for name in ('style.css', 'inventory.css', 'inventory.js'):
                (site / name).write_text('/* fixture */')
            with patch('inventory_site.observation_paths', return_value={'profile': taxonomy / 'observatii/profil.csv'}):
                projections = publish_preview(items, taxonomy / 'integrare', site)
            publish_finder(items, taxonomy / 'integrare', site, projections)
            index = json.loads((site / 'inventar/index.json').read_text())
            family_of = {v['id']: v['family'] for v in index['variables']}
            written = sorted(p.name for p in (site / 'date').iterdir() if p.is_dir() and p.name != 'lista')
            self.assertEqual(written, sorted(i['slug'] for i in items if i.get('inventory', {}).get('url')))
            self.assertGreater(len(written), 0)
            for slug in written:
                with self.subTest(slug=slug):
                    page = (site / 'date' / slug / 'index.html').read_text()
                    payload = json.loads((site / 'inventar' / f'{slug}.json').read_text())
                    entry = next(e for e in index['entries'] if e['slug'] == slug)
                    self.assertEqual(page.count('<section class="vp-source"'), len(payload['sources']))
                    self.assertEqual(len(re.findall(r'<tr><th scope="row">', page)), len(payload['fields']))
                    families = re.findall(r'<section class="vp-family" data-family="([^"]*)"', page)
                    wanted = {family_of[v['id']] for v in entry['variables']}
                    self.assertEqual(set(families), {f if f in {x['id'] for x in document['familii']} else '' for f in wanted})
                    self.assertEqual(families, sorted(families, key=lambda f: [x['id'] for x in document['familii']].index(f) if f else 10**6),
                                     'the families come in the order of the list')
                    for field in payload['fields']:
                        self.assertIn(f'<code>{field["path"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(chr(34), "&quot;").replace(chr(39), "&#x27;")}</code>', page)


if __name__ == '__main__':
    unittest.main()
