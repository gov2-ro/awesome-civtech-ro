"""Offline checks for business-variable groups: selector constraints, structure, evidence pins and stale detection."""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import check_report
from inventory_concepts import (EvidenceLocator, check_concepts, check_evidence, selector_matches, sha, validate_concept, validate_selector)
from inventory_site import variable_matches
from inventory_state import source_id

A, B = 'https://ins.example/api/POP', 'https://ins.example/api/ACC'


def field(name, source='s1', path=None, role='dimensiune'):
    return dict(name=name, path=path or name, role=role, basis='metadata', declaredType=None, observedTypes=[], unit=None,
                description='', source=source, reference='/x')


SOURCES = [{'id': 's1', 'url': A}, {'id': 's2', 'url': B}]


def matched(selector, fields=None):
    concept = [{'id': 'g', 'selectors': [selector]}]
    got = variable_matches('p', fields or [field('REF_AREA'), field('REF_AREA', 's2'), field('TIME_PERIOD')], SOURCES, concept)
    return got[0]['count'] if got else 0


class SelectorConstraints(unittest.TestCase):
    def test_names_alone_keep_the_original_behaviour(self):
        self.assertEqual(matched({'projects': ['p'], 'names': ['REF_AREA']}), 2)
        self.assertEqual(matched({'projects': ['q'], 'names': ['REF_AREA']}), 0, 'another project never matches')

    def test_a_source_narrows_an_ambiguous_name_to_one_dataset(self):
        self.assertEqual(matched({'projects': ['p'], 'names': ['REF_AREA'], 'source': A}), 1)
        self.assertEqual(matched({'projects': ['p'], 'names': ['REF_AREA'], 'source': [A, B]}), 2)
        self.assertEqual(matched({'projects': ['p'], 'names': ['REF_AREA'], 'source': 'https://other.example/'}), 0)

    def test_an_exact_path_and_a_role_narrow_a_name(self):
        fields = [field('cui', path='$.a.cui', role='camp-raspuns'), field('cui', path='cui', role='parametru-api')]
        self.assertEqual(matched({'projects': ['p'], 'names': ['cui'], 'path': ['$.a.cui']}, fields), 1)
        self.assertEqual(matched({'projects': ['p'], 'names': ['cui'], 'role': ['parametru-api']}, fields), 1)
        self.assertEqual(matched({'projects': ['p'], 'names': ['cui'], 'role': 'camp-raspuns', 'path': 'cui'}, fields), 0,
                         'a supplied constraint that fails rejects the field')
        self.assertEqual(matched({'projects': ['p'], 'path': ['$.a.cui', 'cui']}, fields), 2, 'a path alone is enough')

    def test_all_supplied_constraints_must_match_together(self):
        fields = [field('OBS_VALUE', 's1', role='masura'), field('OBS_VALUE', 's2', role='dimensiune')]
        selector = {'projects': ['p'], 'names': ['OBS_VALUE'], 'source': B, 'role': 'masura'}
        self.assertEqual(matched(selector, fields), 0)
        self.assertEqual(matched({**selector, 'source': A}, fields), 1)

    def test_alternative_selectors_of_one_group_add_up(self):
        concept = [{'id': 'g', 'selectors': [{'projects': ['p'], 'names': ['REF_AREA'], 'source': A}, {'projects': ['p'], 'names': ['TIME_PERIOD']}]}]
        got = variable_matches('p', [field('REF_AREA'), field('REF_AREA', 's2'), field('TIME_PERIOD')], SOURCES, concept)
        self.assertEqual(got[0]['count'], 2)

    def test_generic_names_do_not_create_a_match_without_a_selector(self):
        fields = [field(n, path='$.' + n, role='camp-date') for n in ('id', 'value', 'name', 'year')]
        self.assertEqual(matched({'projects': ['p'], 'names': ['cui']}, fields), 0)
        self.assertEqual(matched({'projects': ['p'], 'names': ['year'], 'path': ['$.other.year']}, fields), 0)

    def test_context_and_facts_travel_with_the_matching_field_and_examples_span_sources(self):
        selector = {'projects': ['p'], 'names': ['REF_AREA'], 'context': 'sediul firmei',
                    'fapte': [{'cheie': 'unitate', 'valoare': 'km', 'baza': 'declaratie-directa', 'dovada': {'sursa': A, 'fragment': 'x'}}]}
        fields = [field('REF_AREA'), field('REF_AREA'), field('REF_AREA'), field('REF_AREA', 's2')]
        got = variable_matches('p', fields, SOURCES, [{'id': 'g', 'selectors': [selector]}])[0]
        self.assertEqual(got['count'], 4)
        self.assertEqual(sorted({e['url'] for e in got['evidence']}), sorted([A, B]))
        self.assertEqual(got['evidence'][0]['context'], 'sediul firmei')
        self.assertEqual(got['evidence'][0]['facts'], [{'key': 'unitate', 'value': 'km', 'basis': 'declaratie-directa'}])


class Validation(unittest.TestCase):
    def test_a_selector_must_be_narrow_known_and_wellformed(self):
        self.assertEqual(validate_selector({'projects': ['p'], 'names': ['a']}, 'g'), [])
        self.assertTrue(validate_selector({'projects': ['p']}, 'g'), 'no names and no path would match every field')
        self.assertTrue(validate_selector({'names': ['a']}, 'g'))
        self.assertTrue(validate_selector({'projects': ['p'], 'names': ['a'], 'colour': 'red'}, 'g'))
        self.assertTrue(validate_selector({'projects': ['p'], 'names': ['a'], 'source': 'file:///etc/passwd'}, 'g'))

    def test_a_fact_needs_evidence_unless_it_is_an_editorial_paraphrase(self):
        bad = {'projects': ['p'], 'names': ['a'], 'fapte': [{'cheie': 'unitate', 'valoare': 'RON', 'baza': 'declaratie-directa'}]}
        self.assertTrue(validate_selector(bad, 'g'))
        ok = {'projects': ['p'], 'names': ['a'], 'fapte': [{'cheie': 'etichete', 'valoare': 'x', 'baza': 'parafraza-editoriala'}]}
        self.assertEqual(validate_selector(ok, 'g'), [])
        self.assertTrue(validate_selector({'projects': ['p'], 'names': ['a'], 'fapte': [{'cheie': 'u', 'valoare': 1, 'baza': 'ghicit'}]}, 'g'))

    def test_a_concept_needs_label_definition_selectors_and_known_values(self):
        concept = {'id': 'g', 'label': 'G', 'definition': 'D', 'categorie': 'masura', 'selectors': [{'projects': ['p'], 'names': ['a']}]}
        self.assertEqual(validate_concept(concept, {'p'}), [])
        self.assertTrue(validate_concept({**concept, 'categorie': 'altceva'}, {'p'}))
        self.assertTrue(validate_concept({**concept, 'selectors': []}, {'p'}))
        self.assertTrue(validate_concept(concept, {'other'}), 'an unknown project is an error')
        self.assertTrue(validate_concept({**concept, 'dovezi': [{'sursa': 'u', 'fragment': 'f', 'baza': 'ghicit'}]}, {'p'}))


class EvidencePins(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'inventare'
        (self.out / 'surse').mkdir(parents=True)
        self.body = '{"definitie": "Populatia dupa domiciliu reprezinta numarul persoanelor"}'
        self.source = {'id': source_id(A), 'url': A, 'snapshot': 'surse/' + source_id(A) + '-h.json'}
        (self.out / self.source['snapshot']).write_text(json.dumps({'body': self.body}))
        self.locator = EvidenceLocator(self.out, self.out.parent, [self.source], {})

    def test_status_follows_the_retained_text(self):
        pin = {'sursa': A, 'fragment': 'reprezinta numarul persoanelor', 'sha256': sha(self.body), 'baza': 'declaratie-directa'}
        self.assertEqual(check_evidence(pin, self.locator), '')
        self.assertEqual(check_evidence({**pin, 'sha256': 'old'}, self.locator), 'stale', 'the body changed after the assertion')
        self.assertEqual(check_evidence({**pin, 'fragment': 'a sentence that is not there'}, self.locator), 'fragment-missing')
        self.assertEqual(check_evidence({**pin, 'sursa': 'https://elsewhere.example/'}, self.locator), 'unavailable')

    def test_check_reports_stale_apart_from_errors_and_missing_selectors_are_errors(self):
        concept = {'id': 'pop', 'label': 'P', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['OBS_VALUE'], 'source': A},
                                                                               {'projects': ['p'], 'names': ['MISSING']}],
                   'dovezi': [{'sursa': A, 'fragment': 'numarul persoanelor', 'sha256': 'old', 'baza': 'declaratie-directa'}]}
        fields = {'p': [({'name': 'OBS_VALUE', 'path': 'OBS_VALUE', 'role': 'masura'}, A)]}
        report = check_concepts([concept], fields, self.locator, {'p'})
        self.assertEqual(report['stale'], [f'pop: {A}'])
        self.assertEqual(len(report['errors']), 1)
        self.assertIn('selector 2 matches no field', report['errors'][0])

    def test_inventory_check_includes_the_dictionary(self):
        """A fixture root with one source: the dictionary file next to `observatii/` is read by --check."""
        root = Path(self.tmp.name)
        obs = root / 'observatii'
        out = obs / 'inventare'
        (out / 'surse').mkdir(parents=True)
        response = {'url': A, 'final_url': A, 'state': 'ok', 'body': '{"a": 1}', 'content_type': 'application/json'}
        from inventory import analyse_source
        record = analyse_source(response)
        (out / record['snapshot']).write_text(json.dumps(response))
        (out / 'seturi-date.json').write_text(json.dumps({'surse': [record]}))
        (out / 'proiecte.json').write_text(json.dumps({'proiecte': [{'slug': 'p', 'stare': 'propunere', 'completitudine': 'partial',
                                                                       'surse_structurate': [record['id']], 'intrari_utilizator': []}]}))
        (root / 'inventar-concepte.json').write_text(json.dumps({'concepte': [
            {'id': 'g', 'label': 'G', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['a'], 'source': A}]},
            {'id': 'h', 'label': 'H', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['nope']}]}]}))
        report = check_report(out, obs)
        self.assertEqual(sum('matches no field' in e for e in report['errors']), 1)


class TrackedDictionary(unittest.TestCase):
    """The hand-edited dictionary against the tracked inventories."""
    ROOT = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2'
    # Supported members at v0.13.0 (unique entries). Additional evidence may add members; none may disappear.
    BASELINE = {'cui': {'companii-de-stat', 'demoanaf', 'romania-transparenta', 'transparenta-eu'},
                'cpv': {'demoanaf', 'romania-transparenta', 'achizitii-directe-ti-2026'},
                'siruta': {'romania-transparenta', 'orasul-care-se-intinde'},
                'judet': {'companii-de-stat', 'demoanaf', 'romania-transparenta', 'posturi-gov2', 'orasul-care-se-intinde'},
                'localitate': {'demoanaf', 'romania-transparenta', 'orasul-care-se-intinde'},
                'populatie': {'romania-transparenta', 'orasul-care-se-intinde'}, 'cifra-afaceri': {'companii-de-stat'}}

    @classmethod
    def setUpClass(cls):
        cls.concepts = json.loads((cls.ROOT / 'inventar-concepte.json').read_text())['concepte']
        base = cls.ROOT / 'observatii/inventare'
        cls.profiles = {p['slug']: p for p in json.loads((base / 'proiecte.json').read_text())['proiecte']}
        cls.sources = {s['id']: s for s in json.loads((base / 'seturi-date.json').read_text())['surse']}

    def members(self, concept):
        found = set()
        for slug, profile in self.profiles.items():
            for ref in profile['surse_structurate']:
                source = self.sources[ref]
                for f in source['campuri']:
                    fd = {'name': f['nume'], 'path': f['cale'], 'role': f.get('rol', 'camp-date')}
                    if any(selector_matches(s, slug, fd, source['url']) for s in concept['selectors']):
                        found.add(slug)
        return found

    def test_supported_members_survive_and_every_group_is_well_formed(self):
        by_id = {c['id']: c for c in self.concepts}
        for cid, expected in self.BASELINE.items():
            with self.subTest(concept=cid):
                self.assertTrue(expected <= self.members(by_id[cid]), expected - self.members(by_id[cid]))
        for concept in self.concepts:
            with self.subTest(concept=concept['id']):
                self.assertEqual(validate_concept(concept, set(self.profiles)), [])
                self.assertIn(concept['categorie'], ('identificator', 'dimensiune', 'masura', 'iesire-derivata'))
                self.assertEqual(concept['baza_definitiei'], 'parafraza-editoriala', 'the Romanian definition is editorial wording')
                self.assertTrue(concept['dovezi'] or concept['id'] in self.BASELINE, 'a new group needs evidence')

    def test_ambiguous_name_joins_a_group_for_one_dataset_and_not_for_another(self):
        county = next(c for c in self.concepts if c['id'] == 'judet')
        mixed = 'https://ins.gov2.ro/api/datasets/TRN139A?lang=en'
        county_sources = {u for s in county['selectors'] for u in (s.get('source') if isinstance(s.get('source'), list) else [s.get('source')]) if u}
        self.assertNotIn(mixed, county_sources)
        self.assertNotIn('https://ins.gov2.ro/api/datasets/ACC102B?lang=en', county_sources)
        self.assertIn('https://ins.gov2.ro/api/datasets/POP107D?lang=en', county_sources)

    def test_internal_ids_and_generic_names_are_not_swept_into_shared_groups(self):
        grouped = {}
        for concept in self.concepts:
            for slug in self.members(concept):
                grouped.setdefault(slug, set()).add(concept['id'])
        # Rezultate Vot exposes county_id, locality_id, section and id; none of them is a group member by spelling.
        self.assertNotIn('judet', grouped.get('rezultate-vot', set()))
        self.assertNotIn('localitate', grouped.get('rezultate-vot', set()))
        self.assertNotIn('siruta', grouped.get('rezultate-vot', set()))
        self.assertNotIn('cui', grouped.get('europescope', set()))

    def test_three_voting_measures_and_the_political_group_are_shared_without_a_join_claim(self):
        by_id = {c['id']: c for c in self.concepts}
        for cid in ('voturi-pentru', 'voturi-impotriva', 'voturi-abtinere', 'grup-politic'):
            self.assertEqual(self.members(by_id[cid]), {'europescope', 'monitorul-ai'})
            self.assertTrue(by_id[cid]['ambiguitati'], cid)

    def test_unknown_units_stay_unknown(self):
        by_id = {c['id']: c for c in self.concepts}
        facts = {(c['id'], f['cheie']): f for c in self.concepts for s in c['selectors'] for f in s.get('fapte', [])}
        self.assertEqual(facts[('co2', 'unitate')]['valoare'], 'ppm')
        for cid in ('pm10', 'presiune-atmosferica', 'viteza-vantului', 'cifra-afaceri', 'profit-net'):
            self.assertNotIn((cid, 'unitate'), facts, cid)
        self.assertTrue(by_id['pm10']['ambiguitati'])


if __name__ == '__main__':
    unittest.main()
