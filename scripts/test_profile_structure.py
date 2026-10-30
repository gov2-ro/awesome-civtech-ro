"""Offline checks for the shared structure engine: transport, extraction, state and CLI."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import profile_structure as runner
from structure_discovery import Transport, RobotsPolicy, inferred_patterns, signals, safe_url, MAX_BODY
from structure_state import StructureError, begin, blank, check, evidence, finding, finish, load, project, save, seed_pilot


class Clock:
    def __init__(self): self.value = 0
    def __call__(self): return self.value
    def sleep(self, seconds): self.value += seconds


class Response:
    def __init__(self, status=200, body='', kind='text/plain', location=None):
        self.code, self.body = status, body.encode()
        self.headers = {'Content-Type': kind}
        if location: self.headers['Location'] = location
    def read(self, count): return self.body[:count]
    def __enter__(self): return self
    def __exit__(self, *args): pass


class Opener:
    def __init__(self, mapping=None, clock=None):
        self.mapping, self.calls, self.clock = mapping or {}, [], clock or Clock()
    def open(self, request, timeout):
        self.calls.append((request.full_url, self.clock()))
        result = self.mapping.get(request.full_url, Response(404))
        if isinstance(result, Exception): raise result
        return result


class Engine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = blank()
        project(self.store, 'alpha', 'https://example.test/')
        self.attempt = begin(self.store, 'alpha', 20, 'http')
        self.clock = Clock()
        self.opener = Opener(clock=self.clock)
        self.transport = Transport(self.store, lambda: save(self.store, self.root), opener=self.opener,
                                   clock=self.clock, sleep=self.clock.sleep)
        self.transport.attempt = self.attempt

    def mapped(self, **paths):
        self.opener.mapping.update({'https://example.test/'+p: v for p, v in paths.items()})

    def test_forbidden_host_has_zero_dispatches(self):
        r = self.transport.fetch('https://api.sicap.ai/v1/openapi')
        self.assertEqual(r['reason'], 'colectare-interzisa')
        self.assertEqual(self.opener.calls, [])
        check(self.store, self.root)

    def test_redirect_to_forbidden_host_is_not_followed(self):
        self.mapped(start=Response(302, location='https://api.sicap.ai/v1/openapi'))
        r = self.transport.fetch('https://example.test/start')
        self.assertEqual(r['reason'], 'colectare-interzisa')
        self.assertEqual(len(self.opener.calls), 2, 'robots and start only')

    def test_cross_host_redirect_checks_target_robots(self):
        self.mapped(start=Response(302, location='https://api.example.test/private'))
        self.opener.mapping['https://api.example.test/robots.txt'] = Response(body='User-agent: *\nDisallow: /private')
        r = self.transport.fetch('https://example.test/start')
        self.assertEqual(r['reason'], 'robots-disallow')
        self.assertNotIn('https://api.example.test/private', [x[0] for x in self.opener.calls])

    def test_robots_failure_does_not_grant_access(self):
        self.opener.mapping['https://example.test/robots.txt'] = URLError('DNS failure')
        r = self.transport.fetch('https://example.test/start')
        self.assertEqual(r['reason'], 'robots-unavailable')
        self.assertEqual(len(self.opener.calls), 1)

    def test_disallowed_path_is_not_requested(self):
        self.mapped(**{'robots.txt': Response(body='User-agent: *\nDisallow: /api')})
        self.assertEqual(self.transport.fetch('https://example.test/api/x')['reason'], 'robots-disallow')
        self.assertEqual(len(self.opener.calls), 1)

    def test_specific_disallow_overrides_broad_allow_on_python_312(self):
        self.mapped(**{'robots.txt': Response(body='User-agent: *\nAllow: /\nDisallow: /api/v1/')})
        self.assertEqual(self.transport.fetch('https://example.test/api/v1/firma/1')['reason'],'robots-disallow')
        self.assertEqual(len(self.opener.calls),1)

    def test_robots_wildcard_end_anchor_and_allow_tie(self):
        policy=RobotsPolicy('User-agent: *\nDisallow: /*.json$\nAllow: /public.json\nDisallow: /public.json')
        self.assertFalse(policy.can_fetch('CivTech-Structure','https://example.test/data.json'))
        self.assertTrue(policy.can_fetch('CivTech-Structure','https://example.test/data.json/x'))
        self.assertTrue(policy.can_fetch('CivTech-Structure','https://example.test/public.json'))

    def test_named_robots_groups_merge_and_override_wildcard(self):
        policy=RobotsPolicy('User-agent: *\nDisallow: /\nUser-agent: CivTech-Structure\nDisallow: /private\nUser-agent: CivTech-Structure\nDisallow: /more')
        self.assertFalse(policy.can_fetch('CivTech-Structure/1.0','https://example.test/more'))
        self.assertTrue(policy.can_fetch('CivTech-Structure/1.0','https://example.test/public'))

    def test_robots_cannot_redirect_to_arbitrary_data(self):
        self.mapped(**{'robots.txt': Response(302, location='/account')})
        self.assertEqual(self.transport.fetch('https://example.test/')['reason'], 'robots-unavailable')
        self.assertEqual(len(self.opener.calls), 1)

    def test_host_stop_survives_project_change(self):
        self.mapped(private=Response(429))
        self.assertEqual(self.transport.fetch('https://example.test/private')['outcome'], 'blocked')
        project(self.store, 'beta', 'https://example.test/')
        self.transport.attempt = begin(self.store, 'beta', 20, 'http')
        self.assertEqual(self.transport.fetch('https://example.test/other')['reason'], 'host-stopped')
        self.assertEqual(len(self.opener.calls), 2)

    def test_captcha_is_not_a_successful_empty_page(self):
        self.mapped(page=Response(body='<title>Just a moment</title>', kind='text/html'))
        self.assertEqual(self.transport.fetch('https://example.test/page')['outcome'], 'blocked')

    def test_robots_spends_project_budget(self):
        self.attempt['request_budget'] = 1
        r = self.transport.fetch('https://example.test/')
        self.assertEqual(r['reason'], 'budget-exhausted')
        self.assertEqual(self.attempt['requests_used'], 1)

    def test_total_budget_includes_redirects(self):
        self.transport.total_budget = 2
        self.mapped(start=Response(302, location='/next'))
        self.assertEqual(self.transport.fetch('https://example.test/start')['reason'], 'budget-exhausted')
        self.assertEqual(len(self.opener.calls), 2)

    def test_pacing_is_shared_across_paths(self):
        self.transport.fetch('https://example.test/one')
        self.transport.fetch('https://example.test/two')
        times = [t for _, t in self.opener.calls]
        self.assertTrue(all(b-a >= 1 for a, b in zip(times, times[1:])))

    def test_unicode_url_is_encoded_only_on_the_wire(self):
        self.opener.mapping['https://example.test/desc%C4%83rcare']=Response(body='ok')
        response=self.transport.fetch('https://example.test/descărcare')
        self.assertEqual(response['outcome'],'observed')
        self.assertEqual(self.store['requests'][-1]['url'],'https://example.test/descărcare')
        self.assertEqual(self.opener.calls[-1][0],'https://example.test/desc%C4%83rcare')

    def test_dispatch_policy_is_retained_for_historical_validation(self):
        self.transport.fetch('https://example.test/')
        self.assertIn('sicap.ai',self.store['requests'][0]['policy_hosts'])
        with patch('structure_state.forbidden', side_effect=lambda url, rows=None: rows is None):
            check(self.store,self.root)

    def test_body_cap_prevents_document_inference(self):
        self.mapped(large=Response(body='x'*(MAX_BODY+1)))
        r = self.transport.fetch('https://example.test/large')
        self.assertTrue(r['truncated'])
        self.assertEqual(r['bytes'], MAX_BODY)

    def test_credential_query_is_not_logged(self):
        r = self.transport.fetch('https://example.test/?api_key=do-not-copy')
        self.assertEqual(r['outcome'], 'skipped')
        self.assertNotIn('do-not-copy', json.dumps(self.store))
        self.assertEqual(self.opener.calls, [])

    def test_dispatch_is_persisted(self):
        self.transport.fetch('https://example.test/')
        self.assertEqual(load(self.root)['attempts'][0]['requests_used'], 2)

    def observe(self, text, kind='text/plain', method='http'):
        return runner.observe(self.store, self.root, 'alpha', 'https://example.test/', text, kind,
                              '2026-10-30T00:00:00+00:00', self.attempt['id'], method)

    def test_llms_templates_do_not_guess_cui_namespace(self):
        self.observe('/entities/{cui}: Entity profile\n')
        pattern = next(iter(self.store['projects']['alpha']['patterns'].values()))
        self.assertEqual(pattern['variables'][0]['namespace'], None)
        self.assertEqual(self.store['records'], [])
        self.assertEqual(self.store['assertions'], [])

    def test_query_template_variable_keeps_its_location(self):
        self.observe('/search?q={cui}: Search')
        pattern=next(iter(self.store['projects']['alpha']['patterns'].values()))
        self.assertEqual(pattern['variables'][0]['location'],'query')

    def test_fragment_template_is_preserved_as_structure(self):
        self.observe('/#/company/{id}: Company')
        pattern=next(iter(self.store['projects']['alpha']['patterns'].values()))
        self.assertEqual(pattern['url_template'],'https://example.test/#/company/{id}')
        self.assertEqual(pattern['variables'][0]['location'],'fragment')
        self.assertEqual(safe_url(pattern['url_template']),'https://example.test/')

    def test_numeric_sitemap_needs_two_examples(self):
        self.assertEqual(inferred_patterns(['https://example.test/company/1']), [])
        values = inferred_patterns(['https://example.test/company/1','https://example.test/company/2'])
        self.assertEqual(values[0][0], 'https://example.test/company/{id}')

    def test_sitemap_has_bounded_examples(self):
        text = '<urlset>'+''.join('<url><loc>https://example.test/x/'+str(i)+'</loc></url>' for i in range(300))+'</urlset>'
        self.assertEqual(len(signals(text,'application/xml','https://example.test/sitemap.xml')['sitemap_urls']), 200)

    def test_xml_entities_rejected(self):
        self.observe('<!DOCTYPE x [<!ENTITY private "x">]><x/>', 'application/xml')
        self.assertEqual(self.store['projects']['alpha']['checks'][-1]['outcome'], 'invalid')

    def test_malformed_xml_recorded_without_crash(self):
        self.observe('<?xml version="1.0"?><oops>', 'application/xml')
        self.assertEqual(self.store['projects']['alpha']['checks'][-1]['outcome'], 'invalid')

    def test_get_form_records_names_but_not_values(self):
        self.observe('<form action="/search"><input name="q" value="Private Value"><input type="password" name="password"></form>', 'text/html')
        text = json.dumps(self.store)
        self.assertNotIn('Private Value', text)
        self.assertNotIn('password', text)
        self.assertTrue(self.store['projects']['alpha']['patterns'])

    def test_relative_document_links(self):
        value = signals('[API](/openapi.json)', 'text/plain','https://example.test/docs')
        self.assertIn('https://example.test/openapi.json', value['links'])

    def test_template_prose_punctuation_is_not_part_of_the_url(self):
        value=signals('/entities/{cui}: Entity details','text/plain','https://example.test/')
        self.assertEqual(value['templates'],['https://example.test/entities/{cui}'])

    def api(self, security=None):
        operation = dict(parameters=[{'name':'q','in':'query','required':True}], responses={})
        if security is not None: operation['security'] = security
        return json.dumps({'openapi':'3.1.0','servers':[{'url':'https://example.test'}],
                           'paths':{'/api/search':{'get':operation,'delete':{'responses':{}}}}})

    def test_missing_security_differs_from_explicit_anonymous(self):
        self.observe(self.api(), 'application/json')
        get = next(x for x in self.store['projects']['alpha']['operations'].values() if x['method']=='GET')
        self.assertEqual(get['security']['declared_requirement'], 'unspecified')
        value=signals(self.api([]), 'application/json','https://example.test/openapi.json')
        self.assertEqual(value['operations'][0]['security']['declared_requirement'], 'anonymous')

    def test_mutating_operations_are_documented_but_not_probed(self):
        self.observe(self.api(), 'application/json')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/no-get',self.transport,self.attempt)
        self.assertEqual(self.opener.calls, [])

    def test_missing_required_probe_parameter_skips_dispatch(self):
        self.observe(self.api(), 'application/json')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search',self.transport,self.attempt)
        self.assertEqual(self.opener.calls, [])

    def test_referenced_parameters_are_not_silently_optional(self):
        doc=json.loads(self.api())
        doc['paths']['/api/search']['get']['parameters']=[{'$ref':'#/components/parameters/unknown'}]
        self.observe(json.dumps(doc),'application/json')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search',self.transport,self.attempt)
        self.assertEqual(self.opener.calls,[])

    def test_local_reference_keeps_the_required_query_parameter(self):
        doc=json.loads(self.api())
        doc['components']={'parameters':{'search':{'name':'q','in':'query','required':True,'schema':{'type':'string'}}}}
        doc['paths']['/api/search']['get']['parameters']=[{'$ref':'#/components/parameters/search'}]
        self.observe(json.dumps(doc),'application/json')
        operation=next(x for x in self.store['projects']['alpha']['operations'].values() if x['method']=='GET')
        self.assertFalse(operation['unresolved_parameters'])
        self.assertTrue(operation['parameters'][0]['required'])
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search',self.transport,self.attempt)
        self.assertEqual(self.opener.calls,[])

    def test_cyclic_parameter_references_remain_unresolved(self):
        doc=json.loads(self.api())
        doc['components']={'parameters':{'a':{'$ref':'#/components/parameters/b'},'b':{'$ref':'#/components/parameters/a'}}}
        doc['paths']['/api/search']['get']['parameters']=[{'$ref':'#/components/parameters/a'}]
        result=signals(json.dumps(doc),'application/json','https://example.test/openapi.json')
        self.assertTrue(result['operations'][0]['unresolved_parameters'])

    def test_external_parameter_references_make_no_request(self):
        doc=json.loads(self.api());doc['paths']['/api/search']['get']['parameters']=[{'$ref':'https://external.test/parameters.json#/search'}]
        self.observe(json.dumps(doc),'application/json')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search?q=x',self.transport,self.attempt)
        self.assertEqual(self.opener.calls,[])

    def test_malformed_contract_is_invalid_without_losing_prior_findings(self):
        self.observe('/company/{id}: profile')
        doc=json.loads(self.api());doc['servers']=['not-a-server-object']
        self.observe(json.dumps(doc),'application/json')
        self.assertTrue(self.store['projects']['alpha']['patterns'])
        self.assertEqual(self.store['projects']['alpha']['checks'][-1]['outcome'],'invalid')

    def test_authenticated_probe_skips_dispatch(self):
        self.observe(self.api([{'bearerAuth':[]}]), 'application/json')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search?q=x',self.transport,self.attempt)
        self.assertEqual(self.opener.calls, [])

    def test_changed_security_declaration_controls_the_next_probe(self):
        self.observe(self.api([]), 'application/json')
        self.observe(self.api([{'bearerAuth':[]}]), 'application/json')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search?q=x',self.transport,self.attempt)
        self.assertEqual(self.opener.calls, [])
        operation=next(x for x in self.store['projects']['alpha']['operations'].values() if x['method']=='GET')
        self.assertTrue(operation['declaration_history'])

    def test_probe_stores_types_not_record_values(self):
        self.observe(self.api(), 'application/json')
        self.opener.mapping['https://example.test/api/search?q=x']=Response(body='{"records":[{"name":"Private Name","cui":"001"}]}',kind='application/json')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search?q=x',self.transport,self.attempt)
        contents=''.join(p.read_text() for p in (self.root/'evidence').glob('*'))
        self.assertNotIn('Private Name', contents)
        self.assertNotIn('001', contents)
        self.assertEqual(self.store['records'], [])
        self.assertEqual(next(x for x in self.store['projects']['alpha']['operations'].values() if x['method']=='GET')['security']['observed_enforcement'],'anonymous')

    def test_probe_html_shell_is_invalid(self):
        self.observe(self.api(), 'application/json')
        self.opener.mapping['https://example.test/api/search?q=x']=Response(body='<html>shell</html>',kind='text/html')
        runner.probe_api(self.store,self.root,'alpha','https://example.test/api/search?q=x',self.transport,self.attempt)
        get=next(x for x in self.store['projects']['alpha']['operations'].values() if x['method']=='GET')
        self.assertEqual(get['last_test']['outcome'],'invalid')

    def test_failed_refresh_preserves_findings(self):
        self.observe('/company/{id}: profile')
        previous = copy.deepcopy(self.store['projects']['alpha']['patterns'])
        begin(self.store,'alpha',1,'http')
        self.assertEqual(set(previous),set(self.store['projects']['alpha']['patterns']))
        self.assertEqual(next(iter(self.store['projects']['alpha']['patterns'].values()))['applicability'],'stale')

    def test_retained_refresh_is_historical_not_current(self):
        self.observe('/company/{id}: profile')
        self.observe('/company/{id}: profile',method='retained')
        self.assertEqual(next(iter(self.store['projects']['alpha']['patterns'].values()))['applicability'],'historical')

    def test_evidence_tampering_blocks_load(self):
        self.observe('/company/{id}: profile')
        save(self.store,self.root)
        next((self.root/'evidence').glob('*')).write_text('changed')
        with self.assertRaisesRegex(StructureError,'hash mismatch'): load(self.root)

    def test_decisions_bytes_are_untouched(self):
        self.observe('/company/{id}: profile')
        decisions = b'[\n]\n'
        (self.root/'decisions.json').write_bytes(decisions)
        save(self.store,self.root)
        self.assertEqual((self.root/'decisions.json').read_bytes(), decisions)

    def test_invalid_owner_decisions_are_not_overwritten(self):
        (self.root/'decisions.json').write_text('{broken')
        with self.assertRaises(StructureError): save(self.store,self.root)
        self.assertEqual((self.root/'decisions.json').read_text(),'{broken')

    def test_acceptance_in_generated_finding_is_invalid(self):
        self.observe('/company/{id}: profile')
        next(iter(self.store['projects']['alpha']['patterns'].values()))['state']='accepted'
        with self.assertRaisesRegex(StructureError,'cannot accept'): check(self.store,self.root)

    def test_multi_collection_operation(self):
        self.observe(self.api(), 'application/json')
        p=self.store['projects']['alpha'];op=next(iter(p['operations'].values()))
        col=next(iter(p['collections']))
        op['uses'].append({'collection':col,'subject_role':'buyer','scope':'at_least'})
        check(self.store,self.root)
        op['uses'][1]['collection']='missing'
        with self.assertRaisesRegex(StructureError,'Unknown operation collection'): check(self.store,self.root)

    def test_unknown_mapping_basis_is_invalid(self):
        self.observe('/company/{id}: profile')
        p=self.store['projects']['alpha'];eid=next(iter(self.store['evidence']))
        finding(p,'identifier_rules','test',dict(mapping_basis='guessed'),eid,self.attempt['id'])
        with self.assertRaisesRegex(StructureError,'mapping basis'): check(self.store,self.root)

    def test_request_accounting_cannot_hide_dispatch(self):
        self.transport.fetch('https://example.test/')
        self.attempt['requests_used']=0
        with self.assertRaisesRegex(StructureError,'accounting'): check(self.store,self.root)

    def test_seed_pilot_is_idempotent_and_has_no_owner_decisions(self):
        pilot=Path(__file__).resolve().parents[1]/'docs/reports/site-structure-pilot'
        seed_pilot(self.store,self.root,pilot)
        before=copy.deepcopy(self.store)
        seed_pilot(self.store,self.root,pilot)
        self.assertEqual(self.store,before)
        self.assertEqual(len(self.store['assertions']),2)
        save(self.store,self.root)
        self.assertEqual(json.loads((self.root/'decisions.json').read_text()),[])
        for p in self.store['projects'].values():
            for operation in p['operations'].values():
                if operation.get('last_test',{}).get('evidence'):
                    self.assertIn(operation['last_test']['evidence'],self.store['evidence'])

    def test_dangling_supporting_evidence_blocks_save(self):
        self.observe('/company/{id}: profile')
        next(iter(self.store['projects']['alpha']['patterns'].values()))['declaration_evidence']='missing'
        with self.assertRaisesRegex(StructureError,'supporting evidence'): check(self.store,self.root)

    def test_cli_unknown_slug_creates_no_output(self):
        out=self.root/'new'
        with redirect_stderr(io.StringIO()): code=runner.main(['--out',str(out),'--only','does-not-exist','--offline'])
        self.assertEqual(code,1)
        self.assertFalse(out.exists())

    def test_cli_rejects_public_output(self):
        with redirect_stderr(io.StringIO()): code=runner.main(['--out',str(runner.REPO/'site'),'--only','transparenta-eu','--offline'])
        self.assertEqual(code,1)

    def test_unseeded_discovery_reaches_linked_contract(self):
        self.opener.mapping.update({
            'https://example.test/': Response(body='<html><a href="/date-deschise">Date</a></html>',kind='text/html'),
            'https://example.test/date-deschise': Response(body='<html><a href="/openapi.json">API</a></html>',kind='text/html'),
            'https://example.test/openapi.json': Response(body=self.api([]),kind='application/json'),
        })
        runner.run_project(self.store,self.root,'alpha','https://example.test/',self.transport,budget=12)
        self.assertTrue(self.store['projects']['alpha']['operations'])
        self.assertEqual(self.store['records'],[])
        check(self.store,self.root)

    def test_cli_import_saved_is_offline(self):
        path=self.root/'saved.txt';path.write_text('/company/{id}: company profile')
        out=self.root/'imported'
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network')),redirect_stdout(io.StringIO()):
            code=runner.main(['--out',str(out),'--import-saved','transparenta-eu','https://transparenta.eu/llms.txt',str(path),'--saved-at','2026-10-28T12:00:00+02:00'])
        self.assertEqual(code,0)
        store=load(out)
        self.assertEqual(store['attempts'][0]['requests_used'],0)
        self.assertEqual(next(iter(store['evidence'].values()))['saved_at'],'2026-10-28T12:00:00+02:00')


if __name__ == '__main__': unittest.main()
