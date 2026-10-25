"""Offline checks for INS TEMPO metadata: captured responses (scripts/fixtures/ins), the indicator / dimension / value
distinction, declared against computed facts, and honest missing values."""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, parse_source
from inventory_ins import ins_dataset, ins_listing, is_listing, listed, plain

FIXTURES = Path(__file__).parent / 'fixtures/ins'
ACC = 'https://ins.gov2.ro/api/datasets/ACC102B?lang=en'
POP = 'https://ins.gov2.ro/api/datasets/POP107D?lang=en'
LISTING = 'https://ins.gov2.ro/api/datasets?limit=1'


def fixture(name):
    return (FIXTURES / name).read_text()


def source(url, name):
    return analyse_source({'url': url, 'final_url': url, 'state': 'ok', 'body': fixture(name), 'http_status': 200,
                           'content_type': 'application/json', 'fetched_at': '2026-10-25T00:00:00+00:00'})


class InsListing(unittest.TestCase):
    def test_listing_is_recognised_from_its_real_schema_and_is_a_sample(self):
        body = fixture('listing-limit1.json')
        fmt, fields, _ = parse_source(body, LISTING)
        self.assertEqual(fmt, 'lista-ins')
        self.assertIn('$.datasets[].matrix_code', [f['cale'] for f in fields])
        self.assertTrue(all(f['stare_tip'] == 'observat-in-esantion-json' for f in fields))
        record = source(LISTING, 'listing-limit1.json')
        self.assertEqual(record['baza_tipului'], 'esantion-date')
        catalog = record['catalog']
        self.assertEqual((catalog['total']['valoare'], catalog['carduri_in_esantion'], catalog['complet']), (3368, 1, False))
        self.assertEqual(catalog['carduri'][0]['matrix_code']['pointer'], '/datasets/0/matrix_code')
        self.assertNotIn('offset', json.dumps(catalog), 'a one-card listing does not verify pagination')

    def test_other_json_with_a_datasets_member_is_not_a_listing(self):
        self.assertFalse(is_listing({'total': 2, 'datasets': [{'name': 'x'}]}))
        self.assertFalse(is_listing({'datasets': [{'matrix_code': 'A'}]}))
        self.assertTrue(is_listing({'total': 5, 'datasets': []}))
        self.assertEqual(ins_listing({'total': 1, 'datasets': [{'matrix_code': 'A'}]})['complet'], True)


class InsMetadata(unittest.TestCase):
    def setUp(self):
        self.record = source(ACC, 'ACC102B-trimmed.json')
        self.facts = self.record['set_date']

    def test_dimensions_are_variables_but_their_values_are_not(self):
        self.assertEqual(self.record['format'], 'metadate-ins')
        dimensions = [f for f in self.record['campuri'] if f['rol'] == 'dimensiune']
        self.assertEqual([f['nume'] for f in dimensions], ['CATEGORY', 'REF_AREA', 'TIME_PERIOD', 'UNIT_MEASURE'])
        self.assertTrue(all(f['stare_tip'] == 'declarat-in-metadate' for f in dimensions))
        self.assertEqual([f['nume'] for f in self.record['campuri'] if f['rol'] == 'masura'], ['OBS_VALUE'], 'one measure, not one per value')
        names = {f['nume'] for f in self.record['campuri']}
        self.assertFalse(names & {'Total', 'Fatal', 'Bihor', '1992'})
        category = self.facts['dimensiuni'][0]
        self.assertEqual((category['numar_optiuni_declarat'], category['numar_optiuni_in_raspuns']), (6, 4))
        self.assertTrue(category['trunchiat'])

    def test_codes_keep_the_source_code_next_to_the_display_label(self):
        examples = self.facts['dimensiuni'][0]['exemple_coduri']
        self.assertEqual((examples[1]['cod'], examples[1]['eticheta'], examples[1]['id_sursa']),
                         ('Incapacitate temporara de munca', 'Temporary incapacity of work', 5734))
        self.assertEqual(examples[1]['pointer'], '/dimensions/0/options/1')

    def test_declared_computed_and_counted_facts_are_labelled_apart(self):
        self.assertEqual(self.facts['cod']['baza'], 'declarat-in-metadate')
        self.assertEqual(self.facts['definitie_indicator']['pointer'], '/definitie')
        self.assertEqual(self.facts['perioada']['an_min']['baza'], 'calculat-de-api')
        self.assertEqual((self.facts['perioada']['an_min']['valoare'], self.facts['perioada']['an_max']['valoare']), (1992, 2023))
        self.assertEqual(self.facts['niveluri_geografice']['valoare'], ['county', 'macroregion', 'national', 'region'])
        counted = self.facts['dimensiuni'][1]['niveluri_in_optiuni']
        self.assertEqual(counted['baza'], 'observat-in-optiuni')
        self.assertEqual(counted['valoare'], {'county': 1, 'macroregion': 1, 'national': 1, 'region': 1})

    def test_unit_is_a_dimension_value_and_an_untyped_unit_stays_untyped(self):
        units = {u['cod']: u for u in self.facts['unitati']}
        self.assertEqual(units['Numar persoane']['tip_unitate'], 'count')
        self.assertIsNone(units['Promile']['tip_unitate'])
        self.assertEqual(units['Promile']['tip_optiune'], 'indicator')
        self.assertTrue(all(f.get('unitate') is None for f in self.record['campuri'] if f['rol'] == 'dimensiune'), 'a dimension carries no unit of its own')
        measure = next(f for f in self.record['campuri'] if f['nume'] == 'OBS_VALUE')
        self.assertIsNone(measure['unitate'], 'two declared units: neither is chosen')
        self.assertEqual(measure['unitati_declarate'], ['Numar persoane', 'Promile'])
        pop = next(f for f in source(POP, 'POP107D-trimmed.json')['campuri'] if f['nume'] == 'OBS_VALUE')
        self.assertEqual((pop['unitate'], pop['stare_tip']), ('Numar persoane', 'declarat-in-documentatie-api'))
        self.assertIn('numarul persoanelor', pop['descriere'])
        self.assertEqual(pop['dovada_externa']['url'], 'https://ins.gov2.ro/llms.txt')

    def test_original_source_note_is_kept_verbatim_and_no_publisher_or_licence_is_invented(self):
        note = self.facts['observatii']
        self.assertIn('Inspectia muncii', note['valoare'])
        self.assertEqual(note['pointer'], '/observatii')
        self.assertIsNone(self.facts['licenta'])
        self.assertIn('no licence', self.facts['licenta_motiv'])
        flat = json.dumps(self.facts, ensure_ascii=False)
        self.assertNotIn('Institutul Național', flat)
        self.assertNotIn('furnizor', flat)

    def test_leading_zero_free_codes_and_locality_code_tokens_are_strings(self):
        pop = source(POP, 'POP107D-trimmed.json')['set_date']
        locality = pop['dimensiuni'][3]
        self.assertEqual(locality['nume'], 'REF_AREA_2')
        self.assertEqual(locality['exemple_coduri'][1]['cod'], '1017 MUNICIPIUL ALBA IULIA')
        self.assertTrue(all(isinstance(e['cod'], str) for e in locality['exemple_coduri']))
        self.assertEqual(pop['unitati'][0]['tip_unitate'], 'count')
        self.assertEqual([d['nume'] for d in pop['dimensiuni']], ['AGE', 'SEX', 'REF_AREA', 'REF_AREA_2', 'TIME_PERIOD', 'UNIT_MEASURE'])

    def test_missing_members_stay_missing(self):
        facts = ins_dataset({'matrix_code': 'X1', 'dimensions': []})
        self.assertIsNone(facts['definitie_indicator'])
        self.assertIsNone(facts['actualizat'])
        self.assertNotIn('perioada', facts)
        self.assertEqual(facts['dimensiuni'], [])
        self.assertIsNone(ins_dataset({'matrix_code': 'X1', 'dimensions': [], 'profile': {'geo_levels': 'not json'}})['niveluri_geografice'])

    def test_markup_in_a_declared_text_is_removed_and_its_links_kept(self):
        text, links = plain('Raport: <a href="https://insse.ro/r.pdf" target="_blank"> Raport de calitate </a><br>Alt rand')
        self.assertEqual(text, 'Raport: Raport de calitate\nAlt rand')
        self.assertEqual(links, ['https://insse.ro/r.pdf'])
        facts = ins_dataset({'matrix_code': 'X', 'metodologie': '<a href="https://insse.ro/r.pdf">Raport</a>', 'dimensions': []})
        self.assertEqual((facts['metodologie']['transformare'], facts['metodologie']['legaturi']), ('marcaj-eliminat', ['https://insse.ro/r.pdf']))
        self.assertEqual(listed('["county", "national"]'), ['county', 'national'])

    def test_evidence_check_recomputes_dataset_facts_from_the_retained_body(self):
        record = source(ACC, 'ACC102B-trimmed.json')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps({'url': ACC, 'final_url': ACC, 'state': 'ok', 'body': fixture('ACC102B-trimmed.json')}))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            (out / 'seturi-date.json').write_text(json.dumps({'surse': [record]}))
            self.assertEqual(check_report(out, out)['errors'], [])
            record['set_date']['perioada']['an_max']['valoare'] = 2030
            (out / 'seturi-date.json').write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('Dataset facts differ' in e for e in check_report(out, out)['errors']))

    def test_the_documentation_sentence_behind_the_measure_is_checked_against_the_collected_page(self):
        record = source(ACC, 'ACC102B-trimmed.json')
        llms = 'https://ins.gov2.ro/llms.txt'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps({'url': ACC, 'final_url': ACC, 'state': 'ok', 'body': fixture('ACC102B-trimmed.json')}))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            (out / 'seturi-date.json').write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('external evidence' in u for u in check_report(out, out)['unavailable']), 'no collected page: unavailable, not verified')
            (out / 'documentare/pagini').mkdir(parents=True)
            index = {'entries': [{'slug': 'ins-gov2', 'pages': [{'final_url': llms, 'state': 'colectat', 'snapshot': 'pagini/llms.json'}]}]}
            (out / 'documentare/index.json').write_text(json.dumps(index))
            (out / 'documentare/pagini/llms.json').write_text(json.dumps({'text': '- **OBS_VALUE**: The numeric observation value column in all data responses.'}))
            self.assertEqual(check_report(out, out)['errors'], [])
            (out / 'documentare/pagini/llms.json').write_text(json.dumps({'text': 'The column was renamed.'}))
            self.assertTrue(any('External evidence' in e for e in check_report(out, out)['errors']))


if __name__ == '__main__':
    unittest.main()
