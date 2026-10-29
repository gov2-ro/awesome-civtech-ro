"""Offline synthetic checks for the site structure pilot contract (SP01–SP10)."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from check_structure_pilot import (
    PROJECTS, PilotError, assertion_id, validate, validate_refresh,
)

TIME = '2026-10-30T00:00:00+00:00'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))


def profile(slug):
    evidence = slug + '-evidence'
    return {
        'schema_version': 1, 'project_slug': slug, 'input_url': 'https://example.test/',
        'attempts': [{'id': 'first', 'started_at': TIME, 'finished_at': TIME, 'method': 'retained',
                      'tool_version': 'fixture', 'request_budget': 30, 'requests_used': 0,
                      'outcome': 'partial', 'incomplete_reasons': ['Synthetic bounded pass.']}],
        'collections': [{'id': 'companies', 'label': 'Firme', 'entity_type': 'company',
                         'coverage': 'Synthetic only.', 'evidence': [evidence]}],
        'namespaces': [{'id': key, 'issuer': 'Synthetic issuer', 'scope': 'Synthetic records',
                        'normalization': 'identity', 'evidence': [evidence]}
                       for key in ('ro:cui', slug + ':companies:id')],
        'patterns': [{'id': 'detail', 'collection': 'companies', 'kind': 'detail', 'basis': 'declared',
                      'url_template': 'https://example.test/company/{id}',
                      'variables': [{'name': 'id', 'location': 'path', 'namespace': slug + ':companies:id',
                                     'encoding': 'percent'}],
                      'examples': ['https://example.test/company/local-1'], 'extraction': 'path id',
                      'declaration_evidence': evidence, 'evidence': [evidence]}],
        'operations': [{'id': 'api', 'collection': 'companies', 'method': 'GET', 'purpose': 'detail',
                        'url_template': 'https://example.test/api/company', 'variables': [],
                        'basis': ['documented'], 'authentication': 'unknown', 'parameters': [],
                        'request_body': {}, 'response_paths': {}, 'pagination': {}, 'headers': [],
                        'content_types': [], 'last_test': {'outcome': 'unchecked', 'reason': 'Fixture'},
                        'page_patterns': ['detail'], 'evidence': [evidence]}],
        'identifier_rules': [{'id': 'self', 'collection': 'companies', 'namespace': 'ro:cui',
                              'location': '/cui', 'subject_role': 'self', 'normalization': 'identity',
                              'evidence': [evidence]}],
        'relationships': [],
        'evidence': [{'id': evidence, 'source': 'https://example.test/docs', 'method': 'retained',
                      'observed_at': TIME, 'artifact': 'evidence/example.txt',
                      'sha256': hashlib.sha256(b'CUI 100; local-1; /company/{id}').hexdigest(),
                      'locator': {'type': 'text', 'start': 0, 'end': 30},
                      'excerpt': 'CUI 100; local-1; /company/{id}', 'applicability': 'historical'}],
        'checks': [{'id': 'sample', 'attempt': 'first', 'outcome': 'unchecked', 'reason': 'Synthetic sample'}],
    }


def record(slug):
    return {
        'key': '|'.join([slug, 'companies', slug + ':companies:id', 'local-1']),
        'project': slug, 'collection': 'companies', 'local_namespace': slug + ':companies:id',
        'local_value': 'local-1', 'entity_type': 'company', 'locators': ['https://example.test/company/local-1'],
        'identifiers': [{'namespace': slug + ':companies:id', 'value': 'local-1', 'raw_value': 'local-1', 'subject_role': 'self'},
                        {'namespace': 'ro:cui', 'value': '100', 'raw_value': '100', 'subject_role': 'self'}],
        'evidence': [slug + '-evidence'], 'validity': 'unknown',
    }


class StructurePilot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'profiles').mkdir()
        (self.root / 'evidence').mkdir()
        body = 'CUI 100; local-1; /company/{id}'
        (self.root / 'evidence/example.txt').write_text(body)
        self.profiles = {s: profile(s) for s in PROJECTS}
        for p in self.profiles.values():
            p['evidence'][0]['locator']['end'] = len(body)
        self.slugs = sorted(PROJECTS)[:2]
        records = [record(s) for s in self.slugs]
        keys = [r['key'] for r in records]
        self.doc = {'schema_version': 1, 'records': records, 'assertions': [
            {'id': assertion_id('same_entity', keys), 'kind': 'same_entity', 'records': keys,
             'basis': 'shared_identifier', 'evidence': [s + '-evidence' for s in self.slugs], 'limitations': ['Synthetic only.']}]}
        self.decisions = []
        self.requests = []

    def save(self):
        for s, p in self.profiles.items():
            write(self.root / 'profiles' / (s + '.json'), p)
        write(self.root / 'correspondences.json', self.doc)
        write(self.root / 'decisions.json', self.decisions)
        (self.root / 'requests.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in self.requests))

    def check(self):
        self.save()
        return validate(self.root)

    def bad(self, message):
        with self.assertRaisesRegex(PilotError, message):
            self.check()

    @property
    def p(self):
        return self.profiles[self.slugs[0]]

    def test_SP01_four_profiles(self):
        self.assertEqual(len(self.check()[0]), 4)
        self.assertEqual(self.decisions, [], 'validation never creates decisions')

    def test_SP01_missing_profile(self):
        del self.profiles[self.slugs[0]]
        self.bad('four profiles')

    def test_SP02_two_distinct_examples_for_inference(self):
        pat = self.p['patterns'][0]
        pat['basis'] = 'inferred'
        pat['examples'] *= 2
        self.bad('distinct examples')
        pat['examples'].append('https://example.test/company/local-2')
        self.check()

    def test_SP02_declared_route_needs_evidence(self):
        self.p['patterns'][0]['declaration_evidence'] = 'missing'
        self.bad('route evidence')

    def test_SP02_example_must_match_template(self):
        self.p['patterns'][0]['examples'] = ['https://example.test/wrong/local-1']
        self.bad('does not match')

    def test_SP02_unknown_variable_namespace(self):
        self.p['patterns'][0]['variables'][0]['namespace'] = 'unknown'
        self.bad('variable namespace')

    def test_SP03_documentation_is_not_testing(self):
        self.p['operations'][0]['basis'].append('tested')
        self.bad('timestamp')

    def test_SP03_mutation_not_allowed(self):
        op = self.p['operations'][0]
        op.update(method='POST', read_only_evidence=op['evidence'][0], request_body={'query': 'mutation Delete { deleteAll }'})
        self.bad('read query')

    def test_SP03_post_needs_read_only_evidence(self):
        self.p['operations'][0]['method'] = 'POST'
        self.bad('read-only evidence')

    def test_SP04_related_identifier_cannot_identify_record(self):
        self.doc['records'][0]['identifiers'][1]['subject_role'] = 'buyer'
        self.bad('related identifier')

    def test_SP04_contract_cui_cannot_be_self(self):
        self.doc['records'][0]['entity_type'] = 'contract'
        self.p['collections'][0]['entity_type'] = 'contract'
        self.bad('contract cannot identify itself')

    def test_SP05_local_to_shared_mapping(self):
        result = self.check()
        self.assertEqual(len(result[1]), 2)
        for r in result[1].values():
            self.assertEqual({i['namespace'] for i in r['identifiers']}, {r['local_namespace'], 'ro:cui'})

    def test_SP06_pair_is_stable_under_reversal(self):
        a = self.doc['assertions'][0]
        a['records'].reverse()
        self.check()
        self.assertEqual(a['id'], assertion_id(a['kind'], a['records']))

    def test_SP06_orphan_record(self):
        self.doc['assertions'][0]['records'][0] = 'missing'
        self.bad('unknown assertion record')

    def test_SP06_both_records_need_evidence(self):
        self.doc['assertions'][0]['evidence'].pop()
        self.bad('both records')

    def test_SP07_name_candidate_stays_proposed(self):
        self.doc['assertions'][0]['basis'] = 'name_candidate'
        self.check()
        self.decisions = [{'assertion_id': self.doc['assertions'][0]['id'], 'state': 'accepted',
                           'note': 'Same name only.', 'decided_at': TIME}]
        self.bad('name alone')

    def test_SP07_bare_equal_local_ids_do_not_match(self):
        for r in self.doc['records']:
            r['identifiers'] = r['identifiers'][:1]
        self.bad('common namespace')

    def test_SP07_incompatible_subjects(self):
        self.doc['records'][0]['entity_type'] = 'territory'
        self.p['collections'][0]['entity_type'] = 'territory'
        self.bad('incompatible identity')

    def test_SP07_generated_acceptance_is_rejected(self):
        self.doc['assertions'][0]['state'] = 'accepted'
        self.bad('editorial state')

    def test_SP08_forbidden_host_even_without_success(self):
        self.requests = [dict(project_slug=self.slugs[0], attempt='first', url='https://api.sicap.ai/v1/openapi',
                              method='GET', channel='direct', checked_at=TIME, sent=True,
                              outcome='error', reason='Failure is still a request.', bytes=0, truncated=False)]
        self.p['attempts'][0]['requests_used'] = 1
        self.bad('forbidden host requested')
        self.requests[0].update(sent=False, outcome='skipped', reason='colectare-interzisa')
        self.p['attempts'][0]['requests_used'] = 0
        self.check()

    def test_SP08_request_count_must_agree(self):
        self.p['attempts'][0]['requests_used'] = 1
        self.bad('accounting mismatch')

    def test_SP08_budget_is_enforced(self):
        self.p['attempts'][0]['requests_used'] = 31
        self.bad('request budget')

    def test_SP08_partial_checks_cannot_be_success(self):
        self.p['attempts'][0]['outcome'] = 'observed'
        self.bad('uncertain check')

    def test_SP09_evidence_hash(self):
        self.p['evidence'][0]['sha256'] = '0' * 64
        self.bad('hash mismatch')

    def test_SP09_evidence_locator(self):
        self.p['evidence'][0]['locator']['start'] = 5
        self.bad('does not occur')

    def test_SP09_path_cannot_leave_pilot(self):
        self.p['evidence'][0]['artifact'] = '../outside.txt'
        self.bad('leaves pilot')

    def test_SP09_duplicate_keys(self):
        self.p['patterns'] *= 2
        self.bad('duplicate')

    def test_SP09_identifier_must_occur_in_evidence(self):
        self.doc['records'][0]['identifiers'][1]['raw_value'] = 'invented'
        self.bad('absent from record evidence')

    def test_SP07_normalization_needs_evidence(self):
        self.doc['records'][0]['identifiers'][1]['value'] = '200'
        self.bad('normalization needs evidence')

    def test_SP07_namespace_issuer_conflict(self):
        self.p['namespaces'][0]['issuer'] = 'Different issuer'
        self.bad('namespace issuer conflict')

    def test_SP09_inventory_reference_is_resolved(self):
        self.p['evidence'][0]['inventory_reference'] = {'path': 'docs/missing.json', 'source_id': 'missing', 'pointer': '/surse/0'}
        self.bad('invalid inventory path')

    def test_SP09_unknown_evidence(self):
        self.p['patterns'][0]['evidence'] = ['missing']
        self.bad('unknown evidence')

    def test_SP09_record_type_must_match_collection(self):
        self.doc['records'][0]['entity_type'] = 'territory'
        self.bad('collection subject types differ')

    def test_SP09_json_pointer_locator(self):
        text = '{"a/b": "evidence"}'
        (self.root / 'evidence/pointer.json').write_text(text)
        e = self.p['evidence'][0]
        e.update(artifact='evidence/pointer.json', sha256=hashlib.sha256(text.encode()).hexdigest(),
                 locator={'type': 'json_pointer', 'pointer': '/a~1b'}, excerpt='evidence')
        self.doc = {'schema_version': 1, 'records': [], 'assertions': []}
        self.check()
        e['locator']['pointer'] = '/missing'
        self.bad('unresolved JSON pointer')

    def test_SP09_wrong_type_is_rejected(self):
        self.p['collections'] = {}
        self.bad('invalid collections')

    def test_SP10_failed_refresh_preserves_evidence(self):
        previous = self.check()
        current = copy.deepcopy(previous)
        for p in current[0].values():
            p['attempts'].append({**p['attempts'][0], 'id': 'refresh', 'outcome': 'error'})
            for e in p['evidence']:
                e['applicability'] = 'stale'
        validate_refresh(previous, current)
        del current[0][self.slugs[0]]['patterns'][:]
        with self.assertRaisesRegex(PilotError, 'lost patterns'):
            validate_refresh(previous, current)

    def test_SP10_failed_refresh_requires_stale_mark(self):
        previous = self.check()
        current = copy.deepcopy(previous)
        with self.assertRaisesRegex(PilotError, 'mark prior evidence stale'):
            validate_refresh(previous, current)

    def test_SP10_editorial_decisions_preserved(self):
        previous = self.check()
        current = copy.deepcopy(previous)
        current[3].append({'state': 'accepted'})
        with self.assertRaisesRegex(PilotError, 'changed editorial decisions'):
            validate_refresh(previous, current)

    def test_SP10_correspondences_preserved(self):
        previous = self.check()
        current = copy.deepcopy(previous)
        current[2].clear()
        with self.assertRaisesRegex(PilotError, 'lost assertions'):
            validate_refresh(previous, current)

    def test_SP10_prior_evidence_is_immutable(self):
        previous = self.check()
        current = copy.deepcopy(previous)
        current[0][self.slugs[0]]['evidence'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(PilotError, 'overwrote retained evidence'):
            validate_refresh(previous, current)


if __name__ == '__main__':
    unittest.main()
