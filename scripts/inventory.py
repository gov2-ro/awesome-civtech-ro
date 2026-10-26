"""Draft variable inventories from collected documentation and linked schemas/data. Stdlib only.

    python3 scripts/inventory.py                 # cached docs; admit at most 3 linked files per entry
    python3 scripts/inventory.py --offline       # no requests; rebuild from local evidence
    python3 scripts/inventory.py --only demoanaf --force
    python3 scripts/inventory.py --dry-run       # compute and report; write nothing
    python3 scripts/inventory.py --import-saved SLUG URL FILE --saved-at 2026-10-25T20:39:00+02:00
                                                 # keep a page that the owner saved from their browser; no request

Outputs stay in observatii/inventare/. No catalogue or site field is changed.
Declared schema types, observed JSON types and HTML control types stay distinct.
Every result remains partial and requires editorial review.

Runs are incremental. The tracked state is read first. A run changes only the selected projects (--only) and the
sources they use. Other projects keep their records, references and evidence. A source that cannot be refreshed
(failed request, missing cache, failed parse) keeps its last good evidence and records the failed attempt.
Discoveries live in descoperiri.json, separate from the per-run limits. A run writes all files or none.
A page that the owner saved (--import-saved) keeps its own origin, `copie-salvata-de-proprietar`; it is never labelled as fetched and never requested.
A host in data/taxonomy-v2/colectare-interzisa.csv is never requested, --force and --probe included, and neither is a redirect to it.
The run reports it as `colectare-interzisa` with the reason of the list; the request log gets no row and the request limit does not count it.
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

from collect_docs import Fetcher, canonical, flat, is_saved, restore, saved_copy, saved_errors, scope_of
from common import FORBIDDEN_STATE, PUBLIC_ROOT, data_schema, forbidden, load_catalogue, load_vocabulary, observation_paths
from inventory_concepts import EvidenceLocator, check_concepts, validate_families
from inventory_apidocs import operations as api_operations
from inventory_csvcards import csv_datasets
from inventory_datasette import FORMAT as DATASETTE, database as datasette_database, is_listing as is_datasette, read as datasette_fields
from inventory_ins import ins_dataset, ins_listing, ins_measure, is_listing
from inventory_literals import datasets as literal_datasets, declarations as literal_declarations
from inventory_setlist import list_datasets
from inventory_sheet import header_facts, read as read_sheet
from inventory_text import EXTENSIONS, read_text
from inventory_state import (REGISTRY, counted_fields, RequestLog, StateError, active_members, admit, check_text, dump, load_previous,
                             new_discovery, now_utc, priority, protect, registry_map, retire, seed_registry, sorted_registry,
                             source_id, usable, validate_state, write_atomic, write_file_atomic)

MAX_FIELDS, MAX_DEPTH, SAMPLE_ROWS = 2000, 7, 25
# An object with more keys than this is a keyed collection (identifier -> record), not a record with that many members.
KEYED_COLLECTION = 100
TEXT_FORMATS = ('html-tabele', 'markdown', 'csharp', 'sql', 'php', 'js-acces', 'json-comentat', 'html-api-docs', 'html-carduri-csv', 'js-literale',
                'html-lista-seturi')


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
        if isinstance(value, dict) and len(value) > KEYED_COLLECTION:
            # Sample the first values like array elements. One path per key would turn identifiers into field names.
            here = path + '{*}'
            found.setdefault(here, {'nume': path.rsplit('.', 1)[-1] + '{*}', 'cale': here, 'tipuri_observate': ['object'],
                                    'stare_tip': 'observat-in-esantion-json', 'rol': 'colectie-cu-chei', 'pointer': pointer,
                                    'numar_chei': len(value)})
            for key, child in list(value.items())[:SAMPLE_ROWS]:
                walk(child, here, pointer + '/' + pointer_part(key), depth + 1)
        elif isinstance(value, dict):
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
        return len(value) > KEYED_COLLECTION or any(sampling_limit(v, depth + 1) for v in list(value.values())[:MAX_FIELDS])
    return False


def has_csv_options(hint):
    """True when the reader of a source is {"tip": "csv", ...} with at least one option (see inventory_sheet)."""
    return isinstance(hint, dict) and hint.get('tip') == 'csv' and len(hint) > 1


def parse_source(body, url, content_type='', hint=None):
    """Parse a retained body. `hint` is the registry's `citire`: a reader name, or {'tip': name, ...options}. Without a hint the
    URL's extension picks a code reader; HTML at a schema/data URL is still an error."""
    kind = hint.get('tip') if isinstance(hint, dict) else hint
    if kind and kind != 'csv':
        return read_text(body, kind, hint if isinstance(hint, dict) else None)
    if has_csv_options(hint):
        return 'csv', read_sheet(body, hint), False
    extension = re.search(r'(\.[a-z]{2,4})(?:$|\?)', url, re.I)
    if extension and extension.group(1).lower() in EXTENSIONS:
        return read_text(body, EXTENSIONS[extension.group(1).lower()])
    if re.search(r'<(?:!doctype\s+html|html|head|body)(?:\s|>)', body[:1000], re.I):
        raise ValueError('HTML response at a schema/data URL')
    if kind == 'csv' or re.search(r'\.(csv|tsv)(?:$|\?)', url, re.I) or 'csv' in content_type:
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
    if isinstance(doc, dict) and re.match(r'^\d+(\.\d+)*', str(doc.get('openapi') or doc.get('swagger') or '')):
        fields = openapi_fields(doc)
        return 'openapi', fields, len(fields) >= MAX_FIELDS
    if isinstance(doc, dict) and 'matrix_code' in doc and isinstance(doc.get('dimensions'), list):
        fields = [{'nume': d['dim_column_name'], 'cale': d['dim_column_name'], 'descriere': d.get('dim_label', ''),
                   'tip_semantic': d.get('dim_type'), 'rol': 'dimensiune', 'stare_tip': 'declarat-in-metadate',
                   'pointer': '/dimensions/' + str(n), 'valori_declarate': d.get('option_count')}
                  for n, d in enumerate(doc['dimensions']) if d.get('dim_column_name')]
        fields.append(ins_measure(doc))
        return 'metadate-ins', fields, False
    if isinstance(doc, dict) and (isinstance(doc.get('properties'), dict) or ('$schema' in doc and any(k in doc for k in ('items', 'allOf', 'anyOf', 'oneOf', '$defs', 'definitions'))) or ('$schema' in doc and doc.get('type') in ('object', 'array', 'string', 'integer', 'number', 'boolean', 'null'))):
        fields = declared_fields(doc, doc)
        return 'json-schema', fields, len(fields) >= MAX_FIELDS
    if is_datasette(doc):
        fields, truncated = datasette_fields(doc)
        return DATASETTE, fields, truncated
    fields = observed_fields(doc)
    if is_listing(doc):
        return 'lista-ins', fields, len(fields) >= MAX_FIELDS or sampling_limit(doc)
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


# A Google Sheets export redirects to a signed address whose path holds an access token and the number of a Google account:
# https://doc-NN-c0-sheets.googleusercontent.com/export/<token>/<token>/<time>/<account>/*/<file id>?format=csv
SIGNED_EXPORT = re.compile(r'^(https://[a-z0-9-]+\.googleusercontent\.com/export/)[^?#]*/([^/?#]+)((?:[?#].*)?)$')


def public_url(url):
    """The address as the tracked files keep it: a signed Google export address loses its token and account segments.
    The host, the file ID and the query stay, so the format test of `parse_source` gives the same answer."""
    match = SIGNED_EXPORT.match(url or '')
    return f'{match.group(1)}…/{match.group(2)}{match.group(3)}' if match else url


def analyse_source(response, hint=None):
    metadata = {k: v for k, v in response.items() if k != 'body'}
    if 'final_url' in metadata:
        metadata['final_url'] = public_url(metadata['final_url'])
    if hint:
        metadata['citire'] = hint
    metadata.update(id=source_id(response['url']), campuri=[], completitudine='neconfirmat', snapshot='surse/' + source_id(response['url']) + '.json')
    if response['state'] != 'ok':
        return metadata
    body = response.get('body', '')
    metadata['sha256'] = hashlib.sha256(body.encode()).hexdigest()
    metadata['snapshot'] = 'surse/' + source_id(response['url']) + '-' + metadata['sha256'][:16] + '.json'
    try:
        fmt, fields, truncated = parse_source(body, response['final_url'], response.get('content_type', ''), hint)
        metadata.update(format=fmt, campuri=fields, stare='analizat', completitudine='partial', limita_atinsa=truncated,
                        baza_tipului=('esantion-date' if fmt in ('json', 'lista-ins', 'js-literale') else 'antet-fara-tipuri' if fmt == 'csv'
                                      else 'lista-fara-tipuri' if fmt == DATASETTE
                                      else 'cod-sau-documentatie' if fmt in TEXT_FORMATS else 'schema-declarata'))
        if has_csv_options(hint):
            metadata['antet'] = header_facts(body, hint)
        if fmt == 'metadate-ins':
            metadata['set_date'] = ins_dataset(json.loads(body))
        elif fmt == 'lista-ins':
            metadata['catalog'] = ins_listing(json.loads(body))
        elif fmt == DATASETTE:
            metadata['baza'] = datasette_database(json.loads(body))
        elif fmt == 'html-api-docs':
            metadata['operatii'] = api_operations(body)
        elif fmt == 'html-carduri-csv':
            metadata['seturi'] = csv_datasets(body, response['final_url'])
        elif fmt == 'html-lista-seturi':
            metadata['seturi'] = list_datasets(body)
        elif fmt == 'js-literale':
            metadata['declaratii'] = literal_declarations(body)
            metadata['seturi_ld'] = literal_datasets(body)
    except (ValueError, TypeError, KeyError, csv.Error) as exc:
        metadata.update(stare='eroare-parsare', error=str(exc))
    return metadata


# --- comparison of an API documentation page with the OpenAPI contract of the same project ---------------------------

HTTP_METHODS = ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
CONTRACT_ROLES = ('parametru-api', 'corp-cerere')


def contract_index(document):
    """What an OpenAPI document declares: operations by name, and request inputs by (role, operation, name), each with its pointer."""
    operations, inputs = {}, {}
    for path, raw_item in document.get('paths', {}).items():
        item = dereference(raw_item, document)
        for method in item:
            if method in HTTP_METHODS:
                operations[method.upper() + ' ' + path] = '/paths/' + pointer_part(path) + '/' + method
    for field in openapi_fields(document):
        if field.get('rol') in CONTRACT_ROLES:
            for occurrence in field.get('aparitii', []):
                inputs.setdefault((field['rol'], occurrence['operatie'], field['nume']), field['pointer'])
    return operations, inputs


def strip_links(source):
    """The source without the contract comparison, as the reader alone produces it."""
    bare = {k: v for k, v in source.items() if k != 'comparatie_contract'}
    bare['campuri'] = [{k: v for k, v in f.items() if k != 'in_contract'} for f in source.get('campuri', [])]
    bare['operatii'] = [{k: v for k, v in o.items() if k != 'in_contract'} for o in source.get('operatii', [])]
    return bare


def link_contract(source, contract, document):
    """A copy of an API documentation source that says, for every operation and request input, whether the contract declares it.
    `in_contract` is {sursa_id, pointer} when it does and null when the comparison found nothing. A field with no operation (a response
    member) is not compared. `comparatie_contract` pins the contract version and counts both sides."""
    operations, inputs = contract_index(document)

    def link(pointer):
        return {'sursa_id': contract['id'], 'pointer': pointer} if pointer else None

    linked = strip_links(source)
    linked['operatii'] = [{**o, 'in_contract': link(operations.get(o['operatie']))} for o in linked['operatii']]
    page_inputs = set()
    for index, field in enumerate(linked['campuri']):
        if field.get('operatie') and field.get('rol') in CONTRACT_ROLES:
            key = (field['rol'], field['operatie'], field['nume'])
            page_inputs.add(key)
            linked['campuri'][index] = {**field, 'in_contract': link(inputs.get(key))}
    shared = lambda items: sum(1 for i in items if i.get('in_contract'))
    page_fields = [f for f in linked['campuri'] if 'in_contract' in f]
    linked['comparatie_contract'] = {
        'sursa_id': contract['id'], 'url': contract['url'], 'sha256': contract['sha256'],
        'operatii_comune': shared(linked['operatii']), 'operatii_doar_in_pagina': len(linked['operatii']) - shared(linked['operatii']),
        'operatii_doar_in_contract': sorted(set(operations) - {o['operatie'] for o in linked['operatii']}),
        'intrari_comune': shared(page_fields), 'intrari_doar_in_pagina': len(page_fields) - shared(page_fields),
        'intrari_doar_in_contract': sorted(f'{op} :: {name}' for (role, op, name) in inputs if (role, op, name) not in page_inputs)}
    return linked


def contract_document(root, contract):
    """The retained OpenAPI document of a contract source, or None when this checkout does not hold a body with the recorded hash."""
    try:
        body = json.loads((Path(root) / contract['snapshot']).read_text())['body']
        return json.loads(body) if hashlib.sha256(body.encode()).hexdigest() == contract.get('sha256') else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def contract_of(source, sources):
    """The contract source that an API documentation source names in its reader options (`citire.contract`), or None."""
    hint = source.get('citire')
    url = canonical(hint.get('contract', '')) if isinstance(hint, dict) else ''
    contract = sources.get(source_id(url)) if url else None
    return contract if usable(contract) else None


def apply_contracts(sources, root):
    """Compare each API documentation source with its contract. A contract body that is absent leaves the source as it is."""
    for ident, source in list(sources.items()):
        contract = contract_of(source, sources) if source.get('format') == 'html-api-docs' and usable(source) else None
        document = contract_document(root, contract) if contract else None
        if document is not None:
            sources[ident] = link_contract(source, contract, document)


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
    fields = sum(len(counted_fields(sources[r])) for r in refs if r in sources)
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
    report = {'errors': [], 'unavailable': [], 'verified': 0, 'stale': [], 'concept_stale': [], 'concept_verified': 0,
              'saved': {'total': 0, 'verified': 0, 'unavailable': 0}}
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
        saved = is_saved(source)
        if saved:
            report['saved']['total'] += 1
            errors += [f'{source["url"]}: {problem}' for problem in saved_errors(source)]
        if not source.get('sha256'):
            continue
        try:
            response = json.loads((out / source['snapshot']).read_text())
        except FileNotFoundError:
            report['unavailable'].append(source['url'])
            report['saved']['unavailable'] += saved
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
            if saved:
                report['saved']['verified'] += 1
                if not source.get('redactari') and source.get('sha256_fisier') != source['sha256']:
                    errors.append('The retained body is not the file that the owner saved: ' + source['url'])
            if source.get('format') == 'csv':
                _, fields, _ = parse_source(body, source['final_url'], response.get('content_type', ''), source.get('citire'))
                if [f['nume'] for f in fields] != [f['nume'] for f in source['campuri']]:
                    errors.append('CSV headers differ: ' + source['url'])
                elif has_csv_options(source.get('citire')) and (fields != source['campuri'] or header_facts(body, source['citire']) != source.get('antet')):
                    errors.append('CSV header facts differ from the retained body: ' + source['url'])
            elif source.get('format') == 'html-api-docs':
                _, fields, _ = parse_source(body, source['final_url'], response.get('content_type', ''), source.get('citire'))
                fresh = {**strip_links(source), 'campuri': fields, 'operatii': api_operations(body)}
                contract = contract_of(source, previous['sources'])
                document = contract_document(out, contract) if contract else None
                if document is not None:
                    fresh = link_contract(fresh, contract, document)
                elif source.get('comparatie_contract'):
                    report['unavailable'].append('contract comparison: ' + source['url'])
                    source = strip_links(source)
                if fresh['campuri'] != source['campuri'] or fresh['operatii'] != source['operatii']:
                    errors.append('Fields or operations differ from the retained body: ' + source['url'])
                elif fresh.get('comparatie_contract') != source.get('comparatie_contract'):
                    errors.append('The comparison with the contract differs from the retained bodies: ' + source['url'])
            elif source.get('format') == 'html-carduri-csv':
                _, fields, _ = parse_source(body, source['final_url'], response.get('content_type', ''), source.get('citire'))
                if fields != source['campuri'] or csv_datasets(body, source['final_url']) != source.get('seturi'):
                    errors.append('Fields or datasets differ from the retained body: ' + source['url'])
            elif source.get('format') == 'html-lista-seturi':
                _, fields, _ = parse_source(body, source['final_url'], response.get('content_type', ''), source.get('citire'))
                if fields != source['campuri'] or list_datasets(body) != source.get('seturi'):
                    errors.append('Datasets differ from the retained body: ' + source['url'])
            elif source.get('format') == DATASETTE:
                _, fields, _ = parse_source(body, source['final_url'], response.get('content_type', ''), source.get('citire'))
                if fields != source['campuri'] or datasette_database(json.loads(body)) != source.get('baza'):
                    errors.append('Fields or database facts differ from the retained body: ' + source['url'])
            elif source.get('format') in TEXT_FORMATS:
                _, fields, _ = parse_source(body, source['final_url'], response.get('content_type', ''), source.get('citire'))
                if fields != source['campuri'] or (source['format'] == 'js-literale' and (literal_declarations(body) != source.get('declaratii')
                                                                                         or literal_datasets(body) != source.get('seturi_ld'))):
                    errors.append('Fields differ from the retained body: ' + source['url'])
            elif source.get('campuri'):
                document = json.loads(body)
                if source.get('format') == 'metadate-ins' and ins_dataset(document) != source.get('set_date'):
                    errors.append('Dataset facts differ from the retained body: ' + source['url'])
                if source.get('format') == 'lista-ins' and ins_listing(document) != source.get('catalog'):
                    errors.append('Listing facts differ from the retained body: ' + source['url'])
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
        for record in previous['discoveries']:
            for evidence in [record.get('dovada'), *(record.get('dovezi_suplimentare') or [])]:
                if evidence and record['metoda'] != 'dovada-pilot':
                    status = check_locator(record, evidence, observations)
                    source = previous['sources'].get(record['sursa_id'], {})
                    if status == '' and evidence.get('blob_sha') and source.get('sha256'):
                        try:
                            body = json.loads((out / source['snapshot']).read_text())['body']
                            if git_blob_sha(body) != evidence['blob_sha']:
                                status = f'Retained body of {record["url"]} is not the file {evidence["cale"]} at {evidence["revizie"]}'
                        except (OSError, ValueError, KeyError):
                            pass
                    if status == 'unavailable':
                        report['unavailable'].append(f'discovery: {record["proiect"]} {evidence.get("snapshot")}')
                    elif status:
                        errors.append(status)
    check_saved_pages(report, observations)
    check_dictionary(report, previous, out, observations)
    check_external_fragments(report, previous, observations)
    report['unavailable'] = sorted(set(report['unavailable']))
    return report


def check_saved_pages(report, observations):
    """Documentation pages that the owner saved: the record keys must be consistent and the retained text must have the recorded hash.
    A page whose text is absent from this checkout is unavailable, never verified."""
    path = observations / 'documentare' / 'index.json'
    try:
        entries = json.loads(path.read_text())['entries']
    except (OSError, ValueError, KeyError):
        return
    for entry in entries:
        for page in entry.get('pages', []):
            if not is_saved(page):
                continue
            label = f'{entry["slug"]} {page["url"]}'
            report['saved']['total'] += 1
            report['errors'] += [f'Saved page {label}: {problem}' for problem in saved_errors(page)]
            try:
                text = json.loads((observations / 'documentare' / page['snapshot']).read_text())['text']
            except (OSError, ValueError, KeyError):
                report['unavailable'].append('documentation: ' + label)
                report['saved']['unavailable'] += 1
                continue
            if hashlib.sha256(text.encode()).hexdigest() != page.get('sha256'):
                report['errors'].append(f'Saved page text hash differs: {label}')
            else:
                report['saved']['verified'] += 1


def check_dictionary(report, previous, out, observations):
    """The hand-edited dictionary of business groups: structure, selector reach and evidence pins. A changed pin is stale, not corrupt."""
    path = observations.parent / 'inventar-concepte.json'
    if not path.exists():
        return
    try:
        document = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        report['errors'].append(f'{path}: {exc}')
        return
    concepts = document.get('concepte', [])
    report['errors'] += validate_families(document)
    sources = previous['sources']
    fields = {}
    for slug, profile in previous['profiles'].items():
        for ref in profile.get('surse_structurate', []):
            source = sources.get(ref)
            for field in (source or {}).get('campuri', []):
                fields.setdefault(slug, []).append(({'name': field['nume'], 'path': field['cale'], 'role': field.get('rol', 'camp-date')}, source['url']))
    result = check_concepts(concepts, fields, EvidenceLocator(out, observations, list(sources.values())), set(previous['profiles']))
    report['errors'] += result['errors']
    report['concept_stale'] = result['stale']
    report['concept_verified'] = result['verified']
    report['unavailable'] += ['dictionary evidence: ' + item for item in result['unavailable']]


def check_external_fragments(report, previous, observations):
    """A field may rest on a sentence of another page (`dovada_externa`). The sentence must occur in that page's collected text."""
    pages = {}
    for source in previous['sources'].values():
        for field in source.get('campuri', []):
            evidence = field.get('dovada_externa')
            if not evidence:
                continue
            if evidence['url'] not in pages:
                pages[evidence['url']] = EvidenceLocator(observations / 'inventare', observations, []).text(evidence['url'])[0]
            text = pages[evidence['url']]
            if text is None:
                report['unavailable'].append('external evidence: ' + evidence['url'])
            elif evidence['fragment'] not in text:
                report['errors'].append(f'External evidence for {source["url"]} {field["nume"]} is not in {evidence["url"]}')


def check_locator(record, evidence, observations):
    """Check one discovery locator against its local snapshot. Returns '', 'unavailable' or an error message."""
    label = f'Discovery locator for {record["proiect"]} {record["url"]}'
    if not evidence.get('snapshot'):
        return ''
    if evidence.get('tip') == 'randare':
        try:
            record = json.loads((observations / evidence['snapshot']).read_text())
            seen = record['cereri_date'][int(evidence['pointer'].rsplit('/', 1)[1])]['url']
        except FileNotFoundError:
            return 'unavailable'
        except (OSError, ValueError, KeyError, IndexError):
            return f'{label}: invalid render pointer'
        return '' if seen == evidence['valoare'] and record.get('url_cerut') == evidence['url'] else f'{label}: render record differs'
    if evidence.get('tip') == 'profil':
        try:
            with (observations / evidence['snapshot']).open(newline='') as stream:
                rows = [r for r in csv.DictReader(stream) if r['slug'] == evidence['slug']]
        except FileNotFoundError:
            return 'unavailable'
        return '' if rows and rows[0].get(evidence['coloana']) == evidence['valoare'] else f'{label}: profile value differs'
    try:
        page = json.loads((observations / evidence['snapshot']).read_text())
    except FileNotFoundError:
        return 'unavailable'
    except (OSError, ValueError) as exc:
        return f'{label}: {exc}'
    pointer = evidence.get('pointer', '')
    if evidence.get('blob_sha'):
        try:
            tree_body = page['body']
            entry = json.loads(tree_body)['tree'][int(pointer.rsplit('/', 1)[1])]
        except (KeyError, IndexError, ValueError, TypeError):
            return f'{label}: invalid tree pointer {pointer}'
        if hashlib.sha256(tree_body.encode()).hexdigest() != evidence.get('sha256'):
            return f'{label}: tree listing hash differs'
        if entry.get('path') != evidence.get('cale') or entry.get('sha') != evidence['blob_sha']:
            return f'{label}: tree entry differs from the recorded file'
        return ''
    text = page.get('body') if pointer == '/body' else page.get('text', '')
    if text is None:
        return f'{label}: snapshot has no text'
    if evidence.get('sha256') and hashlib.sha256(text.encode()).hexdigest() != evidence['sha256']:
        return f'{label}: page hash differs'
    if pointer in ('/text', '/body'):
        start, end = evidence.get('interval', [0, 0])
        expected = evidence.get('fragment') or record.get('link_original')
        if text[start:end] != expected:
            return f'{label}: text interval does not hold the fragment'
    elif pointer.startswith('/links/'):
        try:
            link = page['links'][int(pointer.rsplit('/', 1)[1])][0]
        except (KeyError, IndexError, ValueError, TypeError):
            return f'{label}: invalid link pointer {pointer}'
        if link.rstrip('.,;') != (evidence.get('fragment') or record.get('link_original')).rstrip('.,;'):
            return f'{label}: link pointer holds another URL'
    return ''


def check_inventory(out, observations):
    """The evidence errors only. Missing local bodies are reported by check_report, not counted as errors."""
    return check_report(out, observations)['errors']


def locate_text(docs, slug, page_url, needle):
    """Locate an exact fragment in a collected documentation page. Returns the discovery locator, or None."""
    for page in docs.get(slug, {}).get('pages', []):
        if page_url in (page.get('final_url'), page.get('url')) and page.get('state') == 'colectat':
            text = page.get('text', '')
            start = text.find(needle)
            if start >= 0:
                return {'url': page['final_url'], 'sha256': page.get('sha256'), 'pointer': '/text', 'interval': [start, start + len(needle)],
                        'fragment': needle, 'snapshot': 'documentare/' + page['snapshot'] if page.get('snapshot') else None}
    return None


def cached_body(cache, url):
    response = read_cache(Path(cache) / (source_id(url) + '.json'))
    return response if response and response.get('state') == 'ok' else None


def locate_in_cache(cache, url, needle):
    """Locate an exact fragment in a body kept in the source cache (a page the inventory read but did not parse as a source)."""
    response = cached_body(cache, url)
    if not response:
        return None
    body = response.get('body', '')
    start = body.find(needle)
    if start < 0:
        return None
    return {'url': url, 'sha256': hashlib.sha256(body.encode()).hexdigest(), 'pointer': '/body', 'interval': [start, start + len(needle)],
            'fragment': needle, 'snapshot': 'inventare/surse/' + source_id(url) + '.json'}


def git_blob_sha(body):
    data = body.encode()
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def locate_repo_file(cache, tree_url, commit, path):
    """A file of a repository at a recorded commit, found in the cached recursive tree listing of that commit."""
    response = cached_body(cache, tree_url)
    if not response:
        return None
    tree = json.loads(response['body']).get('tree', [])
    for index, entry in enumerate(tree):
        if entry.get('path') == path and entry.get('type') == 'blob':
            return {'url': tree_url, 'revizie': commit, 'cale': path, 'blob_sha': entry['sha'], 'pointer': f'/tree/{index}',
                    'sha256': hashlib.sha256(response['body'].encode()).hexdigest(), 'snapshot': 'inventare/surse/' + source_id(tree_url) + '.json'}
    return None


def locate_link(docs, slug, page_url, link):
    """Locate a link in the link list of a collected documentation page."""
    for page in docs.get(slug, {}).get('pages', []):
        if page_url in (page.get('final_url'), page.get('url')) and page.get('state') == 'colectat':
            for index, (target, _) in enumerate(page.get('links', [])):
                if target.rstrip('.,;') == link or file_url(target) == link:
                    return {'url': page['final_url'], 'sha256': page.get('sha256'), 'pointer': f'/links/{index}', 'fragment': target,
                            'snapshot': 'documentare/' + page['snapshot'] if page.get('snapshot') else None}
    return None


def locate_profile(observations, slug, column):
    """A value in the generated profile table (for example the repository link that the profiler found on the project's site)."""
    path = Path(observations) / 'profil.csv'
    try:
        with path.open(newline='') as stream:
            for row in csv.DictReader(stream):
                if row['slug'] == slug and row.get(column):
                    return {'tip': 'profil', 'snapshot': 'profil.csv', 'slug': slug, 'coloana': column, 'valoare': row[column],
                            'pointer': f'/profil/{slug}/{column}'}
    except OSError:
        pass
    return None


def locate_render(observations, page_url, data_url):
    """A data request that the browser helper saw while it rendered a page (inventare/randare/*.json)."""
    folder = Path(observations) / 'inventare' / 'randare'
    for path in sorted(folder.glob('*.json')) if folder.exists() else []:
        record = json.loads(path.read_text())
        if record.get('url_cerut') == page_url:
            for index, request in enumerate(record.get('cereri_date', [])):
                if request['url'] == data_url:
                    return {'tip': 'randare', 'snapshot': f'inventare/randare/{path.name}', 'url': page_url, 'pointer': f'/cereri_date/{index}', 'valoare': data_url}
    return None


def resolve_spec(docs, slug, spec, cache=None):
    """Turn `locate` / `dovezi` / `repo` requests of an explicit source specification into exact locators.
    A request names a collected documentation page, or (with `cache: true`) a body in the source cache.
    Fails when a fragment or a repository file is absent."""
    spec = dict(spec)

    def find(request):
        if request.get('randare'):
            evidence = locate_render(Path(cache).parent.parent, request['pagina'], request['randare']) if cache else None
        elif request.get('profil'):
            evidence = locate_profile(Path(cache).parent.parent, request.get('proiect', slug), request['profil']) if cache else None
        elif request.get('link'):
            evidence = locate_link(docs, request.get('proiect', slug), request['pagina'], request['link'])
        elif request.get('cache'):
            evidence = locate_in_cache(cache, request['pagina'], request['text']) if cache else None
        else:
            evidence = locate_text(docs, request.get('proiect', slug), request['pagina'], request['text'])
        if not evidence:
            raise StateError(f'Evidence not found for {slug}: {json.dumps(request, ensure_ascii=False)[:160]}')
        return evidence

    if spec.get('locate'):
        spec['dovada'] = find(spec.pop('locate'))
    if spec.get('repo'):
        repo = spec.pop('repo')
        evidence = locate_repo_file(cache, repo['arbore'], repo['revizie'], repo['cale']) if cache else None
        if not evidence:
            raise StateError(f'Repository file not found at {repo["revizie"]}: {repo["cale"]}')
        spec['dovada'] = evidence
    extra = [{**find(request), 'rol': request['rol']} for request in spec.pop('dovezi', [])]
    if extra:
        spec['dovezi_suplimentare'] = extra
    return spec


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
        history.append({k: previous[k] for k in ('sha256', 'fetched_at', 'snapshot', 'origine', 'salvat_la') if k in previous})
    if history:
        result['versiuni_anterioare'] = history
    if not fresh and previous.get('ultima_incercare') and usable(metadata) and previous.get('sha256') == metadata.get('sha256'):
        result['ultima_incercare'] = previous['ultima_incercare']
    return result


def update_inventory(entries, docs, verified, previous, *, cache, selected=(), offline=False, force=False, max_files=3,
                     fetch=None, now=None, concepts=None, retire_sources=(), add_sources=(), force_urls=()):
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
    # A project named by an explicit addition or retirement changes, so it counts as selected.
    if selected:
        selected |= {slug for slug, _ in add_sources} | {slug for slug, _, _ in retire_sources}
    force_urls = {canonical(u) for u in force_urls}
    # New entries have no tracked record to protect; they are built from whatever local evidence exists.
    work = (selected or set(slugs)) | {s for s in slugs if s not in previous['profiles']}
    report = {'pastrate': [], 'reimprospatate': [], 'esuate': [], 'neinspectate': [], 'interzise': [], 'avertismente': [], 'cereri': 0, 'cache': 0}

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
                                          evidence=spec.get('dovada'), discovered_at=now, note=spec.get('nota'),
                                          extra=spec.get('dovezi_suplimentare'), reading=spec.get('citire'))
            registry[key]['istoric'].append({'eveniment': 'adaugat', 'la': now})
        elif registry[key]['stare'] == 'descoperit':
            registry[key]['stare'] = 'activ'
            registry[key]['istoric'].append({'eveniment': 'admis', 'la': now})
        if spec.get('citire') and not registry[key].get('citire'):
            registry[key]['citire'] = spec['citire']
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
    hint_of = {}
    for record in sorted_registry(registry):
        if record.get('citire'):
            hint_of.setdefault(record['url'], record['citire'])
    fetch_urls = {d['url'] for s in (selected or slugs) for d in active_members(registry, s)}

    def obtain(url):
        ident = source_id(url)
        path = cache / (ident + '.json')
        tracked = previous['sources'].get(ident)
        cached = read_cache(path)
        # A copy that the owner saved is never requested again (the site may forbid it). The owner imports a newer copy instead.
        wanted = url in fetch_urls and not offline and not (is_saved(cached) or is_saved(tracked))
        # A host on the list of forbidden hosts is never requested, `force` included. A body already retained stays the evidence.
        skipped = wanted and forbidden(url) is not None
        refresh = wanted and not skipped
        response, origin = None, None
        if cached is not None and not (refresh and (force or url in force_urls)):
            response, origin = cached, 'cache'
        elif refresh:
            response, origin = protect(fetch(url)), 'retea'
            if response.get('state') == 'limita-cereri':
                response, origin = None, 'omis'
        if response is None:
            if tracked:
                return url, tracked, (FORBIDDEN_STATE if skipped else 'neinspectat' if origin == 'omis' else 'pastrat-fara-cache' if url in fetch_urls else 'neatins')
            return url, analyse_source({'url': url, 'state': 'necolectat'}, hint_of.get(url)), (FORBIDDEN_STATE if skipped else 'necolectat')
        if origin == 'retea' and (response.get('state') == 'ok' or cached is None or cached.get('state') != 'ok'):
            write_file_atomic(path, dump(response))
        metadata = analyse_source(response, hint_of.get(url))
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
               'pastrat-fara-cache': 'pastrate', FORBIDDEN_STATE: 'interzise'}.get(outcome)
        if key:
            report[key].append(url)
        report['cache'] += outcome == 'cache'
    for ident, old in previous['sources'].items():
        sources.setdefault(ident, old)  # a tracked source nothing references any more is history, not garbage
    apply_contracts(sources, cache.parent)

    profiles = []
    for entry in entries:
        slug = entry['slug']
        old = previous['profiles'].get(slug)
        refs = [d['sursa_id'] for d in active_members(registry, slug)]
        if slug in work:
            profiles.append(build_profile(entry, docs.get(slug, {}), sources, refs, concepts, old, report['avertismente']))
        else:
            profiles.append({**old, 'campuri_din_surse': sum(len(counted_fields(sources[r])) for r in old['surse_structurate'] if r in sources)})
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


def import_saved(cache, url, raw, saved_at, name, note=None, now=None):
    """Keep a page that the owner saved from their browser as the cached body of `url`. Nothing is fetched.

    The cache record is the same kind of file as a fetched body (`surse/<id>.json`), so the reader, `--check` and the review interface
    treat it alike; it says `origine: copie-salvata-de-proprietar` and has no HTTP status. A fetched body that is already cached is never
    replaced: StateError. Returns (response, previous) where `previous` is the file that the import replaced, or None."""
    try:
        response = protect(saved_copy(url, raw, saved_at, name, note, now))
    except ValueError as exc:
        raise StateError(str(exc)) from exc
    path = Path(cache) / (source_id(response['url']) + '.json')
    old = read_cache(path)
    if old and old.get('state') == 'ok' and old.get('body') and not is_saved(old):
        raise StateError(f'{response["url"]} has a fetched body in the cache. A saved copy never replaces fetched evidence.')
    previous = path.read_bytes() if path.exists() else None
    Path(cache).mkdir(parents=True, exist_ok=True)
    write_file_atomic(path, dump(response))
    return response, previous


def restore_cache(cache, url, previous):
    """Undo `import_saved` when the run that followed it failed."""
    path = Path(cache) / (source_id(canonical(url)) + '.json')
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(previous)


def reading_of(value):
    """`--reading`: a reader name, or a JSON object {tip, ...options}."""
    if value is None:
        return None
    try:
        return json.loads(value) if value.lstrip().startswith('{') else value
    except ValueError as exc:
        raise StateError(f'--reading is not valid JSON: {exc}') from exc


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
    parser.add_argument('--force-url', action='append', default=[], metavar='URL', help='fetch only this source again (repeatable)')
    parser.add_argument('--probe', nargs='+', metavar='URL', help='fetch URLs into the source cache and print a summary; changes no inventory record; needs --lot')
    parser.add_argument('--purpose', default='inventar', help='with --probe: why the request is made; kept in the request log')
    parser.add_argument('--sample-bytes', type=int, help='with --probe: read at most this many bytes (a range request); the body is marked partial')
    parser.add_argument('--max-files', type=int, default=3, help='admit new sources until a project has this many members')
    parser.add_argument('--max-requests', type=int, help='stop fetching after this many direct requests in this run')
    parser.add_argument('--lot', default='', help='name of the collection batch; enables the request log')
    parser.add_argument('--budget', type=int, help='with --lot: total direct requests allowed for the batch across runs')
    parser.add_argument('--retire', nargs=2, action='append', metavar=('SLUG', 'URL'), default=[], help='retire a source membership; needs --reason')
    parser.add_argument('--reason', default='', help='reason recorded with --retire')
    parser.add_argument('--add-source', nargs=2, action='append', metavar=('SLUG', 'URL'), default=[],
                        help='add an explicitly identified structured source to a project')
    parser.add_argument('--add-sources-file', type=Path, metavar='FILE',
                        help='JSON list of source specifications: proiect, url, metoda, parinte, nota, locate {pagina, text}, dovezi [{pagina, text, rol}]')
    parser.add_argument('--method', default='adaugat-explicit', help='with --add-source: how the source was identified')
    parser.add_argument('--parent', help='with --add-source: the page or repository where the source was identified')
    parser.add_argument('--note', help='with --add-source: a short note kept with the discovery; with --import-saved: why the owner saved the page by hand')
    parser.add_argument('--reading', metavar='READER', help='with --add-source or --import-saved: the reader of the source, a name or a JSON object {"tip": name, ...}')
    parser.add_argument('--import-saved', nargs=3, metavar=('SLUG', 'URL', 'FILE'),
                        help='keep a page that the owner saved from their browser as the retained body of URL and add it to SLUG; '
                             'no request is made (implies --offline --only SLUG); needs --saved-at')
    parser.add_argument('--saved-at', metavar='ISO8601', help='with --import-saved: when the owner saved the file, with a UTC offset (2026-10-25T20:39:00+02:00)')
    args = parser.parse_args()
    if args.max_files < 1 or (args.max_requests is not None and args.max_requests < 0):
        parser.error('--max-files must be positive and --max-requests cannot be negative')
    if args.retire and not args.reason.strip():
        parser.error('--retire needs a recorded --reason')
    if args.probe and not args.lot:
        parser.error('--probe needs --lot so that every request is logged')
    if args.import_saved:
        if not args.saved_at:
            parser.error('--import-saved needs --saved-at')
        if args.check or args.probe or args.dry_run or args.force or args.force_url:
            parser.error('--import-saved cannot run with --check, --probe, --dry-run, --force or --force-url')
        if args.only and set(filter(None, args.only.split(','))) != {args.import_saved[0]}:
            parser.error('--import-saved runs for its own slug only')
        args.offline, args.only = True, args.import_saved[0]
    elif args.saved_at:
        parser.error('--saved-at belongs to --import-saved')
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
        for item in report['concept_stale']:
            print('STALE (dictionary evidence changed): ' + item)
        print(f'{len(report["errors"])} inventory evidence errors; {report["verified"]} source bodies hash-verified; '
              f'{len(report["unavailable"])} local bodies unavailable and not verified; {len(report["stale"])} sources with a failed refresh; '
              f'{report["concept_verified"]} dictionary evidence items verified, {len(report["concept_stale"])} stale')
        saved = report['saved']
        if saved['total']:
            print(f'{saved["total"]} copies saved by the owner (not fetched): {saved["verified"]} hash-verified, {saved["unavailable"]} unavailable and not verified')
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
    fetcher = Fetcher(timeout=12, max_requests=limit, log=log, purpose=args.purpose)
    if args.probe:
        cache = out / 'surse'
        cache.mkdir(parents=True, exist_ok=True)
        for url in args.probe:
            url = canonical(url)
            response = protect(fetcher(url, sample=args.sample_bytes))
            path = cache / (source_id(url) + '.json')
            old = read_cache(path)
            if response['state'] == 'ok' or old is None or old.get('state') != 'ok':
                if response['state'] not in ('limita-cereri', FORBIDDEN_STATE):  # no request was made, so there is no evidence to keep
                    write_file_atomic(path, dump(response))
            body = response.get('body', '')
            print(f"{response['state']} {response.get('http_status')} {response.get('content_type', '')} {len(body)} chars"
                  f"{' partial' if response.get('partial') else ''}{' redacted ' + str(response['redactari']) if response.get('redactari') else ''} {url}"
                  f"{' (' + response['motiv'] + ')' if response['state'] == FORBIDDEN_STATE else ''}")
        print(f'{fetcher.requests} requests in this run')
        return 0
    imported = None
    try:
        previous = load_previous(out)
        reading = reading_of(args.reading)
        additions = [(slug, {'url': url, 'metoda': args.method, 'parinte': args.parent, 'nota': args.note, 'citire': reading}) for slug, url in args.add_source]
        if args.import_saved:
            # The copy goes into the cache first, so that a specification of --add-sources-file can locate a fragment in it (`cache: true`).
            slug, url, file = args.import_saved
            try:
                raw = Path(file).read_bytes()
            except OSError as exc:
                raise StateError(f'Cannot read {file}: {exc}') from exc
            response, replaced = import_saved(out / 'surse', url, raw, args.saved_at, file, args.note)
            imported = (response['url'], replaced)
        if args.add_sources_file:
            try:
                specs = json.loads(args.add_sources_file.read_text())
            except (OSError, ValueError) as exc:
                raise StateError(f'Cannot read {args.add_sources_file}: {exc}') from exc
            additions += [(spec['proiect'], resolve_spec(docs, spec['proiect'], {k: v for k, v in spec.items() if k != 'proiect'}, out / 'surse')) for spec in specs]
        if args.import_saved:
            # The source joins the project like `--add-source`; a specification in --add-sources-file for the same address comes first and keeps its locator.
            additions.append((slug, {'url': response['url'], 'metoda': args.method, 'parinte': args.parent, 'nota': None, 'citire': reading}))
        state = update_inventory(
            entries, docs, verified, previous, cache=out / 'surse', selected=selected, offline=args.offline, force=args.force,
            max_files=args.max_files, fetch=fetcher, concepts=concepts, force_urls=args.force_url,
            retire_sources=[(slug, canonical(url), args.reason) for slug, url in args.retire],
            add_sources=additions)
        if not args.dry_run:
            write_atomic(out, render_outputs(state))
    except StateError as exc:
        if imported:
            restore_cache(out / 'surse', *imported)
        print('ERROR: ' + str(exc))
        print('No inventory file was changed.')
        return 2
    if imported:
        print(f'saved copy kept: {imported[0]} (file sha256 {response["sha256_fisier"][:16]}, saved at {response["salvat_la"]}); not fetched')
    report = state['report']
    for key, label in (('reimprospatate', 'refreshed'), ('esuate', 'refresh failed; last evidence kept'),
                       ('pastrate', 'no local body; tracked record kept'), ('neinspectate', 'not inspected: request limit reached'),
                       ('interzise', FORBIDDEN_STATE + ': not requested')):
        for url in report[key]:
            print(f'{label}: {url}' + (f' ({forbidden(url)["motiv"]})' if key == 'interzise' else ''))
    for note in report['avertismente']:
        print('WARNING: ' + note)
    profiles, sources = state['profiles'], state['sources']
    print(f'{len(profiles)} project drafts; {sum(bool(p["campuri_din_surse"]) for p in profiles)} with structured fields; '
          f'{sum(len(s["campuri"]) for s in sources)} shared field records; {fetcher.requests} requests'
          + ('; dry run, nothing written' if args.dry_run else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
