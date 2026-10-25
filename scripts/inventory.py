"""Draft variable inventories from collected documentation and linked schemas/data. Stdlib only.

    python3 scripts/inventory.py                 # cached docs; fetch at most 3 linked files per entry
    python3 scripts/inventory.py --offline       # no requests; rebuild from local evidence
    python3 scripts/inventory.py --only demoanaf --force

Outputs stay in observatii/inventare/. No catalogue or site field is changed.
Declared schema types, observed JSON types and HTML control types stay distinct.
Every result remains partial and requires editorial review.
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


def candidate_sources(entry, documentation, maximum=3, verified_metadata=()):
    found = {}
    for page in documentation.get('pages', []):
        if page['state'] != 'colectat' or page['scope'] != 'proiect':
            continue
        links = [u for u, _ in page.get('links', [])]
        links += re.findall(r'https?://[^\s<>`"\])]+', page.get('text', ''))
        for link in links:
            link = link.rstrip('.,;')
            if '{' in link or not re.search(r'\.(json|csv|tsv|geojson)(?:$|\?)', link, re.I):
                continue
            url = file_url(link)
            if not url or any(word in url.lower() for word in ('package-lock', 'package.json', 'tsconfig.json', 'agent-card', 'mcp.json', 'vendor-list', '/agent-skills/')):
                continue
            host = urlsplit(url).hostname or ''
            own = urlsplit(entry['url']).hostname or ''
            # API subdomains belong to the same site; raw GitHub files must be explicitly linked from its documentation.
            related = host.removeprefix('www.') == own.removeprefix('www.') or host.endswith('.' + own.removeprefix('www.'))
            if not related and host != 'raw.githubusercontent.com':
                continue
            if host == own and scope_of(entry['url'], url) != 'proiect':
                continue
            priority = 0 if 'openapi' in url.lower() or 'swagger' in url.lower() else 1 if '.csv' in url.lower() else 2
            priority += 3 if '/en/' in url else 0
            found[url] = {'url': url, 'link_original': link, 'documentatie': page['final_url'], 'prioritate': priority}
    # Reuse checked metadata links from editorial pilot records, without project-specific URLs in code.
    for evidence in verified_metadata:
        url = canonical(evidence.get('url', ''))
        if url:
            found[url] = {'url': url, 'link_original': url, 'documentatie': url, 'prioritate': 0}
    return sorted(found.values(), key=lambda r: (r['prioritate'], r['url']))[:maximum]


def source_id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20]


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


def build_profiles(entries, docs, sources, candidates, concepts):
    profiles = []
    for entry in entries:
        record = docs.get(entry['slug'], {})
        controls = {}
        for page in record.get('pages', []):
            if page['state'] != 'colectat' or page['scope'] != 'proiect':
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
        refs = [source_id(c['url']) for c in candidates[entry['slug']]]
        fields = sum(len(sources[r]['campuri']) for r in refs)
        gaps = ['Inventar parțial. Controalele HTML și tipurile observate nu definesc întregul model de date.']
        if not fields:
            gaps.append('Nu s-a verificat un dicționar sau o schemă de date în această trecere.')
        if record.get('state') != 'documentatie-gasita':
            gaps.append('Colectarea statică nu a confirmat o pagină de documentare specifică proiectului.')
        profiles.append({'slug': entry['slug'], 'nume': entry['nume'], 'stare': 'propunere', 'completitudine': 'partial' if fields or controls else 'neconfirmat',
                         'scop': entry['descriere_scurta'] or entry['descriere'],
                         'permite': [concepts.get(c, c) for c in entry.get('capabilities', [])],
                         'formate_catalogate': [concepts.get(c, c) for c in entry.get('formats', [])],
                         'baza_descrierii': {'tabel': 'intrari.csv', 'slug': entry['slug']},
                         'intrari_utilizator': list(controls.values()), 'surse_structurate': refs,
                         'campuri_din_surse': fields, 'lacune': gaps})
    return profiles


def pointer_value(document, pointer):
    if pointer == '':
        return document
    value = document
    for part in pointer.lstrip('/').split('/'):
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def check_inventory(out, observations):
    """Check local evidence hashes, field pointers and source references without requests."""
    errors = []
    try:
        sources = json.loads((out / 'seturi-date.json').read_text())['surse']
        profiles = json.loads((out / 'proiecte.json').read_text())['proiecte']
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    known = {s['id'] for s in sources}
    if len(known) != len(sources):
        errors.append('Duplicate structured source IDs.')
    for source in sources:
        if source_id(source['url']) != source['id']:
            errors.append('Source ID does not match URL: ' + source['url'])
        if not source.get('sha256'):
            continue
        try:
            response = json.loads((out / source['snapshot']).read_text())
            body = response['body']
            if hashlib.sha256(body.encode()).hexdigest() != source['sha256']:
                errors.append('Source hash mismatch: ' + source['url'])
                continue
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
            except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
                errors.append(profile['slug'] + ': ' + str(exc))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=PUBLIC_ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--only', default='')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--check', action='store_true', help='check existing evidence and references; no requests or rewrites')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--max-files', type=int, default=3)
    args = parser.parse_args()
    if args.max_files < 1:
        parser.error('--max-files must be positive')
    if data_schema(args.data_dir) != 'v2':
        parser.error('Variable inventories require a taxonomy v2 data root.')
    obs = observation_paths(args.data_dir)['profile'].parent
    out = args.out or obs / 'inventare'
    if args.check:
        errors = check_inventory(out, obs)
        for error in errors:
            print('ERROR: ' + error)
        print(f'{len(errors)} inventory evidence errors')
        return int(bool(errors))
    cache = out / 'surse'
    cache.mkdir(parents=True, exist_ok=True)
    entries = load_catalogue(args.data_dir)
    selected = set(filter(None, args.only.split(',')))
    if selected - {e['slug'] for e in entries}:
        parser.error('Unknown slug: ' + ', '.join(sorted(selected - {e['slug'] for e in entries})))
    docs = restore(obs / 'documentare')
    pilot_path = obs / 'documentare/pilot-inventare.json'
    pilots = json.loads(pilot_path.read_text()).get('proiecte', []) if pilot_path.exists() else []
    verified = {p['slug']: [d['dovada'] for d in p.get('seturi_date_verificate', [])] for p in pilots}
    candidates = {e['slug']: candidate_sources(e, docs.get(e['slug'], {}), args.max_files, verified.get(e['slug'], [])) for e in entries}
    urls = {c['url'] for e in entries for c in candidates[e['slug']]}
    fetch_urls = {c['url'] for e in entries if not selected or e['slug'] in selected for c in candidates[e['slug']]}
    fetcher = Fetcher(timeout=12)
    def obtain(url):
        path = cache / (source_id(url) + '.json')
        if path.exists() and (args.offline or url not in fetch_urls or not args.force):
            response = json.loads(path.read_text())
        elif not args.offline and url in fetch_urls:
            response = fetcher(url)
            path.write_text(json.dumps(response, ensure_ascii=False, indent=2) + '\n')
            print(response['state'] + ' ' + url, flush=True)
        else:
            response = {'url': url, 'state': 'necolectat'}
        metadata = analyse_source(response)
        if metadata.get('sha256'):
            (out / metadata['snapshot']).write_text(json.dumps(response, ensure_ascii=False, indent=2) + '\n')
        return url, metadata
    with ThreadPoolExecutor(max_workers=6) as pool:
        sources = {r['id']: r for _, r in pool.map(obtain, sorted(urls))}
    concepts = {c: row['eticheta_ro'] for c, row in load_vocabulary(args.data_dir)['concepts'].items()}
    profiles = build_profiles(entries, docs, sources, candidates, concepts)
    for name, value in [('proiecte.json', {'versiune': 1, 'stare': 'propuneri', 'proiecte': profiles}),
                        ('seturi-date.json', {'versiune': 1, 'surse': list(sources.values())})]:
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    with (out / 'rezumat.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['slug', 'stare', 'completitudine', 'controale_utilizator', 'surse_structurate', 'campuri_din_surse'])
        for p in profiles:
            writer.writerow([p['slug'], p['stare'], p['completitudine'], len(p['intrari_utilizator']), len(p['surse_structurate']), p['campuri_din_surse']])
    owners = {}
    for profile in profiles:
        for ident in profile['surse_structurate']:
            owners.setdefault(ident, []).append(profile['slug'])
    with (out / 'campuri.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['proiecte', 'sursa_id', 'url', 'format', 'rol', 'nume', 'cale', 'tip_declarat',
                         'tipuri_observate', 'tip_semantic', 'unitate', 'descriere', 'operatii', 'pointer_dovada', 'stare_tip'])
        for source in sources.values():
            for field in source['campuri']:
                declared = field.get('tip_declarat')
                if isinstance(declared, list):
                    declared = json.dumps(declared)
                operations = sorted({a['operatie'] for a in field.get('aparitii', []) if a.get('operatie')})
                writer.writerow(['|'.join(owners.get(source['id'], [])), source['id'], source['url'], source.get('format'),
                                 field.get('rol'), field['nume'], field['cale'], declared,
                                 '|'.join(field.get('tipuri_observate', [])), field.get('tip_semantic'),
                                 field.get('unitate'), field.get('descriere'), '|'.join(operations),
                                 field.get('pointer', 'coloana-csv:' + str(field.get('coloana_csv'))), field['stare_tip']])
    with (out / 'intrari-utilizator.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['slug', 'nume', 'tip_control_html', 'descriere', 'url_dovada', 'pointer_snapshot', 'stare_tip'])
        for profile in profiles:
            for field in profile['intrari_utilizator']:
                writer.writerow([profile['slug'], field['nume'], field['tip_control_html'], field['descriere'],
                                 field['dovada']['url'], field['dovada']['pointer_snapshot'], field['stare_tip']])
    print(f'{len(profiles)} project drafts; {sum(bool(p["campuri_din_surse"]) for p in profiles)} with structured fields; '
          f'{sum(len(s["campuri"]) for s in sources.values())} shared field records; {fetcher.requests} requests')


if __name__ == '__main__':
    raise SystemExit(main())
