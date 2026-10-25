"""Checks for the coverage export and the readable report. They read the tracked files and fixtures only."""
import csv
import io
import unittest
from pathlib import Path

import inventory_report as report
from common import PUBLIC_ROOT

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
        self.assertEqual(len(self.rows), 140)
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

    def test_baseline_figures_are_the_ones_of_the_brief(self):
        self.assertEqual((report.BASELINE['with_fields'], report.BASELINE['field_records'], report.BASELINE['groups']), (14, 2302, 7))
        measured = report.metrics(self.data, self.rows)
        self.assertEqual((report.BASELINE['accepted_providers'], report.BASELINE['accepted_entries']), (26, 11))
        # Editorial decisions change the accepted relations, so the measured value is checked against the data, not against the baseline.
        accepted = [r for r in self.data['relations'] if r['predicat'] == 'date_din' and r['stare'] == 'acceptat']
        self.assertEqual((measured['entries'], measured['finder'], measured['accepted_providers'], measured['accepted_entries']),
                         (140, 127, len(accepted), len({r['subiect'] for r in accepted})))
        self.assertGreater(measured['with_fields'], report.BASELINE['with_fields'])

    def test_report_keeps_provider_proposals_apart_from_accepted_relations(self):
        text = report.render_report(self.data, self.rows)
        self.assertIn('None changes `relatii.csv`', text)
        self.assertIn('D147', text)
        accepted = sum(1 for r in self.data['relations'] if r['predicat'] == 'date_din' and r['stare'] == 'acceptat')
        self.assertIn(f'| 26 / 11 | {accepted} / ', text, 'the report states the measured accepted relations next to the baseline')


if __name__ == '__main__':
    unittest.main()
