"""Role, namespace and collection checks for the second structure expansion."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from common import forbidden
from structure_curation import apply_recipe
from structure_state import blank,check

ROOT=Path(__file__).resolve().parents[1]
RECIPES=ROOT/'data/taxonomy-v2/structura/recipes'
BATCH={'executii-bugetare','banii-nostri','data-expertforum','ce-cumpara-primaria','cat-de-tare'}


class Territories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.out=Path(cls.temp.name);cls.store=blank();cls.recipes={}
        for path in sorted(RECIPES.glob('*.json')):
            recipe=json.loads(path.read_text());cls.recipes[recipe['project_slug']]=recipe
            cls.store=apply_recipe(cls.store,cls.out,recipe,path)
        check(cls.store,cls.out)

    def test_all_five_have_multiple_observed_subjects(self):
        for slug in BATCH:self.assertGreaterEqual(sum(r['project']==slug for r in self.store['records']),3,slug)
        self.assertFalse(self.store.get('conflicts'))
        self.assertFalse([g for g in self.store.get('gaps',[]) if not g.get('resolved')])

    def test_a_purchase_uses_its_own_local_key_not_a_party_cui(self):
        purchases=[r for r in self.store['records'] if r['project']=='banii-nostri' and r['entity_type']=='contract']
        self.assertTrue(purchases)
        for record in purchases:
            self.assertTrue(all(i['namespace']=='banii-nostri:purchase:daid' for i in record['identifiers']))
            roles={x['relation'] for x in self.store['projects']['banii-nostri']['relationships'].values() if x['source']==record['key']}
            self.assertEqual(roles,{'buyer','supplier'})

    def test_local_slug_and_legacy_row_ids_never_create_a_siruta_match(self):
        records=[r for r in self.store['records'] if r['project']=='cat-de-tare']
        self.assertTrue(any('București' in r['label'] for r in records))
        keys={r['key'] for r in records}
        self.assertTrue(all(len(r['identifiers'])==2 and all(i['namespace'].startswith('cat-de-tare:') for i in r['identifiers']) for r in records))
        self.assertFalse(any(keys.intersection(a['records']) for a in self.store['assertions']))
        self.assertTrue(all(not n['shared'] for n in self.store['projects']['cat-de-tare']['namespaces'].values()))

    def test_fiscal_institutions_and_territories_are_related_not_equal(self):
        by_key={r['key']:r for r in self.store['records']}
        edges=list(self.store['projects']['data-expertforum']['relationships'].values())
        self.assertTrue(edges)
        for edge in edges:
            self.assertEqual(edge['relation'],'associated_territory')
            fiscal,territory=by_key[edge['source']],by_key[edge['target']]
            self.assertEqual((fiscal['entity_type'],territory['entity_type']),('public_institution','territory'))
            self.assertEqual(fiscal['identifiers'][0]['namespace'],'ro:cui')
            self.assertEqual(territory['identifiers'][0]['namespace'],'ro:siruta')
            self.assertFalse(any(set(a['records'])=={fiscal['key'],territory['key']} for a in self.store['assertions']))

    def test_named_component_siruta_and_observed_year_are_explicit(self):
        recipe=self.recipes['ce-cumpara-primaria']
        for sample in recipe['samples']:
            self.assertEqual(sample['identifiers'][0]['extractor']['pointer'],'/subject/siruta')
        pattern=next(p for p in recipe['patterns'] if p['kind']=='detail')
        self.assertIn('?an=2025',pattern['url_template'])
        self.assertEqual(pattern['variables'][0]['namespace'],'ro:siruta')
        self.assertIn('2025',pattern['scope_note'])

    def test_budget_context_does_not_change_the_institution_grain(self):
        project=self.store['projects']['executii-bugetare']
        pattern=next(p for p in project['patterns'].values() if p['kind']=='detail')
        self.assertIn('judet=B',pattern['url_template']);self.assertIn('an=2026',pattern['url_template'])
        records=[r for r in self.store['records'] if r['project']=='executii-bugetare']
        self.assertTrue(all(r['record_grain']=='legal_subject' for r in records))
        self.assertTrue(any(c['record_grain']=='institution_year' for c in project['collections'].values()))

    def test_evidence_does_not_reintroduce_redirect_tracking_or_request_a_forbidden_host(self):
        recipe=self.recipes['data-expertforum']
        source=next(e for e in recipe['evidence'] if e['id']=='saved-page')
        payload=json.loads((RECIPES/source['artifact']).read_text())['payload']
        self.assertTrue(payload['sheet_links'])
        self.assertTrue(all(urlsplit(u).hostname=='docs.google.com' for u in payload['sheet_links']))
        self.assertNotIn('usg=',json.dumps(payload))
        journal=ROOT/'docs/reports/site-structure-batch-g/requests.jsonl'
        for line in journal.read_text().splitlines():
            request=json.loads(line)
            if request['sent']:self.assertFalse(forbidden(request['url']))
            self.assertNotIn('expertforum.ro',urlsplit(request['url']).hostname)
            self.assertNotIn('body',request)


if __name__=='__main__':unittest.main()
