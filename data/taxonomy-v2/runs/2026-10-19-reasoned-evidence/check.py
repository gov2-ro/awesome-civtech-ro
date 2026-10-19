"""Run-local candidate checks. Requires jsonschema; does not alter package code."""
import json,csv,hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from jsonschema import Draft202012Validator
RUN=Path(__file__).parent
vocab=json.load(open(RUN/'frozen/vocabulary.json'));schema=json.load(open(RUN/'frozen/output.schema.json'))
Draft202012Validator.check_schema(schema);validator=Draft202012Validator(schema)
cs={c['id']:c for c in vocab['concepts']};roots={k for k,c in cs.items() if c['schema']=='subiect' and not c['mai_larg']};areas={a['id'] for a in vocab['areas']}
rs=list(csv.DictReader(open(RUN/'frozen/clasificare-input.csv')));results=[json.loads(l) for l in (RUN/'results.jsonl').read_text().splitlines()]
errors=[];cite_count=0;assignment_count=0;attribution_count=0;unresolved=0
assert len(results)==len(rs)==122
assert {x['slug'] for x in results}=={r['slug'] for r in rs}
assert len({x['slug'] for x in results})==122
assert len([c for c in cs.values() if c['schema']=='maturitate'])==4
def ancestors(cid):
 if cid in roots:return {cid}
 return set().union(*(ancestors(p) for p in cs[cid]['mai_larg'].split('|') if p))
for r,x in zip(rs,results):
 slug=x['slug'];request=json.load(open(RUN/'requests'/f'{slug}.json'));sources={s['id']:s for s in request['sources']}
 for e in validator.iter_errors(x):errors.append(dict(slug=slug,error=e.message,path=list(e.path)))
 c=x['classification']
 for field in ['subiect_principal','subiecte','teme','scopuri','functionalitati','formate','tehnologii','institutii_vizate','tip_organizatie','maturitate']:
  val=c[field];vs=val if isinstance(val,list) else [val] if val else []
  for v in vs:
   if v not in cs:errors.append(dict(slug=slug,error='Unknown concept '+v))
   elif cs[v]['statut'] in ['retras','retired']:errors.append(dict(slug=slug,error='Retired concept '+v))
 if c['subiect_principal'] and c['subiect_principal'] not in c['subiecte']:errors.append(dict(slug=slug,error='Primary missing from roots'))
 if not set(c['subiecte'])<=roots:errors.append(dict(slug=slug,error='Non-root subject in subjects'))
 if set(c['teme'])&roots:errors.append(dict(slug=slug,error='Root in topics'))
 for t in c['teme']:
  if not ancestors(t)<=set(c['subiecte']):errors.append(dict(slug=slug,error='Missing topic ancestor '+t))
 if not set(c['arii_acoperite'])<=areas:errors.append(dict(slug=slug,error='Unknown geographic ID'))
 if c['nivel_acoperire']=='necunoscut' and c['arii_acoperite']:errors.append(dict(slug=slug,error='Unknown geography with assigned areas'))
 if c['tip_entitate']!='organizatie' and c['tip_organizatie']:errors.append(dict(slug=slug,error='Organisation type on other entity'))
 expected={(f,v) for f,val in c.items() for v in (val if isinstance(val,list) else [val] if val is not None else []) if not(f=='nivel_acoperire' and v=='necunoscut')}
 actual=[(j['field'],j['value']) for j in x['justifications']]
 assignment_count+=len(expected)
 if Counter(actual)!=Counter(expected):errors.append(dict(slug=slug,error='Justification coverage mismatch'))
 for record in x['justifications']+x['attributions']+x['new_concept_proposals']+x['new_area_proposals']:
  for e in record['evidence']:
   cite_count+=1;s=sources.get(e['source_id'])
   if not s or s['locator']!=e['locator'] or e['excerpt'] not in s['text']:errors.append(dict(slug=slug,error='Broken citation',evidence=e))
 for conflict in x['conflicts']:
  if any(s not in sources for s in conflict['source_ids']):errors.append(dict(slug=slug,error='Conflict source absent'))
 expected_attr=Counter((a['resolved_slug'],None if a['resolved_slug'] else a['literal']) for a in request['entry']['original_attributions'])
 actual_attr=Counter((a['object_slug'],a['object_literal']) for a in x['attributions'])
 if actual_attr!=expected_attr:errors.append(dict(slug=slug,error='Attribution lost or merged'))
 attribution_count+=len(actual_attr);unresolved+=sum(1 for a in x['attributions'] if a['object_slug'] is None)
 for p in x['new_concept_proposals']:
  if any(k not in cs for k in p['broader_existing_ids']):errors.append(dict(slug=slug,error='Unknown proposed parent'))
 # Original consolidated fields must remain exact in candidate CSV.
 candidates=list(csv.DictReader(open(RUN/'candidate/intrari-candidate.csv')))
 candidate=next(y for y in candidates if y['slug']==slug)
 if any(candidate[k]!=v for k,v in r.items()):errors.append(dict(slug=slug,error='Original field changed'))
summary=dict(checked_at=datetime.now(timezone.utc).isoformat(),entries=len(results),schema_valid=sum(not list(validator.iter_errors(x)) for x in results),errors=len(errors),error_details=errors,assignments=assignment_count,citations=cite_count,original_attributions_preserved=attribution_count,unresolved_identity_literals=unresolved,typed_attribution_roles=sum(a['predicate']!='atribuit_in_sursa' for x in results for a in x['attributions']),result_status=dict(Counter(x['result_status'] for x in results)),maturity=dict(Counter(x['classification']['maturitate'] or 'unknown' for x in results)),technology=dict(Counter(t for x in results for t in x['classification']['tehnologii'])),concept_proposals=sum(len(x['new_concept_proposals']) for x in results),area_proposals=sum(len(x['new_area_proposals']) for x in results))
(RUN/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
# Seal the classification before the evaluation files are opened. Evaluation can verify this seal.
seal_path=RUN/'classification-seal.json'
if not seal_path.exists():
 paths=[RUN/'results.jsonl',*sorted((RUN/'responses').glob('*.json')),*sorted((RUN/'requests').glob('*.json')),*sorted((RUN/'candidate').glob('*')),*sorted((RUN/'frozen').glob('*')),RUN/'decisions.tsv',RUN/'assemble.py']
 seal=dict(sealed_at=datetime.now(timezone.utc).isoformat(),evaluation_started=False,files={str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
 seal_path.write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
