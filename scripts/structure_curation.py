"""Offline evidence-backed curation and cross-project identity proposals. No network operations."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from structure_state import StructureError, evidence, finding, key, now, project, require
from structure_discovery import safe_url

REPO = Path(__file__).resolve().parents[1]
TYPES = {'company', 'public_institution', 'legal_subject', 'territory', 'registration', 'contract', 'funding_project', 'unknown'}
ROLES = {'self', 'buyer', 'supplier', 'parent', 'associated_territory', 'located_in', 'administers'}


def indexed(values, field='id'):
    require(isinstance(values, list), 'Expected a list of recipe objects.')
    result = {}
    for value in values:
        require(isinstance(value, dict) and isinstance(value.get(field), str) and bool(value[field]), 'Recipe object needs a stable key.')
        require('|' not in value[field], 'Recipe keys cannot contain a record-key separator.')
        require(value[field] not in result, 'Duplicate recipe key.')
        result[value[field]] = value
    return result


def pointer(value, path):
    require(isinstance(path, str) and (not path or path.startswith('/')), 'Invalid JSON pointer.')
    try:
        for part in path.split('/')[1:] if path else []:
            part = part.replace('~1', '/').replace('~0', '~')
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise StructureError('Evidence JSON pointer does not resolve.') from exc


def extract(text, locator):
    require(isinstance(locator, dict), 'An extractor needs an object.')
    if locator.get('type') == 'json_pointer':
        try:
            document = json.loads(text)
        except ValueError as exc:
            raise StructureError('Evidence fragment is not JSON.') from exc
        return pointer(document, locator['pointer'])
    if locator.get('type') == 'regex':
        pattern = re.compile(locator['pattern'])
        require('value' in pattern.groupindex, 'Regex extractor needs a named value group.')
        values = {m.group('value') for m in pattern.finditer(text)}
        require(len(values) == 1, 'Regex extraction is missing or ambiguous.')
        return values.pop()
    if locator.get('type') == 'text':
        start, end = locator.get('start'), locator.get('end')
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Invalid evidence text interval.')
        value = text[start:end]
        require(value == locator.get('excerpt'), 'Evidence excerpt differs from its locator.')
        return value
    raise StructureError('Unsupported evidence extractor.')


def scalar(value):
    require(type(value) in {str, int}, 'Identifier must be a string or integer, not null, boolean or a float.')
    value = str(value)
    require(bool(value) and len(value) <= 300, 'Identifier is empty or too long.')
    return value


def refs(item, sources):
    aliases = item.get('evidence')
    require(isinstance(aliases, list) and bool(aliases) and all(x in sources for x in aliases), 'Claim needs known evidence aliases.')
    return aliases


def prepare(recipe, path, store):
    """Validate and extract all inputs before changing the store or writing artifacts."""
    require(isinstance(recipe, dict) and recipe.get('schema_version') == 1, 'Expected a version-1 curation recipe.')
    slug = recipe.get('project_slug')
    require(isinstance(slug, str) and slug, 'Recipe needs project_slug.')
    require(isinstance(recipe.get('input_url'), str), 'Recipe needs input_url.')
    sources = {}
    for alias, item in indexed(recipe.get('evidence', [])).items():
        artifact = (path.parent / item['artifact']).resolve()
        require(artifact.is_relative_to(path.parent.resolve()) or artifact.is_relative_to(REPO), 'Evidence artifact leaves permitted source roots.')
        require(not any(part.startswith('.') for part in artifact.relative_to(path.parent.resolve() if artifact.is_relative_to(path.parent.resolve()) else REPO).parts), 'Hidden files cannot supply curation evidence.')
        require(artifact.is_file() and artifact.stat().st_size <= 2*1024*1024, 'Evidence artifact is absent or too large.')
        raw = artifact.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == item.get('sha256'), 'Recipe evidence hash mismatch.')
        text = raw.decode('utf-8')
        fragment = extract(text, item['locator'])
        if item['locator'].get('type')=='json_pointer' or not isinstance(fragment, str):
            fragment = json.dumps(fragment, ensure_ascii=False, sort_keys=True)
        require(bool(fragment) and len(fragment) <= 65536, 'Evidence fragment is empty or exceeds 64 KiB.')
        require(isinstance(item.get('source'), str) and isinstance(item.get('observed_at'), str), 'Evidence needs source and time.')
        if urlsplit(item['source']).scheme == 'file':
            require(urlsplit(item['source']).netloc in {'','localhost'}, 'A local evidence origin cannot name a remote file host.')
        else:
            safe_url(item['source'])
        observed = datetime.fromisoformat(item['observed_at'])
        require(observed.utcoffset() is not None and observed <= datetime.now(timezone.utc), 'Evidence observation time is invalid.')
        sources[alias] = dict(item=item, text=text, fragment=fragment)
    collections = indexed(recipe.get('collections', []))
    namespaces = indexed(recipe.get('namespaces', []))
    rules = indexed(recipe.get('identifier_rules', []))
    for item in collections.values():
        refs(item, sources)
        require(item.get('entity_type') in TYPES, 'Unknown collection subject type.')
        require(isinstance(item.get('record_grain'), str) and isinstance(item.get('identity_components'), list), 'Collection needs grain and identity components.')
    for item in namespaces.values():
        refs(item, sources)
        require(isinstance(item.get('issuer'), str) and bool(item['issuer']) and isinstance(item.get('scope'), str), 'Namespace needs issuer and scope.')
        require(type(item.get('shared')) is bool and item.get('normalization') == 'identity', 'Specify namespace sharing and identity normalization.')
        old = store['projects'].get(slug, {}).get('namespaces', {})
        for ns in old.values():
            if ns.get('legacy_id') == item['id']:
                require(ns['issuer'] == item['issuer'], 'Existing namespace has a different issuer.')
    for item in rules.values():
        refs(item, sources)
        require(item.get('collection') in collections and item.get('namespace') in namespaces, 'Unknown rule collection or namespace.')
        require(item.get('subject_role') in ROLES and item.get('mapping_basis') in {'declared','sampled','unknown'}, 'Unknown identifier role or mapping basis.')
    for section in ('patterns', 'operations'):
        for item in indexed(recipe.get(section, [])).values():
            refs(item, sources)
            require(isinstance(item.get('url_template'), str), 'Pattern or operation needs a template.')
            if section == 'patterns':
                require(item.get('collection') in collections, 'Unknown pattern collection.')
                for variable in item.get('variables', []):
                    require(variable.get('namespace') is None or variable['namespace'] in namespaces, 'Unknown variable namespace.')
            else:
                require(isinstance(item.get('uses'), list) and item['uses'], 'Operation needs collection uses.')
                require(all(use.get('collection') in collections and use.get('subject_role') in ROLES | {'unknown'} for use in item['uses']), 'Unknown operation use.')
                require(item.get('method') in {'GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'}, 'Unknown declared HTTP method.')
                require(item.get('security', {}).get('declared_requirement') in {'unspecified','anonymous','authenticated'}, 'Operation needs declared security.')
    for item in indexed(recipe.get('relationships', [])).values():
        refs(item,sources)
        require(item.get('relation') in ROLES-{'self'}, 'Identity assertions cannot be imported as relationships.')
    records, gaps = [], []
    samples = indexed(recipe.get('samples', []))
    require(len(samples) <= 10, 'A recipe can sample at most ten records.')
    for sample in samples.values():
        require(sample.get('collection') in collections, 'Unknown sample collection.')
        collection = collections[sample['collection']]
        require(collection['entity_type'] != 'unknown', 'A record sample needs an explicit subject type.')
        values, aliases, extractions = [], [], []
        try:
            for binding in sample.get('identifiers', []):
                rule = rules[binding['rule']]
                require(rule['subject_role'] == 'self' and rule['collection'] == sample['collection'], 'A related identifier cannot identify this sample.')
                require(not (collection['entity_type'] == 'contract' and rule['namespace'] == 'ro:cui'), 'A contract cannot identify itself by CUI.')
                source = sources[binding['source']]
                value = scalar(extract(source['fragment'], binding['extractor']))
                values.append(dict(namespace=rule['namespace'], value=value, raw_value=value, subject_role='self'))
                extractions.append(dict(namespace=rule['namespace'],value=value,evidence_alias=binding['source'],extractor=binding['extractor']))
                aliases.append(binding['source'])
            require(bool(values) and sample.get('local_namespace') in {v['namespace'] for v in values}, 'Sample local namespace needs a self identifier.')
        except StructureError as exc:
            gaps.append(dict(id=key(slug,sample['id'],str(exc)), project=slug, sample=sample['id'], reason=str(exc)))
            continue
        local = next(v['value'] for v in values if v['namespace'] == sample['local_namespace'])
        require(len({v['namespace'] for v in values}) == len(values), 'A sample has duplicate identifier namespaces.')
        rkey = '|'.join([slug, sample['collection'], sample['local_namespace'], local])
        records.append(dict(key=rkey, sample_id=sample['id'], project=slug, collection=sample['collection'], record_grain=collection['record_grain'],local_namespace=sample['local_namespace'],
                            local_value=local, entity_type=collection['entity_type'], identifiers=values,
                            label=sample.get('label', ''), locators=list(dict.fromkeys(sources[a]['item']['source'] for a in aliases)),
                            aliases=list(dict.fromkeys(aliases)), extractions=extractions,validity='unknown; source observation time is not legal validity'))
    return slug, sources, collections, namespaces, records, gaps


def apply_recipe(store, out, recipe, path):
    slug, sources, collections, namespaces, records, gaps = prepare(recipe, Path(path), store)
    result = copy.deepcopy(store)
    p = project(result, slug, recipe['input_url'])
    recipe_hash = hashlib.sha256(json.dumps(recipe,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    attempt = 'recipe-' + recipe_hash
    evidence_ids = {}
    for alias, source in sources.items():
        item = source['item']
        evidence_ids[alias] = evidence(result, out, slug, item['source'], source['fragment'], item['observed_at'], 'curated',
            local_only=urlsplit(item['source']).scheme=='file',
            provenance=dict(recipe_sha256=recipe_hash, alias=alias, artifact_sha256=item['sha256'], locator=item['locator']))
    for section in ('collections','namespaces','patterns','identifier_rules','operations'):
        for raw in recipe.get(section, []):
            item = {k:v for k,v in raw.items() if k not in {'id','evidence'}}
            item['legacy_id'] = raw['id']
            for field in ('declaration_evidence','read_only_evidence'):
                if field in item: item[field] = evidence_ids[item[field]]
            if item.get('last_test',{}).get('evidence'):
                item['last_test'] = dict(item['last_test'],evidence=evidence_ids[item['last_test']['evidence']])
            identity = raw.get('url_template', raw['id'])
            if section == 'operations':
                identity = raw['method']+' '+raw['url_template']
                item.setdefault('parameters',[])
                item.setdefault('unresolved_parameters',False)
            fid = key(slug,section,identity)
            # A curated proposal is a separate declaration. Keep prior interpretations in its history.
            old = p[section].get(fid)
            if old and old.get('curation_recipe') != recipe_hash:
                item['curation_history'] = old.get('curation_history', []) + [{k:v for k,v in old.items() if k not in {'curation_history'}}]
                item['evidence'] = list(old['evidence'])
                del p[section][fid]
            for alias in raw['evidence']:
                finding(p,section,identity,item,evidence_ids[alias],attempt)
            if old:
                p[section][fid]['evidence'] = list(dict.fromkeys(old['evidence']+p[section][fid]['evidence']))
            p[section][fid]['curation_recipe'] = recipe_hash
            p[section][fid]['applicability'] = 'historical'
    result.setdefault('curation', {})[recipe_hash] = dict(project=slug, recipe_id=recipe.get('id',Path(path).stem))
    result.setdefault('gaps', [])
    known_gaps = {g['id'] for g in result['gaps']}
    result['gaps'].extend(g for g in gaps if g['id'] not in known_gaps)
    existing = {r['key']:r for r in result['records']}
    sample_keys = {r['sample_id']:r['key'] for r in records}
    for r in records:
        r['evidence'] = [evidence_ids[a] for a in r.pop('aliases')]
        for extraction in r['extractions']:
            extraction['evidence'] = evidence_ids[extraction.pop('evidence_alias')]
        for gap in result['gaps']:
            if gap['project']==slug and gap['sample']==r['sample_id']:gap['resolved']=True
        old = existing.get(r['key'])
        if old:
            old_ids = {(i['namespace'],i['value']) for i in old['identifiers']}
            conflicts = [i for i in r['identifiers'] if any(ns == i['namespace'] and value != i['value'] for ns,value in old_ids)]
            if conflicts:
                conflict = dict(id=key(r['key'],conflicts),record=r['key'],project=slug,new_identifiers=conflicts,evidence=r['evidence'])
                result.setdefault('conflicts', [])
                if conflict['id'] not in {c['id'] for c in result['conflicts']}: result['conflicts'].append(conflict)
                old['identity_conflict'] = True
            else:
                old['identifiers'].extend(i for i in r['identifiers'] if (i['namespace'],i['value']) not in old_ids)
            old['evidence'] = list(dict.fromkeys(old['evidence']+r['evidence']))
            old.setdefault('extractions',[])
            old['extractions'].extend(x for x in r['extractions'] if x not in old['extractions'])
        else:
            result['records'].append(r)
            existing[r['key']] = r
    for raw in recipe.get('relationships', []):
        if raw.get('source_sample') not in sample_keys or raw.get('target_sample') not in sample_keys:
            gap=dict(id=key(slug,raw['id'],'missing-sample'),project=slug,sample=raw['id'],reason='Relationship sample is unavailable.')
            if gap['id'] not in {g['id'] for g in result['gaps']}: result['gaps'].append(gap)
            continue
        item=dict(source=sample_keys[raw['source_sample']],target=sample_keys[raw['target_sample']],relation=raw['relation'])
        for alias in raw['evidence']: finding(p,'relationships',raw['id'],item,evidence_ids[alias],attempt)
    propose(result)
    return result


def namespace(store, record, name):
    values = store['projects'][record['project']]['namespaces']
    return next((n for n in values.values() if n.get('legacy_id', n['id']) == name), None)


def assertion_id(records):
    value = json.dumps(['same_entity', sorted(records)], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def propose(store):
    index = {}
    for record in store['records']:
        if record.get('identity_conflict') or record['entity_type'] == 'unknown': continue
        for identifier in record['identifiers']:
            if identifier.get('subject_role') != 'self': continue
            ns = namespace(store,record,identifier['namespace'])
            if not ns or not ns.get('shared',identifier['namespace'].startswith('ro:')): continue
            collection=next((c for c in store['projects'][record['project']]['collections'].values() if c.get('legacy_id',c['id'])==record['collection']),{})
            grain=record.get('record_grain',collection.get('record_grain','unknown'))
            token = (record['entity_type'],grain,identifier['namespace'],ns['issuer'],identifier['value'])
            index.setdefault(token, {})[record['key']] = record
    assertions = {a['id']:a for a in store['assertions']}
    for group in index.values():
        for left,right in itertools.combinations(group.values(),2):
            if left['project'] == right['project']: continue
            keys = [left['key'],right['key']]
            aid = assertion_id(keys)
            if aid not in assertions:
                a = dict(id=aid,kind='same_entity',records=keys,basis='shared_identifier',
                         evidence=list(dict.fromkeys(left['evidence']+right['evidence'])),limitations=['Proposed only; temporal identity needs review.'])
                store['assertions'].append(a);assertions[aid]=a
    conflicts = {r['key'] for r in store['records'] if r.get('identity_conflict')}
    for a in store['assertions']:
        if conflicts.intersection(a['records']): a['identity_conflict'] = True


def report(store, decisions):
    states = {d['assertion_id']:d['state'] for d in decisions}
    records = {r['key']:r for r in store['records']}
    links = []
    for a in store['assertions']:
        subjects=[]
        for r in a['records']:
            subject={k:records[r][k] for k in ('project','collection','entity_type','identifiers','locators')}
            subject['profile_urls']=profile_urls(store,records[r])
            subject['evidence']=records[r]['evidence']
            subjects.append(subject)
        links.append(dict(id=a['id'], state=states.get(a['id'],'proposed'), conflict=a.get('identity_conflict',False),
                          subjects=subjects))
    return dict(projects=len(store['projects']),records=len(records),links=links,conflicts=store.get('conflicts',[]),gaps=[g for g in store.get('gaps',[]) if not g.get('resolved')],
                local_sources=[dict(project=e['project'],source=e['source']) for e in store['evidence'].values() if e.get('local_only')],
                declared_without_samples=[slug for slug,p in store['projects'].items() if p['identifier_rules'] and not any(r['project']==slug for r in records.values())])


def profile_urls(store, record):
    """Instantiate typed detail patterns. The resulting URL is a candidate, not a live check."""
    project=store['projects'][record['project']]
    def collection_id(reference):
        return next((k for k,c in project['collections'].items() if k==reference or c.get('legacy_id')==reference),reference)
    values={i['namespace']:i['value'] for i in record['identifiers'] if i.get('subject_role')=='self'}
    result=[]
    for pattern in project['patterns'].values():
        if pattern.get('kind')!='detail' or collection_id(pattern.get('collection'))!=collection_id(record['collection']):continue
        url=pattern['url_template']
        for variable in pattern.get('variables',[]):
            if variable.get('namespace') not in values:break
            url=url.replace('{'+variable['name']+'}',quote(values[variable['namespace']],safe=''))
        else:
            if '{' not in url and not any(x['url']==url for x in result):
                result.append(dict(url=url,basis='template-derived',evidence=pattern['evidence']))
    return result
