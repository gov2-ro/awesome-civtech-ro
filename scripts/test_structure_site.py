"""Checks for public and isolated structure profiles and observed-identifier lookup data."""
import copy
import io
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from structure_site import INPUTS, REPO, project_preview, publish_preview
from structure_state import StructureError


def item(slug):
    return dict(slug=slug, name=slug.title(), kind='proiect', url=f'https://{slug}.test/')


def fixture():
    evidence = dict(id='e', source='https://source.test/observed', observed_at='2026-10-01T00:00:00Z', sha256='f'*64)
    store = dict(projects={}, records=[], assertions=[], evidence={'e': evidence})
    for slug in ('alpha', 'beta'):
        store['projects'][slug] = dict(input_url=item(slug)['url'],
            namespaces={'local':dict(legacy_id=slug+':id', issuer=slug, shared=False),
                        'cui':dict(legacy_id='ro:cui', issuer='Romanian fiscal issuer', shared=True)},
            collections={'c':dict(id='c', legacy_id='companies', label='Companii', entity_type='company', record_grain='legal_subject', evidence=['e'])},
            patterns={'p':dict(kind='detail', collection='companies', url_template=f'https://{slug}.test/company/{{cui}}',
                               variables=[dict(name='cui', namespace='ro:cui', location='path')], applicability='historical', evidence=['e'])},
            operations={'o':dict(method='GET', url_template=f'https://{slug}.test/api/company/{{cui}}', uses=[dict(collection='companies')],
                                  security=dict(declared_requirement='unspecified', observed_enforcement='unknown'), applicability='historical', evidence=['e'])})
        store['records'].append(dict(key=slug+'-row', project=slug, collection='companies', entity_type='company', record_grain='legal_subject',
            label='Compania observată', identifiers=[dict(namespace=slug+':id',value='007',subject_role='self'),dict(namespace='ro:cui',value='00123',subject_role='self')],evidence=['e']))
    store['assertions']=[dict(id='pair',records=['alpha-row','beta-row'])]
    return store


class Projection(unittest.TestCase):
    def setUp(self):
        self.store=fixture();self.items=[item('alpha'),item('beta')]

    def render(self, state='accepted'):
        return project_preview(self.items,self.store,[dict(assertion_id='pair',state=state)])

    def test_only_explicitly_accepted_pairs_become_links(self):
        for state in ['proposed','deferred','rejected']:
            decisions=[] if state=='proposed' else [dict(assertion_id='pair',state=state)]
            self.assertEqual(project_preview(self.items,self.store,decisions)['links'],[])
        self.assertEqual(len(self.render()['links']),1)

    def test_exact_identifiers_and_issuer_scopes_survive(self):
        payload=self.render();a,b=payload['records']
        self.assertEqual([i['value'] for i in a['identifiers']],['007','00123'])
        self.assertNotEqual(a['identifiers'][0]['scope'],b['identifiers'][0]['scope'])
        self.assertEqual(a['identifiers'][1]['scope'],b['identifiers'][1]['scope'])
        self.store['projects']['beta']['namespaces']['cui']['issuer']='Different issuer'
        changed=self.render()['records'][1]
        self.assertNotEqual(a['identifiers'][1]['scope'],changed['identifiers'][1]['scope'])

    def test_hidden_or_missing_project_cannot_leak_through_an_accepted_pair(self):
        self.items=self.items[:1]
        payload=self.render()
        self.assertEqual(set(payload['projects']),{'alpha'})
        self.assertEqual(len(payload['records']),1)
        self.assertEqual(payload['links'],[])
        self.assertNotIn('beta.test',json.dumps(payload))

    def test_catalogue_url_mismatch_excludes_the_old_profile(self):
        self.items[0]['url']='https://different.test/'
        self.assertNotIn('alpha',self.render()['projects'])
        self.assertEqual(self.render()['links'],[])

    def test_conflict_withdraws_even_an_accepted_correspondence(self):
        self.store['records'][0]['identity_conflict']=True
        payload=self.render()
        self.assertEqual(payload['links'],[])
        self.assertTrue(payload['records'][0]['conflict'])
        del self.store['records'][0]['identity_conflict']
        self.store['assertions'][0]['identity_conflict']=True
        self.assertEqual(self.render()['links'],[])

    def test_template_url_is_separate_from_observed_availability(self):
        record=self.render()['records'][0]
        self.assertEqual(record['profileUrls'],[dict(url='https://alpha.test/company/00123',basis='template-derived')])
        self.assertNotIn('live',json.dumps(record))

    def test_unknown_template_identifier_does_not_create_a_profile_url(self):
        self.store['projects']['alpha']['patterns']['p']['variables'][0]['namespace']=None
        self.assertEqual(self.render()['records'][0]['profileUrls'],[])

    def test_source_dates_and_security_claims_remain_distinct(self):
        p=self.render()['projects']['alpha']
        self.assertEqual(p['patterns'][0]['sources'][0]['observedAt'],'2026-10-01T00:00:00Z')
        op=p['operations'][0]
        self.assertEqual((op['declaredSecurity'],op['observedSecurity']),('unspecified','unknown'))
        self.assertEqual(op['collections'],['Companii'])

    def test_equal_collection_labels_keep_distinct_section_and_api_scopes(self):
        project=self.store['projects']['alpha']
        other=dict(project['collections']['c'],id='d',legacy_id='registrations',record_grain='registration')
        project['collections']['d']=other
        project['patterns']['p']['collection']='registrations'
        payload=self.render();p=payload['projects']['alpha']
        self.assertEqual(p['patterns'][0]['collectionId'],'registrations')
        self.assertEqual(p['operations'][0]['collectionIds'],['companies'])
        self.assertEqual(payload['records'][0]['collectionId'],'companies')

    def test_local_source_keeps_receipt_without_disclosing_a_file_path(self):
        self.store['evidence']['e']['source']='file:///Users/owner/private/sample.json'
        raw=json.dumps(self.render())
        self.assertNotIn('/Users/',raw)
        self.assertTrue(self.render()['records'][0]['sources'][0]['localOnly'])

    def test_unsafe_urls_and_credential_parameters_do_not_become_links(self):
        for bad in ['javascript:alert(1)','https://user:password@site.test/','https://site.test/?api_key=private']:
            self.store['projects']['alpha']['patterns']['p']['url_template']=bad
            self.store['projects']['alpha']['operations']['o']['url_template']=bad
            p=self.render()['projects']['alpha']
            self.assertEqual(p['patterns'],[])
            self.assertEqual(p['operations'],[])

    def test_export_never_mutates_the_store_or_owner_decisions(self):
        before=copy.deepcopy(self.store)
        decisions=[dict(assertion_id='pair',state='accepted')];original=copy.deepcopy(decisions)
        project_preview(self.items,self.store,decisions)
        self.assertEqual(self.store,before);self.assertEqual(decisions,original)

    def test_invalid_or_duplicate_owner_decisions_fail(self):
        for decisions in [[dict(assertion_id='pair',state='automatic')], [dict(assertion_id='pair',state='accepted')]*2]:
            with self.assertRaises(StructureError): project_preview(self.items,self.store,decisions)


class Build(unittest.TestCase):
    def run_build(self,*args):
        return subprocess.run([sys.executable,str(REPO/'scripts/build.py'),*map(str,args)],cwd=REPO,capture_output=True,text=True)

    def test_v1_and_untracked_store_publication_are_refused_before_writes(self):
        before=(REPO/'site/data.json').read_bytes()
        result=self.run_build('--with-structure','--structure-store','/missing')
        self.assertEqual(result.returncode,2)
        self.assertIn('public builds replay tracked recipes',result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            result=self.run_build('--with-structure','--data-dir','data','--site-dir',tmp)
            self.assertEqual(result.returncode,2)
            self.assertEqual(list(Path(tmp).iterdir()),[])
        self.assertEqual((REPO/'site/data.json').read_bytes(),before)

    def test_public_structure_build_includes_both_inventories_without_touching_the_source_site(self):
        import build
        before=(REPO/'site/data.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp).resolve()/'public';build.prepare_site(out)
            with patch.object(build,'SITE',out),patch('sys.argv',['build.py','--with-structure']),redirect_stdout(io.StringIO()):
                build.main()
            db=json.loads((out/'data.json').read_text())
            self.assertTrue(db['inventoryPreview']);self.assertTrue(db['structurePreview'])
            self.assertTrue((out/'date/index.html').is_file());self.assertTrue((out/'entitati/index.html').is_file())
            self.assertIn('data-entity-lookup',(out/'date/index.html').read_text())
            self.assertIn('href="date/"',(out/'entitati/index.html').read_text())
        self.assertEqual((REPO/'site/data.json').read_bytes(),before)

    def test_structure_store_flag_cannot_be_silently_ignored(self):
        self.assertEqual(self.run_build('--structure-store','/missing').returncode,2)

    def test_tracked_recipe_build_is_offline_reproducible_and_cleans_when_disabled(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (REPO/'site').rglob('*') if p.is_file()}
        decisions_before=(INPUTS/'decisions.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'preview'
            first=self.run_build('--site-dir',out,'--with-structure')
            self.assertEqual(first.returncode,0,first.stderr)
            payload=(out/'entitati/data.json').read_bytes()
            db=json.loads((out/'data.json').read_text())
            self.assertTrue(db['structurePreview'])
            projected=json.loads(payload)
            self.assertTrue(projected['records'])
            self.assertIn('structure',next(i for i in db['items'] if i['slug']=='romania-transparenta'))
            selected={l['id'] for l in projected['links']}
            accepted={d['assertion_id'] for d in json.loads(decisions_before) if d['state']=='accepted'}
            self.assertLessEqual(selected,accepted)
            with patch('urllib.request.urlopen',side_effect=AssertionError('Network is forbidden')):
                entries=[{k:e[k] for k in ('slug','name','url','kind')} for e in db['items']]
                publish_preview(entries,out)
            self.assertEqual((out/'entitati/data.json').read_bytes(),payload)
            plain=self.run_build('--site-dir',out)
            self.assertEqual(plain.returncode,0,plain.stderr)
            self.assertFalse((out/'entitati').exists())
            clean=json.loads((out/'data.json').read_text())
            self.assertNotIn('structurePreview',clean)
            self.assertTrue(all('structure' not in i for i in clean['items']))
        self.assertEqual((INPUTS/'decisions.json').read_bytes(),decisions_before)
        after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (REPO/'site').rglob('*') if p.is_file()}
        self.assertEqual(before,after)


if __name__=='__main__':unittest.main()
