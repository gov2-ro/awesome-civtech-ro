"""Bounded HTTP and document signals for site structure. No record harvesting."""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

from common import forbidden, forbidden_rows
from collect_docs import wire_url
from structure_state import StructureError, now, require

AGENT = 'CivTech-Structure/1.0'
MAX_BODY = 2 * 1024 * 1024
SECRET = re.compile(r'(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|secret|signature)')


def safe_url(url, preserve_fragment=False):
    parts = urlsplit(url)
    require(parts.scheme in {'http', 'https'} and bool(parts.hostname), 'Expected a public HTTP URL.')
    require(not parts.username and not parts.password, 'Credentials in URL are not supported.')
    require(not any(SECRET.fullmatch(k) for k, _ in parse_qsl(parts.query)), 'Credential query parameters are not supported.')
    return urlunsplit((parts.scheme, parts.netloc, parts.path or '/', parts.query, parts.fragment if preserve_fragment else ''))


def origin(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, '/', '', ''))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class RobotsPolicy:
    """Use the longest matching rule on Python 3.12 too; merge equally specific agent groups."""
    def __init__(self, text):
        self.groups, self.sitemaps = [], []
        group = {'agents': [], 'rules': []}
        for line in text.splitlines():
            name, separator, value = line.split('#', 1)[0].strip().partition(':')
            if not separator:
                continue
            name, value = name.strip().lower(), value.strip()
            if name == 'sitemap':
                self.sitemaps.append(value)
            elif name == 'user-agent':
                if group['rules']:
                    self.groups.append(group)
                    group = {'agents': [], 'rules': []}
                group['agents'].append(value.lower())
            elif name in {'allow', 'disallow'} and group['agents'] and value:
                group['rules'].append((value, name == 'allow'))
        if group['agents']:
            self.groups.append(group)

    @staticmethod
    def normalized(value):
        value = quote(value, safe="/%:@!$&'()*+,;=?~-._")
        def percent(match):
            char = chr(int(match.group()[1:], 16))
            return char if re.fullmatch(r'[A-Za-z0-9._~-]', char) else match.group().upper()
        return re.sub(r'%[0-9a-fA-F]{2}', percent, value)

    def site_maps(self):
        return self.sitemaps

    def can_fetch(self, agent, url):
        agent = agent.lower().split('/', 1)[0]
        selected, best = [], -1
        for group in self.groups:
            lengths = [0 if token == '*' else len(token) for token in group['agents'] if token == '*' or agent.startswith(token)]
            specificity = max(lengths, default=-1)
            if specificity > best:
                selected, best = [group], specificity
            elif specificity == best and specificity >= 0:
                selected.append(group)
        parts = urlsplit(url)
        target = self.normalized(parts.path + ('?' + parts.query if parts.query else ''))
        matches = []
        for group in selected:
            for path, allowed in group['rules']:
                anchor = path.endswith('$')
                path = self.normalized(path[:-1] if anchor else path)
                expression = '^' + '.*'.join(re.escape(part) for part in path.split('*')) + ('$' if anchor else '')
                if re.search(expression, target):
                    matches.append((len(path.replace('*', '')), allowed))
        return max(matches, default=(0, True))[1]


class Transport:
    def __init__(self, store, persist, total_budget=100, interval=1, opener=None, sleep=time.sleep, clock=time.monotonic):
        self.store, self.persist, self.total_budget = store, persist, total_budget
        self.interval, self.opener, self.sleep, self.clock = interval, opener or urllib.request.build_opener(NoRedirect()), sleep, clock
        self.used, self.last, self.robots, self.stopped = 0, {}, {}, set()
        self.attempt = None

    def event(self, url, sent, outcome, reason='', status=None, content_type='', size=0, truncated=False):
        row = dict(project=self.attempt['project'], attempt=self.attempt['id'], checked_at=now(), url=url,
                   method='GET', sent=sent, outcome=outcome, reason=reason, status=status,
                   content_type=content_type, bytes=size, truncated=truncated,
                   policy_hosts=[r['gazda'] for r in forbidden_rows()])
        self.store['requests'].append(row)
        self.persist()
        return row

    def fetch(self, url, robots=True):
        try:
            url = safe_url(url)
        except (StructureError, ValueError):
            # Never put the supplied credential value in a diagnostic or a log.
            return {'outcome': 'skipped', 'reason': 'invalid-or-credentialed-url', 'body': ''}
        for hop in range(6):
            host = urlsplit(url).hostname
            reason = 'colectare-interzisa' if forbidden(url) else 'host-stopped' if host in self.stopped else ''
            if not reason and (self.used >= self.total_budget or self.attempt['requests_used'] >= self.attempt['request_budget']):
                reason = 'budget-exhausted'
            if not reason and robots:
                base = origin(url)
                if base not in self.robots:
                    response = self.fetch(urljoin(base, 'robots.txt'), robots=False)
                    if response.get('status') in {404, 410}:
                        self.robots[base] = None
                    elif response['outcome'] == 'observed' and not response.get('truncated'):
                        self.robots[base] = RobotsPolicy(response['body'])
                    else:
                        self.robots[base] = False
                policy = self.robots[base]
                reason = 'robots-unavailable' if policy is False else 'robots-disallow' if policy and not policy.can_fetch(AGENT, url) else ''
                # Robots retrieval spent budget and may have stopped this host.
                if not reason and host in self.stopped:
                    reason = 'host-stopped'
                if not reason and (self.used >= self.total_budget or self.attempt['requests_used'] >= self.attempt['request_budget']):
                    reason = 'budget-exhausted'
            if reason:
                row = self.event(url, False, 'skipped', reason)
                return dict(row, body='')
            remaining = self.interval - (self.clock() - self.last.get(host, -1e9))
            if remaining > 0:
                self.sleep(remaining)
            self.last[host] = self.clock()
            self.used += 1
            self.attempt['requests_used'] += 1
            # Persist an unfinished dispatch before the network operation.
            row = self.event(url, True, 'error', 'dispatch-not-completed')
            location, body = None, ''
            try:
                try:
                    response = self.opener.open(urllib.request.Request(wire_url(url), headers={'User-Agent': AGENT}), timeout=20)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    raw = response.read(MAX_BODY + 1)
                    row.update(status=response.code, content_type=response.headers.get('Content-Type', '').split(';')[0],
                               bytes=min(len(raw), MAX_BODY), truncated=len(raw) > MAX_BODY, reason='',
                               body_sha256=hashlib.sha256(raw[:MAX_BODY]).hexdigest())
                    body = raw[:MAX_BODY].decode('utf-8-sig', 'replace')
                    location = response.headers.get('Location')
                status = row['status']
                row['outcome'] = ('blocked' if status in {401, 403, 429} else 'redirect' if status in {301, 302, 303, 307, 308}
                                  else 'observed' if 200 <= status < 300 else 'not_found' if status in {404, 410} else 'error')
                if re.search(r'(?i)vercel security checkpoint|cf-chl-|<title>[^<]*(?:captcha|just a moment)', body[:12000]):
                    row.update(outcome='blocked', reason='challenge')
                if row['outcome'] == 'blocked':
                    self.stopped.add(host)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                row.update(outcome='error', reason=type(exc).__name__)
            self.persist()
            if row['outcome'] != 'redirect':
                return dict(row, body=body)
            if not location or hop == 5:
                return dict(row, outcome='error', reason='redirect-limit-or-missing-location', body='')
            try:
                url = safe_url(urljoin(url, location))
                if not robots and urlsplit(url).path != '/robots.txt':
                    return dict(row, outcome='skipped', reason='robots-redirect-not-supported', body='')
            except (StructureError, ValueError):
                return dict(row, outcome='skipped', reason='invalid-redirect', body='')
        raise AssertionError('unreachable')


class StructureHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.forms, self.base = [], [], None
        self.form, self.hidden = None, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {'script', 'style'}:
            self.hidden += 1
        if tag == 'base' and not self.base:
            self.base = a.get('href')
        if tag in {'a', 'link'} and a.get('href'):
            self.links.append(a['href'])
        if tag == 'form':
            self.form = {'action': a.get('action', ''), 'method': a.get('method', 'get').upper(), 'inputs': []}
            self.forms.append(self.form)
        if tag in {'input', 'select'} and self.form is not None and a.get('name') and not SECRET.fullmatch(a['name']):
            if a.get('type', '').lower() not in {'hidden', 'password', 'submit', 'button'}:
                self.form['inputs'].append(a['name'])

    def handle_endtag(self, tag):
        if tag == 'form':
            self.form = None
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden - 1)


def resolve_parameters(document, parameters):
    """Resolve bounded local parameter references; cycles and external references stay unresolved."""
    resolved, incomplete = [], False
    for parameter in parameters:
        seen = set()
        original = parameter.get('$ref') if isinstance(parameter,dict) else None
        while isinstance(parameter,dict) and '$ref' in parameter:
            reference = parameter['$ref']
            if not isinstance(reference,str) or not reference.startswith('#/') or reference in seen or len(seen)>=16:
                parameter = None
                break
            seen.add(reference)
            value = document
            try:
                for token in reference[2:].split('/'):
                    value=value[token.replace('~1','/').replace('~0','~')]
            except (KeyError,TypeError):
                value=None
            parameter=value
        if not isinstance(parameter,dict) or not parameter.get('name') or not parameter.get('in'):
            incomplete=True
            continue
        item={k:parameter[k] for k in ('name','in','required') if k in parameter}
        if original: item['source_ref']=original
        if isinstance(parameter.get('schema'),dict) and parameter['schema'].get('type'):
            item['type']=parameter['schema']['type']
        resolved.append(item)
    return resolved,incomplete


def signals(text, content_type, url, sitemap_limit=200):
    """Return only structural signals. Do not retain raw data records or page text."""
    result = dict(links=[], templates=[], forms=[], operations=[], sitemap_urls=[], sitemap_children=[])
    html = 'xml' not in content_type and ('html' in content_type or bool(re.search(r'<(?:html|!doctype\s+html)', text[:500], re.I)))
    base = url
    if html:
        parser = StructureHTML()
        parser.feed(text)
        base = urljoin(url, parser.base) if parser.base else url
        result['links'] = parser.links
        result['forms'] = parser.forms
    elif 'xml' in content_type or text.lstrip().startswith('<?xml'):
        require(not re.search(r'<!DOCTYPE|<!ENTITY', text, re.I), 'XML entity declarations are not supported.')
        tree = ET.fromstring(text)
        values = [e.text.strip() for e in tree.iter() if e.tag.rsplit('}', 1)[-1] == 'loc' and e.text]
        result['sitemap_children' if tree.tag.endswith('sitemapindex') else 'sitemap_urls'] = values[:sitemap_limit]
    else:
        # Explicit URLs from llms/Markdown; replace documented angle placeholders, not arbitrary HTML.
        text = re.sub(r'<(CUI|cui|siruta|id)>', r'{\1}', text)
        result['links'] = re.findall(r'https?://[^\s\)\]"<>]+', text)
        result['links'] += re.findall(r'\]\((/[^\s)]+)\)', text)
        result['templates'] = re.findall(r'(?<!\w)(/[^\s<>"\[\]]*\{[A-Za-z_][A-Za-z_0-9]*\}[^\s<>"\[\]]*)', text)
    document = None
    if text.lstrip().startswith('{'):
        document = json.loads(text)
    elif re.match(r'\s*openapi\s*:', text):
        from inventory_yaml import load
        document, _ = load(text)
    if isinstance(document, dict) and ('openapi' in document or 'swagger' in document):
        servers = document.get('servers') or [{'url': origin(url)}]
        api_base = urljoin(url, servers[0]['url'])
        for path, methods in document.get('paths', {}).items():
            if not isinstance(methods, dict):
                continue
            for method, operation in methods.items():
                if method not in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'} or not isinstance(operation, dict):
                    continue
                security = operation.get('security', document.get('security'))
                declared = 'unspecified' if security is None else 'anonymous' if not security or {} in security else 'authenticated'
                parameters = methods.get('parameters', []) + operation.get('parameters', [])
                parameters, unresolved = resolve_parameters(document, parameters)
                result['operations'].append(dict(method=method.upper(), url_template=urljoin(api_base.rstrip('/')+'/', path.lstrip('/')),
                    operation_id=operation.get('operationId'), parameters=parameters,
                    unresolved_parameters=unresolved,
                    security=dict(declared_requirement=declared, schemes=sorted({k for requirement in security or [] for k in requirement}), observed_enforcement='unknown'),
                    purpose='unknown', response_paths={}, pagination={'mechanism':'unknown'}, request_body={},
                    source_pointer='/paths/'+path.replace('~','~0').replace('/','~1')+'/'+method))
    for name in ('links', 'templates', 'sitemap_urls', 'sitemap_children'):
        cleaned = []
        for candidate in result[name]:
            try:
                value = safe_url(urljoin(base, candidate.rstrip('.,;:`')), preserve_fragment='{' in candidate)
                if value not in cleaned:
                    cleaned.append(value)
            except (StructureError, ValueError):
                pass
        result[name] = cleaned[:200]
    return result


def inferred_patterns(urls):
    """Infer path shape only. An integer does not establish a fiscal identifier."""
    groups = {}
    for url in urls:
        p = urlsplit(url)
        segments = p.path.split('/')
        if not segments[-1] or '.' in segments[-1]:
            continue
        if re.fullmatch(r'\d+', segments[-1]):
            segments[-1] = '{id}'
        else:
            continue
        template = urlunsplit((p.scheme, p.netloc, '/'.join(segments), '', ''))
        groups.setdefault(template, []).append(url)
    return [(template, list(dict.fromkeys(examples))[:3]) for template, examples in groups.items() if len(set(examples)) >= 2]
