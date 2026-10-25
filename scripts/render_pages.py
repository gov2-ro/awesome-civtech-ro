# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48"]
# ///
"""Render one public page in a headless browser and record the data requests it makes. Optional helper.

    uv run scripts/render_pages.py https://example.org/edition/ --slug afacut --lot C
    uv run scripts/render_pages.py URL --out-dir /tmp/renders --wait-ms 4000

The collector in collect_docs.py reads static HTML. A page that fills itself with JavaScript hides its data behind requests.
This helper opens the page once, waits for the network to settle, and writes what it saw to `randare/<slug>-<hash>.json`:
the rendered text, the visible controls, and the fetch/XHR requests to the same site (or to hosts named with --allow-host).

It does not click, type, submit a form, sign in or run any project action. It keeps no cookies between pages and records no request
headers. Query values that look like credentials are redacted. Third-party and static-asset traffic is dropped, never stored.
A navigation and its requests go to the request log as browser rows (cache = `browser`), apart from the direct HTTP budget.
The bodies of up to six JSON or CSV data responses (200 000 bytes each) are stored in the source cache, because the page itself
received them. A server may answer the same address with an error to a plain request (a 403 for a client without the page's context).
The helper never works around that answer; the browser copy is the evidence, and its record says `via: browser`.
Needs Playwright's Chromium: `uv run --with playwright playwright install chromium`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from common import PUBLIC_ROOT, observation_paths
from inventory_state import RequestLog, dump, protect, source_id, write_file_atomic

DATA_TYPES = ('fetch', 'xhr', 'eventsource', 'websocket')
BODY_TYPES = ('application/json', 'text/csv', 'application/geo+json', 'text/plain')
MAX_BODY = 200_000
MAX_BODIES = 6
SECRET_KEYS = re.compile(r'(key|token|secret|auth|password|session|signature|sig|code)$', re.I)
MAX_TEXT = 20_000


def redact(url):
    """Replace the value of a query parameter that looks like a credential. The parameter name stays."""
    parts = urlsplit(url)
    query = [(k, 'REDACTED' if SECRET_KEYS.search(k) else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))


def same_site(host, page_host, allowed=()):
    strip = lambda h: (h or '').removeprefix('www.')
    host, page_host = strip(host), strip(page_host)
    return host == page_host or host.endswith('.' + page_host) or page_host.endswith('.' + host) or host in {strip(a) for a in allowed}


def keep_request(event, page_host, allowed=()):
    """Keep data requests of the page's own site. Drop assets, analytics and other third-party traffic."""
    host = urlsplit(event['url']).hostname
    return event['resource_type'] in DATA_TYPES and same_site(host, page_host, allowed)


def summarise(events, page_host, allowed=()):
    """Reduce raw browser events to a deduplicated, ordered list of data requests."""
    seen, kept = set(), []
    for event in events:
        if not keep_request(event, page_host, allowed):
            continue
        key = (event['method'], redact(event['url']))
        if key in seen:
            continue
        seen.add(key)
        kept.append({'metoda': event['method'], 'url': redact(event['url']), 'tip_resursa': event['resource_type'],
                     'http_status': event.get('status'), 'content_type': event.get('content_type'), 'octeti': event.get('size')})
    return kept


def render(urls, args):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright
    obs = observation_paths(args.data_dir)['profile'].parent
    out_dir = args.out_dir or obs / 'inventare' / 'randare'
    out_dir.mkdir(parents=True, exist_ok=True)
    log = RequestLog(obs / 'inventare' / 'jurnal-cereri.csv', args.lot) if args.lot else None
    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url in urls:
            context = browser.new_context(java_script_enabled=True, accept_downloads=False, ignore_https_errors=False)
            page = context.new_page()
            events = []

            bodies, omitted = {}, []

            def on_response(response):
                request = response.request
                try:
                    size = int(response.headers.get('content-length', '')) if response.headers.get('content-length') else None
                except ValueError:
                    size = None
                content_type = (response.headers.get('content-type') or '').split(';')[0]
                events.append({'url': request.url, 'method': request.method, 'resource_type': request.resource_type,
                               'status': response.status, 'content_type': content_type, 'size': size})
                if request.resource_type in ('fetch', 'xhr') and request.method == 'GET' and response.status == 200 and content_type in BODY_TYPES:
                    try:
                        raw = response.body()
                        if len(raw) <= MAX_BODY:
                            bodies[request.url] = (content_type, raw.decode('utf-8'))
                        else:
                            omitted.append({'url': redact(request.url), 'motiv': f'body of {len(raw)} bytes is over the {MAX_BODY} limit'})
                    except Exception as exc:  # an aborted or redirected response has no body to keep; say why
                        omitted.append({'url': redact(request.url), 'motiv': f'{type(exc).__name__}: {str(exc)[:120]}'})

            page.on('response', on_response)
            state, title, text, controls = 'ok', '', '', []
            try:
                response = page.goto(url, wait_until='networkidle', timeout=args.timeout_ms)
                status = response.status if response else None
                page.wait_for_timeout(args.wait_ms)
                title = page.title()
                text = page.inner_text('body')[:MAX_TEXT]
                controls = page.evaluate("""() => [...document.querySelectorAll('input,select,textarea')].filter(e => !['hidden','submit','button','password'].includes((e.type || '').toLowerCase()))
                    .slice(0, 80).map(e => ({tag: e.tagName.toLowerCase(), name: e.name || null, id: e.id || null, type: e.type || null,
                    label: e.getAttribute('aria-label') || e.placeholder || null, options: e.tagName === 'SELECT' ? [...e.options].slice(0, 12).map(o => o.textContent.trim()) : undefined}))""")
            except PlaywrightTimeout:
                state, status = 'timeout', None
            except Exception as exc:  # a navigation failure is a recorded outcome, not a crash
                state, status = 'eroare-browser', None
                title = f'{type(exc).__name__}: {str(exc)[:200]}'
            final_url = page.url
            host = urlsplit(final_url or url).hostname
            requests = summarise(events, host, args.allow_host)
            kept = {item['url'] for item in requests}
            saved = []
            for item_url, (content_type, text) in list(bodies.items())[:MAX_BODIES]:
                if redact(item_url) in kept:
                    response = protect({'url': item_url, 'final_url': item_url, 'http_status': 200, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                                        'content_type': content_type, 'state': 'ok', 'body': text, 'via': 'browser'})
                    cache = obs / 'inventare' / 'surse'
                    cache.mkdir(parents=True, exist_ok=True)
                    write_file_atomic(cache / (source_id(item_url) + '.json'), dump(response))
                    saved.append(item_url)
            context.close()
            record = {'versiune': 1, 'proiect': args.slug, 'url_cerut': url, 'url_final': final_url, 'stare': state, 'http_status': status,
                      'titlu': title, 'randat_la': datetime.now(timezone.utc).isoformat(), 'text_randat': text,
                      'controale_vizibile': controls, 'cereri_date': requests, 'corpuri_pastrate': [redact(u) for u in saved], 'corpuri_omise': omitted,
                      'nota': 'No click, no typing, no form submission. Requests are the same-site fetch/XHR traffic during load only.'}
            name = f'{args.slug or "pagina"}-{hashlib.sha256(url.encode()).hexdigest()[:10]}.json'
            (out_dir / name).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            written.append(out_dir / name)
            if log:
                log.add('BROWSER', redact(url), state, status, None, 'browser', f'randare {args.slug}')
                for item in requests:
                    log.add('BROWSER-' + item['metoda'], item['url'], str(item['http_status']), item['http_status'], item['octeti'], 'browser', f'randare {args.slug}')
            print(f'{state} {status} {url}: {len(requests)} data requests, {len(text)} text characters')
            for item in requests:
                print('   ', item['metoda'], item['http_status'], item['content_type'], item['url'])
        browser.close()
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('urls', nargs='+')
    parser.add_argument('--slug', default='', help='catalogue slug the page belongs to')
    parser.add_argument('--lot', default='', help='request-log batch name')
    parser.add_argument('--data-dir', type=Path, default=PUBLIC_ROOT)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--wait-ms', type=int, default=2500, help='extra wait after the network settles')
    parser.add_argument('--timeout-ms', type=int, default=25000)
    parser.add_argument('--allow-host', action='append', default=[], help='extra host whose data requests may be kept')
    args = parser.parse_args()
    if len(args.urls) > 2:
        parser.error('At most two pages per entry.')
    render(args.urls, args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
