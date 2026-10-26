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
        empty = next(r for r in self.table if r['stare_investigare'] == 'neinvestigat-in-lot')
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
        self.assertEqual(self.by['bani-partide']['stare_investigare'], 'cu-surse-structurate')

    def test_data_expertforum_is_read_from_the_page_that_the_owner_saved_and_says_what_it_could_not_read(self):
        row = self.by['data-expertforum']
        self.assertEqual(row['stare_investigare'], 'cu-surse-structurate')
        self.assertEqual(sorted(row['investigat_in_lot'].split('|')), ['C2', 'S'], 'lot C2, and S for an entry with a page that the owner saved')
        self.assertGreater(int(row['campuri_din_surse']), 0)
        self.assertIn('2.000.000', row['blocaj'], 'the tabs that were too large are named as the blocker')
        profile = self.data['profiles']['data-expertforum']
        failed = [self.data['sources'][r] for r in profile['surse_structurate'] if self.data['sources'][r].get('stare') != 'analizat']
        self.assertTrue(failed and all(s['state'] == 'raspuns-prea-mare' for s in failed), 'a response over the size limit is recorded, not parsed')
        self.assertTrue(all(not s['campuri'] for s in failed))

    def test_bani_partide_is_read_from_the_listing_that_the_owner_saved_and_says_what_it_did_not_read(self):
        row = self.by['bani-partide']
        self.assertEqual(row['stare_investigare'], 'cu-surse-structurate')
        self.assertEqual(sorted(row['investigat_in_lot'].split('|')), ['C2', 'S'], 'lot C2, and S for an entry with a copy that the owner saved')
        self.assertEqual((row['surse_structurate'], row['campuri_din_surse']), ('1', '172'))
        self.assertEqual((row['campuri_cu_definitie'], row['campuri_cu_tip_declarat'], row['campuri_cu_tip_observat']), ('0', '0', '0'), 'the listing declares names only')
        self.assertIn('nu declară tipuri', row['limite'])
        self.assertEqual(row['blocaj'], '', 'the listing was read: nothing blocks the entry')
        source = self.data['sources'][self.data['profiles']['bani-partide']['surse_structurate'][0]]
        self.assertEqual((source['url'], source['format'], source['origine']), ('https://db.banipartide.ro/banipartide.json', 'baza-datasette', 'copie-salvata-de-proprietar'))

    def test_a_blocker_in_the_notes_decides_the_state_of_an_entry_without_sources_and_nothing_else_does(self):
        slug = next(e['slug'] for e in self.data['entries'] if e['kind'] != 'organizatie' and not self.data['profiles'][e['slug']]['surse_structurate']
                    and e['slug'] not in self.data['notes']['note'] and not self.data['scope'][e['slug']])
        notes = self.data['notes']
        blocked = {**self.data, 'notes': {**notes, 'note': {**notes['note'], slug: {'blocaj': 'HTTP 403 la cererea automată'}}}}
        row = {r[0]: dict(zip(report.COLUMNS, r)) for r in report.coverage_rows(blocked)}[slug]
        self.assertEqual((row['stare_investigare'], row['blocaj']), ('blocat', 'HTTP 403 la cererea automată'))
        self.assertEqual(self.by[slug]['stare_investigare'], 'neinvestigat-in-lot', 'without the note the entry has no state of its own')
        self.assertEqual(self.by[next(r['slug'] for r in self.table if r['stare_investigare'] == 'neinvestigat-in-lot')]['stare_investigare'], 'neinvestigat-in-lot',
                         'an entry with no note stays uninvestigated')

    def test_provider_items_of_batch_c2_cite_evidence_that_the_retained_copy_holds(self):
        # The review state belongs to the owner, so the test does not pin it; an item still open must not block the gate.
        items = [r for r in self.data['review'] if r['camp'] == 'surse_date' and r['id'].startswith('D') and 176 <= int(r['id'][1:]) <= 185]
        self.assertEqual([r['id'] for r in items], [f'D{n}' for n in range(176, 186)])
        locator = EvidenceLocator(ROOT / 'data/taxonomy-v2/observatii/inventare', ROOT / 'data/taxonomy-v2/observatii',
                                  list(self.data['sources'].values()))
        for item in items:
            self.assertEqual(item['slug'], 'romania-interactiva', item['id'])
            if item['stare'] == 'deschis':
                self.assertIn(item['prioritate'], ('medie', 'mica'), 'a high-priority open item would block the publication gate')
            self.assertTrue(item['propunere'].startswith('Furnizor propus: '))
            cited = re.search(r'Dovadă: (\S+) \(text păstrat, sha256 ([0-9a-f]{16})\)', item['motiv'])
            self.assertTrue(cited, item['id'])
            text, _ = locator.text(cited.group(1), 'sursa')
            if text is not None:  # the retained bodies are not in git: a fresh checkout cannot compare
                self.assertTrue(hashlib.sha256(text.encode()).hexdigest().startswith(cited.group(2)), item['id'])
                self.assertIn(item['valoare_originala'], text, item['id'])

    def test_the_provider_item_of_batch_c2_part_2_cites_the_saved_page_and_the_text_it_names(self):
        # The review state belongs to the owner, so the test does not pin it.
        # A later item for the same entry (D188, from the owner's note on D186) cites the same page, so each item is checked.
        items = [r for r in self.data['review'] if r['camp'] == 'surse_date' and r['slug'] == 'data-expertforum']
        self.assertIn('D186', [r['id'] for r in items])
        locator = EvidenceLocator(ROOT / 'data/taxonomy-v2/observatii/inventare', ROOT / 'data/taxonomy-v2/observatii', list(self.data['sources'].values()))
        for item in items:
            self.assertTrue(item['propunere'].startswith('Furnizor propus: '), item['id'])
            if item['stare'] == 'deschis':
                self.assertIn(item['prioritate'], ('medie', 'mica'), 'a high-priority open item would block the publication gate')
            cited = re.search(r'Dovadă: (\S+) \(text păstrat, sha256 ([0-9a-f]{16})\)', item['motiv'])
            self.assertEqual(cited.group(1), 'https://data.expertforum.ro/', item['id'])
            text, _ = locator.text(cited.group(1), 'sursa')
            if text is not None:  # the retained bodies are not in git: a fresh checkout cannot compare
                self.assertTrue(hashlib.sha256(text.encode()).hexdigest().startswith(cited.group(2)), item['id'])
                self.assertIn(item['valoare_originala'], text, item['id'])

    def test_the_provider_item_of_batch_c2_part_3_cites_the_saved_listing_and_the_text_it_names(self):
        # The review state belongs to the owner, so the test does not pin it.
        items = [r for r in self.data['review'] if r['camp'] == 'surse_date' and r['slug'] == 'bani-partide']
        self.assertEqual([r['id'] for r in items], ['D187'])
        item = items[0]
        self.assertEqual(item['propunere'], 'Furnizor propus: Ministerul Finanțelor')
        self.assertEqual(item['valoare_originala'], 'Venituri anuale partide de la MF', 'the evidence is a table name of the listing')
        if item['stare'] == 'deschis':
            self.assertIn(item['prioritate'], ('medie', 'mica'), 'a high-priority open item would block the publication gate')
        cited = re.search(r'Dovadă: (\S+) \(text păstrat, sha256 ([0-9a-f]{16})\)', item['motiv'])
        self.assertEqual(cited.group(1), 'https://db.banipartide.ro/banipartide.json')
        locator = EvidenceLocator(ROOT / 'data/taxonomy-v2/observatii/inventare', ROOT / 'data/taxonomy-v2/observatii', list(self.data['sources'].values()))
        text, _ = locator.text(cited.group(1), 'sursa')
        if text is not None:  # the retained bodies are not in git: a fresh checkout cannot compare
            self.assertTrue(hashlib.sha256(text.encode()).hexdigest().startswith(cited.group(2)))
            self.assertIn('"name": "' + item['valoare_originala'] + '"', text)

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


class Scope(unittest.TestCase):
    """The states of an entry that the variable inventory leaves out. Each test builds its own scope; none pins the `relatie_date` that an editor sets."""

    @classmethod
    def setUpClass(cls):
        cls.data = report.load(PUBLIC_ROOT)
        cls.bare = [e['slug'] for e in cls.data['entries'] if e['kind'] != 'organizatie' and not cls.data['profiles'][e['slug']]['surse_structurate']
                    and e['slug'] not in cls.data['notes']['note']]
        cls.with_sources = next(e['slug'] for e in cls.data['entries'] if cls.data['profiles'][e['slug']]['surse_structurate'] and e['kind'] != 'organizatie'
                                and any(cls.data['sources'][r].get('stare') == 'analizat' for r in cls.data['profiles'][e['slug']]['surse_structurate']))

    def rows(self, scope, **changes):
        data = {**self.data, 'scope': {**self.data['scope'], **scope}, **changes}
        return {r[0]: dict(zip(report.COLUMNS, r)) for r in report.coverage_rows(data)}

    def test_an_entry_out_of_scope_gets_the_reason_as_its_state_and_no_next_step_except_for_a_missing_value(self):
        a, b, c, d = self.bare[:4]
        rows = self.rows({a: 'fara-date', b: 'inactiv', c: 'neevaluat', d: ''})
        self.assertEqual((rows[a]['stare_investigare'], rows[a]['urmatorul_pas']), ('fara-date', ''))
        self.assertEqual((rows[b]['stare_investigare'], rows[b]['urmatorul_pas']), ('inactiv', ''))
        self.assertEqual(rows[c]['stare_investigare'], 'neevaluat')
        self.assertIn('relatie_date', rows[c]['urmatorul_pas'], 'an editor sets the value; without it the entry stays out of /date/')
        self.assertEqual(rows[d]['stare_investigare'], 'neinvestigat-in-lot')
        self.assertIn('Lipsa extragerii nu înseamnă lipsa datelor', rows[d]['urmatorul_pas'], 'the old sentence stays with the entries that are in scope')
        self.assertTrue({'fara-date', 'inactiv', 'neevaluat'} <= set(report.STATES))

    def test_evidence_decides_before_scope(self):
        rows = self.rows({self.with_sources: 'inactiv'})
        self.assertEqual(rows[self.with_sources]['stare_investigare'], 'cu-surse-structurate', 'retained evidence is never hidden by the scope')
        self.assertGreater(int(rows[self.with_sources]['campuri_din_surse']), 0)
        blocked = {**self.data['notes'], 'note': {**self.data['notes']['note'], self.bare[0]: {'blocaj': 'HTTP 403'}}}
        self.assertEqual(self.rows({self.bare[0]: 'fara-date'}, notes=blocked)[self.bare[0]]['stare_investigare'], 'blocat')

    def test_an_organisation_stays_outside_the_area_and_a_hidden_entry_has_no_next_step(self):
        organisation = next(e['slug'] for e in self.data['entries'] if e['kind'] == 'organizatie')
        self.assertEqual(self.rows({organisation: 'in-afara-ariei'})[organisation]['stare_investigare'], 'in-afara-ariei')
        hidden = [{**e, 'classification_state': 'ascuns'} if e['slug'] == self.bare[0] else e for e in self.data['entries']]
        row = self.rows({self.bare[0]: 'neevaluat'}, entries=hidden)[self.bare[0]]
        self.assertEqual((row['stare_investigare'], row['urmatorul_pas']), ('neevaluat', ''))

    def test_the_tracked_table_gives_the_state_that_the_shared_rule_gives(self):
        from common import OUT_OF_SCOPE
        scope = self.data['scope']
        self.assertEqual(set(scope), {e['slug'] for e in self.data['entries']})
        table = {r[0]: r[3] for r in report.coverage_rows(self.data)}
        for slug, state in table.items():
            if state in OUT_OF_SCOPE:
                self.assertEqual(scope[slug], state, slug)
            if state == 'neinvestigat-in-lot':
                self.assertEqual(scope[slug], '', slug + ' is out of scope, so it is not "not investigated in the batch"')
        self.assertTrue(set(table.values()) <= set(report.STATES))

    def test_the_report_counts_what_the_finder_leaves_out_and_hidden_entries_apart(self):
        entries = [e for e in self.data['entries'] if e['kind'] != 'organizatie']
        pick = [e['slug'] for e in entries if e.get('classification_state') != 'ascuns'][:7]
        reasons = dict(zip(pick, ['', '', 'fara-date', 'fara-date', 'neevaluat', 'inactiv', 'inactiv']))
        scope = {**self.data['scope'], **{e['slug']: '' for e in entries}, **reasons}
        data = {**self.data, 'scope': scope}
        measured = report.metrics(data, report.coverage_rows(data))
        public = len([e for e in entries if e.get('classification_state') != 'ascuns'])
        self.assertEqual(measured['left_out'], {'fara-date': 2, 'neevaluat': 1, 'inactiv': 2})
        self.assertEqual(measured['in_scope'], public - 5)
        self.assertEqual(measured['hidden'], len(entries) - public)
        text = report.render_report(data, report.coverage_rows(data))
        self.assertIn(f'{public - 5} of the {public} public projects and resources are in scope', text)
        self.assertIn('2 without data (`fara-date`), 1 not assessed (empty value), 2 inactive', text)


if __name__ == '__main__':
    unittest.main()
