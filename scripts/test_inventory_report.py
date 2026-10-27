"""Checks for the coverage export and the readable report. They read the tracked files and fixtures only."""
import csv
import hashlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import inventory_report as report
from common import PUBLIC_ROOT, forbidden
from inventory_concepts import EvidenceLocator, selector_matches
from inventory_persons import is_marked, problems as person_problems

ROOT = Path(__file__).resolve().parents[1]
LISTA_FIRME_API = 'https://lista-firme.info/api/v1/info?cui=51859625'
# Keys of a representative record that hold a label and not an identity: a role and a country name say nothing about who the person is.
LABEL_KEYS = ('role', 'birth_country', 'current_country')


def person_values(body):
    """The string values of the person relations of a response of the lista-firme API, without the label keys. Numbers (ids) are left out."""
    values = set()
    for relation in ('legal_representatives', 'natural_person_representatives'):
        for record in body.get(relation) or []:
            values |= {v for k, v in record.items() if isinstance(v, str) and len(v) >= 4 and k not in LABEL_KEYS}
    return values


def leaked(values, files):
    """(file, fingerprint) pairs where a value is in the text of a file. The answer holds the first 8 hex digits of the SHA-256 of the value,
    never the value, so that a failing run does not print a person into a log."""
    found = []
    for path in files:
        text = Path(path).read_text(errors='replace')
        found += [(path, hashlib.sha256(value.encode()).hexdigest()[:8]) for value in sorted(values) if value in text]
    return found
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
        # The count follows the reader (a discarded personal identifier leaves the fields), so it is compared with the tracked source.
        listing = self.data['sources'][self.data['profiles']['bani-partide']['surse_structurate'][0]]
        self.assertEqual((row['surse_structurate'], row['campuri_din_surse']), ('1', str(len(listing['campuri']))))
        self.assertGreater(len(listing['campuri']), 0)
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

    # --- batch D -------------------------------------------------------------------------------------------------------------------------------
    def tracked_fields(self):
        fields = {}
        for slug, profile in self.data['profiles'].items():
            for ref in profile['surse_structurate']:
                source = self.data['sources'][ref]
                fields.setdefault(slug, []).extend(({'name': f['nume'], 'path': f['cale'], 'role': f.get('rol')}, source['url']) for f in source['campuri'])
        return fields

    def test_batch_d_is_the_twelve_entries_of_the_brief_and_each_state_follows_the_evidence(self):
        self.assertEqual(report.BATCH_D, ['lista-firme', 'dupa-cutremur', 'reciclare-arad', 'onorata-instanta', 'sondaje-romania', 'guvernezi', 'politicieni-corupti',
                                          'unde-locuiesc', 'trei-din-patru', 'statul-digital', 'pe-datorie', 'ce-face-statul-cu-1000-de-lei'])
        for reserve in ('monitor-safe', 'igov', 'ce-fac-politicienii'):
            self.assertNotIn(reserve, report.BATCH_D, 'a reserve entry joins the lot only when a primary entry is blocked')
        for slug in report.BATCH_D:
            self.assertEqual(self.by[slug]['investigat_in_lot'].split('|').count('D'), 1, slug)
            note = self.data['notes']['note'][slug]
            self.assertTrue(note['rezultat'] and note['limite'] and note['limite_en'] and note['urmator_en'], slug)
            usable = [r for r in self.data['profiles'][slug]['surse_structurate'] if self.data['sources'][r].get('stare') == 'analizat']
            self.assertEqual(self.by[slug]['stare_investigare'], 'cu-surse-structurate' if usable else 'investigat-fara-surse', slug)
            self.assertEqual(int(self.by[slug]['surse_structurate']), len(usable), slug)
            if not usable:
                self.assertTrue(self.by[slug]['urmatorul_pas'], 'an entry without a source says what could help')

    def test_an_entry_that_a_lot_touched_without_a_source_or_a_blocker_has_its_own_state_and_nothing_else_does(self):
        slug = next(e['slug'] for e in self.data['entries'] if e['kind'] != 'organizatie' and not self.data['profiles'][e['slug']]['surse_structurate']
                    and e['slug'] not in self.data['notes']['note'] and not self.data['scope'][e['slug']] and e['slug'] not in report.lots(self.data))
        rows = lambda data: {r[0]: dict(zip(report.COLUMNS, r)) for r in report.coverage_rows(data)}
        self.assertEqual(rows(self.data)[slug]['stare_investigare'], 'neinvestigat-in-lot')
        with patch.object(report, 'BATCH_D', [slug]):
            touched = rows(self.data)[slug]
            self.assertEqual((touched['investigat_in_lot'], touched['stare_investigare']), ('D', 'investigat-fara-surse'))
            self.assertEqual(touched['surse_structurate'], 0)
            self.assertEqual((touched['concepte_propuse'], touched['masuri_cu_unitate'], touched['masuri_fara_unitate']), ('', '', ''), 'unknown stays unknown')
            self.assertIn('investigat-fara-surse', report.STATES)
            notes = self.data['notes']
            blocked = {**self.data, 'notes': {**notes, 'note': {**notes['note'], slug: {'blocaj': 'HTTP 403 la cererea automată'}}}}
            self.assertEqual(rows(blocked)[slug]['stare_investigare'], 'blocat', 'a recorded blocker decides before the lot')
            hidden = {**self.data, 'scope': {**self.data['scope'], slug: 'fara-date'}}
            self.assertEqual(rows(hidden)[slug]['stare_investigare'], 'fara-date', 'the scope decides before the lot')

    def check_provider_items(self, slugs, first):
        """The provider items of the given entries from the review item D<first> on: each cites a retained copy, its hash and a fragment of it."""
        # The review state belongs to the owner, so the test does not pin it. An item still open must not block the publication gate.
        items = [r for r in self.data['review'] if r['camp'] == 'surse_date' and r['slug'] in slugs and r['id'].startswith('D') and int(r['id'][1:]) >= first]
        self.assertTrue(items)
        locator = EvidenceLocator(ROOT / 'data/taxonomy-v2/observatii/inventare', ROOT / 'data/taxonomy-v2/observatii', list(self.data['sources'].values()))
        for item in items:
            if item['stare'] == 'deschis':
                self.assertIn(item['prioritate'], ('medie', 'mica'), item['id'] + ': a high-priority open item would block the publication gate')
            self.assertTrue(item['propunere'].startswith('Furnizor propus: '), item['id'])
            self.assertIn('nu schimbă relatii.csv', item['motiv'], item['id'])
            cited = re.search(r'Dovadă: (\S+) \(text păstrat, sha256 ([0-9a-f]{16})\)', item['motiv'])
            self.assertTrue(cited, item['id'])
            copies = [text for kind in ('sursa', 'documentatie', 'cache') for text, _ in [locator.text(cited.group(1), kind)] if text is not None]
            matching = [t for t in copies if hashlib.sha256(t.encode()).hexdigest().startswith(cited.group(2))]
            if copies:  # the retained bodies are not in git: a fresh checkout cannot compare
                self.assertTrue(matching, item['id'] + ': no retained copy has the cited hash')
                self.assertTrue(any(item['valoare_originala'] in t for t in matching), item['id'])

    def test_provider_items_of_batch_d_cite_evidence_that_a_retained_copy_holds(self):
        self.check_provider_items(report.BATCH_D, 189)

    def test_provider_items_of_batch_e_cite_evidence_that_a_retained_copy_holds(self):
        self.check_provider_items(report.BATCH_E + report.RESERVES_E, 211)

    def test_a_provider_item_never_repeats_a_relation_that_the_entry_already_has(self):
        accepted = {(r['subiect'], r['obiect_literal']) for r in self.data['relations'] if r['predicat'] == 'date_din' and r['stare'] == 'acceptat'}
        for item in self.data['review']:
            if item['camp'] == 'surse_date' and item['slug'] in report.BATCH_D + report.BATCH_E + report.RESERVES_E and item['id'].startswith('D') \
                    and int(item['id'][1:]) >= 189 and item['stare'] == 'deschis':
                self.assertNotIn((item['slug'], item['propunere'].removeprefix('Furnizor propus: ')), accepted, item['id'])

    def test_the_candidate_members_of_batch_d_belong_to_reviewed_groups_match_a_field_and_are_not_members_yet(self):
        # Confirmed candidates leave the notes, so a confirmed one passes this test by being absent.
        fields = self.tracked_fields()
        groups = {c['id']: c for c in self.data['concepts']}
        for item in self.data['notes'].get('selectori_candidati', []):
            selector = item['selector']
            if not set(selector['projects']) & set(report.BATCH_D + report.BATCH_E + report.RESERVES_E):
                continue
            self.assertIn(item['grup'], groups)
            self.assertTrue(any(selector_matches(selector, slug, f, url) for slug in selector['projects'] for f, url in fields.get(slug, [])), (item['grup'], selector['names']))
            self.assertNotIn(selector, groups[item['grup']]['selectors'], 'a member leaves the candidate list when the owner confirms it')

    def test_every_selector_that_names_a_project_of_batch_d_matches_a_field_of_it(self):
        fields = self.tracked_fields()
        for group in self.data['concepts']:
            for number, selector in enumerate(group['selectors'], 1):
                if selector.get('stare') == 'exclus' or not set(selector['projects']) & set(report.BATCH_D + report.BATCH_E + report.RESERVES_E):
                    continue
                self.assertTrue(any(selector_matches(selector, slug, f, url) for slug in selector['projects'] for f, url in fields.get(slug, [])),
                                f'{group["id"]} selector {number}')

    def test_the_inventory_of_the_entries_with_records_about_persons_keeps_field_names_and_no_value(self):
        # The mark `persoane` (inventory_persons) is what keeps a source of persons to key names, types and counts. The form of each marked record is checked here from
        # the tracked files alone, so that a fresh checkout without the retained bodies checks it too.
        for slug in ('onorata-instanta', 'politicieni-corupti', 'dupa-cutremur', 'lista-firme'):
            for ref in self.data['profiles'][slug]['surse_structurate']:
                source = self.data['sources'][ref]
                if slug == 'lista-firme' and source['url'] != LISTA_FIRME_API:
                    continue  # the migrations of the repository hold columns; only the live response names persons
                self.assertTrue(is_marked(source), source['url'])
                self.assertEqual(person_problems(source), [], source['url'])
                self.assertIn(source['format'], ('csv', 'json-esantion', 'json'), source['url'])
        for group in self.data['concepts']:
            evidence = list(group.get('dovezi', [])) + [f['dovada'] for s in group['selectors'] for f in s.get('fapte', []) if f.get('dovada')]
            for item in evidence:
                if any(slug in item['sursa'] for slug in ('dupacutremur', 'posibil-penali')):
                    self.assertNotIn('"expert"', item['fragment'], 'the name of a person is not evidence of a variable')

    def test_the_live_response_of_lista_firme_is_a_source_of_key_paths_and_types_and_holds_no_value(self):
        source = next((s for s in self.data['sources'].values() if s['url'] == LISTA_FIRME_API), None)
        self.assertIsNotNone(source, 'the source of the one request that the owner allowed')
        self.assertIn(source['id'], self.data['profiles']['lista-firme']['surse_structurate'])
        self.assertEqual((source['format'], source['stare'], source['http_status']), ('json', 'analizat', 200))
        # The tracked record holds the metadata of the request and key paths. No key of it can hold a body or a sample of values.
        self.assertTrue(is_marked(source))
        self.assertEqual(person_problems(source), [])
        self.assertLessEqual(set(source), {'url', 'final_url', 'http_status', 'fetched_at', 'content_type', 'state', 'id', 'campuri', 'completitudine', 'snapshot',
                                           'sha256', 'format', 'stare', 'limita_atinsa', 'baza_tipului', 'citire', 'ultima_incercare', 'versiuni_anterioare', 'persoane'})
        types = {'string', 'integer', 'number', 'boolean', 'null', 'object', 'array'}
        self.assertTrue(source['campuri'])
        for field in source['campuri']:
            self.assertLessEqual(set(field['tipuri_observate']), types, field['cale'])
            # A key name is an identifier. A name with a space, a digit run or an accent could be a value used as a key.
            self.assertRegex(field['cale'], r'^\$(\.[A-Za-z_][A-Za-z_]*(\[\])?)+$', 'a path of the response is a chain of key names')
        notes = self.data['notes']['note']['lista-firme']
        self.assertTrue(notes['rezultat'] and notes['limite_en'] and notes['urmator_en'])
        # With the retained body (it is not in git, so a fresh checkout skips this part): no value of a person is in a file that git tracks.
        locator = EvidenceLocator(ROOT / 'data/taxonomy-v2/observatii/inventare', ROOT / 'data/taxonomy-v2/observatii', list(self.data['sources'].values()))
        text, _ = locator.text(LISTA_FIRME_API, 'sursa')
        if text is None:
            return
        values = person_values(json.loads(text))
        self.assertTrue(values, 'the check must have values to look for')
        files = [p for pattern in ('data/taxonomy-v2/observatii/inventare/*.json', 'data/taxonomy-v2/observatii/inventare/*.csv',
                                   'data/taxonomy-v2/observatii/inventare/adaugari/*.json', 'data/taxonomy-v2/*.json', 'data/taxonomy-v2/integrare/*.csv',
                                   'docs/*.md', 'docs/reports/*.md', 'docs/briefs/*.md') for p in sorted(ROOT.glob(pattern))]
        self.assertTrue(files)
        self.assertEqual(leaked(values, files), [], 'a value of a person reached a file that git tracks (the answer shows file and fingerprint)')

    def test_the_leak_check_finds_a_value_that_it_is_given(self):
        # Without this test the check above would pass for a wrong list of files or a wrong list of values.
        body = {'legal_representatives': [{'id': 7, 'person_name': 'Ana Exemplu', 'role': 'Administrator', 'birth_date': '1980-01-01T00:00:00.000000Z'}],
                'natural_person_representatives': [{'person_name': 'Ion Fictiv'}], 'name': 'A COMPANY'}
        values = person_values(body)
        self.assertEqual(sorted(values), ['1980-01-01T00:00:00.000000Z', 'Ana Exemplu', 'Ion Fictiv'], 'a role is a label, an id is a number, a company name is not a person')
        with tempfile.TemporaryDirectory() as folder:
            clean, dirty = Path(folder) / 'clean.md', Path(folder) / 'dirty.md'
            clean.write_text('Legal representatives: key names only.\n')
            dirty.write_text('The administrator is Ion Fictiv.\n')
            self.assertEqual(leaked(values, [clean, dirty]), [(dirty, hashlib.sha256(b'Ion Fictiv').hexdigest()[:8])])
            self.assertEqual(leaked(values, [clean]), [])

    def test_lista_firme_got_one_api_request_and_no_other_request_to_its_host(self):
        # The owner raised the limit of the entry for ONE request. The log is append-only, so this pins history, not an editor's choice.
        rows = [r for r in self.data['log'] if r['cache'] == 'nu' and urlsplit(r['url']).hostname == 'lista-firme.info']
        api = [r for r in rows if r['url'] == LISTA_FIRME_API]
        self.assertEqual(len(api), 1, 'one request to the API, no retry')
        self.assertEqual((api[0]['lot'], api[0]['metoda'], api[0]['stare'], api[0]['http_status']), ('D', 'GET', 'ok', '200'))
        others = [r['url'] for r in rows if r['url'] != LISTA_FIRME_API]
        self.assertFalse([u for u in others if urlsplit(u).path.startswith('/api') or 'cui=' in u or 'name=' in u or 'company=' in u], 'no other API path, CUI or name query')

    def test_the_poll_index_of_sondaje_romania_is_one_keyed_collection_that_the_browser_received_and_no_key_is_a_field_name(self):
        # `seats-index.json` has poll identifiers as keys. Before the corrected reader the keys would have become field names. The owner admitted the source on 2026-10-27.
        url = 'https://sondajeromania.ro/seats-index.json'
        source = next((s for s in self.data['sources'].values() if s['url'] == url), None)
        self.assertIsNotNone(source)
        self.assertIn(source['id'], self.data['profiles']['sondaje-romania']['surse_structurate'])
        self.assertEqual((source['format'], source['stare'], source.get('via')), ('json', 'analizat', 'browser'))
        self.assertEqual([(f['cale'], f['rol']) for f in source['campuri']], [('${*}', 'colectie-cu-chei')], 'one field: the collection, never a key')
        self.assertGreater(source['campuri'][0]['numar_chei'], 1)
        # The browser received the file, so the plain request was not made: the log has browser rows for it and no direct request.
        rows = [r for r in self.data['log'] if r['url'] == url]
        self.assertTrue(rows)
        self.assertEqual([r['url'] for r in rows if r['cache'] == 'nu'], [], 'no direct request for the index')
        locator = EvidenceLocator(ROOT / 'data/taxonomy-v2/observatii/inventare', ROOT / 'data/taxonomy-v2/observatii', list(self.data['sources'].values()))
        text, _ = locator.text(url, 'sursa')
        if text is not None:  # the retained body is not in git; a fresh checkout skips this part
            self.assertEqual(source['campuri'][0]['numar_chei'], len(json.loads(text)))

    def test_the_request_log_of_batch_d_stays_inside_the_limits_and_asks_no_listed_host(self):
        rows = [r for r in self.data['log'] if r['lot'] == 'D']
        direct = [r for r in rows if r['cache'] == 'nu']
        self.assertTrue(direct)
        self.assertLessEqual(len(direct), 120, 'the brief allows 120 direct requests in all')
        self.assertFalse([r['url'] for r in direct if forbidden(r['url'])], 'a listed host gets no request')
        self.assertEqual({r['metoda'] for r in direct}, {'GET'})
        navigations = [r for r in rows if r['metoda'] == 'BROWSER']
        self.assertEqual(len({r['url'] for r in navigations}), len(navigations), 'a page is rendered once')

    # --- batch E -------------------------------------------------------------------------------------------------------------------------------
    def test_batch_e_is_the_twelve_entries_of_the_brief_a_reserve_replaces_a_blocked_entry_and_each_state_follows_the_evidence(self):
        self.assertEqual(report.BATCH_E, ['monitor-safe', 'igov', 'companii-publice-ro', 'executii-bugetare', 'ce-cumpara-primaria', 'sicap-ai', 'open-budget', 'monitor-social',
                                          'verifica-psiholog', 'portal-just-modern', 'cat-de-tare', 'recontorizarea'])
        brief_reserves = ['de-unde-vine-apa', 'ani-de-pensie', 'ai-aflat']
        self.assertEqual(report.RESERVES_E, brief_reserves[:len(report.RESERVES_E)], 'the reserves are used in the order of the brief')
        self.assertLessEqual(len(report.RESERVES_E), 3, 'the brief allows at most three replacements')
        # A reserve joined because a primary entry was blocked; its note names that entry. The entry can leave the state `blocat` later (sicap-ai did, from a copy that the owner saved).
        for reserve in report.RESERVES_E:
            replaced = [s for s in report.BATCH_E if f'replacing {s}' in self.data['notes']['note'][reserve]['rezultat']]
            self.assertEqual(len(replaced), 1, f'the note of the reserve {reserve} names the primary entry that it replaced')
        for slug in report.BATCH_E + report.RESERVES_E:
            self.assertEqual(self.by[slug]['investigat_in_lot'].split('|').count('E'), 1, slug)
            note = self.data['notes']['note'][slug]
            self.assertTrue(note['rezultat'] and note['limite'] and note['limite_en'] and note['urmator_en'], slug)
            usable = [r for r in self.data['profiles'][slug]['surse_structurate'] if self.data['sources'][r].get('stare') == 'analizat']
            self.assertEqual(int(self.by[slug]['surse_structurate']), len(usable), slug)
            if usable:
                self.assertEqual(self.by[slug]['stare_investigare'], 'cu-surse-structurate', slug)
            elif note.get('blocaj'):
                self.assertEqual(self.by[slug]['stare_investigare'], 'blocat', slug)
                self.assertTrue(note['blocaj_en'], 'a blocked entry says why in English too')
            else:
                self.assertEqual(self.by[slug]['stare_investigare'], 'investigat-fara-surse', slug)
                self.assertTrue(self.by[slug]['urmatorul_pas'], 'an entry without a source says what could help')

    def test_a_blocked_entry_of_batch_e_got_no_new_request_to_its_host_after_the_answer_that_blocked_it(self):
        rows = [r for r in self.data['log'] if r['lot'] == 'E' and r['cache'] == 'nu']
        self.assertFalse([r['url'] for r in rows if urlsplit(r['url']).hostname in ('sicap.ai', 'www.sicap.ai')], 'sicap.ai answered HTTP 429: the batch rule is to stop on that host')
        # open-budget did not refuse; it never answered. One direct request and one browser render were the only attempts of the batch.
        self.assertEqual(len([r for r in rows if urlsplit(r['url']).hostname == 'www.openbudget.ro']), 1)
        navigations = [r for r in self.data['log'] if r['lot'] == 'E' and r['metoda'] == 'BROWSER' and 'openbudget' in r['url']]
        self.assertEqual(len(navigations), 1)

    def test_sicap_ai_is_read_from_a_copy_that_the_owner_saved_and_from_a_repository_at_a_recorded_commit_without_a_request_to_its_host(self):
        slug = 'sicap-ai'
        sources = [self.data['sources'][ref] for ref in self.data['profiles'][slug]['surse_structurate']]
        contract = [s for s in sources if s['format'] == 'openapi']
        self.assertTrue(contract, 'the contract that the owner saved')
        for source in contract:
            self.assertEqual((source['origine'], source['citire'], source['stare']), ('copie-salvata-de-proprietar', 'openapi-yaml', 'analizat'))
            self.assertIsNone(source['http_status'], 'a saved copy has no HTTP status')
            self.assertTrue(all('linie' in f for f in source['campuri']), 'a YAML contract gives the line of each declaration')
        code = [s for s in sources if s['format'] == 'typescript']
        self.assertTrue(code, 'the type declarations of the public repository')
        commits = {re.search(r'/ciocan/SICAP\.ai/([0-9a-f]{40})/', s['url']).group(1) for s in code}
        self.assertEqual(len(commits), 1, 'all files are read at one recorded commit')
        registry = [r for r in self.data['registry'] if r['proiect'] == slug and r['stare'] == 'activ' and r['metoda'] == 'repo-la-revizie']
        self.assertEqual(len(registry), len(code))
        for record in registry:
            self.assertEqual(record['dovada']['revizie'], commits.copy().pop())
            self.assertTrue(record['dovada']['blob_sha'] and record['dovada']['sha256'], 'the tree entry and the listing are pinned')
        self.assertEqual(self.by[slug]['stare_investigare'], 'cu-surse-structurate')
        self.assertEqual(self.by[slug]['investigat_in_lot'], 'E|S')
        # The host is on the list, so no script requested it: the log has no row for it, and the repository took at most 15 direct requests.
        self.assertIsNotNone(forbidden('https://api.sicap.ai/v1/openapi'))
        self.assertIsNotNone(forbidden('https://sicap.ai/api/mcp'))
        rows = [r for r in self.data['log'] if r['cache'] == 'nu' and '/ciocan/SICAP.ai' in r['url']]
        self.assertTrue(rows)
        self.assertLessEqual(len(rows), 15, 'at most 15 direct requests for this entry')
        self.assertEqual({urlsplit(r['url']).hostname for r in rows} - {'api.github.com', 'raw.githubusercontent.com'}, set())
        self.assertFalse([r for r in self.data['log'] if (urlsplit(r['url']).hostname or '').endswith('sicap.ai') and r['lot'] == 'E'])

    def test_the_request_log_of_batch_e_stays_inside_the_limits_and_asks_no_listed_host(self):
        rows = [r for r in self.data['log'] if r['lot'] == 'E']
        direct = [r for r in rows if r['cache'] == 'nu']
        self.assertTrue(direct)
        self.assertLessEqual(len(direct), 120, 'the brief allows 120 direct requests in all, retries included')
        self.assertFalse([r['url'] for r in direct if forbidden(r['url'])], 'a listed host gets no request')
        self.assertEqual({r['metoda'] for r in direct}, {'GET'})
        entries_on = {}
        for entry in self.data['entries']:
            if entry['slug'] in report.BATCH_E + report.RESERVES_E:
                entries_on[urlsplit(entry['url']).hostname.removeprefix('www.')] = entries_on.get(urlsplit(entry['url']).hostname.removeprefix('www.'), 0) + 1
        per_host = {}
        for r in direct:
            host = urlsplit(r['url']).hostname.removeprefix('www.')
            per_host[host] = per_host.get(host, 0) + 1
        for host, count in per_host.items():
            self.assertLessEqual(count, 15 * max(1, entries_on.get(host, 1)), f'at most 15 direct requests for each entry: {host}')
        navigations = {}
        for r in rows:
            if r['metoda'] == 'BROWSER':
                slug = r['scop'].removeprefix('randare ')
                navigations[slug] = navigations.get(slug, 0) + 1
        self.assertTrue(navigations)
        self.assertTrue(all(count <= 2 for count in navigations.values()), 'at most two browser pages for each entry')
        self.assertTrue(set(navigations) <= set(report.BATCH_E), 'only the entries of the lot were rendered')

    def test_the_sources_of_batch_e_marked_with_persons_keep_the_form_and_the_render_of_the_registry_page_kept_no_text(self):
        marked = []
        for slug in report.BATCH_E + report.RESERVES_E:
            for ref in self.data['profiles'][slug]['surse_structurate']:
                source = self.data['sources'][ref]
                if is_marked(source):
                    marked.append(source['url'])
                    self.assertEqual(person_problems(source), [], source['url'])
                    self.assertIn(source['format'], ('csv', 'json-esantion', 'json'), source['url'])
        self.assertTrue(marked, 'the registry list of verifica-psiholog holds records about persons')
        records = [json.loads(p.read_text()) for p in (ROOT / 'data/taxonomy-v2/observatii/inventare/randare').glob('verifica-psiholog-*.json')]
        self.assertTrue(records)
        for record in records:
            self.assertIsNone(record['text_randat'], 'a page that lists persons is rendered with --fara-text')

    def test_every_lot_e_source_with_an_inventory_is_a_read_source_and_the_new_readers_are_known_to_the_site(self):
        from inventory_site import FORMATS
        for slug in report.BATCH_E + report.RESERVES_E:
            for ref in self.data['profiles'][slug]['surse_structurate']:
                source = self.data['sources'][ref]
                self.assertEqual(source.get('stare'), 'analizat', source['url'])
                self.assertIn(source['format'], FORMATS, 'the field browser needs a label for the format: ' + source['url'])

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
