"""Checks for evidence-backed data sources and geographic breakdowns."""
import copy
import csv
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import common
import taxonomy_v2


class DataSources(unittest.TestCase):
    def test_invalid_evidence_is_a_validation_error(self):
        for value in ('', 'javascript:alert(1)', 'https://[', 'https://', 'https://bad host/'):
            with self.subTest(value=value):
                self.assertFalse(taxonomy_v2.http_evidence(value))
        self.assertTrue(taxonomy_v2.http_evidence('https://example.org/method#data'))

    def test_only_accepted_sources_are_public_and_never_authors(self):
        pkg = copy.deepcopy(taxonomy_v2.load(common.PUBLIC_ROOT))
        slug = next(iter(pkg.entries))
        pkg.tables['relatii.csv'] = [
            dict(id=f'T{n}', subiect=slug, predicat='date_din', obiect='', obiect_literal=f'Provider {n}',
                 camp_sursa='surse_date', valoare_sursa='https://example.org/method', stare=state)
            for n, state in enumerate(('acceptat', 'propus', 'respins', 'rol_neconfirmat'))
        ]
        with patch.object(taxonomy_v2, 'load', return_value=pkg):
            entry = next(e for e in common.load_catalogue(common.PUBLIC_ROOT) if e['slug'] == slug)
        self.assertEqual([s['name'] for s in entry['data_sources']], ['Provider 0'])
        self.assertEqual(entry['data_sources'][0]['evidence'], 'https://example.org/method')
        self.assertEqual(entry['attributions'], [])

    def test_source_can_reference_a_catalogue_organisation(self):
        pkg = copy.deepcopy(taxonomy_v2.load(common.PUBLIC_ROOT))
        slug = next(iter(pkg.entries))
        target = next(r for r in pkg.entries.values() if r['tip_entitate'] == 'organizatie')
        pkg.tables['relatii.csv'] = [dict(id='T1', subiect=slug, predicat='date_din', obiect=target['slug'],
                                         obiect_literal='', camp_sursa='surse_date',
                                         valoare_sursa='https://example.org/method', stare='acceptat')]
        with patch.object(taxonomy_v2, 'load', return_value=pkg):
            entry = next(e for e in common.load_catalogue(common.PUBLIC_ROOT) if e['slug'] == slug)
        self.assertEqual(entry['data_sources'][0]['name'], target['nume'])
        self.assertEqual(entry['attributions'], [])

    def test_publication_rejects_unsafe_source_and_breakdown_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'taxonomy-v2'
            shutil.copytree(common.PUBLIC_ROOT.parent, root,
                            ignore=shutil.ignore_patterns('runs', '__pycache__', 'catalogue.json'))
            for path, field, select in [
                (root / 'relatii.csv', 'valoare_sursa', lambda r: r['predicat'] == 'date_din' and r['stare'] == 'acceptat'),
                (root / 'integrare/intrari.csv', 'dovada_detaliere', lambda r: bool(r['detaliere_date'])),
            ]:
                with path.open() as f:
                    reader = csv.DictReader(f)
                    header, rows = reader.fieldnames, list(reader)
                next(r for r in rows if select(r))[field] = 'javascript:alert(1)'
                with path.open('w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=header, lineterminator='\n')
                    writer.writeheader()
                    writer.writerows(rows)
            errors, _ = taxonomy_v2.check(root / 'integrare', publication=True)
            self.assertTrue(any('a data source needs an HTTP evidence URL' in e for e in errors), errors)
            self.assertTrue(any('a data breakdown needs an HTTP evidence URL' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()
