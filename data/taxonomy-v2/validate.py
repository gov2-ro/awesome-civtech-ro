"""Check the isolated taxonomy proposal. Stdlib only; production data is never written.

python3 data/taxonomy-v2/validate.py
python3 data/taxonomy-v2/validate.py --baseline --export

--baseline also proves that the initial copy retained every source entry and text field.
--export refreshes catalogue.json from the editable CSVs, after all checks pass.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ID = re.compile(r'^[a-z][a-z0-9-]*:[a-z0-9]+(?:-[a-z0-9]+)*$')
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def values(cell):
    return cell.split('|') if cell else []


def check(root=HERE, baseline=False, export=False):
    errors = []
    fail = errors.append
    schema = json.loads((root / 'schema.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    settings = json.loads((root / 'setari.json').read_text(encoding='utf-8'))
    tables = {}
    for name, columns in schema['headers'].items():
        with (root / name).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != columns:
                fail(f'{name}: header differs from schema.json')
            rows = list(reader)
            for n, row in enumerate(rows, 2):
                if None in row or any(v is None for v in row.values()):
                    fail(f'{name}:{n}: row width differs from the header')
            tables[name] = rows
    if errors:
        return errors, {}

    def indexed(name, key):
        out = {}
        for row in tables[name]:
            ident = row[key]
            if not ident or ident in out:
                fail(f'{name}: missing or duplicate {key}: {ident!r}')
            out[ident] = row
        return out

    entries = indexed('intrari.csv', 'slug')
    concepts = indexed('concepte.csv', 'id')
    areas = indexed('arii.csv', 'id')
    indexed('relatii.csv', 'id')
    indexed('revizuire.csv', 'id')
    if {s['key'] for s in settings['sectiuni']} != set(schema['enums']['sectiune_url']):
        fail('setari.json: sections differ from the URL section enum')
    role_keys = [r['key'] for r in settings['roluri_linkuri']]
    if len(role_keys) != len(set(role_keys)):
        fail('setari.json: duplicate link role')

    def links(name, ident, cell, targets):
        items = values(cell)
        if len(items) != len(set(items)) or any(not x or x != x.strip() for x in items):
            fail(f'{name} {ident}: duplicate, blank, or untrimmed list item')
        for value in items:
            if value not in targets:
                fail(f'{name} {ident}: unknown reference {value}')
        return items

    def cyclic(nodes, parent_field):
        visiting, visited = set(), set()

        def visit(ident):
            if ident in visiting:
                fail(f'{parent_field}: hierarchy cycle at {ident}')
                return
            if ident in visited:
                return
            visiting.add(ident)
            for parent in values(nodes[ident][parent_field]):
                if parent in nodes:
                    visit(parent)
            visiting.remove(ident)
            visited.add(ident)
        for ident in nodes:
            visit(ident)

    preferred_labels = set()
    for ident, row in concepts.items():
        if not ID.fullmatch(ident) or ident.split(':')[0] != row['schema']:
            fail(f'concepte.csv: invalid ID or scheme: {ident}')
        if not row['eticheta_ro'] or not row['eticheta_en'] or not row['definitie_ro']:
            fail(f'concepte.csv {ident}: labels and definition are required')
        if row['statut'] not in ('propus', 'acceptat', 'retras'):
            fail(f'concepte.csv {ident}: invalid status')
        for language in ('ro','en'):
            label = (row['schema'],language,row['eticheta_'+language].casefold())
            if label in preferred_labels:
                fail(f'concepte.csv {ident}: duplicate preferred label in the same scheme')
            preferred_labels.add(label)
        for parent in links('concepte.csv', ident, row['mai_larg'], concepts):
            if parent in concepts and concepts[parent]['schema'] != row['schema']:
                fail(f'concepte.csv {ident}: broader concept belongs to another scheme')
        links('concepte.csv', ident, row['asociate'], concepts)
    cyclic(concepts, 'mai_larg')
    for ident, row in areas.items():
        links('arii.csv', ident, row['parinte'], areas)
        if row['tip'] not in ('tara', 'regiune', 'judet', 'localitate'):
            fail(f'arii.csv {ident}: invalid area type')
        if row['cod_iso_3166_1'] and not re.fullmatch(r'[A-Z]{2}', row['cod_iso_3166_1']):
            fail(f'arii.csv {ident}: invalid country code')
    cyclic(areas, 'parinte')

    def subject_roots(ident, seen=None):
        seen = set() if seen is None else seen
        if ident not in concepts or ident in seen:
            return set()
        seen.add(ident)
        parents = values(concepts[ident]['mai_larg'])
        if not parents:
            return {ident}
        result = set()
        for parent in parents:
            result |= subject_roots(parent, seen.copy())
        return result

    for slug, row in entries.items():
        if not SLUG.fullmatch(slug) or not row['nume']:
            fail(f'intrari.csv: invalid slug or missing name: {slug}')
        for field, choices in schema['enums'].items():
            if row[field] not in choices:
                fail(f'intrari.csv {slug}: invalid {field}: {row[field]!r}')
        for field, scheme in schema['concept_fields'].items():
            chosen = links('intrari.csv '+field, slug, row[field], concepts)
            if field == 'subiect_principal' and len(chosen) != 1:
                fail(f'intrari.csv {slug}: one primary subject is required')
            for ident in chosen:
                if ident not in concepts:
                    continue
                if concepts[ident]['schema'] != scheme:
                    fail(f'intrari.csv {slug}: wrong scheme in {field}: {ident}')
                if concepts[ident]['statut'] == 'retras':
                    fail(f'intrari.csv {slug}: assignment uses a retired concept: {ident}')
                if field in ('subiect_principal', 'subiecte') and concepts[ident]['mai_larg']:
                    fail(f'intrari.csv {slug}: {field} requires top-level subjects')
                if field == 'teme':
                    if not concepts[ident]['mai_larg']:
                        fail(f'intrari.csv {slug}: teme requires narrower subjects')
                    if not subject_roots(ident) <= set(values(row['subiecte'])):
                        fail(f'intrari.csv {slug}: topic root missing from subiecte: {ident}')
        if row['subiect_principal'] not in values(row['subiecte']):
            fail(f'intrari.csv {slug}: primary subject missing from subiecte')
        chosen_areas = links('intrari.csv arii_acoperite', slug, row['arii_acoperite'], areas)
        if row['nivel_acoperire'] == 'local' and not any(areas[x]['tip'] in ('judet', 'localitate') for x in chosen_areas if x in areas):
            fail(f'intrari.csv {slug}: local coverage needs a locality or county')
        if row['tip_entitate'] == 'organizatie' and row['sectiune_url'] != 'organizatie':
            fail(f'intrari.csv {slug}: organisation URL section differs')
        if row['tip_organizatie'] and row['tip_entitate'] != 'organizatie':
            fail(f'intrari.csv {slug}: organisation type on a non-organisation')

    for row in tables['relatii.csv']:
        if row['subiect'] not in entries or (row['obiect'] and row['obiect'] not in entries):
            fail(f'relatii.csv {row["id"]}: unknown endpoint')
        if bool(row['obiect']) == bool(row['obiect_literal']):
            fail(f'relatii.csv {row["id"]}: choose one object ID or literal')
        if row['predicat'] not in schema['relation_predicates']:
            fail(f'relatii.csv {row["id"]}: unknown predicate')
        if row['stare'] not in ('rol_neconfirmat','propus','acceptat','respins'):
            fail(f'relatii.csv {row["id"]}: invalid review state')
        if row['predicat'] != 'atribuit_in_sursa' and row['stare'] == 'acceptat' and not row['valoare_sursa']:
            fail(f'relatii.csv {row["id"]}: an accepted role needs source evidence')
    for row in tables['revizuire.csv']:
        if row['slug'] not in entries or row['stare'] not in ('deschis','acceptat','respins','amanat'):
            fail(f'revizuire.csv {row["id"]}: unknown entry or status')
        if row['prioritate'] not in ('mare','medie','mica'):
            fail(f'revizuire.csv {row["id"]}: invalid priority')
        if row['stare'] in ('acceptat','respins') and not row['decizie_editor']:
            fail(f'revizuire.csv {row["id"]}: a closed item needs an editor decision')
    for row in tables['atribuiri-initiale.csv']:
        if row['slug'] not in entries or row['concept'] not in concepts:
            fail('atribuiri-initiale.csv: unknown entry or concept')
    for row in tables['corespondente-v1.csv']:
        links('corespondente-v1.csv', row['termen_original'], row['concepte_candidate'], concepts)
    official = json.loads((root / 'reference/eurovoc-response.json').read_text(encoding='utf-8'))['results']['bindings']
    official_labels = {r['concept']['value']:(r.get('ro',{}).get('value',''),r['en']['value']) for r in official}
    seen_maps = set()
    for row in tables['mapari-externe.csv']:
        mapping = (row['concept_local'],row['uri_tinta'])
        if mapping in seen_maps:
            fail(f'mapari-externe.csv: duplicate mapping {mapping}')
        seen_maps.add(mapping)
        if row['concept_local'] not in concepts:
            fail(f'mapari-externe.csv: unknown local concept {row["concept_local"]}')
        if row['relatie'] not in ('closeMatch','exactMatch','broadMatch','narrowMatch','relatedMatch'):
            fail('mapari-externe.csv: invalid SKOS mapping relation')
        if row['stare_mapare'] not in ('propus','acceptat','respins'):
            fail('mapari-externe.csv: invalid mapping status')
        if row['vocabular'] == 'EuroVoc' and official_labels.get(row['uri_tinta']) != (row['eticheta_tinta_ro'],row['eticheta_tinta_en']):
            fail(f'mapari-externe.csv: identifier/labels do not match the official snapshot: {mapping}')

    source_tables = {}
    for ref in manifest.get('references', []):
        if hashlib.sha256((root/ref['path']).read_bytes()).hexdigest() != ref['sha256']:
            fail(f'{ref["path"]}: immutable reference snapshot changed')
    for src in manifest['sources']:
        snapshot = root / src['snapshot']
        if hashlib.sha256(snapshot.read_bytes()).hexdigest() != src['sha256']:
            fail(f'{src["snapshot"]}: immutable source snapshot changed')
        if snapshot.suffix == '.csv':
            with snapshot.open(encoding='utf-8-sig',newline='') as f:
                source_tables[snapshot.name] = list(csv.DictReader(f))
    for snapshot_name in ('profil.csv','mentiuni.csv','mentiuni_etichete.csv'):
        observation = root/'observatii'/snapshot_name
        if not observation.exists():
            if snapshot_name in source_tables:
                fail(f'observatii/{snapshot_name}: missing working observation table')
            continue
        with observation.open(encoding='utf-8-sig',newline='') as f:
            reader = csv.DictReader(f)
            expected = list(source_tables.get(snapshot_name,[{}])[0]) if source_tables.get(snapshot_name) else None
            if expected is not None and reader.fieldnames != expected:
                fail(f'observatii/{snapshot_name}: headers differ from the source observation schema')
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    fail(f'observatii/{snapshot_name}: row width differs from its header')
        if baseline and observation.read_bytes() != (root/'source'/snapshot_name).read_bytes():
            fail(f'baseline: observations differ from source/{snapshot_name}')
    if baseline:
        originals = {r['slug']:r for name in ('proiecte.csv','orgs.csv') for r in source_tables[name]}
        if set(entries) != set(originals):
            fail('baseline: entry slugs differ from the 122 source entries')
        keep = {'nume':'nume','descriere_scurta':'descriere_scurta','descriere':'descriere','url':'url','linkuri':'linkuri',
                'localitate_originala':'oras','autor_original':'autor','contact':'contact','civictech_original':'civictech','stare':'stare','nota':'nota'}
        for slug, row in entries.items():
            if slug not in originals:
                continue
            for dest, source in keep.items():
                if row[dest] != originals[slug].get(source,''):
                    fail(f'baseline {slug}: original value differs in {dest}')
            source_name = row['sursa_fisier']
            try:
                source_row = source_tables[source_name][int(row['sursa_rand'])-2]
            except (KeyError,ValueError,IndexError):
                fail(f'baseline {slug}: invalid source row reference')
            else:
                if source_row['slug'] != slug:
                    fail(f'baseline {slug}: source row identifies another entry')
        for row in originals.values():
            for field in ('domeniu','tip','cuvinte'):
                delimiter = ',' if field != 'domeniu' else '|'
                for token in (row.get(field,'') or '').split(delimiter):
                    if token.strip() and not any(c['camp_original']==field and c['termen_original']==token.strip() for c in tables['corespondente-v1.csv']):
                        fail(f'baseline: no crosswalk for {field}={token.strip()}')
        for row in tables['atribuiri-initiale.csv']:
            if row['concept'] not in values(entries[row['slug']][row['camp']]):
                fail(f'baseline: initial assignment absent from entry {row["slug"]}')

    summary = {'entries':len(entries),'concepts':len(concepts),'relations':len(tables['relatii.csv']),
               'review_items':len(tables['revizuire.csv']),
               'open_review_items':sum(r['stare']=='deschis' for r in tables['revizuire.csv']),
               'proposed_entries':sum(r['clasificare_stare']=='propus' for r in entries.values()),
               'external_mappings':len(tables['mapari-externe.csv']),
               'primary_subjects':dict(Counter(r['subiect_principal'] for r in entries.values()))}
    if export and not errors:
        data = {'schema_version':schema['version'],'status':'editorial_proposal',
                'snapshot_date':manifest['created'], 'entries':[], 'concepts':[],
                'areas':tables['arii.csv'],'relations':tables['relatii.csv'],
                'external_mappings':tables['mapari-externe.csv'],'settings':settings}
        arrays = set(schema['concept_fields']) - {'subiect_principal'} | {'arii_acoperite'}
        for row in entries.values():
            data['entries'].append({k:values(v) if k in arrays else v for k,v in row.items()})
        for row in concepts.values():
            data['concepts'].append({k:values(v) if k in ('mai_larg','asociate','alternative_ro') else v for k,v in row.items()})
        (root/'catalogue.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return errors, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--export',action='store_true')
    args = parser.parse_args()
    errors, summary = check(baseline=args.baseline,export=args.export)
    for error in errors:
        print('ERROR:',error)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(f'{len(errors)} errors')
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
