"""Evidence and subject-role checks for the five-site structure expansion."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from structure_curation import apply_recipe, report
from structure_state import blank, check

ROOT=Path(__file__).resolve().parents[1]
RECIPES=ROOT/'data/taxonomy-v2/structura/recipes'
BATCH={'lista-firme','demoanaf','companii-de-stat','companii-publice-ro','orasul-care-se-intinde'}


class Expansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.out=Path(cls.temp.name);cls.store=blank();cls.recipes={}
        for path in sorted(RECIPES.glob('*.json')):
            recipe=json.loads(path.read_text());cls.recipes[recipe['project_slug']]=recipe
            cls.store=apply_recipe(cls.store,cls.out,recipe,path)
        check(cls.store,cls.out)

    def test_all_five_recipes_extract_multiple_real_records_without_conflicts(self):
        for slug in BATCH:
            self.assertGreaterEqual(sum(r['project']==slug for r in self.store['records']),2,slug)
        queue=report(self.store,[])
        self.assertEqual(queue['gaps'],[]);self.assertEqual(queue['conflicts'],[])

    def test_parent_and_authority_ids_never_identify_the_child_company(self):
        child=next(r for r in self.store['records'] if r['project']=='companii-publice-ro' and r['local_value']=='5622225')
        self.assertEqual({i['value'] for i in child['identifiers']},{'5622225'})
        p=self.store['projects']['companii-publice-ro'];relationships=list(p['relationships'].values())
        self.assertTrue(any(x['source']==child['key'] and x['relation']=='parent' for x in relationships))
        self.assertTrue(any(x['target']==child['key'] and x['relation']=='administers' for x in relationships))
        for assertion in self.store['assertions']:
            self.assertFalse(child['key'] in assertion['records'] and any('8359779' in k or '11795573' in k for k in assertion['records']))

    def test_territory_and_fiscal_institution_remain_separate(self):
        territory=next(r for r in self.store['records'] if r['project']=='orasul-care-se-intinde' and r['local_value']=='179132')
        self.assertEqual(territory['entity_type'],'territory')
        by_key={r['key']:r for r in self.store['records']}
        pairs=[a for a in self.store['assertions'] if territory['key'] in a['records']]
        self.assertTrue(pairs)
        self.assertTrue(all(by_key[k]['entity_type']=='territory' for a in pairs for k in a['records']))

    def test_paid_api_declarations_are_not_frontend_record_observations(self):
        p=self.store['projects']['demoanaf']
        company=next(o for o in p['operations'].values() if o['url_template']=='https://demoanaf.ro/api/company/{cui}')
        self.assertEqual(company['security']['declared_requirement'],'authenticated')
        self.assertEqual(company['security']['observed_enforcement'],'unknown')
        self.assertEqual(company['last_test']['outcome'],'unchecked')
        self.assertTrue(all('frontend-' in r['sample_id'] for r in self.store['records'] if r['project']=='demoanaf'))
        operation=next(iter(self.store['projects']['lista-firme']['operations'].values()))
        self.assertTrue(operation['unresolved_parameters'])
        self.assertNotIn('required',operation['parameters'][0])

    def test_identity_excerpts_keep_only_corporate_or_territory_values(self):
        recipes=[self.recipes[s] for s in BATCH]
        for recipe in recipes:
            for evidence in recipe['evidence']:
                artifact=(RECIPES/evidence['artifact']).resolve()
                payload=json.loads(artifact.read_text())['payload']
                if (re.fullmatch(r'company-[0-9]+',evidence['id']) or evidence['id']=='retained-company') and recipe['project_slug'] in {'lista-firme','companii-de-stat'}:
                    self.assertLessEqual(set(payload),{'name','nume','cui','euid'})
                if recipe['project_slug']=='companii-publice-ro' and evidence['id']=='corporate-roles':
                    self.assertFalse(payload['complete_document'])
                    self.assertEqual(payload['recovery'],'inventory_jsonsample.recover')
                    self.assertTrue(all(set(row)=={'source_index','cui','denumire','apt_cui','apt_denumire','parent_cui','parent_denumire'} for row in payload['rows']))

    def test_reapplication_preserves_the_baseline_assertions_and_store(self):
        before=copy.deepcopy(self.store);updated=copy.deepcopy(self.store)
        for slug in sorted(BATCH):
            updated=apply_recipe(updated,self.out,self.recipes[slug],RECIPES/(slug+'.json'))
        self.assertEqual(updated,before)
        self.assertTrue(all('state' not in a for a in updated['assertions']))


if __name__=='__main__':unittest.main()
