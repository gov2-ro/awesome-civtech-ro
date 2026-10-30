"""Offline behavioral checks for typed curation, extraction, conflicts and identity proposals."""
import copy
import hashlib
import json
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path

from structure_curation import apply_recipe, prepare, report, profile_urls
from structure_state import StructureError, blank, save, check
from curate_structure import main

TIME='2026-10-20T00:00:00+00:00'


class Curation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.out=self.root/'out';self.out.mkdir()
        self.inputs=self.root/'inputs';self.inputs.mkdir()
        self.store=blank()

    def recipe(self,slug='alpha',cui='100',local='001',kind='company',issuer='Fiscal issuer'):
        text=json.dumps({'id':local,'cui':cui,'name':'Same Name'})
        path=self.inputs/(slug+'-data.json');path.write_text(text)
        r=dict(schema_version=1,project_slug=slug,input_url='https://'+slug+'.test/',
               evidence=[dict(id='row',source='https://'+slug+'.test/record',artifact=path.name,sha256=hashlib.sha256(text.encode()).hexdigest(),observed_at=TIME,locator=dict(type='text',start=0,end=len(text),excerpt=text))],
               collections=[dict(id='companies',label='Firme',entity_type=kind,record_grain='legal_subject',identity_components=['ro:cui'],evidence=['row'])],
               namespaces=[dict(id=slug+':id',issuer=slug,scope='local records',shared=False,normalization='identity',evidence=['row']),dict(id='ro:cui',issuer=issuer,scope='fiscal entities',shared=True,normalization='identity',evidence=['row'])],
               identifier_rules=[dict(id='local',collection='companies',namespace=slug+':id',subject_role='self',mapping_basis='sampled',location='/id',evidence=['row']),dict(id='cui',collection='companies',namespace='ro:cui',subject_role='self',mapping_basis='sampled',location='/cui',evidence=['row'])],
               patterns=[],operations=[],relationships=[],samples=[dict(id='one',collection='companies',local_namespace=slug+':id',label='Same Name',identifiers=[dict(rule='local',source='row',extractor=dict(type='json_pointer',pointer='/id')),dict(rule='cui',source='row',extractor=dict(type='json_pointer',pointer='/cui'))])])
        return r,self.inputs/(slug+'.json')

    def apply(self,r,path):
        self.store=apply_recipe(self.store,self.out,r,path)
        check(self.store,self.out)
        return self.store

    def test_shared_cui_with_distinct_local_ids_proposes_a_pair(self):
        self.apply(*self.recipe())
        self.apply(*self.recipe('beta',local='different'))
        self.assertEqual(len(self.store['assertions']),1)
        self.assertNotIn('state',self.store['assertions'][0])

    def test_equal_local_ids_and_names_do_not_establish_identity(self):
        self.apply(*self.recipe())
        self.apply(*self.recipe('beta',cui='200'))
        self.assertEqual(self.store['assertions'],[])

    def test_namespace_issuer_must_agree(self):
        self.apply(*self.recipe())
        self.apply(*self.recipe('beta',issuer='Different issuer'))
        self.assertEqual(self.store['assertions'],[])

    def test_local_namespace_is_not_shared_by_numeric_shape(self):
        self.apply(*self.recipe())
        r,p=self.recipe('beta');r['namespaces'][1]['shared']=False
        self.apply(r,p)
        self.assertEqual(self.store['assertions'],[])

    def test_subject_types_must_agree(self):
        self.apply(*self.recipe())
        self.apply(*self.recipe('beta',kind='territory'))
        self.assertEqual(self.store['assertions'],[])

    def test_record_grain_is_part_of_match_compatibility(self):
        self.apply(*self.recipe())
        r,p=self.recipe('beta');r['collections'][0]['record_grain']='financial_year'
        self.apply(r,p)
        self.assertEqual(self.store['assertions'],[])

    def test_truthful_local_file_provenance_needs_no_public_url(self):
        r,p=self.recipe();r['evidence'][0]['source']=(self.inputs/'alpha-data.json').as_uri()
        self.apply(r,p)
        self.assertEqual(len(self.store['records']),1)
        self.assertEqual(len(report(self.store,[])['local_sources']),1)

    def test_remote_file_origin_is_not_local_provenance(self):
        r,p=self.recipe();r['evidence'][0]['source']='file://remote-host/data.json'
        with self.assertRaisesRegex(StructureError,'remote file host'):self.apply(r,p)

    def test_leading_zeroes_are_not_removed(self):
        self.apply(*self.recipe(cui='00100'))
        self.apply(*self.recipe('beta',cui='100'))
        self.assertEqual(self.store['assertions'],[])
        self.assertEqual(self.store['records'][0]['local_value'],'001')

    def test_foreign_role_becomes_a_gap_not_a_self_id(self):
        r,p=self.recipe();r['identifier_rules'][1]['subject_role']='buyer'
        self.apply(r,p)
        self.assertEqual(self.store['records'],[])
        self.assertEqual(len(report(self.store,[])['gaps']),1)

    def test_contract_cannot_identify_itself_by_cui(self):
        self.apply(*self.recipe(kind='contract'))
        self.assertEqual(self.store['records'],[])
        self.assertIn('contract',self.store['gaps'][0]['reason'])

    def test_null_identifier_is_not_fabricated(self):
        self.apply(*self.recipe(cui=None))
        self.assertEqual(self.store['records'],[])

    def test_boolean_identifier_is_not_a_number(self):
        self.apply(*self.recipe(cui=True))
        self.assertEqual(self.store['records'],[])

    def test_float_identifier_is_rejected(self):
        self.apply(*self.recipe(cui=100.0))
        self.assertEqual(self.store['records'],[])

    def test_bad_evidence_hash_fails_before_store_changes(self):
        r,p=self.recipe();r['evidence'][0]['sha256']='0'*64
        previous=copy.deepcopy(self.store)
        with self.assertRaisesRegex(StructureError,'hash mismatch'): self.apply(r,p)
        self.assertEqual(self.store,previous)
        self.assertFalse((self.out/'evidence').exists())

    def test_wrong_excerpt_fails(self):
        r,p=self.recipe();r['evidence'][0]['locator']['excerpt']='invented'
        with self.assertRaisesRegex(StructureError,'differs'):self.apply(r,p)

    def test_artifact_cannot_leave_input_or_repository(self):
        r,p=self.recipe();r['evidence'][0]['artifact']='../outside.json'
        (self.root/'outside.json').write_text('{}')
        with self.assertRaisesRegex(StructureError,'permitted source roots'):self.apply(r,p)

    def test_observation_time_cannot_be_in_future(self):
        r,p=self.recipe();r['evidence'][0]['observed_at']='2099-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(StructureError,'time is invalid'):self.apply(r,p)

    def test_unknown_evidence_alias_fails(self):
        r,p=self.recipe();r['namespaces'][1]['evidence']=['missing']
        with self.assertRaisesRegex(StructureError,'known evidence'):self.apply(r,p)

    def test_extractor_is_limited_to_the_cited_fragment(self):
        r,p=self.recipe()
        text=(self.inputs/'alpha-data.json').read_text()
        r['evidence'][0]['locator']=dict(type='json_pointer',pointer='/id')
        self.apply(r,p)
        self.assertEqual(self.store['records'],[])
        self.assertTrue(self.store['gaps'])

    def test_regex_needs_one_distinct_value(self):
        r,p=self.recipe()
        r['samples'][0]['identifiers'][1]['extractor']=dict(type='regex',pattern=r'(?P<value>001|100)')
        self.apply(r,p)
        self.assertEqual(self.store['records'],[])

    def test_only_identity_normalization_is_supported(self):
        r,p=self.recipe();r['namespaces'][1]['normalization']='strip-zeroes'
        with self.assertRaisesRegex(StructureError,'normalization'):self.apply(r,p)

    def test_import_is_idempotent(self):
        r,p=self.recipe();self.apply(r,p);before=copy.deepcopy(self.store)
        self.apply(r,p)
        self.assertEqual(self.store,before)

    def test_owner_decisions_keep_their_bytes(self):
        self.apply(*self.recipe());self.apply(*self.recipe('beta'))
        save(self.store,self.out)
        decisions=json.dumps([dict(assertion_id=self.store['assertions'][0]['id'],state='accepted',note='Owner decision')],indent=3)+'\n'
        (self.out/'decisions.json').write_text(decisions)
        self.apply(*self.recipe('gamma'))
        save(self.store,self.out)
        self.assertEqual((self.out/'decisions.json').read_text(),decisions)
        self.assertEqual(report(self.store,json.loads(decisions))['links'][0]['state'],'accepted')

    def test_durable_decisions_are_a_read_only_report_overlay(self):
        self.apply(*self.recipe());self.apply(*self.recipe('beta'));save(self.store,self.out)
        path=self.root/'owner.json';text=json.dumps([dict(assertion_id=self.store['assertions'][0]['id'],state='accepted')])+'\n';path.write_text(text)
        output=io.StringIO()
        with redirect_stdout(output):code=main(['report','--out',str(self.out),'--decisions',str(path),'--json'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())['links'][0]['state'],'accepted')
        self.assertEqual(path.read_text(),text)
        self.assertEqual((self.out/'decisions.json').read_text(),'[]\n')

    def test_unselected_owner_decisions_remain_visible(self):
        self.apply(*self.recipe());save(self.store,self.out)
        path=self.root/'owner.json';path.write_text(json.dumps([dict(assertion_id='other-scope',state='deferred')]))
        output=io.StringIO()
        with redirect_stdout(output):code=main(['report','--out',str(self.out),'--decisions',str(path),'--json'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())['unapplied_decisions'],['other-scope'])

    def test_conflicting_local_key_is_retained_for_review(self):
        self.apply(*self.recipe());self.apply(*self.recipe('beta'))
        self.apply(*self.recipe(cui='200'))
        self.assertEqual(len(self.store['conflicts']),1)
        alpha=next(r for r in self.store['records'] if r['project']=='alpha')
        self.assertTrue(alpha['identity_conflict'])
        self.assertIn('100',{i['value'] for i in alpha['identifiers']})
        self.assertTrue(self.store['assertions'][0]['identity_conflict'])
        self.apply(*self.recipe('gamma',cui='200'))
        self.assertEqual(len(self.store['assertions']),1,'conflicted alpha cannot produce a new match')

    def test_same_namespace_cannot_change_issuer(self):
        self.apply(*self.recipe())
        r,p=self.recipe(issuer='Different')
        with self.assertRaisesRegex(StructureError,'different issuer'):self.apply(r,p)

    def test_missing_sample_can_be_resolved_without_losing_history(self):
        self.apply(*self.recipe(cui=None));self.assertEqual(len(report(self.store,[])['gaps']),1)
        self.apply(*self.recipe(cui='100'))
        self.assertEqual(report(self.store,[])['gaps'],[])
        self.assertTrue(self.store['gaps'][0]['resolved'])

    def test_same_project_records_are_not_cross_project_matches(self):
        self.apply(*self.recipe())
        r,p=self.recipe(local='002');r['samples'][0]['id']='two'
        self.apply(r,p)
        self.assertEqual(len(self.store['records']),2)
        self.assertEqual(self.store['assertions'],[])

    def test_record_extraction_provenance_is_retained(self):
        self.apply(*self.recipe())
        for extraction in self.store['records'][0]['extractions']:
            self.assertIn(extraction['evidence'],self.store['evidence'])
            self.assertIn('pointer',extraction['extractor'])

    def test_record_extraction_reference_is_checked(self):
        self.apply(*self.recipe())
        self.store['records'][0]['extractions'][0]['evidence']='missing'
        with self.assertRaisesRegex(StructureError,'extraction evidence'):check(self.store,self.out)

    def test_operation_can_serve_multiple_collections(self):
        r,p=self.recipe()
        r['collections'].append(dict(r['collections'][0],id='buyers',label='Cumpărători'))
        r['operations']=[dict(id='lookup',url_template='https://alpha.test/api/{cui}',method='GET',uses=[dict(collection='companies',subject_role='supplier'),dict(collection='buyers',subject_role='buyer')],security=dict(declared_requirement='unspecified',schemes=[],observed_enforcement='unknown'),evidence=['row'])]
        self.apply(r,p)
        self.assertEqual(len(next(iter(self.store['projects']['alpha']['operations'].values()))['uses']),2)
        before=copy.deepcopy(self.store);self.apply(r,p);self.assertEqual(before,self.store)

    def test_sample_limit_is_explicit(self):
        r,p=self.recipe();r['samples']=[dict(r['samples'][0],id=str(i)) for i in range(11)]
        with self.assertRaisesRegex(StructureError,'at most ten'):self.apply(r,p)

    def test_typed_profile_link_preserves_and_encodes_local_id(self):
        r,p=self.recipe(local='001/part')
        r['patterns']=[dict(id='detail',kind='detail',collection='companies',url_template='https://alpha.test/company/{id}',variables=[dict(name='id',namespace='alpha:id',location='path')],evidence=['row'])]
        self.apply(r,p)
        links=profile_urls(self.store,self.store['records'][0])
        self.assertEqual(links[0]['url'],'https://alpha.test/company/001%2Fpart')
        self.assertEqual(links[0]['basis'],'template-derived')

    def test_unbound_variable_does_not_generate_a_profile_link(self):
        r,p=self.recipe()
        r['patterns']=[dict(id='detail',kind='detail',collection='companies',url_template='https://alpha.test/company/{cui}',variables=[dict(name='cui',namespace=None,location='path')],evidence=['row'])]
        self.apply(r,p)
        self.assertEqual(profile_urls(self.store,self.store['records'][0]),[])

    def test_identity_cannot_be_smuggled_as_a_relationship(self):
        r,p=self.recipe();r['relationships']=[dict(id='fake',source_sample='one',target_sample='one',relation='same_entity',evidence=['row'])]
        with self.assertRaisesRegex(StructureError,'Identity assertions'):self.apply(r,p)

    def test_cross_namespace_relationship_is_not_an_identity_match(self):
        r,p=self.recipe();r['samples'].append(dict(r['samples'][0],id='second'))
        r['relationships']=[dict(id='associated',source_sample='one',target_sample='second',relation='associated_territory',evidence=['row'])]
        self.apply(r,p)
        self.assertEqual(self.store['assertions'],[])
        self.assertEqual(len(self.store['projects']['alpha']['relationships']),1)


if __name__=='__main__':unittest.main()
