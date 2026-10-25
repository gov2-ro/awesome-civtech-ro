"""Draft variable inventories from collected documentation and linked schemas/data. Stdlib only.

    python3 scripts/inventory.py                 # cached docs; admit at most 3 linked files per entry
    python3 scripts/inventory.py --offline       # no requests; rebuild from local evidence
    python3 scripts/inventory.py --only demoanaf --force
    python3 scripts/inventory.py --dry-run       # compute and report; write nothing

Outputs stay in observatii/inventare/. No catalogue or site field is changed.
Declared schema types, observed JSON types and HTML control types stay distinct.
Every result remains partial and requires editorial review.

Runs are incremental. The tracked state is read first. A run changes only the selected projects (--only) and the
sources they use. Other projects keep their records, references and evidence. A source that cannot be refreshed
(failed request, missing cache, failed parse) keeps its last good evidence and records the failed attempt.
Discoveries live in descoperiri.json, separate from the per-run limits. A run writes all files or none.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlsplit

from collect_docs import Fetcher, canonical, flat, restore, scope_of
from common import PUBLIC_ROOT, data_schema, load_catalogue, load_vocabulary, observation_paths
from inventory_state import (REGISTRY, RequestLog, StateError, active_members, admit, check_text, dump, load_previous,
                             new_discovery, now_utc, priority, registry_map, retire, seed_registry, sorted_registry,
                             source_id, usable, validate_state, write_atomic, write_file_atomic)

MAX_FIELDS, MAX_DEPTH, SAMPLE_ROWS = 2000, 7, 25


def pointer_part(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def dereference(node, root, visited=()):
    if not isinstance(node, dict):
        return {}
    ref = node.get('$ref', '')
    if not ref.startswith('#/') or ref in visited:
        return node
    target = root
    try:
        for part in ref[2:].split('/'):
            target = target[unquote(part).replace('~1', '/').replace('~0', '~')]
    except (KeyError, TypeError):
        return node
    return {**dereference(target, root, (*visited, ref)), **{k: v for k, v in node.items() if k != '$ref'}}


def declared_fields(schema, root, path='$', pointer='', depth=0):
    """Read declared properties; limits and unresolved refs never imply a complete schema."""
    if depth > MAX_DEPTH:
        return []
    if isinstance(schema, dict) and schema.get('$ref', '').startswith('#/'):
        pointer = schema['$ref'][1:]
    schema = dereference(schema, root)
    fields = []
    for join in ('allOf', 'oneOf', 'anyOf'):
        for n, part in enumerate(schema.get(join, [])):
            fields += declared_fields(part, root, path, f'{pointer}/{join}/{n}', depth + 1)
    required = schema.get('required', [])
    for name, raw in schema.get('properties', {}).items():
        prop = dereference(raw, root)
        here = f'{pointer}/properties/{pointer_part(name)}'
        field_path = path + '.' + name
        fields.append({'nume': name, 'cale': field_path, 'tip_declarat': prop.get('type'),
                       'format': prop.get('format'), 'descriere': prop.get('description', ''),
                       'obligatoriu': name in required, 'unitate': prop.get('unit') or prop.get('x-unit'),
                       'valori_enum': prop.get('enum', [])[:30], 'stare_tip': 'declarat-in-schema', 'pointer': here})
        fields += declared_fields(raw, root, field_path, here, depth + 1)
        if len(fields) >= MAX_FIELDS:
            return fields[:MAX_FIELDS]
    if not schema.get('properties') and 'items' in schema:
        fields += declared_fields(schema['items'], root, path + '[]', pointer + '/items', depth + 1)
    return fields[:MAX_FIELDS]


def openapi_fields(doc):
    fields = []
    for path, raw_item in doc.get('paths', {}).items():
        item = dereference(raw_item, doc)
        for method, raw_op in item.items():
            if method not in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options'):
                continue
            operation = dereference(raw_op, doc)
            op = method.upper() + ' ' + path
            op_pointer = '/paths/' + pointer_part(path) + '/' + method
            parameters = [(raw, '/paths/' + pointer_part(path) + '/parameters/' + str(n)) for n, raw in enumerate(item.get('parameters', []))]
            parameters += [(raw, op_pointer + '/parameters/' + str(n)) for n, raw in enumerate(operation.get('parameters', []))]
            for raw, parameter_pointer in parameters:
                if isinstance(raw, dict) and raw.get('$ref', '').startswith('#/'):
                    parameter_pointer = raw['$ref'][1:]
                parameter = dereference(raw, doc)
                schema = dereference(parameter.get('schema', parameter), doc)
                fields.append({'nume': parameter.get('name', ''), 'cale': parameter.get('name', ''),
                               'rol': 'parametru-api', 'operatie': op, 'loc': parameter.get('in'),
                               'tip_declarat': schema.get('type'), 'format': schema.get('format'),
                               'descriere': parameter.get('description', ''), 'obligatoriu': parameter.get('required', False),
                               'stare_tip': 'declarat-in-schema', 'pointer': parameter_pointer})
                if parameter.get('in') == 'body':
                    for f in declared_fields(schema, doc, pointer=parameter_pointer + '/schema'):
                        fields.append({**f, 'rol': 'corp-cerere', 'operatie': op})
            body = dereference(operation.get('requestBody', {}), doc)
            for mime, content in body.get('content', {}).items():
                if 'json' in mime:
                    for f in declared_fields(content.get('schema', {}), doc, pointer=op_pointer + '/requestBody/content/' + pointer_part(mime) + '/schema'):
                        fields.append({**f, 'rol': 'corp-cerere', 'operatie': op})
                    break
            for status, raw_response in operation.get('responses', {}).items():
                if not str(status).startswith('2'):
                    continue
                response = dereference(raw_response, doc)
                schemas = [(mime, c.get('schema', {})) for mime, c in response.get('content', {}).items() if 'json' in mime]
                if not schemas and 'schema' in response:
                    schemas = [('', response['schema'])]
                for mime, schema in schemas[:1]:
                    location = op_pointer + '/responses/' + str(status)
                    location += '/content/' + pointer_part(mime) if mime else ''
                    for f in declared_fields(schema, doc, pointer=location + '/schema'):
                        fields.append({**f, 'rol': 'camp-raspuns', 'operatie': op, 'status_raspuns': str(status)})
    # Some published files define models without paths. Preserve those declarations without claiming an operation uses them.
    if not fields:
        for name, schema in doc.get('components', {}).get('schemas', doc.get('definitions', {})).items():
            for f in declared_fields(schema, doc, pointer='/components/schemas/' + pointer_part(name)):
                fields.append({**f, 'rol': 'model-de-date', 'model': name})
    grouped = {}
    for field in fields:
        key = (field['pointer'], field['rol'])
        if key not in grouped:
            grouped[key] = {**field, 'aparitii': []}
        if field.get('operatie'):
            occurrence = {'operatie': field['operatie'], 'cale': field['cale']}
            if field.get('status_raspuns'):
                occurrence['status_raspuns'] = field['status_raspuns']
            if occurrence not in grouped[key]['aparitii']:
                grouped[key]['aparitii'].append(occurrence)
    return list(grouped.values())[:MAX_FIELDS]


def json_type(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, int):
        return 'integer'
    if isinstance(value, float):
        return 'number'
    if isinstance(value, str):
        return 'string'
    return 'array' if isinstance(value, list) else 'object'


def observed_fields(doc):
    found = {}
    def walk(value, path='$', pointer='', depth=0):
        if depth > MAX_DEPTH or len(found) >= MAX_FIELDS:
            return
        if isinstance(value, dict):
            for key, child in list(value.items())[:MAX_FIELDS]:
                walk(child, path + '.' + key, pointer + '/' + pointer_part(key), depth + 1)
        elif isinstance(value, list):
            for n, child in enumerate(value[:SAMPLE_ROWS]):
                walk(child, path + '[]', pointer + '/' + str(n), depth + 1)
        else:
            if path not in found:
                found[path] = {'nume': path.rsplit('.', 1)[-1], 'cale': path, 'tipuri_observate': [],
                               'stare_tip': 'observat-in-esantion-json', 'rol': 'camp-date', 'pointer': pointer}
            typ = json_type(value)
            if typ not in found[path]['tipuri_observate']:
                found[path]['tipuri_observate'].append(typ)
    walk(doc)
    return list(found.values())


def sampling_limit(value, depth=0):
    if depth > MAX_DEPTH:
        return isinstance(value, (dict, list)) and bool(value)
    if isinstance(value, list):
        return len(value) > SAMPLE_ROWS or any(sampling_limit(v, depth + 1) for v in value[:SAMPLE_ROWS])
    if isinstance(value, dict):
        return len(value) > MAX_FIELDS or any(sampling_limit(v, depth + 1) for v in list(value.values())[:MAX_FIELDS])
    return False


def parse_source(body, url, content_type=''):
    if re.search(r'<(?:!doctype\s+html|html|head|body)(?:\s|>)', body[:1000], re.I):
        raise ValueError('HTML response at a schema/data URL')
    if re.search(r'\.(csv|tsv)(?:$|\?)', url, re.I) or 'csv' in content_type:
        sample = body.lstrip('\ufeff')
        try:
            dialect = csv.Sniffer().sniff(sample[:20000], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        rows = csv.reader(io.StringIO(sample), dialect)
        header = next(rows, [])
        if not header or len(set(header)) != len(header) or any(not h.strip() for h in header):
            raise ValueError('CSV header is empty or contains duplicate/unnamed columns')
        return 'csv', [{'nume': name, 'cale': name, 'tip_declarat': None, 'stare_tip': 'neprecizat-in-antet-csv',
                        'rol': 'camp-date', 'coloana_csv': n} for n, name in enumerate(header)], False
    doc = json.loads(body)
    if isinstance(doc, dict) and ('openapi' in doc or 'swagger' in doc):
        fields = openapi_fields(doc)
        return 'openapi', fields, len(fields) >= MAX_FIELDS
    if isinstance(doc, dict) and 'matrix_code' in doc and isinstance(doc.get('dimensions'), list):
        fields = [{'nume': d['dim_column_name'], 'cale': d['dim_column_name'], 'descriere': d.get('dim_label', ''),
                   'tip_semantic': d.get('dim_type'), 'rol': 'dimensiune', 'stare_tip': 'declarat-in-metadate',
                   'pointer': '/dimensions/' + str(n), 'valori_declarate': d.get('option_count')}
                  for n, d in enumerate(doc['dimensions']) if d.get('dim_column_name')]
        return 'metadate-ins', fields, False
    if isinstance(doc, dict) and (isinstance(doc.get('properties'), dict) or ('$schema' in doc and any(k in doc for k in ('items', 'allOf', 'anyOf', 'oneOf', '$defs', 'definitions'))) or ('$schema' in doc and doc.get('type') in ('object', 'array', 'string', 'integer', 'number', 'boolean', 'null'))):
        fields = declared_fields(doc, doc)
        return 'json-schema', fields, len(fields) >= MAX_FIELDS
    fields = observed_fields(doc)
    return 'json', fields, len(fields) >= MAX_FIELDS or sampling_limit(doc)


def file_url(url):
    """Convert an explicitly linked GitHub blob to its raw representation."""
    url = canonical(url)
    if not url:
        return ''
    parts = urlsplit(url)
    if parts.hostname == 'github.com':
        match = re.match(r'^/([^/]+/[^/]+)/blob/([^/]+)/(.+)$', parts.path)
        if match:
            return 'https://raw.githubusercontent.com/' + '/'.join(match.groups())
    return url


LINK_IN_TEXT = re.compile(r'https?://[^\s<>`"\])]+')
EXCLUDED_WORDS = ('package-lock', 'package.json', 'tsconfig.json', 'agent-card', 'mcp.json', 'vendor-list', '/agent-skills/')


def related_source(entry, url):
    """A source belongs to a project when it sits on its site, on an API subdomain, or in an explicitly linked raw file.
    Shared-host files outside the project path are excluded unless project-specific evidence links them."""
    host = urlsplit(url).hostname or ''
    own = urlsplit(entry['url']).hostname or ''
    related = host.removeprefix('www.') == own.removeprefix('www.') or host.endswith('.' + own.removeprefix('www.'))
    if not related and host != 'raw.githubusercontent.com':
        return False
    return not (host == own and scope_of(entry['url'], url) != 'proiect')


def discover_candidates(entry, documentation, verified_metadata=()):
    """Every structured-source candidate that the entry's own documentation links or names, with its locator.
    No limit applies here; the per-run limit is applied when a candidate is admitted."""
    found = {}
    for page in documentation.get('pages', []):
        if page['state'] != 'colectat' or page['scope'] != 'proiect':
            continue
        snapshot = 'documentare/' + page['snapshot'] if page.get('snapshot') else None
        located = [(link, 'link-in-documentatie', {'pointer': f'/links/{n}'}) for n, (link, _) in enumerate(page.get('links', []))]
        for match in LINK_IN_TEXT.finditer(page.get('text', '')):
            link = match.group(0).rstrip('.,;')
            located.append((link, 'url-in-text', {'pointer': '/text', 'interval': [match.start(), match.start() + len(link)]}))
        for link, method, where in located:
            link = link.rstrip('.,;')
            if '{' in link or not re.search(r'\.(json|csv|tsv|geojson)(?:$|\?)', link, re.I):
                continue
            url = file_url(link)
            if not url or any(word in url.lower() for word in EXCLUDED_WORDS) or not related_source(entry, url):
                continue
            if url not in found:
                found[url] = {'url': url, 'link_original': link, 'documentatie': page['final_url'], 'prioritate': priority(url),
                              'metoda': method, 'parinte': page['final_url'], 'descoperit_la': page.get('fetched_at'),
                              'dovada': {'url': page['final_url'], 'sha256': page.get('sha256'), 'snapshot': snapshot, **where}}
    # Reuse checked metadata links from editorial pilot records, without project-specific URLs in code.
    for evidence in verified_metadata:
        url = canonical(evidence.get('url', ''))
        if url:
            found[url] = {'url': url, 'link_original': url, 'documentatie': url, 'prioritate': 0, 'metoda': 'dovada-pilot',
                          'parinte': None, 'descoperit_la': None,
                          'dovada': {'url': url, 'sha256': evidence.get('sha256'), 'pointer': '/seturi_date_verificate',
                                     'snapshot': 'documentare/' + evidence['snapshot'] if evidence.get('snapshot') else None}}
    return sorted(found.values(), key=lambda r: (r['prioritate'], r['url']))


def candidate_sources(entry, documentation, maximum=3, verified_metadata=()):
    return discover_candidates(entry, documentation, verified_metadata)[:maximum]


def discovery_record(slug, candidate):
    return new_discovery(slug, candidate['url'], candidate['metoda'], parent=candidate['parinte'], evidence=candidate['dovada'],
                         original=candidate['link_original'], discovered_at=candidate['descoperit_la'], rank=candidate['prioritate'])


def analyse_source(response):
    metadata = {k: v for k, v in response.items() if k != 'body'}
    metadata.update(id=source_id(response['url']), campuri=[], completitudine='neconfirmat', snapshot='surse/' + source_id(response['url']) + '.json')
    if response['state'] != 'ok':
        return metadata
    body = response.get('body', '')
    metadata['sha256'] = hashlib.sha256(body.encode()).hexdigest()
    metadata['snapshot'] = 'surse/' + source_id(response['url']) + '-' + metadata['sha256'][:16] + '.json'
    try:
        fmt, fields, truncated = parse_source(body, response['final_url'], response.get('content_type', ''))
        metadata.update(format=fmt, campuri=fields, stare='analizat', completitudine='partial', limita_atinsa=truncated,
                        baza_tipului='esantion-date' if fmt == 'json' else 'antet-fara-tipuri' if fmt == 'csv' else 'schema-declarata')
    except (ValueError, TypeError, KeyError, csv.Error) as exc:
        metadata.update(stare='eroare-parsare', error=str(exc))
    return metadata


def control_candidates(record):
    """HTML control candidates of a project's own pages, and whether every page body was available locally."""
    controls, complete = {}, True
    for page in record.get('pages', []):
        if page['state'] != 'colectat' or page['scope'] != 'proiect':
            continue
        if 'input_candidates' not in page:
            complete = False
            continue
        controls_hash = hashlib.sha256(json.dumps(page.get('input_candidates', []), sort_keys=True).encode()).hexdigest()
        for control_index, control in enumerate(page.get('input_candidates', [])):
            name = control.get('name') or control.get('id') or control.get('aria-label') or control.get('placeholder')
            if not name:
                continue
            key = (name, control.get('type', ''))
            controls.setdefault(key, {'nume': name, 'rol': 'control-utilizator', 'tip_control_html': control.get('type'),
                                     'descriere': control.get('aria-label') or control.get('placeholder', ''),
                                     'stare_tip': 'control-html-candidat',
                                     'dovada': {'url': page['final_url'], 'sha256': page.get('sha256'), 'sha256_lista_controale': controls_hash,
                                                'pointer_snapshot': '/input_candidates/' + str(control_index), 'snapshot': 'documentare/' + page['snapshot'] if page.get('snapshot') else None}})
    return list(controls.values()), complete


def build_profile(entry, record, sources, refs, concepts, previous=None, notes=None):
    """One draft profile. When a documentation snapshot is missing locally, the previous controls stay."""
    controls, complete = control_candidates(record)
    if not complete and previous is not None:
        controls = previous.get('intrari_utilizator', [])
        if notes is not None:
            notes.append(f'{entry["slug"]}: documentation snapshots missing; previous HTML control candidates kept')
    fields = sum(len(sources[r]['campuri']) for r in refs if r in sources)
    gaps = ['Inventar parțial. Controalele HTML și tipurile observate nu definesc întregul model de date.']
    if not fields:
        gaps.append('Nu s-a verificat un dicționar sau o schemă de date în această trecere.')
    if record.get('state') != 'documentatie-gasita':
        gaps.append('Colectarea statică nu a confirmat o pagină de documentare specifică proiectului.')
    return {'slug': entry['slug'], 'nume': entry['nume'], 'stare': 'propunere', 'completitudine': 'partial' if fields or controls else 'neconfirmat',
            'scop': entry['descriere_scurta'] or entry['descriere'],
            'permite': [concepts.get(c, c) for c in entry.get('capabilities', [])],
            'formate_catalogate': [concepts.get(c, c) for c in entry.get('formats', [])],
            'baza_descrierii': {'tabel': 'intrari.csv', 'slug': entry['slug']},
            'intrari_utilizator': controls, 'surse_structurate': refs,
            'campuri_din_surse': fields, 'lacune': gaps}


def build_profiles(entries, docs, sources, candidates, concepts):
    return [build_profile(entry, docs.get(entry['slug'], {}), sources, [source_id(c['url']) for c in candidates[entry['slug']]], concepts)
            for entry in entries]


def pointer_value(document, pointer):
    if pointer == '':
        return document
    value = document
    for part in pointer.lstrip('/').split('/'):
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def check_report(out, observations):
    """Check local evidence hashes, field pointers, references and the registry without requests.
    `errors` are corrupt or inconsistent records. `unavailable` lists evidence bodies absent from this checkout;
    those are not hash-verified and are never counted as verified. `stale` lists sources whose last refresh failed."""
    report = {'errors': [], 'unavailable': [], 'verified': 0, 'stale': []}
    errors = report['errors']
    try:
        previous = load_previous(out)
    except StateError as exc:
        return {**report, 'errors': [str(exc)]}
    if not (out / 'seturi-date.json').exists() or not (out / 'proiecte.json').exists():
        return {**report, 'errors': [f'{out}: generated inventory files are missing']}
    sources, profiles = list(previous['sources'].values()), list(previous['profiles'].values())
    known = {s['id'] for s in sources}
    if len(known) != len(sources):
        errors.append('Duplicate structured source IDs.')
    for source in sources:
        if source_id(source['url']) != source['id']:
            errors.append('Source ID does not match URL: ' + source['url'])
        if source.get('ultima_incercare'):
            report['stale'].append(source['url'])
        if not source.get('sha256'):
            continue
        try:
            response = json.loads((out / source['snapshot']).read_text())
        except FileNotFoundError:
            report['unavailable'].append(source['url'])
            continue
        except (OSError, ValueError) as exc:
            errors.append(source['url'] + ': ' + str(exc))
            continue
        try:
            body = response['body']
            if hashlib.sha256(body.encode()).hexdigest() != source['sha256']:
                errors.append('Source hash mismatch: ' + source['url'])
                continue
            report['verified'] += 1
            if source.get('format') == 'csv':
                _, fields, _ = parse_source(body, source['final_url'], response.get('content_type', ''))
                if [f['nume'] for f in fields] != [f['nume'] for f in source['campuri']]:
                    errors.append('CSV headers differ: ' + source['url'])
            elif source.get('campuri'):
                document = json.loads(body)
                for field in source['campuri']:
                    try:
                        declaration = pointer_value(document, field['pointer'])
                        if field.get('stare_tip') == 'declarat-in-schema' and field.get('tip_declarat') is not None:
                            schema = declaration.get('schema', declaration) if isinstance(declaration, dict) else {}
                            schema = dereference(schema, document)
                            if schema.get('type') != field['tip_declarat']:
                                errors.append('Declared type differs: ' + source['url'] + ' ' + field['pointer'])
                    except (KeyError, TypeError, ValueError, IndexError):
                        errors.append('Invalid field pointer: ' + source['url'] + ' ' + str(field.get('pointer')))
        except (OSError, ValueError, KeyError, csv.Error) as exc:
            errors.append(source['url'] + ': ' + str(exc))
    for profile in profiles:
        if profile['stare'] != 'propunere' or profile['completitudine'] not in ('partial', 'neconfirmat'):
            errors.append('A generated profile claims acceptance or completeness: ' + profile['slug'])
        for reference in profile['surse_structurate']:
            if reference not in known:
                errors.append('Unknown source reference: ' + profile['slug'] + ' ' + reference)
        for control in profile['intrari_utilizator']:
            evidence = control['dovada']
            try:
                document = json.loads((observations / evidence['snapshot']).read_text())
                digest = hashlib.sha256(json.dumps(document['input_candidates'], sort_keys=True).encode()).hexdigest()
                if digest != evidence['sha256_lista_controale']:
                    errors.append('Control-list hash mismatch: ' + profile['slug'])
                candidate = pointer_value(document, evidence['pointer_snapshot'])
                name = candidate.get('name') or candidate.get('id') or candidate.get('aria-label') or candidate.get('placeholder')
                if name != control['nume'] or candidate.get('type') != control['tip_control_html']:
                    errors.append('Control differs from its evidence: ' + profile['slug'] + ' ' + control['nume'])
            except FileNotFoundError:
                report['unavailable'].append('documentation: ' + profile['slug'] + ' ' + str(evidence.get('snapshot')))
            except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
                errors.append(profile['slug'] + ': ' + str(exc))
    if previous['registry']:
        registry = registry_map(previous['discoveries'])
        errors += validate_state(profiles, sources, registry)
    return report


def check_inventory(out, observations):
    """The evidence errors only. Missing local bodies are reported by check_report, not counted as errors."""
    return check_report(out, observations)['errors']


# --- incremental update ------------------------------------------------------------------------------------------

def read_cache(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def attempt_of(metadata, when):
    """The last refresh attempt, kept next to (never instead of) the last good evidence."""
    return {'la': metadata.get('fetched_at') or when, 'stare': metadata.get('state') or metadata.get('stare'),
            'http_status': metadata.get('http_status'), 'eroare': metadata.get('error')}


def reconcile(previous, metadata, fresh, when):
    """Merge a new analysis of a source with its tracked record. Field evidence is replaced only by better evidence.

    A usable record whose refresh failed (request error, HTTP error, unparsable body) stays and gains `ultima_incercare`.
    A changed body keeps the earlier version in `versiuni_anterioare`. A fresh success clears an earlier failure."""
    if not previous:
        return metadata
    if usable(previous) and not usable(metadata):
        return {**previous, 'ultima_incercare': attempt_of(metadata, when)}
    result = dict(metadata)
    history = list(previous.get('versiuni_anterioare', []))
    if usable(previous) and usable(metadata) and previous['sha256'] != metadata['sha256']:
        history.append({k: previous[k] for k in ('sha256', 'fetched_at', 'snapshot') if k in previous})
    if history:
        result['versiuni_anterioare'] = history
    if not fresh and previous.get('ultima_incercare') and usable(metadata) and previous.get('sha256') == metadata.get('sha256'):
        result['ultima_incercare'] = previous['ultima_incercare']
    return result


def update_inventory(entries, docs, verified, previous, *, cache, selected=(), offline=False, force=False, max_files=3,
                     fetch=None, now=None, concepts=None, retire_sources=(), add_sources=()):
    """Compute the next inventory state from the tracked state, local documentation and caches.

    Only the selected projects change. `fetch` is called only for sources that selected projects use.
    Raises StateError before returning when the proposed state is invalid."""
    now = now or now_utc()
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    concepts = concepts or {}
    slugs = [e['slug'] for e in entries]
    by_slug = {e['slug']: e for e in entries}
    selected = set(selected)
    if selected - set(slugs):
        raise StateError('Unknown slug: ' + ', '.join(sorted(selected - set(slugs))))
    # New entries have no tracked record to protect; they are built from whatever local evidence exists.
    work = (selected or set(slugs)) | {s for s in slugs if s not in previous['profiles']}
    report = {'pastrate': [], 'reimprospatate': [], 'esuate': [], 'neinspectate': [], 'avertismente': [], 'cereri': 0, 'cache': 0}

    candidates = {s: discover_candidates(by_slug[s], docs.get(s, {}), verified.get(s, [])) for s in slugs}
    found = {(s, c['url']): discovery_record(s, c) for s in slugs for c in candidates[s]}
    registry = seed_registry(previous, found)
    for slug, url, reason in retire_sources:
        retire(registry, slug, url, reason, now)
    for slug, spec in add_sources:
        if slug not in by_slug:
            raise StateError('Unknown slug: ' + slug)
        url = canonical(spec['url'])
        if not url:
            raise StateError('Not an HTTP URL: ' + spec['url'])
        key = (slug, url)
        if key in registry and registry[key]['stare'] == 'retras':
            registry[key].update(stare='activ', retras=None)
            registry[key]['istoric'].append({'eveniment': 'reactivat', 'la': now})
        elif key not in registry:
            registry[key] = new_discovery(slug, url, spec.get('metoda', 'adaugat-explicit'), state='activ', parent=spec.get('parinte'),
                                          evidence=spec.get('dovada'), discovered_at=now, note=spec.get('nota'))
            registry[key]['istoric'].append({'eveniment': 'adaugat', 'la': now})
        elif registry[key]['stare'] == 'descoperit':
            registry[key]['stare'] = 'activ'
            registry[key]['istoric'].append({'eveniment': 'admis', 'la': now})
    for slug in sorted(work):
        for candidate in candidates[slug]:
            key = (slug, candidate['url'])
            if key not in registry:
                registry[key] = found[key]
            elif registry[key]['locator_stare'] == 'necunoscut' and candidate['dovada']:
                registry[key].update({k: found[key][k] for k in ('metoda', 'parinte', 'link_original', 'dovada', 'locator_stare', 'descoperit_la')})
                registry[key]['istoric'].append({'eveniment': 'locator-completat', 'la': now})
        for record in admit(registry, slug, max_files):
            record['istoric'].append({'eveniment': 'admis', 'la': now})
    for (slug, url), record in registry.items():
        if slug not in by_slug and record['stare'] != 'retras':
            retire(registry, slug, url, 'entry absent from the catalogue', now)

    urls = sorted({d['url'] for d in registry.values() if d['stare'] in ('activ', 'retras')})
    fetch_urls = {d['url'] for s in (selected or slugs) for d in active_members(registry, s)}

    def obtain(url):
        ident = source_id(url)
        path = cache / (ident + '.json')
        tracked = previous['sources'].get(ident)
        cached = read_cache(path)
        refresh = url in fetch_urls and not offline
        response, origin = None, None
        if cached is not None and not (refresh and force):
            response, origin = cached, 'cache'
        elif refresh:
            response, origin = fetch(url), 'retea'
            if response.get('state') == 'limita-cereri':
                response, origin = None, 'omis'
        if response is None:
            if tracked:
                return url, tracked, ('neinspectat' if origin == 'omis' else 'pastrat-fara-cache' if url in fetch_urls else 'neatins')
            return url, analyse_source({'url': url, 'state': 'necolectat'}), 'necolectat'
        if origin == 'retea' and (response.get('state') == 'ok' or cached is None or cached.get('state') != 'ok'):
            write_file_atomic(path, dump(response))
        metadata = analyse_source(response)
        if metadata.get('sha256'):
            snapshot = cache.parent / metadata['snapshot']
            if not snapshot.exists():
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                write_file_atomic(snapshot, dump(response))
        merged = reconcile(tracked, metadata, origin == 'retea', now)
        if origin == 'retea':
            outcome = 'reimprospatat' if merged is not tracked and usable(merged) and not merged.get('ultima_incercare') else 'esuat'
        else:
            outcome = 'cache'
        return url, merged, outcome

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(obtain, urls))
    sources = {}
    for url, metadata, outcome in results:
        sources[metadata['id']] = metadata
        key = {'reimprospatat': 'reimprospatate', 'esuat': 'esuate', 'neinspectat': 'neinspectate',
               'pastrat-fara-cache': 'pastrate'}.get(outcome)
        if key:
            report[key].append(url)
        report['cache'] += outcome == 'cache'
    for ident, old in previous['sources'].items():
        sources.setdefault(ident, old)  # a tracked source nothing references any more is history, not garbage

    profiles = []
    for entry in entries:
        slug = entry['slug']
        old = previous['profiles'].get(slug)
        refs = [d['sursa_id'] for d in active_members(registry, slug)]
        if slug in work:
            profiles.append(build_profile(entry, docs.get(slug, {}), sources, refs, concepts, old, report['avertismente']))
        else:
            profiles.append({**old, 'campuri_din_surse': sum(len(sources[r]['campuri']) for r in old['surse_structurate'] if r in sources)})
    ordered = sorted(sources.values(), key=lambda s: s['url'])
    errors = validate_state(profiles, ordered, registry, previous)
    if errors:
        raise StateError('Proposed inventory is invalid:\n  ' + '\n  '.join(errors[:20]))
    return {'profiles': profiles, 'sources': ordered, 'registry': registry, 'report': report}


def render_outputs(state):
    """Serialise a state into the six generated files. Deterministic: the same state gives the same bytes."""
    profiles, sources, registry = state['profiles'], state['sources'], state['registry']

    def table(header, rows):
        stream = io.StringIO()
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(header)
        writer.writerows(rows)
        return stream.getvalue()

    owners = {}
    for profile in profiles:
        for ident in profile['surse_structurate']:
            owners.setdefault(ident, []).append(profile['slug'])
    field_rows = []
    for source in sources:
        for field in source['campuri']:
            declared = field.get('tip_declarat')
            if isinstance(declared, list):
                declared = json.dumps(declared)
            operations = sorted({a['operatie'] for a in field.get('aparitii', []) if a.get('operatie')})
            field_rows.append(['|'.join(owners.get(source['id'], [])), source['id'], source['url'], source.get('format'),
                               field.get('rol'), field['nume'], field['cale'], declared,
                               '|'.join(field.get('tipuri_observate', [])), field.get('tip_semantic'),
                               field.get('unitate'), field.get('descriere'), '|'.join(operations),
                               field.get('pointer', 'coloana-csv:' + str(field.get('coloana_csv'))), field['stare_tip']])
    return {
        'proiecte.json': dump({'versiune': 1, 'stare': 'propuneri', 'proiecte': profiles}),
        'seturi-date.json': dump({'versiune': 1, 'surse': sources}),
        REGISTRY: dump({'versiune': 1, 'stare': 'propuneri', 'descoperiri': sorted_registry(registry)}),
        'rezumat.csv': table(['slug', 'stare', 'completitudine', 'controale_utilizator', 'surse_structurate', 'campuri_din_surse'],
                             [[p['slug'], p['stare'], p['completitudine'], len(p['intrari_utilizator']), len(p['surse_structurate']),
                               p['campuri_din_surse']] for p in profiles]),
        'campuri.csv': table(['proiecte', 'sursa_id', 'url', 'format', 'rol', 'nume', 'cale', 'tip_declarat', 'tipuri_observate',
                              'tip_semantic', 'unitate', 'descriere', 'operatii', 'pointer_dovada', 'stare_tip'], field_rows),
        'intrari-utilizator.csv': table(['slug', 'nume', 'tip_control_html', 'descriere', 'url_dovada', 'pointer_snapshot', 'stare_tip'],
                                        [[p['slug'], f['nume'], f['tip_control_html'], f['descriere'], f['dovada']['url'],
                                          f['dovada']['pointer_snapshot'], f['stare_tip']] for p in profiles for f in p['intrari_utilizator']]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data-dir', type=Path, default=PUBLIC_ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--only', default='', help='comma-separated slugs; other projects keep their records and evidence')
    parser.add_argument('--offline', action='store_true', help='no requests; a missing cache keeps the tracked record')
    parser.add_argument('--check', action='store_true', help='check existing evidence and references; no requests or rewrites')
    parser.add_argument('--strict-snapshots', action='store_true', help='with --check: fail when local evidence bodies are absent')
    parser.add_argument('--dry-run', action='store_true', help='compute and report the next state; write nothing')
    parser.add_argument('--force', action='store_true', help='fetch selected sources again even when a cache exists')
    parser.add_argument('--max-files', type=int, default=3, help='admit new sources until a project has this many members')
    parser.add_argument('--max-requests', type=int, help='stop fetching after this many direct requests in this run')
    parser.add_argument('--lot', default='', help='name of the collection batch; enables the request log')
    parser.add_argument('--budget', type=int, help='with --lot: total direct requests allowed for the batch across runs')
    parser.add_argument('--retire', nargs=2, action='append', metavar=('SLUG', 'URL'), default=[], help='retire a source membership; needs --reason')
    parser.add_argument('--reason', default='', help='reason recorded with --retire')
    parser.add_argument('--add-source', nargs=2, action='append', metavar=('SLUG', 'URL'), default=[],
                        help='add an explicitly identified structured source to a project')
    parser.add_argument('--method', default='adaugat-explicit', help='with --add-source: how the source was identified')
    parser.add_argument('--parent', help='with --add-source: the page or repository where the source was identified')
    parser.add_argument('--note', help='with --add-source: a short note kept with the discovery')
    args = parser.parse_args()
    if args.max_files < 1 or (args.max_requests is not None and args.max_requests < 0):
        parser.error('--max-files must be positive and --max-requests cannot be negative')
    if args.retire and not args.reason.strip():
        parser.error('--retire needs a recorded --reason')
    if data_schema(args.data_dir) != 'v2':
        parser.error('Variable inventories require a taxonomy v2 data root.')
    obs = observation_paths(args.data_dir)['profile'].parent
    out = args.out or obs / 'inventare'
    if args.check:
        report = check_report(out, obs)
        for error in report['errors']:
            print('ERROR: ' + error)
        for item in report['unavailable']:
            print('UNAVAILABLE (not verified): ' + item)
        for url in report['stale']:
            print('STALE (last refresh failed): ' + url)
        print(f'{len(report["errors"])} inventory evidence errors; {report["verified"]} source bodies hash-verified; '
              f'{len(report["unavailable"])} local bodies unavailable and not verified; {len(report["stale"])} sources with a failed refresh')
        return int(bool(report['errors']) or (args.strict_snapshots and bool(report['unavailable'])))
    entries = load_catalogue(args.data_dir)
    selected = set(filter(None, args.only.split(',')))
    if selected - {e['slug'] for e in entries}:
        parser.error('Unknown slug: ' + ', '.join(sorted(selected - {e['slug'] for e in entries})))
    docs = restore(obs / 'documentare')
    pilot_path = obs / 'documentare/pilot-inventare.json'
    pilots = json.loads(pilot_path.read_text()).get('proiecte', []) if pilot_path.exists() else []
    verified = {p['slug']: [d['dovada'] for d in p.get('seturi_date_verificate', [])] for p in pilots}
    concepts = {c: row['eticheta_ro'] for c, row in load_vocabulary(args.data_dir)['concepts'].items()}
    log = RequestLog(out / 'jurnal-cereri.csv', args.lot) if args.lot else None
    limit = args.max_requests
    if log and args.budget is not None:
        left = args.budget - log.direct_requests()
        limit = left if limit is None else min(limit, left)
    fetcher = Fetcher(timeout=12, max_requests=limit, log=log, purpose='inventar')
    try:
        previous = load_previous(out)
        state = update_inventory(
            entries, docs, verified, previous, cache=out / 'surse', selected=selected, offline=args.offline, force=args.force,
            max_files=args.max_files, fetch=fetcher, concepts=concepts,
            retire_sources=[(slug, canonical(url), args.reason) for slug, url in args.retire],
            add_sources=[(slug, {'url': url, 'metoda': args.method, 'parinte': args.parent, 'nota': args.note}) for slug, url in args.add_source])
        if not args.dry_run:
            write_atomic(out, render_outputs(state))
    except StateError as exc:
        print('ERROR: ' + str(exc))
        print('No inventory file was changed.')
        return 2
    report = state['report']
    for key, label in (('reimprospatate', 'refreshed'), ('esuate', 'refresh failed; last evidence kept'),
                       ('pastrate', 'no local body; tracked record kept'), ('neinspectate', 'not inspected: request limit reached')):
        for url in report[key]:
            print(f'{label}: {url}')
    for note in report['avertismente']:
        print('WARNING: ' + note)
    profiles, sources = state['profiles'], state['sources']
    print(f'{len(profiles)} project drafts; {sum(bool(p["campuri_din_surse"]) for p in profiles)} with structured fields; '
          f'{sum(len(s["campuri"]) for s in sources)} shared field records; {fetcher.requests} requests'
          + ('; dry run, nothing written' if args.dry_run else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
