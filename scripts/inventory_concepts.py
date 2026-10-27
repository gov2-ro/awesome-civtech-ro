"""Business-variable groups for discovery: selectors with context constraints, structure checks and evidence pins. Stdlib only.

A group (concept) names a variable that several projects expose under different field names. It is a proposal for discovery:
membership says "this field plausibly carries the variable", never "these datasets can be joined".

A selector picks fields. `projects` is required. A selector also needs `names` or `path`. The optional `source` (a source URL or a list of them),
`path` and `role` narrow it. Every constraint that a selector supplies must match; two selectors of one group are alternatives.
That is how an ambiguous name such as `REF_AREA` joins the county group for one dataset and not for another.

Review state (written by scripts/review_ui.py; a missing key means `propus`): a group has `stare` (propus | revizuit | respins | amanat),
`decizie_editor` and `data_revizie`; a selector has `stare` (propus | confirmat | exclus) and `nota_editor`. An `exclus` selector stays in the
file for history and never matches a field. A `respins` group produces no matches in the finder.

Families (`familii`, top level) sort the groups for browsing by what they describe: identifiers, geography, time, then subject areas.
A group names its family in `familie`. A family is a reading aid; it says nothing about compatibility. A group without one is listed last.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

CATEGORIES = ('identificator', 'dimensiune', 'masura', 'intrare-utilizator', 'iesire-derivata')
EVIDENCE_BASES = ('declaratie-directa', 'observatie-esantion', 'deductie-din-dovezi', 'parafraza-editoriala')
# The labels of the evidence bases. The review interface (review_ui.py) and the public pages of the data inventory share this one list.
BASIS_LABELS = {'declaratie-directa': 'declarație directă', 'observatie-esantion': 'observație din eșantion',
                'deductie-din-dovezi': 'deducție din dovezi', 'parafraza-editoriala': 'parafrază editorială'}
SELECTOR_KEYS = {'projects', 'names', 'source', 'path', 'role', 'context', 'fapte', 'nota', 'stare', 'nota_editor'}
GROUP_STATES = ('propus', 'revizuit', 'respins', 'amanat')
SELECTOR_STATES = ('propus', 'confirmat', 'exclus')
# The keys that a review decision writes, in file order (new keys go after the existing ones).
GROUP_REVIEW_KEYS = ('stare', 'decizie_editor', 'data_revizie')
SELECTOR_REVIEW_KEYS = ('stare', 'nota_editor')


def as_list(value):
    return [] if value is None else [value] if isinstance(value, str) else list(value)


def group_state(concept):
    return concept.get('stare') or 'propus'


def selector_state(selector):
    return selector.get('stare') or 'propus'


def active_groups(concepts):
    """The groups that discovery shows: every group but the rejected ones."""
    return [c for c in concepts if group_state(c) != 'respins']


def selector_matches(selector, slug, field, source_url, include_excluded=False):
    """True when the field satisfies every constraint of the selector. An excluded selector (`stare` = exclus) never matches,
    unless the caller asks for it to show what the excluded member would have matched."""
    if selector_state(selector) == 'exclus' and not include_excluded:
        return False
    if slug not in selector['projects']:
        return False
    if selector.get('names') is not None and field['name'] not in as_list(selector['names']):
        return False
    if selector.get('path') is not None and field['path'] not in as_list(selector['path']):
        return False
    if selector.get('role') is not None and field['role'] not in as_list(selector['role']):
        return False
    if selector.get('source') is not None and source_url not in as_list(selector['source']):
        return False
    return True


def validate_selector(selector, where):
    errors = []
    if not as_list(selector.get('projects')):
        errors.append(f'{where}: a selector needs projects')
    if selector.get('names') is None and selector.get('path') is None:
        errors.append(f'{where}: a selector needs names or path, so that it cannot match every field of a project')
    for key in set(selector) - SELECTOR_KEYS:
        errors.append(f'{where}: unknown selector key {key}')
    for url in as_list(selector.get('source')):
        if not url.startswith(('http://', 'https://')):
            errors.append(f'{where}: source is not an http(s) URL: {url}')
    for fact in selector.get('fapte', []):
        errors += validate_fact(fact, where)
    if selector.get('stare') is not None and selector['stare'] not in SELECTOR_STATES:
        errors.append(f'{where}: unknown selector state {selector["stare"]!r} (use {", ".join(SELECTOR_STATES)})')
    if selector.get('nota_editor') is not None and not isinstance(selector['nota_editor'], str):
        errors.append(f'{where}: nota_editor must be text')
    if selector.get('stare') == 'exclus' and not str(selector.get('nota_editor') or '').strip():
        errors.append(f'{where}: an excluded selector needs nota_editor')
    return errors


def validate_fact(fact, where):
    errors = []
    if not fact.get('cheie') or 'valoare' not in fact:
        errors.append(f'{where}: a fact needs cheie and valoare')
    if fact.get('baza') not in EVIDENCE_BASES:
        errors.append(f'{where}: a fact needs a baza from {EVIDENCE_BASES}')
    if fact.get('baza') != 'parafraza-editoriala' and not fact.get('dovada'):
        errors.append(f'{where}: a fact that is not an editorial paraphrase needs evidence')
    return errors


def validate_group_state(concept, where):
    """Review state of one group: known values, a decision text where the state needs one, and no member left `propus` in a reviewed group."""
    errors = []
    state = concept.get('stare')
    if state is not None and state not in GROUP_STATES:
        errors.append(f'{where}: unknown group state {state!r} (use {", ".join(GROUP_STATES)})')
    if concept.get('decizie_editor') is not None and not isinstance(concept['decizie_editor'], str):
        errors.append(f'{where}: decizie_editor must be text')
    if state in ('revizuit', 'respins') and not str(concept.get('decizie_editor') or '').strip():
        errors.append(f'{where}: a {state} group needs decizie_editor')
    date = concept.get('data_revizie')
    if date is not None:
        try:
            datetime.date.fromisoformat(date)
        except (TypeError, ValueError):
            errors.append(f'{where}: data_revizie is not an ISO date: {date!r}')
    if state == 'revizuit':
        open_members = [n for n, s in enumerate(concept.get('selectors', []), 1) if selector_state(s) == 'propus']
        if open_members:
            errors.append(f'{where}: a revizuit group cannot have a propus member (selector {", ".join(map(str, open_members))})')
    return errors


def validate_concept(concept, known_projects=None):
    errors, where = [], concept.get('id', '?')
    for key in ('id', 'label', 'definition'):
        if not concept.get(key):
            errors.append(f'{where}: missing {key}')
    if concept.get('categorie') is not None and concept['categorie'] not in CATEGORIES:
        errors.append(f'{where}: unknown category {concept["categorie"]}')
    if concept.get('baza_definitiei') is not None and concept['baza_definitiei'] not in EVIDENCE_BASES:
        errors.append(f'{where}: unknown baza_definitiei')
    errors += validate_group_state(concept, where)
    for number, selector in enumerate(concept.get('selectors', []), 1):
        errors += validate_selector(selector, f'{where} selector {number}')
        for slug in as_list(selector.get('projects')):
            if known_projects is not None and slug not in known_projects:
                errors.append(f'{where} selector {number}: unknown project {slug}')
    if not concept.get('selectors'):
        errors.append(f'{where}: no selectors')
    for evidence in concept.get('dovezi', []):
        if evidence.get('baza') not in EVIDENCE_BASES or not evidence.get('sursa') or not evidence.get('fragment'):
            errors.append(f'{where}: evidence needs sursa, fragment and a baza')
    return errors


def validate_families(document):
    """The `familii` list and the `familie` of each group: unique ids with a label, and no group pointing at an unknown family."""
    errors, ids = [], []
    for number, family in enumerate(document.get('familii', []), 1):
        if not isinstance(family, dict) or not family.get('id') or not family.get('label'):
            errors.append(f'familii {number}: a family needs id and label')
            continue
        if family['id'] in ids:
            errors.append(f'familii {number}: duplicate family id {family["id"]}')
        ids.append(family['id'])
    for concept in document.get('concepte', []):
        family = concept.get('familie')
        if family is not None and family not in ids:
            errors.append(f'{concept.get("id", "?")}: unknown family {family!r}')
    return errors


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class EvidenceLocator:
    """Finds the retained text behind an evidence URL: a tracked source body, a collected documentation page or a cached page."""

    def __init__(self, out, observations, sources, docs_pages=None):
        self.out, self.obs = Path(out), Path(observations)
        self.sources = {s['url']: s for s in sources}
        self.docs_pages = docs_pages if docs_pages is not None else self._docs_index()

    def _docs_index(self):
        path = self.obs / 'documentare' / 'index.json'
        pages = {}
        try:
            for entry in json.loads(path.read_text())['entries']:
                for page in entry['pages']:
                    if page.get('snapshot') and page.get('state') == 'colectat':
                        pages.setdefault(page['final_url'], page['snapshot'])
        except (OSError, ValueError, KeyError):
            pass
        return pages

    def text(self, url, only=None):
        """(text, kind) or (None, None) when no local copy exists. `only` limits the search to one kind of copy:
        `sursa` (a tracked source body), `documentatie` (the text of a collected page) or `cache` (a cached page body).
        The same address can have different text in each kind, so a pin made on one must not be compared with another."""
        source = self.sources.get(url)
        candidates = []
        if source and source.get('snapshot'):
            candidates.append((self.out / source['snapshot'], 'body', 'sursa'))
        if url in self.docs_pages:
            candidates.append((self.obs / 'documentare' / self.docs_pages[url], 'text', 'documentatie'))
        from inventory_state import source_id
        candidates.append((self.out / 'surse' / (source_id(url) + '.json'), 'body', 'cache'))
        for path, key, kind in candidates:
            if only and kind != only:
                continue
            try:
                value = json.loads(path.read_text()).get(key)
            except (OSError, ValueError):
                continue
            if isinstance(value, str):
                return value, kind
        return None, None


def check_evidence(evidence, locator):
    """'' when the fragment is in the retained text and the hash matches, 'stale' when the text changed, 'unavailable' without a copy."""
    text, _ = locator.text(evidence['sursa'], evidence.get('text'))
    if text is None:
        return 'unavailable'
    if evidence['fragment'] not in text:
        return 'fragment-missing'
    return '' if not evidence.get('sha256') or sha(text) == evidence['sha256'] else 'stale'


def check_concepts(concepts, fields_by_project, locator, known_projects):
    """Structure, selector reach and evidence pins. `fields_by_project` maps slug to [(field, source_url)]."""
    report = {'errors': [], 'stale': [], 'unavailable': [], 'verified': 0}
    ids = [c.get('id') for c in concepts]
    if len(set(ids)) != len(ids):
        report['errors'].append('Duplicate concept IDs.')
    for concept in concepts:
        report['errors'] += validate_concept(concept, known_projects)
        for number, selector in enumerate(concept.get('selectors', []), 1):
            if selector_state(selector) == 'exclus':
                continue  # an excluded member stays in the file as history; it need not match a field
            if not any(selector_matches(selector, slug, field, url) for slug in as_list(selector.get('projects')) for field, url in fields_by_project.get(slug, [])):
                report['errors'].append(f'{concept["id"]} selector {number} matches no field of its projects')
        items = list(concept.get('dovezi', [])) + [f['dovada'] for s in concept.get('selectors', []) for f in s.get('fapte', []) if f.get('dovada')]
        for evidence in items:
            status = check_evidence(evidence, locator)
            label = f'{concept["id"]}: {evidence["sursa"]}'
            if status == '':
                report['verified'] += 1
            elif status == 'stale':
                report['stale'].append(label)
            elif status == 'unavailable':
                report['unavailable'].append(label)
            else:
                report['errors'].append(f'{label}: the fragment is not in the retained text')
    return report
