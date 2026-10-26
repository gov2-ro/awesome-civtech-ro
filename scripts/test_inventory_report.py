"""Checks for the coverage export and the readable report. They read the tracked files and fixtures only."""
import csv
import hashlib
import io
import re
import unittest
from pathlib import Path

import inventory_report as report
from common import PUBLIC_ROOT
from inventory_concepts import EvidenceLocator

ROOT = Path(__file__).resolve().parents[1]
BRIEF_COLUMNS = ['slug', 'tip_entitate', 'investigat_in_lot', 'stare_investigare', 'surse_structurate', 'campuri_din_surse', 'concepte_propuse',
                 'campuri_cu_definitie', 'campuri_cu_tip_declarat', 'campuri_cu_tip_observat', 'masuri_cu_unitate', 'masuri_fara_unitate',
                 'surse_cu_provenienta_verificata', 'limite', 'blocaj', 'urmatorul_pas']


class Coverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = report.load(PUBLIC_ROOT)
        cls.rows = report.coverage_rows(cls.data)
        cls.table = list(csv.DictReader(io.StringIO(report.csv_text(cls.rows))))
        cls.by = {r['slug']: r for r in cls.table}

    def test_columns_match_the_specification_and_every_entry_has_one_row(self):
        self.assertEqual(report.COLUMNS, BRIEF_COLUMNS)
        self.assertEqual([r[0] for r in self.rows], [e['slug'] for e in self.data['entries']])
        self.assertEqual(len(self.rows), len(self.data['entries']))
        self.assertGreaterEqual(len(self.rows), report.BASELINE['entries'], 'the catalogue only grows')
        self.assertTrue(all(len(r) == len(BRIEF_COLUMNS) for r in self.rows))

    def test_the_tracked_files_are_current(self):
        csv_path = ROOT / 'data/taxonomy-v2/observatii/inventare/acoperire.csv'
        self.assertEqual(csv_path.read_text(), report.csv_text(self.rows), 'run scripts/inventory_report.py')
        text = (ROOT / 'docs/reports/inventory-expansion.md').read_text()
        self.assertEqual(text, report.render_report(self.data, self.rows) + '\n', 'run scripts/inventory_report.py')

    def test_unknown_stays_unknown_and_zero_means_checked(self):
        empty = self.by['465']
        self.assertEqual((empty['stare_investigare'], empty['surse_structurate'], empty['campuri_din_surse']), ('neinvestigat-in-lot', '0', '0'))
        for column in ('concepte_propuse', 'masuri_cu_unitate', 'masuri_fara_unitate', 'surse_cu_provenienta_verificata'):
            self.assertEqual(empty[column], '', column)
        self.assertTrue(empty['urmatorul_pas'])
        organisation = next(r for r in self.table if r['stare_investigare'] == 'in-afara-ariei')
        self.assertEqual(organisation['tip_entitate'], 'organizatie')
        self.assertEqual(self.by['monitor-energie']['stare_investigare'], 'blocat')
        self.assertIn('401', self.by['monitor-energie']['blocaj'])

    def test_fields_groups_declarations_observations_and_units_are_separate_columns(self):
        weather = self.by['calitate-aer-radauti']
        self.assertEqual((weather['campuri_din_surse'], weather['campuri_cu_tip_declarat'], weather['campuri_cu_tip_observat']), ('41', '0', '41'))
        self.assertEqual((weather['masuri_cu_unitate'], weather['masuri_fara_unitate']), ('4', '28'), 'only the centre station declares units')
        code = self.by['votdiaspora']
        self.assertEqual((code['campuri_cu_tip_declarat'], code['campuri_cu_tip_observat']), ('50', '0'))
        for row in self.table:
            if row['campuri_din_surse'] not in ('', '0'):
                self.assertLessEqual(int(row['campuri_cu_definitie']), int(row['campuri_din_surse']), row['slug'])
                self.assertLessEqual(int(row['campuri_cu_tip_declarat']) + 0, int(row['campuri_din_surse']), row['slug'])

    def test_every_primary_entry_has_an_outcome_and_the_batch_is_the_specified_twelve(self):
        self.assertEqual(report.BATCH, ['afacut', 'biografia-localitatii', 'registrul-firmelor', 'dignitas', 'monitorul-ai', 'rezultate-vot', 'votdiaspora',
                                        'aerlive', 'calitate-aer-radauti', 'banii-nostri', 'europescope', 'despre-femicid'])
        for slug in report.BATCH:
            self.assertIn('C', self.by[slug]['investigat_in_lot'].split('|'))
            self.assertTrue(self.data['notes']['note'][slug]['rezultat'], slug)
            self.assertTrue(self.data['notes']['note'][slug]['limite'], slug)

    def test_batch_c2_has_its_lot_a_state_and_a_note_for_each_entry(self):
        self.assertEqual(report.BATCH_C2, ['data-expertforum', 'bani-partide', 'romania-interactiva'])
        for slug in report.BATCH_C2:
            self.assertEqual(self.by[slug]['investigat_in_lot'].split('|').count('C2'), 1, slug)
            note = self.data['notes']['note'][slug]
            self.assertTrue(note['rezultat'] and note['limite'] and note['urmator_en'] and note['limite_en'], slug)
        for slug in ('harta-banilor-publici', 'parlament-transparent', 'bani-pierduti'):
            self.assertNotIn('C2', self.by[slug]['investigat_in_lot'], 'inactive entries are not in the batch: ' + slug)
        self.assertEqual(self.by['romania-interactiva']['stare_investigare'], 'cu-surse-structurate')
        for slug in ('data-expertforum', 'bani-partide'):
            row = self.by[slug]
            self.assertEqual((row['stare_investigare'], row['surse_structurate'], row['campuri_din_surse'], row['concepte_propuse']), ('blocat', '0', '0', ''), slug)
            self.assertIn('403', row['blocaj'])

    def test_a_blocker_in_the_notes_decides_the_state_of_an_entry_without_sources_and_nothing_else_does(self):
        slug = 'bani-partide'
        without = {**self.data, 'notes': {**self.data['notes'], 'note': {k: v for k, v in self.data['notes']['note'].items() if k != slug}}}
        row = {r[0]: dict(zip(report.COLUMNS, r)) for r in report.coverage_rows(without)}[slug]
        self.assertEqual((row['stare_investigare'], row['blocaj']), ('neinvestigat-in-lot', ''), 'without the note the entry has no state of its own')
        self.assertEqual(self.by['465']['stare_investigare'], 'neinvestigat-in-lot', 'an entry with no note stays uninvestigated')

    def test_provider_items_of_batch_c2_are_open_proposals_with_evidence_that_the_retained_copy_holds(self):
        items = [r for r in self.data['review'] if r['camp'] == 'surse_date' and r['id'].startswith('D') and 176 <= int(r['id'][1:]) <= 185]
        self.assertEqual([r['id'] for r in items], [f'D{n}' for n in range(176, 186)])
        locator = EvidenceLocator(ROOT / 'data/taxonomy-v2/observatii/inventare', ROOT / 'data/taxonomy-v2/observatii',
                                  list(self.data['sources'].values()))
        for item in items:
            self.assertEqual((item['slug'], item['stare'], item['decizie_editor']), ('romania-interactiva', 'deschis', ''), item['id'])
            self.assertIn(item['prioritate'], ('medie', 'mica'), 'a high-priority open item would block the publication gate')
            self.assertTrue(item['propunere'].startswith('Furnizor propus: '))
            cited = re.search(r'Dovadă: (\S+) \(text păstrat, sha256 ([0-9a-f]{16})\)', item['motiv'])
            self.assertTrue(cited, item['id'])
            text, _ = locator.text(cited.group(1), 'sursa')
            if text is not None:  # the retained bodies are not in git: a fresh checkout cannot compare
                self.assertTrue(hashlib.sha256(text.encode()).hexdigest().startswith(cited.group(2)), item['id'])
                self.assertIn(item['valoare_originala'], text, item['id'])

    def test_baseline_figures_are_the_ones_of_the_brief(self):
        self.assertEqual((report.BASELINE['with_fields'], report.BASELINE['field_records'], report.BASELINE['groups']), (14, 2302, 7))
        measured = report.metrics(self.data, self.rows)
        self.assertEqual((report.BASELINE['accepted_providers'], report.BASELINE['accepted_entries']), (26, 11))
        # Editorial decisions change the accepted relations, so the measured value is checked against the data, not against the baseline.
        accepted = [r for r in self.data['relations'] if r['predicat'] == 'date_din' and r['stare'] == 'acceptat']
        self.assertEqual((measured['entries'], measured['finder'], measured['accepted_providers'], measured['accepted_entries']),
                         (len(self.data['entries']), sum(e['kind'] != 'organizatie' for e in self.data['entries']), len(accepted),
                          len({r['subiect'] for r in accepted})))
        self.assertGreater(measured['with_fields'], report.BASELINE['with_fields'])

    def test_report_keeps_provider_proposals_apart_from_accepted_relations(self):
        text = report.render_report(self.data, self.rows)
        self.assertIn('None changes `relatii.csv`', text)
        self.assertIn('D147', text)
        accepted = sum(1 for r in self.data['relations'] if r['predicat'] == 'date_din' and r['stare'] == 'acceptat')
        self.assertIn(f'| 26 / 11 | {accepted} / ', text, 'the report states the measured accepted relations next to the baseline')


if __name__ == '__main__':
    unittest.main()
