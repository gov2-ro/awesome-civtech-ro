"""Checks for compact, explicitly partial explorer inventory previews."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inventory_site import document_links, group_api_parameters, publish_preview, variable_matches, publish_finder


class InventorySite(unittest.TestCase):
    def test_draft_inventory_flag_cannot_write_the_public_site(self):
        root = Path(__file__).resolve().parents[1]
        before = (root / 'site/data.json').read_bytes()
        result = subprocess.run([sys.executable, str(root / 'scripts/build.py'), '--with-inventory'],
                                capture_output=True, text=True, cwd=root)
        self.assertEqual(result.returncode, 2)
        self.assertIn('separate --site-dir', result.stderr)
        self.assertEqual((root / 'site/data.json').read_bytes(), before)

    def test_document_links_exclude_shared_host_and_failed_pages(self):
        records = {'pages': [
            {'state': 'colectat', 'scope': 'gazda-comuna', 'kind': 'llms', 'final_url': 'https://example.org/llms.txt'},
            {'state': 'eroare-http', 'scope': 'proiect', 'kind': 'despre', 'final_url': 'https://example.org/about'},
            {'state': 'colectat', 'scope': 'proiect', 'kind': 'pagina', 'final_url': 'https://example.org/',
             'sections': [{'kind': 'metodologie', 'url': 'https://example.org/#method', 'heading': 'Metoda'}]},
        ]}
        self.assertEqual([d['url'] for d in document_links(records)], ['https://example.org/#method'])

    def test_preview_splits_fields_and_never_exports_control_candidates_or_private_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); obs = root / 'observatii'; inv = obs / 'inventare'; inv.mkdir(parents=True)
            (obs / 'documentare').mkdir()
            (obs / 'documentare/index.json').write_text(json.dumps({'entries': []}))
            (inv / 'proiecte.json').write_text(json.dumps({'proiecte': [
                {'slug': 'x', 'surse_structurate': ['s'], 'intrari_utilizator': [{'nume': 'newsletter'}]},
                {'slug': 'empty', 'surse_structurate': []},
            ]}))
            (inv / 'seturi-date.json').write_text(json.dumps({'surse': [
                {'id': 's', 'url': 'https://example.org/schema.json', 'format': 'openapi', 'snapshot': 'private/raw.json',
                 'sha256': 'private-hash', 'campuri': [{'nume': 'cui', 'cale': '$.cui', 'rol': 'camp-raspuns',
                      'tip_declarat': 'string', 'stare_tip': 'declarat-in-schema', 'pointer': '/properties/cui'}]},
            ]}))
            site = root / 'site'; site.mkdir(); items = [{'slug': 'x'}, {'slug': 'empty'}]
            with patch('inventory_site.observation_paths', return_value={'profile': obs / 'profil.csv'}):
                publish_preview(items, root, site)
            self.assertEqual(items[0]['inventory']['count'], 1)
            self.assertTrue(items[0]['inventory']['partial'])
            self.assertIn('cui', items[0]['inventory']['keywords'])
            self.assertNotIn('fields', items[0]['inventory'])
            self.assertNotIn('inventory', items[1])
            data = json.loads((site / 'inventar/x.json').read_text())
            self.assertEqual(data['fields'][0]['basis'], 'schema')
            self.assertEqual(data['fields'][0]['declaredType'], 'string')
            raw = (site / 'inventar/x.json').read_text()
            self.assertNotIn('private', raw)
            self.assertNotIn('newsletter', raw)
            self.assertNotIn('snapshot', raw)
            (site / 'inventar/stale.json').write_text('{}')
            with patch('inventory_site.observation_paths', return_value={'profile': obs / 'profil.csv'}):
                publish_preview(items, root, site)
            self.assertFalse((site / 'inventar/stale.json').exists())

    def test_failed_refresh_is_visible_and_the_evidence_is_not_called_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); obs = root / 'observatii'; inv = obs / 'inventare'; inv.mkdir(parents=True)
            (inv / 'proiecte.json').write_text(json.dumps({'proiecte': [{'slug': 'x', 'surse_structurate': ['s', 't']}]}))
            field = {'nume': 'cui', 'cale': '$.cui', 'rol': 'camp-raspuns', 'tip_declarat': 'string', 'stare_tip': 'declarat-in-schema', 'pointer': '/p'}
            (inv / 'seturi-date.json').write_text(json.dumps({'surse': [
                {'id': 's', 'url': 'https://example.org/a.json', 'format': 'openapi', 'fetched_at': '2026-10-24T10:00:00+00:00', 'campuri': [field],
                 'ultima_incercare': {'la': '2026-10-25T09:00:00+00:00', 'stare': 'eroare-http', 'http_status': 503}},
                {'id': 't', 'url': 'https://example.org/b.json', 'format': 'openapi', 'fetched_at': '2026-10-24T10:00:00+00:00', 'campuri': [field]}]}))
            site = root / 'site'; site.mkdir(); items = [{'slug': 'x'}]
            with patch('inventory_site.observation_paths', return_value={'profile': obs / 'profil.csv'}):
                publish_preview(items, root, site)
            sources = json.loads((site / 'inventar/x.json').read_text())['sources']
            self.assertEqual(sources[0]['refreshFailed'], {'date': '2026-10-25', 'status': 503, 'state': 'eroare-http'})
            self.assertEqual(sources[0]['checked'], '2026-10-24')
            self.assertNotIn('refreshFailed', sources[1])
            self.assertEqual(items[0]['inventory']['stale'], 1)

    def test_repeated_api_parameters_keep_their_contexts(self):
        def field(pointer, operation, typ='string'):
            return {'source': 's', 'name': 'cpv', 'role': 'parametru-api', 'declaredType': typ,
                    'description': '', 'unit': None, 'format': None, 'path': 'cpv', 'reference': pointer,
                    'operations': [operation], 'location': 'query'}
        fields = group_api_parameters([field('/a', 'GET /a'), field('/b', 'GET /b'), field('/c', 'GET /c', 'integer')])
        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0]['operations'], ['GET /a', 'GET /b'])
        self.assertEqual([c['reference'] for c in fields[0]['contexts']], ['/a', '/b'])
        self.assertEqual(fields[1]['declaredType'], 'integer')

    def test_unsafe_source_url_does_not_become_a_public_link(self):
        pages = {'pages': [{'state': 'colectat', 'scope': 'proiect', 'kind': 'llms', 'final_url': 'javascript:alert(1)'}]}
        self.assertEqual(document_links(pages), [])

    def test_variable_groups_require_explicit_project_and_name_and_retain_type_evidence(self):
        concepts = [{'id': 'cui', 'selectors': [{'projects': ['known'], 'names': ['cui']}]}]
        def field(name, typ, basis):
            return dict(name=name, path='$.company.' + name, role='camp-date', basis=basis,
                        declaredType=typ, observedTypes=[], unit=None, description='', source='s', reference='/x')
        fields = [field('cui', 'string', 'schema'), field('cui', None, 'header'), field('id', 'integer', 'schema')]
        sources = [{'id': 's', 'url': 'https://example.org/data'}]
        self.assertEqual(variable_matches('unknown', fields, sources, concepts), [])
        matches = variable_matches('known', fields, sources, concepts)
        self.assertEqual(matches[0]['count'], 2)
        self.assertEqual([e['declaredType'] for e in matches[0]['evidence']], ['string', None])
        self.assertEqual([e['basis'] for e in matches[0]['evidence']], ['schema', 'header'])
        self.assertEqual(matches[0]['evidence'][0]['url'], sources[0]['url'])

    def test_finder_keeps_uninventoried_projects_and_separates_institutions_from_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); site = root / 'site'; (site / 'inventar').mkdir(parents=True)
            for name in ('style.css', 'inventory.css', 'inventory.js'):
                (site / name).write_text('/* fixture */')
            items = [dict(slug='no-fields', name='No fields', kind='proiect', institutions=['institutie:parlament'],
                          dataSources=[{'name': 'Camera Deputaților', 'evidence': 'https://example.org/method'},
                                       {'name': 'Senatul României', 'evidence': 'https://example.org/other'}]),
                     dict(slug='resource', name='A resource', kind='resursa'),
                     dict(slug='org', name='An organisation', kind='organizatie')]
            publish_finder(items, root / 'integrare', site, {})
            index = json.loads((site / 'inventar/index.json').read_text())
            self.assertEqual([e['slug'] for e in index['entries']], ['no-fields', 'resource'])
            entry = index['entries'][0]
            self.assertEqual(entry['variables'], [])
            self.assertEqual(entry['institutions'], ['institutie:parlament'])
            self.assertEqual(list(entry['providers']), ['Parlament'])
            self.assertEqual(len(entry['providers']['Parlament']), 2)
            page = (site / 'date/index.html').read_text()
            self.assertNotIn('v=BUILD', page)
            self.assertIn('<base href="../">', page)

    def test_every_seed_selector_has_current_field_evidence(self):
        root = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2'
        concepts = json.loads((root / 'inventar-concepte.json').read_text())['concepte']
        profiles = json.loads((root / 'observatii/inventare/proiecte.json').read_text())['proiecte']
        sources = json.loads((root / 'observatii/inventare/seturi-date.json').read_text())['surse']
        names = {s['id']: {f['nume'] for f in s.get('campuri', [])} for s in sources}
        by_project = {p['slug']: set().union(*(names[s] for s in p['surse_structurate'])) for p in profiles}
        for concept in concepts:
            for selector in concept['selectors']:
                for slug in selector['projects']:
                    with self.subTest(concept=concept['id'], project=slug):
                        self.assertTrue(set(selector['names']).issubset(by_project[slug]))

    def test_ordinary_rebuild_removes_stale_draft_pages_from_an_isolated_output(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / 'index.html').write_text('old preview')
            for name in ('inventar', 'date'):
                (site / name).mkdir()
                (site / name / 'index.json').write_text('draft')
            result = subprocess.run([sys.executable, str(root / 'scripts/build.py'), '--site-dir', str(site)],
                                    capture_output=True, text=True, cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((site / 'date').exists())
            self.assertFalse((site / 'inventar').exists())
            self.assertNotIn('inventoryPreview', json.loads((site / 'data.json').read_text()))


if __name__ == '__main__':
    unittest.main()
