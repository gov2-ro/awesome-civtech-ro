"""Collect first-party documentation for project-data inventories. Stdlib only.

    python3 scripts/collect_docs.py --only afacut,ins-gov2,ani-de-pensie
    python3 scripts/collect_docs.py             # all entries; reuse collected entry records
    python3 scripts/collect_docs.py --force     # refresh the selected entries

The collector follows methodology/about links and checks llms.txt. It saves evidence, not classifications.
It never changes the catalogue, profile, labels, or public site. Requests use no paid API or credentials.
HTML is read without JavaScript. Missing pages, blocked requests and thin text remain explicit gaps.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from common import PUBLIC_ROOT, load_catalogue, observation_paths

MAX_BYTES = 2_000_000
MAX_TEXT = 60_000
UA = 'Mozilla/5.0 (compatible; CivTech-documentation/1.0; +https://civtech.gov2.ro/)'
IGNORE = {'script', 'style', 'noscript', 'svg', 'template'}
BREAKS = {'p', 'div', 'section', 'article', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'br'}
PATTERNS = {
    'metodologie': r'\b(metod\w*|method\w*|surse|sources|provenance|data dictionary|dictionar\w*)\b',
    'despre': r'\b(despre|about|cum functioneaza|how it works|documentatie|documentation|readme)\b',
    'llms': r'\bllms(?:-full)?\.txt\b',
}


def flat(value):
    return unicodedata.normalize('NFKD', value.casefold()).encode('ascii', 'ignore').decode()


def canonical(url):
    try:
        url = urldefrag(url)[0]
        parsed = urlsplit(url)
    except ValueError:
        return ''
    if parsed.scheme not in ('https', 'http') or not parsed.hostname:
        return ''
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', parsed.query, ''))


def kind_of(url, text=''):
    path = urlsplit(url).path
    if re.search(PATTERNS['llms'], flat(path + ' ' + text)):
        return 'llms'
    value = flat(path.replace('-', ' ') + ' ' + text)
    # Keep llms first: the text may also mention methodology.
    for kind in ('llms', 'metodologie', 'despre'):
        if re.search(PATTERNS[kind], value):
            return kind
    return ''


def inline_sections(parser, url):
    sections = []
    for href, label in parser.links:
        if not href:
            continue
        if urlsplit(urljoin(url, href)).fragment and canonical(urljoin(url, href)) == canonical(url) and (kind := kind_of('https://example.org/', label)):
            sections.append({'kind': kind, 'heading': label, 'url': urljoin(url, href)})
    for heading in parser.headings:
        value = flat(heading)
        if re.match(r'^(metod\w*|method\w*|surse|sources|despre (noi|proiect|platforma)|about|cum functioneaza|how it works)\b', value):
            if kind := kind_of('https://example.org/', heading):
                sections.append({'kind': kind, 'heading': heading, 'url': url})
    return sections


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.headings, self.inputs, self.tables = [], [], [], [], []
        self.hidden = 0
        self.anchor = None
        self.heading = None
        self.row = None
        self.cell = None
        self.title_parts = []
        self.in_title = False
        self.base = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in IGNORE:
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'base' and not self.base:
            self.base = attrs.get('href', '')
        if tag == 'title':
            self.in_title = True
        if tag in BREAKS:
            self.parts.append('\n')
        if tag == 'a':
            self.anchor = {'href': attrs.get('href', ''), 'parts': []}
        if re.fullmatch(r'h[1-6]', tag):
            self.heading = []
        if tag == 'tr':
            self.row = []
        if tag in ('th', 'td'):
            self.cell = []
        if tag in ('input', 'select', 'textarea') and attrs.get('type', '').lower() not in ('hidden', 'submit', 'button', 'password'):
            self.inputs.append({k: attrs[k] for k in ('name', 'id', 'type', 'aria-label', 'placeholder', 'min', 'max', 'step') if attrs.get(k)})

    def handle_endtag(self, tag):
        if tag in IGNORE:
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag == 'title':
            self.in_title = False
        if tag == 'a' and self.anchor:
            self.links.append((self.anchor['href'], ' '.join(self.anchor['parts'])))
            self.anchor = None
        if re.fullmatch(r'h[1-6]', tag) and self.heading is not None:
            self.headings.append(' '.join(self.heading))
            self.heading = None
        if tag in ('th', 'td') and self.cell is not None:
            if self.row is not None:
                self.row.append(' '.join(self.cell))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            if self.row:
                self.tables.append(self.row)
            self.row = None
        if tag in BREAKS:
            self.parts.append('\n')

    def handle_data(self, value):
        if self.hidden:
            return
        value = ' '.join(value.split())
        if not value:
            return
        self.parts.append(value + ' ')
        if self.in_title:
            self.title_parts.append(value)
        if self.anchor is not None:
            self.anchor['parts'].append(value)
        if self.heading is not None:
            self.heading.append(value)
        if self.cell is not None:
            self.cell.append(value)

    @property
    def text(self):
        return '\n'.join(line.strip() for line in ''.join(self.parts).splitlines() if line.strip())


def parse_page(body, content_type, url, kind):
    html = 'html' in content_type.lower() or bool(re.search(r'<(?:!doctype\s+html|html|head|body)(?:\s|>)', body[:500], re.I))
    if kind == 'llms' and html:
        return {'state': 'html-in-loc-de-llms', 'text': '', 'links': []}
    if not html and not (content_type.startswith('text/') or content_type in ('application/json', 'application/ld+json')):
        return {'state': 'format-neacceptat', 'text': '', 'links': []}
    parser = PageParser()
    if html:
        parser.feed(body)
        text = parser.text
        base = urljoin(url, parser.base) if parser.base else url
        links = [(canonical(urljoin(base, href)), label) for href, label in parser.links if href]
    else:
        text = body.strip()
        links = [(canonical(urljoin(url, href)), label) for label, href in re.findall(r'\[([^\]]+)\]\(([^\s)]+)\)', text)]
    return {'state': 'colectat' if len(text) >= 100 else 'text-insuficient', 'text': text[:MAX_TEXT],
            'truncated': len(text) > MAX_TEXT, 'title': ' '.join(parser.title_parts), 'links': links,
            'sections': inline_sections(parser, url),
            'headings': parser.headings[:150], 'input_candidates': parser.inputs[:80], 'table_candidates': parser.tables[:100]}


def scope_of(project_url, url):
    project, target = urlsplit(project_url), urlsplit(url)
    if project.hostname != target.hostname:
        return 'alta-gazda'
    prefix = project.path.rstrip('/') + '/'
    if project.path in ('', '/') or target.path == project.path or target.path.startswith(prefix):
        return 'proiect'
    return 'gazda-comuna'


BINARY_MAGIC = (b'PK\x03\x04', b'%PDF', b'\xd0\xcf\x11\xe0', b'\x1f\x8b')


def is_binary(raw, content_type=''):
    """Detect a binary body before decoding it as text. A spreadsheet, a PDF or a gzip file is not text."""
    return raw.startswith(BINARY_MAGIC) or b'\x00' in raw[:2000] or content_type in (
        'application/pdf', 'application/zip',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel')


class Fetcher:
    """GET with a timeout, a size cap, two concurrent requests per host and an optional hard request budget.
    `log` is a RequestLog; every direct request is logged with its outcome and size. Nothing is retried."""

    def __init__(self, timeout=8, max_requests=None, log=None, purpose=''):
        self.timeout = timeout
        self.max_requests, self.log, self.purpose = max_requests, log, purpose
        self.cache, self.locks, self.hosts = {}, {}, {}
        self.guard = threading.Lock()
        self.requests = 0

    def __call__(self, url, sample=None):
        """Fetch a URL. With `sample` (bytes) the request asks for a byte range and reads no more than that:
        a bounded sample of a large file. A sample body ends at its last complete line and carries `partial: true`."""
        key = (url, sample)
        with self.guard:
            lock = self.locks.setdefault(key, threading.Lock())
            host = self.hosts.setdefault(urlsplit(url).hostname, threading.Semaphore(2))
        with lock:
            if key in self.cache:
                if self.log:
                    self.log.add('GET', url, self.cache[key]['state'], self.cache[key].get('http_status'), None, True, self.purpose)
                return self.cache[key]
            result = {'url': url, 'final_url': url, 'http_status': None, 'fetched_at': datetime.now(timezone.utc).isoformat()}
            with self.guard:
                if self.max_requests is not None and self.requests >= self.max_requests:
                    return {**result, 'state': 'limita-cereri', 'error': 'request budget reached'}
                self.requests += 1
            size = None
            headers = {'User-Agent': UA, 'Accept-Language': 'ro,en;q=0.8'}
            if sample:
                headers['Range'] = f'bytes=0-{sample - 1}'
            try:
                with host, urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                    raw = response.read((sample or MAX_BYTES) + 1)
                    size = len(raw)
                    result.update(http_status=response.status, final_url=response.url,
                                  content_type=response.headers.get_content_type())
                    if sample and len(raw) > sample:
                        raw = raw[:sample]
                        result['partial'] = True
                    elif sample and response.status == 206:
                        # The server honoured the range. The body is complete only when the range covers the whole file.
                        covered = re.match(r'bytes \d+-(\d+)/(\d+)$', response.headers.get('Content-Range', ''))
                        result['partial'] = not (covered and int(covered.group(2)) <= int(covered.group(1)) + 1)
                    if len(raw) > MAX_BYTES:
                        result.update(state='raspuns-prea-mare', body='')
                    elif is_binary(raw, result['content_type']):
                        result.update(state='format-binar', body='')
                    else:
                        charset = response.headers.get_content_charset() or 'utf-8'
                        text = raw.decode(charset, errors='replace')
                        if result.get('partial'):
                            text = text[:text.rfind('\n') + 1] if '\n' in text else text
                        result.update(state='ok', body=text)
            except HTTPError as exc:
                result.update(state='eroare-http', http_status=exc.code, error=str(exc))
            except (URLError, OSError, ValueError, LookupError, HTTPException) as exc:
                result.update(state='eroare-retea', error=str(exc))
            self.cache[key] = result
            if self.log:
                self.log.add('GET', url, result['state'], result.get('http_status'), size, False, self.purpose)
            return result


def collect(entry, fetch, max_pages=5, follow_data_links=False):
    start = canonical(entry['url'])
    if not start:
        return {'slug': entry['slug'], 'url': entry['url'], 'state': 'fara-url-http', 'pages': []}
    parsed = urlsplit(start)
    # A path identifies a project on a shared host. Check its llms file before the host-wide one.
    directory = start if parsed.path.endswith('/') else (start + '/' if not Path(parsed.path).suffix else urljoin(start, './'))
    scoped_llms = canonical(urljoin(directory, 'llms.txt'))
    root_llms = canonical(urljoin(start, '/llms.txt'))
    queue = [(start, 'pagina'), (scoped_llms, 'llms')]
    if root_llms != scoped_llms:
        queue.append((root_llms, 'llms'))
    seen, pages = set(), []
    home_text = None
    while queue and len(pages) < max_pages:
        url, kind = queue.pop(0)
        if not url or url in seen:
            continue
        seen.add(url)
        response = fetch(url)
        page = {k: v for k, v in response.items() if k != 'body'}
        page.update(kind=kind, scope=scope_of(start, response.get('final_url', url)))
        if response['state'] == 'ok':
            page.update(parse_page(response['body'], response.get('content_type', ''), response['final_url'], kind))
            if url == start:
                home_text = page.get('text')
            elif page.get('text') and page['text'] == home_text:
                page['state'] = 'copie-pagina-initiala'
            text = page.get('text', '')
            page['sha256'] = hashlib.sha256(text.encode()).hexdigest()
            # A shared host index may name other projects. Preserve its links, but do not crawl them as this project.
            if page['state'] == 'colectat' and page['scope'] == 'proiect':
                for target, label in page['links']:
                    candidate = kind_of(target, label) if target else ''
                    if not candidate and follow_data_links and target and not re.search(r'\.(json|csv|xlsx|pdf)(?:$|\?)', target, re.I):
                        if re.search(r'\b(editia|edition|datasets|descarca|download|datele tabelare)\b', flat(label)):
                            candidate = 'pagina-date'
                    if candidate and scope_of(start, target) == 'proiect' and target not in seen:
                        queue.append((target, candidate))
        pages.append(page)
        if not queue and len(pages) < max_pages:
            for path, kind in [('metodologie/', 'metodologie'), ('despre/', 'despre')]:
                if not any((p['kind'] == kind or any(s['kind'] == kind for s in p.get('sections', []))) and p['state'] == 'colectat' for p in pages):
                    target = canonical(urljoin(directory, path))
                    if target not in seen:
                        queue.append((target, kind))
    return {'slug': entry['slug'], 'url': start, 'state': documentation_state(pages),
            'inventory_completeness': 'neanalizat', 'pages': pages}


def documentation_state(pages):
    documentation = [p for p in pages if p['state'] == 'colectat' and (p['kind'] != 'pagina' or p.get('sections')) and p['scope'] == 'proiect']
    return 'documentatie-gasita' if documentation else 'documentatie-neconfirmata'


def merge_refresh(old, new):
    """Keep the pages that an earlier run collected and this run could not collect again.

    A page that fails (HTTP error, timeout, thin text) or that the new run never requested stays, with the failed
    attempt in `ultima_incercare`. A page collected again replaces its earlier copy. A changed project URL starts over."""
    if not old or old.get('url') != new.get('url') or new.get('state') == 'fara-url-http':
        return new
    fresh = {p['url']: p for p in new['pages']}
    old_pages = {p['url']: p for p in old['pages']}
    pages = []
    for page in new['pages']:
        earlier = old_pages.get(page['url'])
        if earlier and earlier['state'] == 'colectat' and page['state'] != 'colectat':
            attempt = {k: page.get(k) for k in ('fetched_at', 'state', 'http_status', 'error') if page.get(k) is not None}
            page = {**earlier, 'ultima_incercare': attempt}
        pages.append(page)
    pages += [p for url, p in old_pages.items() if url not in fresh and p['state'] == 'colectat']
    state = new['state'] if new.get('state') == 'eroare-colectare' else documentation_state(pages)
    return {**new, 'state': state, 'pages': pages}


def save(records, out):
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / 'pagini'
    raw_dir.mkdir(exist_ok=True)
    index = []
    for record in sorted(records.values(), key=lambda r: r['slug']):
        item = {k: v for k, v in record.items() if k != 'pages'}
        item['pages'] = []
        for page in record['pages']:
            metadata = {k: v for k, v in page.items() if k not in ('text', 'links', 'headings', 'input_candidates', 'table_candidates')}
            if 'text' in page:
                key = hashlib.sha256((page['url'] + '\n' + page.get('sha256', '')).encode()).hexdigest()[:24]
                path = raw_dir / (key + '.json')
                # The snapshot holds what was collected. Index-only keys stay out, so a restored page rewrites the same bytes.
                body = {k: v for k, v in page.items() if k not in ('snapshot', 'text_chars', 'ultima_incercare')}
                path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
                metadata['snapshot'] = str(path.relative_to(out))
                metadata['text_chars'] = len(page['text'])
            item['pages'].append(metadata)
        index.append(item)
    path = out / 'index.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'version': 1, 'entries': index}, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)
    with (out / 'rezumat.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['slug', 'url', 'stare_colectare', 'pagini_colectate', 'metodologie', 'despre', 'llms', 'completitudine_inventar'])
        for record in index:
            links = lambda kind: '|'.join(p['final_url'] for p in record['pages'] if (p['kind'] == kind or any(s['kind'] == kind for s in p.get('sections', []))) and p['state'] == 'colectat' and p['scope'] == 'proiect')
            writer.writerow([record['slug'], record['url'], record['state'], sum(p['state'] == 'colectat' for p in record['pages']),
                             links('metodologie'), links('despre'), links('llms'), record['inventory_completeness']])


def restore(out):
    path = out / 'index.json'
    if not path.exists():
        return {}
    records = {}
    for entry in json.loads(path.read_text())['entries']:
        for page in entry['pages']:
            if page.get('snapshot'):
                snapshot = out / page['snapshot']
                if snapshot.exists():
                    body = json.loads(snapshot.read_text())
                    for key in ('text', 'links', 'headings', 'input_candidates', 'table_candidates', 'sections'):
                        if key in body:
                            page[key] = body[key]
        records[entry['slug']] = entry
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=PUBLIC_ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--only', default='')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--follow-data-links', action='store_true', help='also follow explicit edition/download/data-page links')
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--max-pages', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=8)
    args = parser.parse_args()
    if args.workers < 1 or args.max_pages < 2 or args.timeout <= 0:
        parser.error('Use positive workers/timeout and at least two pages.')
    out = args.out or observation_paths(args.data_dir)['profile'].parent / 'documentare'
    entries = load_catalogue(args.data_dir)
    selected = set(filter(None, args.only.split(',')))
    if selected - {r['slug'] for r in entries}:
        parser.error('Unknown slug: ' + ', '.join(sorted(selected - {r['slug'] for r in entries})))
    records = restore(out)
    todo = [r for r in entries if (not selected or r['slug'] in selected) and
            (args.force or r['slug'] not in records or canonical(r['url']) != records[r['slug']]['url'])]
    fetcher = Fetcher(args.timeout)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(collect, entry, fetcher, args.max_pages, args.follow_data_links): entry['slug'] for entry in todo}
        for future in as_completed(futures):
            try:
                record = future.result()
            except Exception as exc:
                slug = futures[future]
                record = {'slug': slug, 'url': next(e['url'] for e in todo if e['slug'] == slug),
                          'state': 'eroare-colectare', 'error': f'{type(exc).__name__}: {exc}',
                          'inventory_completeness': 'neanalizat', 'pages': []}
            records[record['slug']] = merge_refresh(records.get(record['slug']), record)
            save(records, out)
            found = [p['kind'] for p in record['pages'] if p['state'] == 'colectat']
            print(record['slug'] + ': ' + record['state'] + ' · ' + ', '.join(found), flush=True)
    print(f'{len(todo)} entries processed; {fetcher.requests} requests; index: {out / "index.json"}')
    return int(any(records[e['slug']]['state'] == 'eroare-colectare' for e in todo))


if __name__ == '__main__':
    raise SystemExit(main())
