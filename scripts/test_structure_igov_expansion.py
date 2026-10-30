"""Checks for igov enrichment and the third structure enrollment batch."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from common import forbidden
from structure_curation import apply_recipe,profile_urls
from structure_state import blank,check

ROOT=Path(__file__).resolve().parents[1]
RECIPES=ROOT/'data/taxonomy-v2/structura/recipes'


class IgovExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.out=Path(cls.temp.name);cls.store=blank();cls.recipes={}
        for p in sorted(RECIPES.glob('*.json')):
            recipe=json.loads(p.read_text());cls.recipes[recipe['project_slug']]=recipe
            cls.store=apply_recipe(cls.store,cls.out,recipe,p)
        check(cls.store,cls.out)

    def records(self,slug):return [r for r in self.store['records'] if r['project']==slug]

    def test_igov_legacy_record_keys_and_explicit_cuis_survive(self):
        records=self.records('igov')
        expected={'1973096':'inst_cui-1973096_89f11b5bc5','31029694':'inst_cui-31029694_fbc8ca0d0e'}
        for cui,local in expected.items():
            record=next(r for r in records if r['key']=='igov|companies|igov:companies:id|'+local)
            self.assertIn(('ro:cui',cui),{(i['namespace'],i['value']) for i in record['identifiers']})
        self.assertTrue(any(r['local_value']=='inst_cui-8359779_f989662eb7' for r in records))

    def test_igov_canonical_ids_have_their_own_namespace_and_profile_route(self):
        canonical=[r for r in self.records('igov') if r['local_namespace']=='igov:organizations:id']
        self.assertEqual(len(canonical),2)
        for record in canonical:
            ids={i['namespace']:i['value'] for i in record['identifiers']}
            self.assertNotIn('igov:companies:id',ids,'Null registry_id cannot establish a legacy-ID correspondence.')
            self.assertTrue(ids['igov:organizations:id'].startswith('cui-'))
            self.assertEqual(profile_urls(self.store,record)[0]['url'],'https://igov.ro/organizatii/'+ids['igov:organizations:id'])
        legacy=next(r for r in self.records('igov') if r['local_value']=='inst_cui-1973096_89f11b5bc5')
        self.assertEqual(profile_urls(self.store,legacy),[],'A catalogue route must not be grafted onto a legacy report node.')

    def test_monitor_safe_keeps_both_typed_fragment_patterns(self):
        records=self.records('monitor-safe');self.assertEqual({r['entity_type'] for r in records},{'contract','funding_project'})
        patterns=[p for p in self.store['projects']['monitor-safe']['patterns'].values() if p['kind']=='detail']
        self.assertEqual(len(patterns),2,'Distinct collection bindings must survive the shared fragment grammar.')
        for record in records:
            self.assertEqual(len(profile_urls(self.store,record)),1)
            self.assertEqual(profile_urls(self.store,record)[0]['url'],'https://monitorsafe.ro/contracte/#'+record['local_value'])
            if record['entity_type']=='funding_project':self.assertEqual(record['record_grain'],'proposal')

    def test_purchase_rows_do_not_create_party_ids_from_names(self):
        records=self.records('achizitii-directe-ti-2026');self.assertTrue(records)
        for record in records:
            self.assertEqual(record['entity_type'],'contract')
            self.assertTrue(all(i['namespace']=='achizitii-directe-ti-2026:purchase-number' for i in record['identifiers']))
            self.assertFalse(any(i['namespace']=='ro:cui' for i in record['identifiers']))

    def test_historical_court_description_is_not_a_record_or_a_fiscal_id(self):
        records=self.records('onorata-instanta');self.assertEqual(len(records),3)
        self.assertTrue(all(r['entity_type']=='public_institution' and r['record_grain']=='legal_subject' for r in records))
        self.assertFalse(any('Denumirea instantei' in r['label'] for r in records))
        self.assertTrue(all(all(i['namespace']=='onorata-instanta:court-code' for i in r['identifiers']) for r in records))

    def test_biography_slug_does_not_replace_the_independently_named_siruta(self):
        records=self.records('biografia-localitatii');self.assertEqual(len(records),3)
        for record in records:
            ids={i['namespace']:i['value'] for i in record['identifiers']}
            self.assertEqual(set(ids),{'ro:siruta','biografia-localitatii:slug'})
            self.assertEqual(profile_urls(self.store,record)[0]['url'],'https://mariuscomper.uk/biografia-localitatii/'+ids['biografia-localitatii:slug']+'/')
            self.assertEqual(record['entity_type'],'territory')
        keys={r['key'] for r in self.records('cat-de-tare')}
        self.assertFalse(any(keys.intersection(a['records']) for a in self.store['assertions']))

    def test_aggregate_site_has_sections_without_invented_subject_ids(self):
        p=self.store['projects']['afacut']
        self.assertEqual(len(p['patterns']),4);self.assertEqual(len(p['collections']),4)
        self.assertEqual(self.records('afacut'),[]);self.assertEqual(p['identifier_rules'],{})

    def test_request_journal_has_no_writes_private_api_or_forbidden_host(self):
        journal=ROOT/'docs/reports/site-structure-batch-h/requests.jsonl'
        for line in journal.read_text().splitlines():
            request=json.loads(line);self.assertEqual(request['method'],'GET')
            self.assertFalse(forbidden(request['url']))
            self.assertFalse(urlsplit(request['url']).path.startswith('/api/account/'))
            self.assertNotIn('body',request)


if __name__=='__main__':unittest.main()
