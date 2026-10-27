#!/usr/bin/env python3
"""Local review interface for the inventory proposals. Stdlib only. Never published: build.py copies none of it.

    python3 scripts/review_ui.py [--port 8790] [--data-dir data/taxonomy-v2/integrare]

It serves one page and a small JSON API on 127.0.0.1 and nothing else. Three queues:

* Providers: the open `revizuire.csv` items with `camp=surse_date` (written: `revizuire.csv`, `relatii.csv` of the data root).
* Variable groups: the groups of `inventar-concepte.json` and their members, the selectors (written: that file).
* Candidate members: the selectors that a batch proposes for a reviewed group (`selectori_candidati` of `inventar-note.json`). A confirmed candidate
  moves into its group; an excluded one stays in the notes with `stare` and `nota_editor` (written: both files, together).

The tool writes repository files and never commits: git is the audit trail. Each write reads the file, applies one decision, validates
the result with the existing loaders, and replaces the file atomically. A request carries the hash of the file that the page loaded;
a different hash on disk refuses the write. CSV and JSON are written byte-stable (same quoting, order, indentation and ending), and a
file that does not round-trip byte for byte is refused rather than rewritten. POST needs the per-process token that the page carries,
and every request needs a `Host` of localhost or 127.0.0.1 with the server port. The server makes no network request.
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import threading
import unicodedata
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import taxonomy_v2
from common import PUBLIC_ROOT, ROOT, observation_paths
from inventory_concepts import (BASIS_LABELS, CANDIDATE_REVIEW_KEYS, CANDIDATES, GROUP_REVIEW_KEYS, GROUP_STATES, SELECTOR_REVIEW_KEYS, SELECTOR_STATES,
                                EvidenceLocator, as_list, candidate_blockers, candidate_items, candidate_key, candidate_label, candidate_state,
                                group_state, repeated_exclusions, same_member, selector_matches, selector_state, sha, validate_candidates,
                                validate_concept, validate_families)

SCRIPTS = Path(__file__).resolve().parent
TEMPLATES = SCRIPTS / 'templates'
ASSETS = {'review_ui.css': 'text/css; charset=utf-8', 'review_ui.js': 'text/javascript; charset=utf-8'}
SITE_URL = 'https://civtech.gov2.ro/'  # the public catalogue; the same constant as build.py (that module is heavy to import)
PROVIDER_ID = re.compile(r'^D\d+$')
GROUP_ID = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
CANDIDATE_ID = re.compile(r'^(\d+)-([0-9a-f]{12})$')  # its place in the list and the start of the SHA-256 of its group and selector
LINKED = re.compile(r'^(L\d+): (.*)$', re.S)
APPENDED = re.compile(r'\(rând (L\d+)\)')
EVIDENCE_IN_REASON = re.compile(r'Dovadă: (\S+) \(text păstrat, sha256 ([0-9a-f]{8,64})\)')
LIMITED_TO_SET = re.compile(r'\b(?:numai|doar) pentru set(?:ul|urile)\b', re.I)
LIMITED_SUFFIX = re.compile(r',?\s*(?:numai|doar) pentru set(?:ul|urile)\b.*$', re.I | re.S)
PROPOSAL_PREFIX = 'Furnizor propus: '
DUPLICATE = re.compile(r'^Duplicat: (D\d+)\.')
ORIGINAL_REASON = ' Motiv inițial: '
MAX_BODY = 64 * 1024
MAX_NOTE = 1500
CHECK_TIMEOUT = 300
PROVIDER_OPEN = ('deschis', 'amanat')  # still needs a decision
PROVIDER_DECIDED = ('acceptat', 'respins', 'tehnic')
GROUP_OPEN = ('propus', 'amanat')
GROUP_DECIDED = ('revizuit', 'respins')
STATE_LABELS = {'verificat': 'verificat', 'schimbat': 'schimbat', 'indisponibil': 'indisponibil local',
                'fara-amprenta': 'fără amprentă', 'fragment-lipsa': 'fragment lipsă'}
COPY_KINDS = ('sursa', 'documentatie', 'cache')
STALE = 'Un fișier s-a schimbat pe disc după ce pagina l-a încărcat (editor, Sheets sau git). Reîncărcați datele.'
STALE_CANDIDATE = 'Lista de candidați s-a schimbat: candidatul nu mai este la această poziție. Reîncărcați datele.'


class ReviewError(Exception):
    """A request that cannot be carried out. `status` is the HTTP status; `reload` tells the page to load the files again."""

    def __init__(self, message, status=400, reload=False):
        super().__init__(message)
        self.status, self.reload = status, reload


# ---------------------------------------------------------------------------------------------------------------------
# Files: byte-stable CSV and JSON, hashes, atomic replacement
# ---------------------------------------------------------------------------------------------------------------------

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_csv(raw: bytes) -> tuple[list[str], list[dict]]:
    """Header and rows with the cell values unchanged. Raises ReviewError for a file that the tool would not write back identically."""
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ReviewError(f'Fișierul nu este UTF-8: {exc}', 500) from exc
    if text.startswith('\ufeff'):
        raise ReviewError('Fișierul CSV începe cu un marcaj de ordine a octeților (BOM). Instrumentul refuză să-l rescrie.', 500)
    rows = list(csv.reader(io.StringIO(text, newline='')))
    if not rows:
        raise ReviewError('Fișierul CSV este gol.', 500)
    header, body = rows[0], rows[1:]
    if any(len(r) != len(header) for r in body):
        raise ReviewError('Un rând CSV are altă lățime decât antetul.', 500)
    parsed = [dict(zip(header, r)) for r in body]
    if dump_csv(header, parsed) != raw:
        raise ReviewError('Fișierul CSV nu se rescrie identic octet cu octet (sfârșituri de rând, ghilimele sau lipsa newline-ului final). '
                          'Instrumentul refuză să-l rescrie.', 500)
    return header, parsed


def dump_csv(header: list[str], rows: list[dict]) -> bytes:
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(header)
    writer.writerows([[row[c] for c in header] for row in rows])
    return out.getvalue().encode('utf-8')


def parse_json(raw: bytes):
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ReviewError(f'Fișierul JSON nu poate fi citit: {exc}', 500) from exc
    if dump_json(data, raw) != raw:
        raise ReviewError('Fișierul JSON nu se rescrie identic octet cu octet (indentare, ordinea cheilor sau newline-ul final). Instrumentul refuză să-l rescrie.', 500)
    return data


def dump_json(data, like: bytes | None = None) -> bytes:
    """Two-space indentation, readable characters, and the final newline that the file already has (the dictionary has none)."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    return (text + ('\n' if like is not None and like.endswith(b'\n') else '')).encode('utf-8')


def replace_atomically(changes: dict[Path, bytes], expected: dict[Path, str]):
    """Replace every file in `changes`, all or none. `expected` maps a path to the hash that the page loaded; any other hash on disk refuses
    the write. The temporary files sit next to their targets, so os.replace is atomic. A failure after the first replacement restores it."""
    for path, wanted in expected.items():
        if digest(path.read_bytes()) != wanted:
            raise ReviewError(STALE, 409, reload=True)
    changes = {p: b for p, b in changes.items() if p.read_bytes() != b}
    temporary, replaced = {}, []
    try:
        for path, data in changes.items():
            handle = tempfile.NamedTemporaryFile('wb', dir=path.parent, prefix='.review-', suffix='.tmp', delete=False)
            temporary[path] = Path(handle.name)
            with handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(handle.name, stat.S_IMODE(path.stat().st_mode))
        for path, tmp in temporary.items():
            original = path.read_bytes()
            os.replace(tmp, path)
            replaced.append((path, original))
    except BaseException:
        for path, original in reversed(replaced):
            restore = path.with_name('.review-restore.tmp')
            restore.write_bytes(original)
            os.replace(restore, path)
        raise
    finally:
        for tmp in temporary.values():
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------------------------------------------------
# Git: the baseline of a reset, the diff of the check panel
# ---------------------------------------------------------------------------------------------------------------------

class Git:
    """Read-only use of git for the repository that holds the data root. Everything degrades to 'unavailable' without git or a HEAD."""

    def __init__(self, anchor: Path):
        self.top = None
        try:
            found = self.run(['rev-parse', '--show-toplevel'], cwd=anchor, check=True)
            self.top = Path(found.strip()).resolve()
        except (OSError, ReviewError):
            self.top = None

    @staticmethod
    def run(args, cwd, check=False, binary=False):
        env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_PAGER': 'cat', 'LC_ALL': 'C'}
        done = subprocess.run(['git', '--no-pager', *args], cwd=cwd, capture_output=True, env=env, timeout=30)
        if done.returncode != 0:
            if check:
                raise ReviewError(done.stderr.decode('utf-8', 'replace').strip() or 'git failed', 500)
            return None
        return done.stdout if binary else done.stdout.decode('utf-8', 'replace')

    @property
    def available(self) -> bool:
        return self.top is not None

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.top).as_posix()

    def head_bytes(self, path: Path) -> bytes | None:
        """The file at HEAD, or None (no git, no HEAD, or the file is new)."""
        if not self.available:
            return None
        return self.run(['show', f'HEAD:{self.rel(path)}'], cwd=self.top, binary=True)

    def status(self, paths: list[Path]) -> list[dict]:
        if not self.available:
            return []
        out = self.run(['status', '--porcelain', '--', *[self.rel(p) for p in paths]], cwd=self.top) or ''
        return [{'status': line[:2].strip() or '?', 'path': line[3:]} for line in out.splitlines() if line.strip()]

    def diff_stat(self, paths: list[Path]) -> str:
        if not self.available:
            return ''
        return (self.run(['diff', 'HEAD', '--stat', '--', *[self.rel(p) for p in paths]], cwd=self.top) or '').rstrip()


# ---------------------------------------------------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------------------------------------------------

def fold(text: str) -> str:
    """Lower case without diacritics; one output character per input character, so that positions stay valid."""
    out = []
    for char in text:
        base = unicodedata.normalize('NFD', char)[0].lower()
        out.append(base if len(base) == 1 else char)
    return ''.join(out)


def provider_name(item: dict) -> str:
    """The provider that a proposal names: the text after `L132: ` or after `Furnizor propus: `, without a limit to one dataset."""
    text = item['propunere']
    linked = LINKED.match(text)
    text = linked.group(2) if linked else text
    if text.startswith(PROPOSAL_PREFIX):
        text = text[len(PROPOSAL_PREFIX):]
    return LIMITED_SUFFIX.sub('', text).strip()


def provider_aliases(name: str) -> list[str]:
    """Strings that stand for the provider in a page: the name, its abbreviation in brackets, and the parts of `A / B`."""
    found = [name, re.sub(r'\s*\([^)]*\)', '', name).strip()]
    found += re.findall(r'\(([^)]{2,12})\)', name)
    for part in re.split(r'\s+/\s+', re.sub(r'\([^)]*\)', '', name)):
        found.append(part.strip())
    return [a for a in dict.fromkeys(found) if len(a) >= 3]


def provider_key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', fold(re.sub(r'\([^)]*\)', ' ', name))).strip()


def same_provider(a: str, b: str) -> bool:
    if provider_key(a) and provider_key(a) == provider_key(b):
        return True
    abbreviations = lambda name: {fold(x) for x in re.findall(r'\(([^)\s]{2,12})\)', name)}
    return bool(abbreviations(a) & ({fold(b)} | abbreviations(b))) or bool(abbreviations(b) & {fold(a)})


def exact_name(name: str) -> str:
    return re.sub(r'\s+', ' ', fold(name)).strip()


def clean_text(value, label: str, required=True, limit=MAX_NOTE) -> str:
    """One line of text for a CSV cell: whitespace collapsed, no control characters, bounded."""
    if not isinstance(value, str):
        raise ReviewError(f'{label}: câmpul este obligatoriu.')
    text = re.sub(r'\s+', ' ', value).strip()
    if required and not text:
        raise ReviewError(f'{label}: câmpul este obligatoriu.')
    if any(ord(c) < 32 for c in text) or len(text) > limit:
        raise ReviewError(f'{label}: caractere de control sau mai mult de {limit} de caractere.')
    return text


def snippet(text: str, start: int, end: int, width=220) -> dict:
    return {'before': text[max(0, start - width):start], 'match': text[start:end], 'after': text[end:end + width],
            'cut_before': start > width, 'cut_after': end + width < len(text)}


# ---------------------------------------------------------------------------------------------------------------------
# Evidence: retained copies, hash check, highlighted fragment
# ---------------------------------------------------------------------------------------------------------------------

class Evidence:
    """Reads the retained copies that `inventory.py --check` uses. Never fetches. One instance serves one request."""

    def __init__(self, locator: EvidenceLocator):
        self.locator, self.memo = locator, {}

    def copies(self, url: str, only: str | None = None) -> list[tuple[str, str, str]]:
        """(kind, text, sha256) of each retained copy of the address; a pin names the kind of copy it was made on."""
        key = (url, only)
        if key not in self.memo:
            found = []
            for kind in ([only] if only in COPY_KINDS else COPY_KINDS):
                text, _ = self.locator.text(url, only=kind)
                if text is not None:
                    found.append((kind, text, sha(text)))
            self.memo[key] = found
        return self.memo[key]

    def view(self, url: str, pin: str | None = None, fragment: str | None = None, kind: str | None = None, needles=()) -> dict:
        """The evidence state of one reference. `verificat` needs a recorded hash that matches the retained copy and the fragment in it.
        Without a recorded hash the state is `fara-amprenta`: the copy is shown, never called verified."""
        result = {'url': url, 'pin': pin, 'fragment': fragment, 'kind': None, 'sha': None, 'snippets': [], 'fragment_found': None}
        copies = self.copies(url, kind)
        if not copies:
            return {**result, 'state': 'indisponibil', 'label': STATE_LABELS['indisponibil']}
        chosen = next((c for c in copies if pin and c[2].startswith(pin)), None)
        if pin and chosen is None:
            state, chosen = 'schimbat', copies[0]
        else:
            chosen = chosen or copies[0]
            state = 'fara-amprenta' if not pin else 'verificat'
        result.update(kind=chosen[0], sha=chosen[2][:16])
        text = chosen[1]
        if fragment:
            at = text.find(fragment)
            result['fragment_found'] = at >= 0
            if at >= 0:
                result['snippets'].append({**snippet(text, at, at + len(fragment)), 'needle': fragment})
            elif state == 'verificat':
                state = 'fragment-lipsa'
        else:
            folded = fold(text)
            for needle in needles:
                at = folded.find(fold(needle))
                if at >= 0 and len(result['snippets']) < 3:
                    result['snippets'].append({**snippet(text, at, at + len(needle)), 'needle': needle})
        return {**result, 'state': state, 'label': STATE_LABELS[state]}


class FieldIndex:
    """The retained field records (observatii/inventare), loaded again when either file changes."""

    def __init__(self, folder: Path):
        self.folder, self.signature, self.profiles, self.sources = folder, None, {}, {}

    def load(self):
        paths = [self.folder / 'proiecte.json', self.folder / 'seturi-date.json']
        signature = [(p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None for p in paths]
        if signature != self.signature:
            self.signature = signature
            self.profiles = {p['slug']: p for p in json.loads(paths[0].read_text())['proiecte']} if paths[0].exists() else {}
            self.sources = {s['id']: s for s in json.loads(paths[1].read_text())['surse']} if paths[1].exists() else {}

    def examples(self, selector: dict, limit=3) -> dict:
        """The fields that the selector reaches (an excluded one too, to show what it would have matched): a count and up to three examples,
        from different sources first."""
        self.load()
        found = []
        for slug in as_list(selector['projects']):
            for ref in self.profiles.get(slug, {}).get('surse_structurate', []):
                source = self.sources.get(ref)
                for field in (source or {}).get('campuri', []):
                    view = {'name': field['nume'], 'path': field['cale'], 'role': field.get('rol', 'camp-date')}
                    if selector_matches(selector, slug, view, source['url'], include_excluded=True):
                        found.append((slug, field, source))
        seen, first, rest = set(), [], []
        for item in found:
            (rest if item[2]['url'] in seen else first).append(item)
            seen.add(item[2]['url'])
        picked = (first + rest)[:limit]
        return {'count': len(found), 'examples': [{
            'project': slug, 'name': f['nume'], 'path': f['cale'], 'role': f.get('rol', 'camp-date'), 'declared_type': f.get('tip_declarat'),
            'observed_types': f.get('tipuri_observate', []), 'unit': f.get('unitate'), 'format': f.get('format'),
            'description': (f.get('descriere') or '')[:240], 'source_url': s['url'], 'pointer': f.get('pointer', ''), 'basis': f.get('stare_tip')}
            for slug, f, s in picked]}


# ---------------------------------------------------------------------------------------------------------------------
# Provider decisions (pure: rows in, rows out)
# ---------------------------------------------------------------------------------------------------------------------

def linked_row_id(item: dict) -> str | None:
    found = LINKED.match(item['propunere'])
    return found.group(1) if found else None


def appended_row_id(item: dict) -> str | None:
    found = APPENDED.search(item['decizie_editor'])
    return found.group(1) if found else None


def own_row_id(item: dict) -> str | None:
    return linked_row_id(item) or appended_row_id(item)


def original_reason(item: dict) -> str:
    """The reason of an item, as it was before a duplicate decision replaced it."""
    reason = item['motiv']
    if DUPLICATE.match(reason) and ORIGINAL_REASON in reason:
        return reason.split(ORIGINAL_REASON, 1)[1]
    return reason


def next_relation_id(rel_rows: list[dict], rev_rows: list[dict]) -> str:
    named = [r['id'] for r in rel_rows] + [m.group(1) for r in rev_rows if (m := LINKED.match(r['propunere']))]
    numbers = [int(m.group(1)) for x in named if (m := re.fullmatch(r'L(\d+)', x))]
    return f'L{max(numbers, default=0) + 1:03d}'


def find_row(rows: list[dict], row_id: str) -> dict | None:
    return next((r for r in rows if r['id'] == row_id), None)


def apply_provider(rev_rows, rel_rows, item_id, action, *, note='', name='', url='', other='', today='', head_rev=None, head_rel=None):
    """One provider decision on copies of the two tables. `head_rev` and `head_rel` map ids to the rows at HEAD (None without git).
    Returns (revizuire rows, relatii rows, a sentence for the page)."""
    rev_rows, rel_rows = copy.deepcopy(rev_rows), copy.deepcopy(rel_rows)
    item = find_row(rev_rows, item_id)
    if item is None or item['camp'] != 'surse_date' or not PROVIDER_ID.match(item_id):
        raise ReviewError(f'{item_id} nu este un element de furnizor (camp surse_date).', 404)
    linked, appended = linked_row_id(item), appended_row_id(item)
    own = find_row(rel_rows, linked or appended) if (linked or appended) else None
    at_head = (lambda rid: True) if head_rel is None else (lambda rid: rid in head_rel)
    if linked and own is None:
        raise ReviewError(f'{item_id} numește relația {linked}, dar relatii.csv nu o conține.', 409)

    if action == 'reset':
        if head_rev is None or head_rel is None or item_id not in head_rev:
            raise ReviewError('Nu există o versiune HEAD a elementului la care să revină (fără depozit git, fără commit sau element nou).')
        rows_to_restore = {r for r in (linked, appended, linked_row_id(head_rev[item_id]), appended_row_id(head_rev[item_id])) if r}
        rev_rows[rev_rows.index(item)] = dict(head_rev[item_id])
        for rid in rows_to_restore:
            current = find_row(rel_rows, rid)
            if rid in head_rel:
                if current is None:
                    rel_rows.append(dict(head_rel[rid]))
                else:
                    rel_rows[rel_rows.index(current)] = dict(head_rel[rid])
            elif current is not None and rid == appended:
                rel_rows.remove(current)  # a row that this item appended and HEAD does not hold
        return rev_rows, rel_rows, f'{item_id} a revenit la valorile din HEAD.'

    note = clean_text(note, 'Notă')
    marker = ''
    if action == 'accept':
        name = clean_text(name, 'Numele furnizorului', required=own is None or not own['obiect'], limit=200)
        if name and name[0] in '=+-@':
            raise ReviewError('Numele furnizorului nu poate începe cu = + - sau @.')
        url = clean_text(url, 'Adresa dovezii', limit=500)
        if not taxonomy_v2.http_evidence(url):
            raise ReviewError('Adresa dovezii: este nevoie de o adresă http(s) fără spații.')
        target_name = name or (own['obiect'] if own is not None else '')  # a provider that is a catalogue entry keeps its slug as its name
        for row in rel_rows:
            if (row['subiect'] == item['slug'] and row['predicat'] == 'date_din' and row['stare'] == 'acceptat' and (own is None or row['id'] != own['id'])
                    and exact_name(row['obiect_literal'] or row['obiect']) == exact_name(target_name)):
                raise ReviewError(f'«{target_name}» este deja sursă acceptată pentru {item["slug"]} ({row["id"]}). Închideți elementul ca duplicat.')
        if own is None:
            rid = next_relation_id(rel_rows, rev_rows)
            rel_rows.append({'id': rid, 'subiect': item['slug'], 'predicat': 'date_din', 'obiect': '', 'obiect_literal': name,
                             'camp_sursa': 'surse_date', 'valoare_sursa': url, 'stare': 'acceptat'})
            marker = f' (rând {rid})'
        else:
            if not own['obiect']:
                own['obiect_literal'] = name
            own.update(camp_sursa='surse_date', valoare_sursa=url, stare='acceptat')
            marker = f' (rând {appended})' if appended and not linked else ''
        item.update(stare='acceptat', decizie_editor=f'Acceptat {today}{marker}: {note}', motiv=original_reason(item))
        return rev_rows, rel_rows, f'{item_id} acceptat: «{target_name}» devine sursă de date pentru {item["slug"]}.'

    # reject, defer and duplicate close or park the item and unwind what an earlier decision wrote to relatii.csv.
    if action not in ('reject', 'defer', 'duplicate'):
        raise ReviewError(f'Acțiune necunoscută: {action!r}.')
    if own is not None:
        if linked:  # the relation that the proposal names stays in the file: reject closes it, defer parks it, a duplicate only withdraws an acceptance
            if action == 'reject':
                own['stare'] = 'respins'
            elif action == 'defer' or own['stare'] == 'acceptat':
                own['stare'] = 'propus'
        elif at_head(own['id']):
            own['stare'] = 'respins' if action in ('reject', 'duplicate') else 'propus'
            marker = f' (rând {own["id"]})' if action != 'duplicate' else ''
        else:
            rel_rows.remove(own)  # this item appended the row and no commit holds it yet
    if action == 'duplicate':
        other = clean_text(other, 'Duplicat al elementului', limit=20)
        target = find_row(rev_rows, other)
        if not PROVIDER_ID.match(other) or target is None or target['camp'] != 'surse_date':
            raise ReviewError(f'{other} nu este un element de furnizor existent.')
        if other == item_id or target['slug'] != item['slug']:
            raise ReviewError('Un duplicat trebuie să indice un alt element al aceluiași proiect.')
        if DUPLICATE.match(target['motiv']):
            raise ReviewError(f'{other} este el însuși un duplicat. Indicați elementul pe care îl dublează.')
        item.update(stare='tehnic', decizie_editor='', motiv=f'Duplicat: {other}. {note}{ORIGINAL_REASON}{original_reason(item)}')
        return rev_rows, rel_rows, f'{item_id} închis ca duplicat al lui {other}.'
    word, state = ('Respins', 'respins') if action == 'reject' else ('Amânat', 'amanat')
    item.update(stare=state, decizie_editor=f'{word} {today}{marker}: {note}', motiv=original_reason(item))
    return rev_rows, rel_rows, f'{item_id} {word.lower()}.'


# ---------------------------------------------------------------------------------------------------------------------
# Group decisions (pure: the dictionary in, the dictionary out)
# ---------------------------------------------------------------------------------------------------------------------

def reorder(item: dict, keys: tuple[str, ...]) -> dict:
    """The existing keys in their order, then the review keys in theirs (new keys go after the existing ones)."""
    base = {k: v for k, v in item.items() if k not in keys}
    base.update({k: item[k] for k in keys if k in item})
    return base


def deduction_items(concept: dict) -> list[dict]:
    """What the editor must tick before the group can be `revizuit`: every statement that rests on a deduction from evidence."""
    items = []
    if concept.get('baza_definitiei') == 'deductie-din-dovezi':
        items.append({'id': 'definitie', 'text': 'Definiția grupului'})
    for n, evidence in enumerate(concept.get('dovezi', []), 1):
        if evidence.get('baza') == 'deductie-din-dovezi':
            items.append({'id': f'dovada-{n}', 'text': f'Dovada {n} a definiției: {evidence["fragment"][:120]}'})
    for s, selector in enumerate(concept.get('selectors', []), 1):
        for f, fact in enumerate(selector.get('fapte', []), 1):
            if fact.get('baza') == 'deductie-din-dovezi':
                items.append({'id': f'fapt-{s}-{f}', 'text': f'Membrul {s}, {fact["cheie"]}: {fact["valoare"]}'})
    return items


def review_blockers(concept: dict, ticked=None) -> list[str]:
    """Why the group cannot be `revizuit` yet (empty when it can). The page shows these; the server enforces the same rules.
    The ticks of the deductions belong to the request, so they count only when the caller passes them (`ticked` is a list of ids)."""
    reasons = []
    selectors = concept.get('selectors', [])
    open_members = sum(selector_state(s) == 'propus' for s in selectors)
    if open_members:
        reasons.append(f'{open_members} membri sunt încă «propuși»: confirmați-i sau excludeți-i.')
    if not any(selector_state(s) == 'confirmat' for s in selectors):
        reasons.append('Niciun membru nu este confirmat.')
    missing = [] if ticked is None else [d for d in deduction_items(concept) if d['id'] not in set(ticked)]
    if missing:
        reasons.append(f'{len(missing)} deducții nu sunt bifate ca verificate.')
    return reasons


def find_group(data: dict, gid: str) -> dict:
    found = next((c for c in data['concepte'] if c['id'] == gid), None)
    if found is None:
        raise ReviewError(f'Nu există grupul {gid}.', 404)
    return found


def apply_group(data, gid, action, *, note='', ticked=(), today='', head_data=None):
    data = copy.deepcopy(data)
    concept = find_group(data, gid)
    index = data['concepte'].index(concept)
    if action == 'reset':
        if head_data is None:
            raise ReviewError('Nu există o versiune HEAD a dicționarului la care să revină (fără depozit git sau commit).')
        head = next((c for c in head_data['concepte'] if c['id'] == gid), None)
        if head and len(head['selectors']) != len(concept['selectors']):
            raise ReviewError(f'Membrii lui {gid} diferă de HEAD; resetați cheile de revizuire manual.')
        for key in GROUP_REVIEW_KEYS:
            concept.pop(key, None)
            if head and key in head:
                concept[key] = copy.deepcopy(head[key])
        for number, selector in enumerate(concept['selectors']):
            old = head['selectors'][number] if head else {}
            for key in SELECTOR_REVIEW_KEYS:
                selector.pop(key, None)
                if key in old:
                    selector[key] = copy.deepcopy(old[key])
            concept['selectors'][number] = reorder(selector, SELECTOR_REVIEW_KEYS)
        data['concepte'][index] = reorder(concept, GROUP_REVIEW_KEYS)
        return data, f'{gid} a revenit la starea de revizuire din HEAD.'
    states = {'revizuit': 'revizuit', 'respins': 'respins', 'amanat': 'amanat'}
    if action not in states:
        raise ReviewError(f'Acțiune necunoscută: {action!r}.')
    note = clean_text(note, 'Notă')
    if action == 'revizuit':
        reasons = review_blockers(concept, ticked)
        if reasons:
            raise ReviewError('Grupul nu poate fi marcat «revizuit»: ' + ' '.join(reasons))
    concept.update(stare=states[action], decizie_editor=note, data_revizie=today)
    data['concepte'][index] = reorder(concept, GROUP_REVIEW_KEYS)
    return data, f'{gid}: {states[action]}.'


def apply_member(data, gid, number, action, *, note=''):
    data = copy.deepcopy(data)
    concept = find_group(data, gid)
    if group_state(concept) not in GROUP_OPEN:
        raise ReviewError(f'Grupul {gid} este «{group_state(concept)}». Resetați grupul înainte să schimbați un membru.')
    if not isinstance(number, int) or not 1 <= number <= len(concept['selectors']):
        raise ReviewError(f'Grupul {gid} nu are membrul {number}.', 404)
    selector = concept['selectors'][number - 1]
    if action == 'reset':
        for key in SELECTOR_REVIEW_KEYS:
            selector.pop(key, None)
    elif action in ('confirm', 'exclude'):
        text = clean_text(note, 'Notă', required=action == 'exclude')
        selector['stare'] = 'confirmat' if action == 'confirm' else 'exclus'
        selector.pop('nota_editor', None)
        if text:
            selector['nota_editor'] = text
    else:
        raise ReviewError(f'Acțiune necunoscută: {action!r}.')
    concept['selectors'][number - 1] = reorder(selector, SELECTOR_REVIEW_KEYS)
    return data, f'{gid}, membrul {number}: {selector_state(selector)}.'


# ---------------------------------------------------------------------------------------------------------------------
# Candidate decisions (pure: the dictionary and the notes in, the dictionary and the notes out)
# ---------------------------------------------------------------------------------------------------------------------

def candidate_id(number: int, item: dict) -> str:
    return f'{number}-{candidate_key(item)[:12]}'


def blocker_text(reason: str, value) -> str:
    return {'missing-group': f'Grupul «{value}» nu există.',
            'group-state': f'Grupul este «{value}». Un candidat se confirmă numai într-un grup revizuit; un membru al unui alt grup se adaugă direct în grup.',
            'held': f'Grupul are deja acest selector ca membru (membrul {value}).'}[reason]


def confirmed_since_head(data: dict, notes: dict, head_data, head_notes) -> list[dict]:
    """The candidates that HEAD lists, that the notes do not list any more, and whose selector a group holds now but did not hold at HEAD:
    confirmed and not committed. Each is {'number' (its place at HEAD), 'item', 'member' (its number in the group)}, in HEAD order."""
    if head_data is None or head_notes is None:
        return []
    present = {candidate_key(i) for i in candidate_items(notes)}
    groups = {c['id']: c for c in data['concepte']}
    head_groups = {c['id']: c for c in head_data['concepte']}
    found, seen = [], set()
    for number, item in enumerate(candidate_items(head_notes), 1):
        key, group = candidate_key(item), groups.get(item.get('grup'))
        if key in present or key in seen or group is None:
            continue
        selector = item.get('selector') or {}
        at = next((n for n, member in enumerate(group['selectors'], 1) if same_member(selector, member)), None)
        held = any(same_member(selector, member) for member in head_groups.get(item.get('grup'), {}).get('selectors', []))
        if at is not None and not held:
            seen.add(key)
            found.append({'number': number, 'item': item, 'member': at})
    return found


def with_candidates(notes: dict, items: list, head_notes) -> dict:
    """The notes with this candidate list. An empty list removes the key, as the batches do. A key that comes back goes where HEAD had it,
    so that a reset gives the bytes of HEAD."""
    if not items:
        notes.pop(CANDIDATES, None)
        return notes
    if CANDIDATES in notes:
        notes[CANDIDATES] = items
        return notes
    order = list(head_notes) if head_notes is not None and CANDIDATES in head_notes else list(notes) + [CANDIDATES]
    before = [k for k in order[:order.index(CANDIDATES)] if k in notes]
    out = {CANDIDATES: items} if not before else {}
    for key, value in notes.items():
        out[key] = value
        if before and key == before[-1]:
            out[CANDIDATES] = items
    return out


def insert_position(items: list, head_items: list, at_head: int) -> int:
    """Where a candidate that HEAD lists at `at_head` goes back: after the last listed candidate that HEAD lists before it."""
    head_index = {}
    for n, item in enumerate(head_items):
        head_index.setdefault(candidate_key(item), n)
    position = 0
    for n, item in enumerate(items):
        placed = head_index.get(candidate_key(item))
        if placed is not None and placed < at_head:
            position = n + 1
    return position


def apply_candidate(data, notes, cid, action, *, note='', head_data=None, head_notes=None):
    """One decision on a candidate (`cid` is its place in the list and the start of its hash, as in the page). Returns (dictionary, notes,
    a sentence for the page, the key of the candidate). `head_data` and `head_notes` are the two files at HEAD (None without git)."""
    data, notes = copy.deepcopy(data), copy.deepcopy(notes)
    found = CANDIDATE_ID.match(cid or '')
    if not found:
        raise ReviewError('Nu este un identificator de candidat.', 404)
    number, prefix = int(found.group(1)), found.group(2)
    if action not in ('confirm', 'exclude', 'reset'):
        raise ReviewError(f'Acțiune necunoscută: {action!r}.')
    items = candidate_items(notes)
    at = number - 1 if 1 <= number <= len(items) and candidate_key(items[number - 1]).startswith(prefix) else None
    since = [g for g in confirmed_since_head(data, notes, head_data, head_notes) if g['number'] == number and candidate_key(g['item']).startswith(prefix)]
    if action == 'reset':
        if head_data is None or head_notes is None:
            raise ReviewError('Nu există o versiune HEAD a notelor la care să revină (fără depozit git sau commit).')
        if at is None and not since:
            raise ReviewError(STALE_CANDIDATE, 409, reload=True)
        item = items[at] if at is not None else since[0]['item']
        head_items = candidate_items(head_notes)
        at_head = next((n for n, held in enumerate(head_items) if candidate_key(held) == candidate_key(item)), None)
        if at_head is None:
            raise ReviewError('Candidatul nu există în HEAD (a fost propus după ultimul commit); nu are la ce să revină.')
        restored = copy.deepcopy(head_items[at_head])
        if at is not None:
            items[at] = restored
        else:  # confirmed since HEAD: the member leaves its group and the candidate goes back to its place
            group = find_group(data, item['grup'])
            del group['selectors'][since[0]['member'] - 1]
            items.insert(insert_position(items, head_items, at_head), restored)
        return data, with_candidates(notes, items, head_notes), f'Candidatul «{candidate_label(item)}» a revenit la valorile din HEAD.', candidate_key(item)
    if at is None:
        if since:
            raise ReviewError('Candidatul este deja confirmat și nu este în HEAD. Resetați-l înainte să-l schimbați.')
        raise ReviewError(STALE_CANDIDATE, 409, reload=True)
    item = items[at]
    label = candidate_label(item)
    if action == 'exclude':
        text = clean_text(note, 'Notă')
        items[at] = reorder({**item, 'stare': 'exclus', 'nota_editor': text}, CANDIDATE_REVIEW_KEYS)
        return data, with_candidates(notes, items, head_notes), f'Candidatul «{label}»: exclus.', candidate_key(item)
    groups = {c['id']: c for c in data['concepte']}
    blockers = candidate_blockers(item, groups)
    if blockers:
        raise ReviewError('Candidatul nu poate fi confirmat. ' + ' '.join(blocker_text(*b) for b in blockers), 422)
    text = clean_text(note, 'Notă', required=False)
    member = {k: v for k, v in copy.deepcopy(item['selector']).items() if k not in SELECTOR_REVIEW_KEYS}
    member['stare'] = 'confirmat'
    if text:
        member['nota_editor'] = text
    group = groups[item['grup']]
    group['selectors'].append(reorder(member, SELECTOR_REVIEW_KEYS))
    del items[at]
    return data, with_candidates(notes, items, head_notes), f'Candidatul «{label}» este membrul {len(group["selectors"])} al grupului {group["id"]}: confirmat.', candidate_key(item)


# ---------------------------------------------------------------------------------------------------------------------
# The store: one data root
# ---------------------------------------------------------------------------------------------------------------------

class Store:
    """Reads, shows and writes the four review files of one data root. Every public method takes the lock."""

    def __init__(self, root: Path = PUBLIC_ROOT, today=None):
        self.root = Path(root).resolve()
        if not taxonomy_v2.is_v2(self.root):
            raise SystemExit(f'{root}: not a taxonomy v2 data root')
        files = taxonomy_v2.Files(self.root)
        self.paths = {'revizuire': files.path('revizuire.csv'), 'relatii': files.path('relatii.csv'),
                      'concepte': self.root.parent / 'inventar-concepte.json', 'note': self.root.parent / 'inventar-note.json'}
        missing = [str(p) for p in self.paths.values() if not p.exists()]
        if missing:
            raise SystemExit('Missing review files: ' + ', '.join(missing))
        self.inventory = observation_paths(self.root)['profile'].parent / 'inventare'
        self.observations = observation_paths(self.root)['profile'].parent
        self.git = Git(self.root)
        self.fields = FieldIndex(self.inventory)
        self.lock = threading.RLock()
        self.today = today or (lambda: datetime.date.today().isoformat())
        self._validation = (None, None)

    # -- reading ---------------------------------------------------------------------------------------------------

    def read(self) -> dict:
        raw = {k: p.read_bytes() for k, p in self.paths.items()}
        rev_header, rev_rows = parse_csv(raw['revizuire'])
        rel_header, rel_rows = parse_csv(raw['relatii'])
        return {'raw': raw, 'hashes': {k: digest(v) for k, v in raw.items()}, 'rev_header': rev_header, 'rev_rows': rev_rows,
                'rel_header': rel_header, 'rel_rows': rel_rows, 'concepts': parse_json(raw['concepte']), 'notes': parse_json(raw['note'])}

    def head(self) -> dict:
        """The four files at HEAD, parsed; an entry is None when git or the commit is missing."""
        out = {'rev': None, 'rel': None, 'concepts': None, 'notes': None}
        for key, name, parser in (('rev', 'revizuire', parse_csv), ('rel', 'relatii', parse_csv), ('concepts', 'concepte', parse_json),
                                  ('notes', 'note', parse_json)):
            raw = self.git.head_bytes(self.paths[name])
            if raw is None:
                continue
            try:
                parsed = parser(raw)
            except ReviewError:
                continue
            out[key] = {r['id']: r for r in parsed[1]} if parser is parse_csv else parsed
        return out

    def evidence(self) -> Evidence:
        sources_path = self.inventory / 'seturi-date.json'
        sources = json.loads(sources_path.read_text())['surse'] if sources_path.exists() else []
        return Evidence(EvidenceLocator(self.inventory, self.observations, sources))

    def package(self):
        return taxonomy_v2.load(self.root)

    def hashes(self) -> dict:
        with self.lock:
            return {k: digest(p.read_bytes()) for k, p in self.paths.items()}

    # -- validation ------------------------------------------------------------------------------------------------

    def errors_of(self, data: dict, rev_rows=None, rel_rows=None, notes=None) -> list[str]:
        """Package errors (with the publication gate), dictionary errors and candidate errors for the given content of the four files.
        A file that the caller does not pass is the file on disk."""
        pkg = self.package()
        if rev_rows is not None:
            pkg.tables['revizuire.csv'] = rev_rows
        if rel_rows is not None:
            pkg.tables['relatii.csv'] = rel_rows
        errors, _ = taxonomy_v2.check(self.root, publication=True, package=pkg)
        known = set(pkg.entries)
        ids = [c.get('id') for c in data['concepte']]
        if len(set(ids)) != len(ids):
            errors.append('inventar-concepte.json: duplicate group ids')
        for concept in data['concepte']:
            errors += validate_concept(concept, known)
        notes = notes if notes is not None else parse_json(self.paths['note'].read_bytes())
        return errors + validate_families(data) + validate_candidates(notes.get(CANDIDATES), data['concepte'], known)

    def current_errors(self, snapshot: dict) -> list[str]:
        """The errors of the files as they are on disk, computed once for each content of the three files."""
        key = tuple(snapshot['hashes'].values())
        if self._validation[0] != key:
            self._validation = (key, self.errors_of(snapshot['concepts'], notes=snapshot['notes']))
        return self._validation[1]

    def validation(self, snapshot: dict) -> dict:
        errors = self.current_errors(snapshot)
        return {'ok': not errors, 'count': len(errors), 'errors': errors[:20]}

    def remember_errors(self, written: dict[str, bytes], snapshot: dict, errors: list[str]):
        """After a write, the errors found before it are the errors of the new files: nothing needs checking again."""
        key = tuple(digest(written[k]) if k in written else h for k, h in snapshot['hashes'].items())
        self._validation = (key, errors)

    def refuse_new_errors(self, before: list[str], after: list[str]):
        new = [e for e in after if e not in before]
        if new:
            raise ReviewError('Rezultatul nu ar trece validarea; nu s-a scris nimic. ' + ' | '.join(new[:5]), 422)

    # -- state and views -------------------------------------------------------------------------------------------

    def entry_names(self) -> dict:
        pkg = self.package()
        return {slug: row for slug, row in pkg.entries.items()}

    def state(self) -> dict:
        with self.lock:
            snap = self.read()
            entries = self.entry_names()
            providers = []
            for row in snap['rev_rows']:
                if row['camp'] != 'surse_date':
                    continue
                providers.append({'id': row['id'], 'slug': row['slug'], 'project': entries.get(row['slug'], {}).get('nume', row['slug']),
                                  'proposal': provider_name(row), 'stare': row['stare'], 'prioritate': row['prioritate'],
                                  'duplicate_of': (DUPLICATE.match(row['motiv']) or [None, None])[1]})
            groups = []
            for concept in snap['concepts']['concepte']:
                members = Counter(selector_state(s) for s in concept['selectors'])
                groups.append({'id': concept['id'], 'label': concept['label'], 'categorie': concept.get('categorie'), 'stare': group_state(concept),
                               'members': len(concept['selectors']), 'confirmat': members['confirmat'], 'exclus': members['exclus'],
                               'propus': members['propus']})
            by_state = Counter(p['stare'] for p in providers)
            group_states = Counter(g['stare'] for g in groups)
            by_id = {c['id']: c for c in snap['concepts']['concepte']}
            candidates = [self.candidate_row(r, by_id, entries) for r in self.candidate_records(snap, self.head())]
            candidate_states = Counter(c['stare'] for c in candidates)
            return {
                'hashes': snap['hashes'], 'today': self.today(), 'root': str(self.root), 'providers': providers, 'groups': groups, 'candidates': candidates,
                'progress': {
                    'providers': {'total': len(providers), 'decided': sum(by_state[s] for s in PROVIDER_DECIDED), 'by_state': dict(by_state)},
                    'groups': {'total': len(groups), 'decided': sum(group_states[s] for s in GROUP_DECIDED), 'by_state': dict(group_states)},
                    'candidates': {'total': len(candidates), 'open': candidate_states['propus'], 'decided': candidate_states['exclus'] + candidate_states['confirmat'],
                                   'by_state': dict(candidate_states)}},
                'validation': self.validation(snap), 'git': {'available': self.git.available},
            }

    # -- the candidate queue -----------------------------------------------------------------------------------------

    def candidate_records(self, snap: dict, head: dict) -> list[dict]:
        """The candidate queue: the listed candidates in file order, and among them (in their place at HEAD) the ones confirmed since HEAD,
        which the notes do not list any more and a group holds now. Each record has its `id`, `key`, `item`, `origin` (`lista` or `confirmat`)
        and `head` (`available`: HEAD lists it; `changed`: it differs from HEAD, so a reset has something to do)."""
        head_notes = head['notes']
        head_items = candidate_items(head_notes) if head_notes is not None else None
        head_index = {}
        for n, item in enumerate(head_items or []):
            head_index.setdefault(candidate_key(item), n)
        listed = []
        for number, item in enumerate(candidate_items(snap['notes']), 1):
            key = candidate_key(item)
            at_head = head_index.get(key)
            listed.append({'origin': 'lista', 'number': number, 'key': key, 'item': item, 'member': None, 'at_head': at_head,
                           'head': {'available': at_head is not None, 'changed': at_head is not None and head_items[at_head] != item}})
        ghosts = [{'origin': 'confirmat', 'number': g['number'], 'key': candidate_key(g['item']), 'item': g['item'], 'member': g['member'],
                   'at_head': g['number'] - 1, 'head': {'available': True, 'changed': True}}
                  for g in confirmed_since_head(snap['concepts'], snap['notes'], head['concepts'], head_notes)]
        ordered = []
        for record in listed:
            while ghosts and record['at_head'] is not None and ghosts[0]['at_head'] < record['at_head']:
                ordered.append(ghosts.pop(0))
            ordered.append(record)
        ordered += ghosts
        for record in ordered:
            record['id'] = candidate_id(record['number'], record['item'])
        return ordered

    def candidate_row(self, record: dict, groups: dict, entries: dict) -> dict:
        item, group = record['item'], groups.get(record['item'].get('grup'))
        selector = item.get('selector') or {}
        what = ', '.join(map(str, as_list(selector.get('names')) or as_list(selector.get('path'))))
        projects = ', '.join(entries.get(s, {}).get('nume', s) for s in as_list(selector.get('projects')))
        stare = 'confirmat' if record['origin'] == 'confirmat' else candidate_state(item)
        return {'id': record['id'], 'short': f'#{record["number"]}', 'number': record['number'], 'key': record['key'], 'group': item.get('grup'),
                'label': group['label'] if group else str(item.get('grup')), 'group_stare': group_state(group) if group else None,
                'proposal': f'{what} · {projects}', 'stare': stare,
                'problems': len(candidate_blockers(item, groups)) if stare == 'propus' else 0}

    def related(self, rows, item) -> list[dict]:
        name = provider_name(item)
        return [{'id': r['id'], 'proposal': provider_name(r), 'stare': r['stare'], 'same_provider': same_provider(name, provider_name(r))}
                for r in rows if r['camp'] == 'surse_date' and r['slug'] == item['slug'] and r['id'] != item['id']]

    def provider(self, item_id: str) -> dict:
        with self.lock:
            if not PROVIDER_ID.match(item_id):
                raise ReviewError('Nu este un identificator de element de furnizor.', 404)
            snap = self.read()
            item = find_row(snap['rev_rows'], item_id)
            if item is None or item['camp'] != 'surse_date':
                raise ReviewError(f'{item_id} nu este un element de furnizor.', 404)
            entry = self.entry_names().get(item['slug'], {})
            linked, appended = linked_row_id(item), appended_row_id(item)
            row = find_row(snap['rel_rows'], linked or appended) if (linked or appended) else None
            name = provider_name(item)
            reason = original_reason(item)
            cited = EVIDENCE_IN_REASON.search(reason)
            url = row['valoare_sursa'] if row and row['valoare_sursa'] else (cited.group(1) if cited else '')
            pin = cited.group(2) if cited and cited.group(1) == url else None
            if row and not row['obiect'] and row['obiect_literal']:
                name = row['obiect_literal']
            evidence = self.evidence().view(url, pin=pin, fragment=item['valoare_originala'] if pin else None,
                                            needles=provider_aliases(name)) if url else None
            accepted = [{'id': r['id'], 'name': r['obiect_literal'] or r['obiect'], 'evidence': r['valoare_sursa']}
                        for r in snap['rel_rows'] if r['subiect'] == item['slug'] and r['predicat'] == 'date_din' and r['stare'] == 'acceptat']
            warnings = []
            if LIMITED_TO_SET.search(item['propunere']):
                warnings.append('Propunerea limitează furnizorul la un singur set de date. O relație se aplică întregului proiect.')
            related = self.related(snap['rev_rows'], item)
            if any(r['same_provider'] and r['stare'] == 'acceptat' for r in related):
                warnings.append('Un element înrudit, pentru același furnizor, este deja acceptat. Marcați acest element ca duplicat.')
            head = self.head()
            head_item = (head['rev'] or {}).get(item_id)
            return {
                'id': item_id, 'slug': item['slug'], 'camp': item['camp'], 'valoare_originala': item['valoare_originala'], 'propunere': item['propunere'],
                'motiv': item['motiv'], 'prioritate': item['prioritate'], 'stare': item['stare'], 'decizie_editor': item['decizie_editor'],
                'duplicate_of': (DUPLICATE.match(item['motiv']) or [None, None])[1],
                'project': {'name': entry.get('nume', item['slug']), 'kind': entry.get('sectiune_url', 'proiect'),
                            'catalogue_url': f"{SITE_URL}{entry.get('sectiune_url', 'proiect')}/{item['slug']}/", 'url': entry.get('url', '')},
                'prefill': {'name': name, 'url': url, 'name_locked': bool(row and row['obiect'])},
                'row': row, 'row_origin': 'propunere' if linked else 'marcaj' if appended else None,
                'new_row_id': None if row else next_relation_id(snap['rel_rows'], snap['rev_rows']),
                'evidence': evidence, 'related': related, 'accepted': accepted, 'warnings': warnings,
                'head': {'available': head_item is not None, 'changed': head_item is not None and head_item != item},
                'hashes': {k: snap['hashes'][k] for k in ('revizuire', 'relatii')},
            }

    @staticmethod
    def pin_view(evidence: Evidence, pin):
        return None if not pin else evidence.view(pin['sursa'], pin=pin.get('sha256'), fragment=pin['fragment'], kind=pin.get('text'))

    def member_view(self, number, selector: dict, entries: dict, evidence: Evidence) -> dict:
        """What the page shows of one selector: where it points, how far it reaches in the retained inventory, and its pinned facts with their evidence."""
        return {
            'number': number, 'projects': [{'slug': s, 'name': entries.get(s, {}).get('nume', s)} for s in as_list(selector['projects'])],
            'names': as_list(selector.get('names')), 'path': as_list(selector.get('path')), 'source': as_list(selector.get('source')),
            'role': as_list(selector.get('role')), 'context': selector.get('context', ''), 'nota': selector.get('nota', ''),
            'stare': selector_state(selector), 'nota_editor': selector.get('nota_editor', ''), 'reach': self.fields.examples(selector),
            'facts': [{'key': f['cheie'], 'value': f['valoare'], 'basis': f['baza'], 'basis_label': BASIS_LABELS.get(f['baza'], f['baza']),
                       'evidence': self.pin_view(evidence, f.get('dovada'))} for f in selector.get('fapte', [])]}

    def group(self, gid: str) -> dict:
        with self.lock:
            if not GROUP_ID.match(gid):
                raise ReviewError('Nu este un identificator de grup.', 404)
            snap = self.read()
            concept = find_group(snap['concepts'], gid)
            entries, evidence = self.entry_names(), self.evidence()
            view = lambda pin: self.pin_view(evidence, pin)
            members = [self.member_view(number, selector, entries, evidence) for number, selector in enumerate(concept['selectors'], 1)]
            head = self.head()['concepts']
            head_concept = next((c for c in head['concepte'] if c['id'] == gid), None) if head else None
            blockers = review_blockers(concept)
            return {
                'id': gid, 'label': concept['label'], 'categorie': concept.get('categorie'), 'definition': concept['definition'],
                'basis': concept.get('baza_definitiei'), 'basis_label': BASIS_LABELS.get(concept.get('baza_definitiei'), concept.get('baza_definitiei')),
                'ambiguities': concept.get('ambiguitati', []), 'stare': group_state(concept), 'decizie_editor': concept.get('decizie_editor', ''),
                'data_revizie': concept.get('data_revizie', ''),
                'proofs': [{'basis': p.get('baza'), 'basis_label': BASIS_LABELS.get(p.get('baza'), p.get('baza')), 'evidence': view(p)}
                           for p in concept.get('dovezi', [])],
                'deductions': deduction_items(concept), 'blockers': blockers, 'members': members,
                'head': {'available': head_concept is not None, 'changed': head_concept is not None and head_concept != concept},
                'hashes': {'concepte': snap['hashes']['concepte']},
            }

    def candidate(self, cid: str) -> dict:
        """One candidate as the page shows it: the group, the selector with its reach and pinned facts, and the confirmed members of the group."""
        with self.lock:
            if not CANDIDATE_ID.match(cid):
                raise ReviewError('Nu este un identificator de candidat.', 404)
            snap, head = self.read(), self.head()
            records = self.candidate_records(snap, head)
            record = next((r for r in records if r['id'] == cid), None)
            if record is None:
                raise ReviewError(STALE_CANDIDATE, 404, reload=True)
            groups = {c['id']: c for c in snap['concepts']['concepte']}
            item, entries = record['item'], self.entry_names()
            group, listed = groups.get(item.get('grup')), record['origin'] == 'lista'
            selector = item['selector'] if listed else group['selectors'][record['member'] - 1]
            member = self.member_view(record['member'], selector, entries, self.evidence())
            stare = candidate_state(item) if listed else 'confirmat'
            if listed:
                member.update(stare=stare, nota_editor=item.get('nota_editor', ''))
            mine = set(as_list(selector.get('projects')))
            confirmed = [{'number': n, 'projects': [{'slug': s, 'name': entries.get(s, {}).get('nume', s)} for s in as_list(m.get('projects'))],
                          'names': as_list(m.get('names')), 'path': as_list(m.get('path')), 'source': as_list(m.get('source')), 'role': as_list(m.get('role')),
                          'context': m.get('context', ''), 'same_project': bool(mine & set(as_list(m.get('projects')))),
                          'this': not listed and n == record['member']}
                         for n, m in enumerate(group['selectors'] if group else [], 1) if selector_state(m) == 'confirmat']
            confirmed.sort(key=lambda m: not m['same_project'])
            warnings = [f'Un candidat cu aceeași selecție a fost exclus înainte: „{e.get("nota_editor", "")}”. Citiți nota înainte să confirmați.'
                        for o, e in repeated_exclusions(candidate_items(snap['notes'])) if o is item]
            return {
                'id': cid, 'number': record['number'], 'origin': record['origin'], 'group_id': item.get('grup'), 'stare': stare,
                'nota_editor': member['nota_editor'],
                'group': None if group is None else {
                    'id': group['id'], 'label': group['label'], 'categorie': group.get('categorie'), 'definition': group['definition'],
                    'basis': group.get('baza_definitiei'), 'basis_label': BASIS_LABELS.get(group.get('baza_definitiei'), group.get('baza_definitiei')),
                    'ambiguities': group.get('ambiguitati', []), 'stare': group_state(group), 'decizie_editor': group.get('decizie_editor', ''),
                    'data_revizie': group.get('data_revizie', ''), 'members': len(group['selectors'])},
                'member': member, 'confirmed': confirmed, 'member_number': record['member'],
                'blockers': [blocker_text(*b) for b in candidate_blockers(item, groups)] if listed else [], 'warnings': warnings,
                'head': record['head'], 'hashes': {k: snap['hashes'][k] for k in ('concepte', 'note')},
            }

    # -- writing ---------------------------------------------------------------------------------------------------

    def _expected(self, request: dict, names: tuple[str, ...]) -> dict[Path, str]:
        hashes = request.get('hashes') if isinstance(request.get('hashes'), dict) else {}
        if any(not isinstance(hashes.get(n), str) for n in names):
            raise ReviewError('Cererea nu conține amprentele fișierelor încărcate de pagină.', 400, reload=True)
        return {self.paths[n]: hashes[n] for n in names}

    def decide_provider(self, item_id: str, request: dict) -> dict:
        with self.lock:
            expected = self._expected(request, ('revizuire', 'relatii'))
            snap = self.read()
            if any(digest(p.read_bytes()) != h for p, h in expected.items()):
                raise ReviewError(STALE, 409, reload=True)
            head = self.head()
            action = request.get('action')
            rev_rows, rel_rows, message = apply_provider(
                snap['rev_rows'], snap['rel_rows'], item_id, action, note=request.get('note', ''), name=request.get('name', ''),
                url=request.get('url', ''), other=request.get('duplicate_of', ''), today=self.today(), head_rev=head['rev'], head_rel=head['rel'])
            after = self.errors_of(snap['concepts'], rev_rows, rel_rows, notes=snap['notes'])
            self.refuse_new_errors(self.current_errors(snap), after)
            written = {'revizuire': dump_csv(snap['rev_header'], rev_rows), 'relatii': dump_csv(snap['rel_header'], rel_rows)}
            replace_atomically({self.paths[k]: v for k, v in written.items()}, expected)
            self.remember_errors(written, snap, after)
            return {'message': message, 'state': self.state(), 'item': self.provider(item_id)}

    def decide_group(self, gid: str, request: dict, member: int | None = None) -> dict:
        with self.lock:
            expected = self._expected(request, ('concepte',))
            snap = self.read()
            if any(digest(p.read_bytes()) != h for p, h in expected.items()):
                raise ReviewError(STALE, 409, reload=True)
            action = request.get('action')
            if member is None:
                ticked = request.get('ticked') if isinstance(request.get('ticked'), list) else []
                data, message = apply_group(snap['concepts'], gid, action, note=request.get('note', ''), ticked=ticked, today=self.today(),
                                            head_data=self.head()['concepts'])
            else:
                data, message = apply_member(snap['concepts'], gid, member, action, note=request.get('note', ''))
            after = self.errors_of(data, notes=snap['notes'])
            self.refuse_new_errors(self.current_errors(snap), after)
            written = {'concepte': dump_json(data, snap['raw']['concepte'])}
            replace_atomically({self.paths[k]: v for k, v in written.items()}, expected)
            self.remember_errors(written, snap, after)
            return {'message': message, 'state': self.state(), 'item': self.group(gid)}

    def decide_candidate(self, cid: str, request: dict) -> dict:
        """Confirm, exclude or reset one candidate. The dictionary and the notes are written together or not at all."""
        with self.lock:
            expected = self._expected(request, ('concepte', 'note'))
            snap = self.read()
            if any(digest(p.read_bytes()) != h for p, h in expected.items()):
                raise ReviewError(STALE, 409, reload=True)
            head = self.head()
            data, notes, message, key = apply_candidate(snap['concepts'], snap['notes'], cid, request.get('action'), note=request.get('note', ''),
                                                        head_data=head['concepts'], head_notes=head['notes'])
            after = self.errors_of(data, notes=notes)
            self.refuse_new_errors(self.current_errors(snap), after)
            written = {'concepte': dump_json(data, snap['raw']['concepte']), 'note': dump_json(notes, snap['raw']['note'])}
            replace_atomically({self.paths[k]: v for k, v in written.items()}, expected)
            self.remember_errors(written, snap, after)
            # The candidate may have a new place (a reset puts it back at HEAD) or none (a confirmation that no commit holds has nothing to show).
            now = next((r['id'] for r in self.candidate_records(self.read(), self.head()) if r['key'] == key), None)
            return {'message': message, 'state': self.state(), 'item': self.candidate(now) if now else None}

    # -- the check panel ---------------------------------------------------------------------------------------------

    def public_diff(self) -> dict:
        """Accepted providers per entry, HEAD against the working tree: what the public build would add or remove."""
        head = self.git.head_bytes(self.paths['relatii'])
        if head is None:
            return {'available': False, 'lines': []}
        accepted = lambda rows: {(r['subiect'], r['obiect_literal'] or r['obiect'], r['valoare_sursa'])
                                 for r in rows if r['predicat'] == 'date_din' and r['stare'] == 'acceptat'}
        before, after = accepted(parse_csv(head)[1]), accepted(self.read()['rel_rows'])
        lines = [{'sign': '-', 'slug': s, 'name': n, 'evidence': e} for s, n, e in sorted(before - after)]
        lines += [{'sign': '+', 'slug': s, 'name': n, 'evidence': e} for s, n, e in sorted(after - before)]
        return {'available': True, 'lines': sorted(lines, key=lambda x: (x['slug'], x['sign'], x['name']))}

    def git_panel(self) -> dict:
        with self.lock:
            paths = list(self.paths.values())
            relative = [self.git.rel(p) for p in paths] if self.git.available else [str(p) for p in paths]
            generated = ['docs/reports/inventory-expansion.md', 'data/taxonomy-v2/observatii/inventare/acoperire.csv']
            counts = Counter(c['stare'] for c in self.state()['candidates'])
            return {'available': self.git.available, 'files': self.git.status(paths) if self.git.available else [],
                    'candidates': {'open': counts['propus'], 'excluded': counts['exclus'], 'confirmed': counts['confirmat']},
                    'stat': self.git.diff_stat(paths), 'public': self.public_diff() if self.git.available else {'available': False, 'lines': []},
                    'commands': ['python3 scripts/inventory_report.py', 'python3 scripts/validate.py --publication',
                                 'python3 scripts/inventory.py --check', 'python3 scripts/build.py',
                                 'git add ' + ' '.join(relative + generated),
                                 'git commit -m "docs(review): record provider and group decisions"']}

    def run_checks(self) -> list[dict]:
        """The three checks of the brief in subprocesses, each with its exit code and the last lines of its output."""
        with self.lock:
            runs = [('validate.py --publication', ['validate.py', '--data-dir', str(self.root), '--publication']),
                    ('inventory.py --check', ['inventory.py', '--data-dir', str(self.root), '--check']),
                    ('inventory_report.py --check', ['inventory_report.py', '--data-dir', str(self.root), '--check'])]
            results = []
            for label, argv in runs:
                try:
                    done = subprocess.run([sys.executable, str(SCRIPTS / argv[0]), *argv[1:]], cwd=ROOT, capture_output=True, text=True, timeout=CHECK_TIMEOUT)
                    lines = (done.stdout + done.stderr).strip().splitlines()
                    results.append({'name': label, 'code': done.returncode, 'tail': lines[-12:]})
                except subprocess.TimeoutExpired:
                    results.append({'name': label, 'code': None, 'tail': [f'Timed out after {CHECK_TIMEOUT} s.']})
            return results


# ---------------------------------------------------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------------------------------------------------

PAGE_HEADERS = {
    'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; "
                               "form-action 'none'; frame-ancestors 'none'",
    'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store',
}


class Handler(BaseHTTPRequestHandler):
    server_version = 'review-ui'

    def log_message(self, fmt, *args):
        if getattr(self.server, 'verbose', False):
            sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))

    # -- plumbing ----------------------------------------------------------------------------------------------------

    def send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        for key, value in PAGE_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def send_json(self, status: int, payload):
        self.send(status, json.dumps(payload, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def fail(self, error: ReviewError):
        self.send_json(error.status, {'error': str(error), 'reload': error.reload})

    def allowed_host(self) -> bool:
        port = self.server.server_address[1]
        return (self.headers.get('Host') or '').lower() in (f'localhost:{port}', f'127.0.0.1:{port}')

    def guard(self, post: bool) -> bool:
        """403 for a foreign Host, a foreign Origin or (POST) a missing or wrong token. Nothing else runs before this."""
        port = self.server.server_address[1]
        origin = self.headers.get('Origin')
        refused = not self.allowed_host() or (origin is not None and origin not in (f'http://localhost:{port}', f'http://127.0.0.1:{port}'))
        if post and not refused:
            refused = not hmac.compare_digest((self.headers.get('X-Review-Token') or '').encode(), self.server.token.encode())
        if refused:
            self.send_json(403, {'error': 'Forbidden.'})
        return not refused

    def body(self) -> dict:
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            raise ReviewError('Bad Content-Length.')
        if length > MAX_BODY:
            raise ReviewError('The request is too large.', 413)
        if 'application/json' not in (self.headers.get('Content-Type') or ''):
            raise ReviewError('JSON is required.', 415)
        try:
            data = json.loads(self.rfile.read(length) or b'{}')
        except ValueError as exc:
            raise ReviewError(f'The request is not JSON: {exc}')
        if not isinstance(data, dict):
            raise ReviewError('A JSON object is required.')
        return data

    # -- routes ------------------------------------------------------------------------------------------------------

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.guard(post=False):
            return
        store, path = self.server.store, urlsplit(self.path).path
        try:
            if path in ('/', '/index.html'):
                page = (TEMPLATES / 'review_ui.html').read_text(encoding='utf-8').replace('{{TOKEN}}', self.server.token)
                for name in ASSETS:
                    page = page.replace(f'{name}?v=BUILD', f'{name}?v={digest((TEMPLATES / name).read_bytes())[:10]}')
                return self.send(200, page.encode('utf-8'), 'text/html; charset=utf-8')
            if path.startswith('/assets/') and path[8:] in ASSETS:
                return self.send(200, (TEMPLATES / path[8:]).read_bytes(), ASSETS[path[8:]])
            if path == '/api/state':
                return self.send_json(200, store.state())
            if path == '/api/git':
                return self.send_json(200, store.git_panel())
            found = re.fullmatch(r'/api/(provider|group|candidate)/([A-Za-z0-9-]+)', path)
            if found:
                return self.send_json(200, getattr(store, found.group(1))(found.group(2)))
            self.send_json(404, {'error': 'Not found.'})
        except ReviewError as error:
            self.fail(error)

    def do_POST(self):
        if not self.guard(post=True):
            return
        store, path = self.server.store, urlsplit(self.path).path
        try:
            request = self.body()
            if path == '/api/check':
                return self.send_json(200, {'checks': store.run_checks()})
            found = re.fullmatch(r'/api/provider/(D\d+)/decide', path)
            if found:
                return self.send_json(200, store.decide_provider(found.group(1), request))
            found = re.fullmatch(r'/api/group/([a-z0-9-]+)/decide', path)
            if found:
                return self.send_json(200, store.decide_group(found.group(1), request))
            found = re.fullmatch(r'/api/group/([a-z0-9-]+)/member/(\d+)', path)
            if found:
                return self.send_json(200, store.decide_group(found.group(1), request, member=int(found.group(2))))
            found = re.fullmatch(r'/api/candidate/(\d+-[0-9a-f]{12})/decide', path)
            if found:
                return self.send_json(200, store.decide_candidate(found.group(1), request))
            self.send_json(404, {'error': 'Not found.'})
        except ReviewError as error:
            self.fail(error)

    def do_PUT(self):
        self.send_json(405, {'error': 'Method not allowed.'})

    do_DELETE = do_PATCH = do_PUT


def make_server(store: Store, port: int = 0, verbose=False) -> ThreadingHTTPServer:
    """A server bound to 127.0.0.1 only. `port` 0 picks a free port; read it from `server.server_address[1]`."""
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.store, server.token, server.verbose = store, secrets.token_urlsafe(24), verbose
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8790, help='port on 127.0.0.1 (0 picks a free one)')
    parser.add_argument('--data-dir', type=Path, default=PUBLIC_ROOT, help='the taxonomy v2 data root (default: the public root)')
    parser.add_argument('--verbose', action='store_true', help='log each request')
    args = parser.parse_args(argv)
    store = Store(args.data_dir)
    try:
        server = make_server(store, args.port, args.verbose)
    except OSError as error:
        raise SystemExit(f'Cannot listen on 127.0.0.1:{args.port}: {error}')
    print(f'Review interface for {store.root}\nOpen http://127.0.0.1:{server.server_address[1]}/  (Ctrl+C stops it; it never commits)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
