'use strict';

const $ = (s, el = document) => el.querySelector(s);
const slot = name => $(`[data-slot="${name}"]`);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const plural = (n, one, many) => n === 1 ? `1 ${one}` : `${n}${n % 100 >= 20 || n % 100 === 0 ? ' de' : ''} ${many}`;
const hue = s => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % 360;
const initials = name => {
  const w = name.replace(/\.(ro|eu|org|com|info|ai|help)$/i, '').split(/[\s\-–—·.:]+/).filter(x => /^[\p{L}\d]/u.test(x));
  return (w.length > 1 ? w[0][0] + w[1][0] : (w[0] || '?').slice(0, 2)).toUpperCase();
};
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const ICON = {
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  out: '<svg viewBox="0 0 24 24"><path d="M7 17 17 7M8 7h9v9"/></svg>',
  code: '<svg viewBox="0 0 24 24"><path d="m8 7-5 5 5 5M16 7l5 5-5 5"/></svg>',
  grid: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg>',
  list: '<svg viewBox="0 0 24 24"><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/></svg>',
  archive: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10h14V9M10 13h4"/></svg>',
};

// Logos of the networks a link can point to, as SVG paths in a 24 × 24 box. From Simple Icons 16.35.0 (CC0), inline so the
// page loads nothing from a third party. Keys are the link roles of data/taxonomy.json; keep in step with NETWORK_ROLES in scripts/common.py.
const NETWORK = {
  facebook: 'M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z',
  instagram: 'M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077',
  linkedin: 'M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z',
  x: 'M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z',
  bluesky: 'M5.202 2.857C7.954 4.922 10.913 9.11 12 11.358c1.087-2.247 4.046-6.436 6.798-8.501C20.783 1.366 24 .213 24 3.883c0 .732-.42 6.156-.667 7.037-.856 3.061-3.978 3.842-6.755 3.37 4.854.826 6.089 3.562 3.422 6.299-5.065 5.196-7.28-1.304-7.847-2.97-.104-.305-.152-.448-.153-.327 0-.121-.05.022-.153.327-.568 1.666-2.782 8.166-7.847 2.97-2.667-2.737-1.432-5.473 3.422-6.3-2.777.473-5.899-.308-6.755-3.369C.42 10.04 0 4.615 0 3.883c0-3.67 3.217-2.517 5.202-1.026',
  mastodon: 'M23.268 5.313c-.35-2.578-2.617-4.61-5.304-5.004C17.51.242 15.792 0 11.813 0h-.03c-3.98 0-4.835.242-5.288.309C3.882.692 1.496 2.518.917 5.127.64 6.412.61 7.837.661 9.143c.074 1.874.088 3.745.26 5.611.118 1.24.325 2.47.62 3.68.55 2.237 2.777 4.098 4.96 4.857 2.336.792 4.849.923 7.256.38.265-.061.527-.132.786-.213.585-.184 1.27-.39 1.774-.753a.057.057 0 0 0 .023-.043v-1.809a.052.052 0 0 0-.02-.041.053.053 0 0 0-.046-.01 20.282 20.282 0 0 1-4.709.545c-2.73 0-3.463-1.284-3.674-1.818a5.593 5.593 0 0 1-.319-1.433.053.053 0 0 1 .066-.054c1.517.363 3.072.546 4.632.546.376 0 .75 0 1.125-.01 1.57-.044 3.224-.124 4.768-.422.038-.008.077-.015.11-.024 2.435-.464 4.753-1.92 4.989-5.604.008-.145.03-1.52.03-1.67.002-.512.167-3.63-.024-5.545zm-3.748 9.195h-2.561V8.29c0-1.309-.55-1.976-1.67-1.976-1.23 0-1.846.79-1.846 2.35v3.403h-2.546V8.663c0-1.56-.617-2.35-1.848-2.35-1.112 0-1.668.668-1.67 1.977v6.218H4.822V8.102c0-1.31.337-2.35 1.011-3.12.696-.77 1.608-1.164 2.74-1.164 1.311 0 2.302.5 2.962 1.498l.638 1.06.638-1.06c.66-.999 1.65-1.498 2.96-1.498 1.13 0 2.043.395 2.74 1.164.675.77 1.012 1.81 1.012 3.12z',
  threads: 'M18.263 11.097c-.03-3.486-1.92-5.586-5.111-5.586-2.13 0-3.922.963-4.863 2.499l2.062 1.438c.535-.843 1.272-1.543 2.628-1.543 1.528 0 2.318.85 2.544 2.431a15 15 0 0 0-2.236-.173c-4.125 0-6.068 1.867-6.068 4.336s1.943 3.99 4.804 3.99c3.139 0 5.013-2.115 5.781-4.735.798.361 1.348 1.204 1.348 2.47 0 3.387-3.907 5.232-7.22 5.232-4.885 0-8.077-3.207-8.077-8.424 0-6.392 4.223-10.487 9.9-10.487 3.808 0 5.69 1.671 6.97 3.914l2.108-1.475C21.44 2.078 18.331 0 13.663 0 6.227 0 1.168 5.277 1.168 12.934c0 7 4.953 11.066 10.856 11.066 4.878 0 9.809-2.846 9.809-7.716 0-2.545-1.46-4.231-3.569-5.187m-6.33 4.855c-1.077 0-2.026-.512-2.026-1.453 0-1.483 1.822-1.934 3.606-1.934.678 0 1.34.045 1.927.173-.422 1.927-1.671 3.215-3.508 3.214Z',
  tiktok: 'M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z',
  youtube: 'M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z',
  telegram: 'M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z',
  discord: 'M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z',
  github: 'M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12',
  gitlab: 'm23.6004 9.5927-.0337-.0862L20.3.9814a.851.851 0 0 0-.3362-.405.8748.8748 0 0 0-.9997.0539.8748.8748 0 0 0-.29.4399l-2.2055 6.748H7.5375l-2.2057-6.748a.8573.8573 0 0 0-.29-.4412.8748.8748 0 0 0-.9997-.0537.8585.8585 0 0 0-.3362.4049L.4332 9.5015l-.0325.0862a6.0657 6.0657 0 0 0 2.0119 7.0105l.0113.0087.03.0213 4.976 3.7264 2.462 1.8633 1.4995 1.1321a1.0085 1.0085 0 0 0 1.2197 0l1.4995-1.1321 2.4619-1.8633 5.006-3.7489.0125-.01a6.0682 6.0682 0 0 0 2.0094-7.003z',
};

const TITLES = ['CivTech România', 'Cu datele pe față', 'Soros2 suntem noi', 'Prinosul poporului', 'Programatori pentru patrie',
  'Minirevoluția digitală', 'Împreună suntem mai mulți', 'Guvernul paralel'];

const STATUS = {
  activ: { label: 'Activ', cls: 'ok', group: 'activ' },
  offline: { label: 'Offline', cls: 'bad', group: 'inactiv' },
  arhivat: { label: 'Arhivat', cls: 'bad', group: 'inactiv' },
  necunoscut: { label: 'Neconfirmat', cls: 'warn', group: 'neconfirmat' },
  neverificat: { label: 'Neverificat', cls: 'warn', group: 'neconfirmat' },
};
const SORTS = [['domeniu', 'Pe domenii'], ['az', 'A–Z'], ['top', 'Active și relevante'], ['relevanta', 'Relevanță'], ['nou', 'Cele mai noi'], ['recent', 'Actualizate recent'], ['random', 'Aleatoriu']];
const MIN_Q = 3;
// ina=1 shows inactive projects (hidden by default); a and s are kept for URLs but have no UI for now.
const DEFAULTS = { k: 'proiect', q: '', d: '', t: '', kw: '', c: '', org: '', a: '', s: '', cod: '', civ: '', nou: '', ina: '', v: '', o: '', p: '' };
const FILTERS = ['q', 'd', 't', 'kw', 'c', 'org', 'a', 's', 'cod', 'civ', 'nou', 'ina'];
const FRESH_DAYS = 183, LAUNCH_DAYS = 60;

let DB = null, TAX = null, seed = Math.random();
const BY_SLUG = new Map();
let title = TITLES[0];
const state = { ...DEFAULTS };
// First visit on desktop: only "domeniu" is open. Once a visitor toggles a facet, their choice is stored and wins.
const wide = matchMedia('(min-width: 1024px)').matches;
const closed = new Set(store.get('ct.closed', wide ? ['tip', 'cuvinte', 'optiuni'] : ['cuvinte']));
let lastFocus = null;

const isInactive = it => STATUS[it.status].group === 'inactiv';
const listOf = key => state[key] ? state[key].split(',') : [];
const tips = () => listOf('t');
const kwLabel = k => k.replace(/-/g, ' ');
const query = () => state.q.length >= MIN_Q ? state.q : '';

/* ---------- URL state ---------- */
// Projects read best grouped by domain; the short org/resource lists read best flat.
const defaultSort = () => state.k === 'proiect' ? 'domeniu' : 'az';
// An entry opens at its own address, /<kind>/<slug>/ with kind = proiect | organizatie | resursa (a page that
// scripts/build.py writes, so link previews and search engines see it), with the filters in the query. The old
// ?p=<slug> still opens it. ROOT is the site's path, whatever page loaded.
const KINDS = 'proiect|organizatie|resursa';
const ROOT = location.pathname.replace(new RegExp(`((${KINDS})/[^/]*/?|index\\.html)$`), '');
const pathSlug = () => decodeURIComponent((location.pathname.match(new RegExp(`/(?:${KINDS})/([^/]+)/?$`)) || [])[1] || '');
const entryPath = slug => `${ROOT}${BY_SLUG.get(slug)?.kind || 'proiect'}/${encodeURIComponent(slug)}/`;
function readURL() {
  const u = new URLSearchParams(location.search);
  for (const k of Object.keys(DEFAULTS)) state[k] = u.get(k) ?? DEFAULTS[k];
  if (!state.p) state.p = pathSlug();
  // An entry from the address alone (no kind in the query) opens on its own tab: an organisation, not the project list.
  if (state.p && !u.has('k')) { const it = BY_SLUG.get(state.p); if (it) state.k = it.kind; }
  if (!state.o) state.o = defaultSort();
}
// The filters, as a query string; the open entry is in the path, not here.
function filterQuery() {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(state)) if (v && k !== 'p' && v !== (k === 'o' ? defaultSort() : DEFAULTS[k])) u.set(k, v);
  return u.toString() ? '?' + u : '';
}
function writeURL(push = false) {
  const url = (state.p ? entryPath(state.p) : ROOT) + filterQuery() + location.hash;
  if (url !== location.pathname + location.search + location.hash) history[push ? 'pushState' : 'replaceState'](null, '', url);
}
const hrefFor = slug => entryPath(slug) + filterQuery();

/* ---------- filtering ---------- */
function matches(it, skip) {
  if (it.kind !== state.k) return false;
  if (skip !== 'd' && state.d && it.domeniu !== state.d) return false;
  if (skip !== 't' && state.t && !tips().some(t => it.tips.includes(t))) return false;
  if (skip !== 'kw' && state.kw && !listOf('kw').some(k => it.keywords.includes(k))) return false;
  if (skip !== 'c' && state.c && it.oras !== state.c) return false;
  if (skip !== 'org' && state.org && !it._orgs.includes(state.org)) return false;
  if (skip !== 'a' && state.a && it.acoperire !== state.a) return false;
  if (skip !== 's' && state.s && STATUS[it.status].group !== state.s) return false;
  if (skip !== 'cod' && state.cod && !it.code) return false;
  if (skip !== 'civ' && state.civ && !it.civictech) return false;
  if (skip !== 'nou' && state.nou && !isFresh(it)) return false;
  if (skip !== 'ina' && !state.ina && isInactive(it)) return false;
  const q = query();
  if (q) {
    const terms = norm(q).split(/\s+/).filter(Boolean);
    if (!terms.every(t => it._hay.includes(t))) return false;
  }
  return true;
}
const kindItems = () => DB.items.filter(i => i.kind === state.k);
const countBy = (skip, key) => {
  const c = {};
  // key may return several values (an item with two tips counts under both).
  for (const it of DB.items) if (matches(it, skip)) for (const v of [key(it)].flat()) c[v] = (c[v] || 0) + 1;
  return c;
};
const activeFilterCount = () => ['d', 'c', 'org', 'a', 's', 'cod', 'civ', 'nou', 'ina'].filter(k => state[k]).length + tips().length + listOf('kw').length;
const rank = it => ({ activ: 0, neconfirmat: 1, inactiv: 2 })[STATUS[it.status].group];
const byName = (a, b) => a._sort.localeCompare(b._sort);
// Last sign of life: the last update, or the launch date when that is later. A recent launch thus
// sorts like a recent update. Entries with neither go last.
const lastSign = it => [it.updated, isLaunched(it) ? it.since : ''].sort().at(-1) || '';
// "Active și relevante": the build's relevance score, discounted by time since the last sign of life
// (half-life ~8 months; unknown counts as old), plus a small bump for a launch in the last 60 days.
function topScore(it) {
  const d = lastSign(it);
  const recency = d ? Math.exp(-daysSince(d) / 365) : .25;
  return it.score * (.5 + .5 * recency) + (isLaunched(it) ? 8 : 0);
}
function sorted(list) {
  if (state.o === 'random') {
    const r = it => Math.sin(it.id * 9301 + seed * 49297) % 1;
    return [...list].sort((a, b) => r(a) - r(b));
  }
  if (state.o === 'top') return [...list].sort((a, b) => topScore(b) - topScore(a) || byName(a, b));
  if (state.o === 'domeniu') return [...list].sort((a, b) => rank(a) - rank(b) || lastSign(b).localeCompare(lastSign(a)) || byName(a, b));
  if (state.o === 'relevanta') return [...list].sort((a, b) => b.score - a.score || byName(a, b));
  // Entries with no known start date go last.
  if (state.o === 'nou') return [...list].sort((a, b) => (b.since || '0').localeCompare(a.since || '0') || byName(a, b));
  if (state.o === 'recent') return [...list].sort((a, b) => (b.updated || '').localeCompare(a.updated || '') || byName(a, b));
  return [...list].sort((a, b) => rank(a) - rank(b) || byName(a, b));
}

/* ---------- small renderers ---------- */
function media(it) {
  const im = it.img;
  if (im) {
    return `<div class="media media-${im.kind}" style="--c:${im.color}"><img src="${esc(im.src)}" alt="" loading="lazy" decoding="async" width="${im.w}" height="${im.h}"></div>`;
  }
  const icon = it.icon ? `<img class="ico" src="${esc(it.icon)}" alt="" loading="lazy">` : `<span class="mark">${esc(initials(it.name))}</span>`;
  return `<div class="media media-none" style="--h:${hue(it.domain || it.name)}">${icon}<span class="dom">${esc(it.domain || '—')}</span></div>`;
}
function thumb(it) {
  const im = it.img;
  if (im && im.kind !== 'logo') return `<div class="thumb" style="--c:${im.color}"><img src="${esc(im.src)}" alt="" loading="lazy" decoding="async"></div>`;
  if (im) return `<div class="thumb logo" style="--c:${im.color}"><img src="${esc(im.src)}" alt="" loading="lazy"></div>`;
  if (it.icon) return `<div class="thumb icon"><img src="${esc(it.icon)}" alt="" loading="lazy"></div>`;
  return `<div class="thumb none" style="--h:${hue(it.domain || it.name)}" aria-hidden="true">${esc(initials(it.name))}</div>`;
}
// The project's logo (its icon, up to 128 px) before its name in a row. Without one, the name starts at the left edge.
const logo = it => it.icon ? `<img class="fav fav-name" src="${esc(it.icon)}" alt="" width="24" height="24" loading="lazy">` : '';
const tipLabels = it => it.tips.map(t => TAX.tip[t]?.label).filter(Boolean);
// A resource that is an article, guide, campaign or piece of research says so; plain "resursa" says nothing.
const felLabel = it => it.kind === 'resursa' && it.fel && it.fel !== 'resursa' ? TAX.fel[it.fel]?.label || '' : '';
const placeLabel = it => it.acoperire === 'local' ? (it.oras || 'Local') : '';
function metaLine(it, withDomain) {
  const st = STATUS[it.status];
  const parts = [...new Set([felLabel(it), ...tipLabels(it), placeLabel(it)])];
  if (withDomain) parts.unshift(TAX.domeniu[it.domeniu]?.short);
  let html = parts.filter(Boolean).map(esc).join(' · ');
  if (st.group !== 'activ') html += ` <span class="status-tag ${st.cls}">· ${st.label}</span>`;
  else if (it.stale) html += ` <span class="status-tag warn">· neactualizat din ${it.stale}</span>`;
  return html;
}
const statusDot = it => `<span class="dot ${STATUS[it.status].cls}" title="${STATUS[it.status].label}"></span>`;
const codeTag = it => it.code ? `<span class="code-tag" title="Cod sursă deschis">${ICON.code}cod</span>` : '';
const newTag = it => !isFresh(it) ? ''
  : `<span class="code-tag new-tag${isLaunched(it) ? ' launch' : ''}" title="Apărut acum ${esc(age(it))} · ${esc(ageTitle(it))}">${isLaunched(it) ? 'lansat recent' : 'nou'}</span>`;
const blurb = it => it.tagline || it.desc;
const clip = (s, n) => s.length > n ? s.slice(0, s.lastIndexOf(' ', n) > n * .6 ? s.lastIndexOf(' ', n) : n).replace(/[\s,.;:–-]+$/, '') + '…' : s;
// Native tooltip: the start of the long description, when there is more to say than the tagline.
const hint = it => { const d = it.desc && it.desc !== it.tagline ? it.desc : ''; return d ? ` title="${esc(clip(d, 220))}"` : ''; };

/* ---------- dates ---------- */
const DAY = 864e5;
function span(days) {
  if (days < 1) return 'azi';
  if (days < 31) return plural(Math.floor(days), 'zi', 'zile');
  if (days < 365) return plural(Math.floor(days / 30.4), 'lună', 'luni');
  return plural(Math.floor(days / 365.25), 'an', 'ani');
}
// Compact span for the list columns, no space: "9Z" days, "2L" months, "13A" years.
function shortSpan(days) {
  if (days < 1) return 'azi';
  if (days < 31) return `${Math.floor(days)}Z`;
  if (days < 365) return `${Math.floor(days / 30.4)}L`;
  return `${Math.floor(days / 365.25)}A`;
}
const daysSince = d => (Date.now() - Date.parse(d)) / DAY;
// "Fresh": first seen less than FRESH_DAYS ago, by the same date the Vechime column shows.
const isFresh = it => !!it.since && daysSince(it.since) < FRESH_DAYS;
const isLaunched = it => !!it.since && daysSince(it.since) < LAUNCH_DAYS;
const age = it => it.since ? span(daysSince(it.since)) : '';
const ageShort = it => it.since ? shortSpan(daysSince(it.since)) : '';
const updatedShort = it => it.updated ? shortSpan(daysSince(it.updated)) : '';
const updatedLabel = it => !it.updated ? '' : daysSince(it.updated) < 1 ? 'azi' : `acum ${span(daysSince(it.updated))}`;
const UPDATED_SRC = { cod: 'ultimul commit', sitemap: 'sitemap', server: 'antetul Last-Modified', arhiva: 'ultima arhivare Wayback' };
const SINCE_SRC = { arhiva: 'prima arhivare Wayback', cod: 'crearea depozitului de cod', certificat: 'primul certificat TLS al domeniului' };
const ageTitle = it => !it.since ? 'Necunoscut' : it.sinceSrc ? `${it.since} · după ${SINCE_SRC[it.sinceSrc] || it.sinceSrc}` : it.since;
const updatedTitle = it => it.updated ? `${it.updated} · după ${UPDATED_SRC[it.updatedSrc] || it.updatedSrc}` : 'Necunoscut';

// Cards and rows are not links themselves: the name is (stretched over the whole item, opening the
// detail panel), so the project's own site can sit inside as a second, real link.
const extHref = it => (!isInactive(it) && it.url) || it.wayback || '';
function extLink(it, label, cls = '') {
  const href = extHref(it);
  if (!href) return label ? `<span class="${cls}">${label}</span>` : '';
  const title = isInactive(it) ? 'Vezi în arhivă' : `Deschide ${it.domain}`;
  return `<a class="ext ${cls}" href="${esc(href)}" target="_blank" rel="noopener" title="${esc(title)}"${label ? '' : ` aria-label="${esc(title)}"`}>${label}${ICON.out}</a>`;
}
const nameLink = it => `<a class="stretch" href="${hrefFor(it.slug)}">${esc(it.name)}</a>`;

function card(it, withDomain) {
  return `<div class="card${isInactive(it) ? ' inactive' : ''}" data-open="${it.slug}"${hint(it)}>
    ${media(it)}
    <div class="card-body">
      <div class="meta">${metaLine(it, withDomain)}</div>
      <h3>${nameLink(it)}</h3>
      ${blurb(it) ? `<p class="tagline">${esc(blurb(it))}</p>` : ''}
      <div class="foot">${statusDot(it)}${extLink(it, `<span class="dom">${esc(it.domain)}</span>`)}${newTag(it)}${codeTag(it)}</div>
    </div>
  </div>`;
}
// Icon-only links for the list column: curated links first, then those found on the site. A network shows its logo, any
// other link its host's favicon, else a plain arrow. Past ROW_LINKS, "+n" stands for the rest (they are in the detail panel).
const ROW_LINKS = 4;
function rowLinks(it) {
  const ls = [...it.links].sort((a, b) => (b.src === 'manual') - (a.src === 'manual'));
  const one = l => {
    const glyph = NETWORK[l.role] ? `<svg class="logo" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${NETWORK[l.role]}"/></svg>`
      : l.icon ? `<img class="fav" src="${esc(l.icon)}" alt="" width="14" height="14" loading="lazy">` : ICON.out;
    return `<a class="ext rl" href="${esc(l.url)}" target="_blank" rel="noopener" title="${esc(l.label)}" aria-label="${esc(l.label)}">${glyph}</a>`;
  };
  const more = ls.length - ROW_LINKS;
  return ls.slice(0, ROW_LINKS).map(one).join('') + (more > 0 ? `<span class="rl-more" title="${esc(ls.slice(ROW_LINKS).map(l => l.label).join(', '))}">+${more}</span>` : '');
}
function row(it, withDomain) {
  const desc = it.tagline && it.desc && it.desc !== it.tagline ? it.desc : '';
  const dates = [age(it) && `${age(it)} vechime`, updatedLabel(it) && `actualizat ${updatedLabel(it)}`].filter(Boolean).join(' · ');
  return `<div class="row${isInactive(it) ? ' inactive' : ''}" data-open="${it.slug}"${hint(it)}>
    ${thumb(it)}
    <div class="row-main">
      <div class="row-title">${logo(it)}${nameLink(it)} ${statusDot(it)} ${newTag(it)} ${codeTag(it)} ${extLink(it, '', 'ext-m')}</div>
      ${blurb(it) ? `<div class="row-tag">${esc(blurb(it))}</div>` : ''}
      ${desc ? `<div class="row-desc">${esc(clip(desc, 160))}</div>` : ''}
      ${it.keywords.length ? `<div class="row-kw">${it.keywords.map(k => `<span>#${esc(kwLabel(k))}</span>`).join('')}</div>` : ''}
      <div class="meta meta-m">${metaLine(it, withDomain)}${dates ? ` · ${esc(dates)}` : ''}</div>
    </div>
    <div class="row-side row-links">${rowLinks(it)}</div>
    <div class="row-side" title="${esc(ageTitle(it))}">${esc(ageShort(it) || '—')}</div>
    <div class="row-side${it.updatedSrc === 'arhiva' ? ' faint' : ''}" title="${esc(updatedTitle(it))}">${esc(updatedShort(it) || '—')}</div>
    <div class="row-side">${extLink(it, `<span class="dom">${esc(it.domain)}</span>`)}</div>
  </div>`;
}
const LIST_HEAD = '<div class="list-head" aria-hidden="true"><span>Proiect</span><span>Links</span><span>Age</span><span>Updated</span><span>Site</span></div>';

/* ---------- filters ---------- */
function renderTabs() {
  // Counters show what is alive, not what was ever catalogued.
  const c = {};
  for (const it of DB.items) if (!isInactive(it)) c[it.kind] = (c[it.kind] || 0) + 1;
  slot('tabs').innerHTML = DB.taxonomy.kinds.map(k =>
    `<button class="tab" data-act="kind" data-val="${k.key}" ${state.k === k.key ? 'aria-current="page"' : ''}>${esc(k.label)}<span class="n">${c[k.key] || 0}</span></button>`
  ).join('');
}

function facet(id, label, body) {
  return `<details class="facet" data-facet="${id}" ${closed.has(id) ? '' : 'open'}><summary><span class="kicker">${label}</span></summary>${body}</details>`;
}
function facetsHTML() {
  const mine = kindItems();
  const has = (pred) => mine.some(pred);
  const dC = countBy('d', i => i.domeniu), tC = countBy('t', i => i.tips);
  const out = [];

  // Only choices that exist for the current tab are offered.
  const tagFacet = (id, label, key, options, counts) => {
    const sel = listOf(key);
    return facet(id, label, `<div class="tags">${options.map(([val, text]) => {
      const on = sel.includes(val), n = counts[val] || 0;
      return `<button class="tag" data-act="multi" data-key="${key}" data-val="${esc(val)}" aria-pressed="${on}" ${!n && !on ? 'disabled' : ''}>${esc(text)}<span class="n">${n}</span></button>`;
    }).join('')}</div>`);
  };
  const tipList = DB.taxonomy.tipuri.filter(t => has(i => i.tips.includes(t.key)));
  if (tipList.length > 1) out.push(tagFacet('tip', 'Tip', 't', tipList.map(t => [t.key, t.label]), tC));
  const domList = DB.taxonomy.domenii.filter(d => has(i => i.domeniu === d.key));
  if (domList.length > 1) {
    const total = DB.items.filter(i => matches(i, 'd')).length;
    const opt = (val, label, n) => `<button class="fopt radio" data-act="set" data-key="d" data-val="${val}" aria-pressed="${state.d === val}" ${!n && state.d !== val ? 'disabled' : ''}>
      <span class="l">${esc(label)}</span><span class="n">${n || 0}</span></button>`;
    out.push(facet('domeniu', 'Domeniu', `<div class="flist">${opt('', 'Toate', total)}${domList.map(d => opt(d.key, d.label, dC[d.key])).join('')}</div>`));
  }

  const kwC = {};
  for (const it of DB.items) if (matches(it, 'kw')) for (const k of it.keywords) kwC[k] = (kwC[k] || 0) + 1;
  const kwAll = {};
  for (const it of mine) for (const k of it.keywords) kwAll[k] = (kwAll[k] || 0) + 1;
  const kwList = Object.keys(kwAll).sort((a, b) => kwAll[b] - kwAll[a] || a.localeCompare(b));
  if (kwList.length) out.push(tagFacet('cuvinte', 'Cuvinte cheie', 'kw', kwList.map(k => [k, kwLabel(k)]), kwC));

  const toggles = [];
  const toggle = (key, label, checked, n) => toggles.push(`<label class="toggle"><input type="checkbox" data-act="toggle" data-key="${key}" ${checked ? 'checked' : ''}><span class="l">${label}</span>${n != null ? `<span class="n">${n}</span>` : ''}</label>`);
  if (has(i => i.code) && has(i => !i.code)) toggle('cod', 'Doar cu cod sursă deschis', state.cod, DB.items.filter(i => matches(i, 'cod') && i.code).length);
  if (has(isFresh) && has(i => !isFresh(i))) toggle('nou', 'Doar proiecte noi', state.nou, DB.items.filter(i => matches(i, 'nou') && isFresh(i)).length);
  if (has(isInactive)) toggle('ina', 'Ascunde proiecte inactive', !state.ina, null);
  if (has(i => i.civictech) && has(i => !i.civictech)) toggle('civ', 'Doar proiecte civtech', state.civ, DB.items.filter(i => matches(i, 'civ') && i.civictech).length);
  if (toggles.length) out.push(facet('optiuni', 'Opțiuni', toggles.join('')));
  return out.join('');
}

function renderChips() {
  const dC = countBy('d', i => i.domeniu);
  const total = DB.items.filter(i => matches(i, 'd')).length;
  const chip = (val, label, n) => `<button class="chip" data-act="set" data-key="d" data-val="${val}" aria-pressed="${state.d === val}">${esc(label)}<span class="n">${n || 0}</span></button>`;
  slot('chips').innerHTML = chip('', 'Toate', total) + DB.taxonomy.domenii.filter(d => dC[d.key] || state.d === d.key).map(d => chip(d.key, d.short, dC[d.key])).join('');
}

function renderToolbar(n) {
  const pills = [];
  const pill = (key, val, label) => pills.push(`<button class="pill" data-act="unset" data-key="${key}" data-val="${esc(val)}" aria-label="Elimină filtrul ${esc(label)}">${esc(label)}${ICON.x}</button>`);
  if (state.d) pill('d', '', TAX.domeniu[state.d]?.short);
  for (const t of tips()) pill('t', t, TAX.tip[t]?.label || t);
  for (const k of listOf('kw')) pill('kw', k, '#' + kwLabel(k));
  if (state.c) pill('c', '', state.c);
  if (state.org) pill('org', '', state.org);
  if (state.a) pill('a', '', state.a);
  if (state.s) pill('s', '', state.s);
  if (state.cod) pill('cod', '', 'Cod deschis');
  if (state.civ) pill('civ', '', 'Civtech');
  if (state.nou) pill('nou', '', 'Noi');
  if (state.ina) pill('ina', '', 'Inclusiv inactive');
  if (query()) pill('q', '', `„${state.q}”`);
  const view = currentView();
  slot('toolbar').innerHTML = `
    <span class="count"><b>${n}</b> ${n === 1 ? 'rezultat' : 'rezultate'}</span>
    ${pills.length ? `<span class="active">${pills.join('')}</span><button class="linkbtn" data-act="reset">Șterge filtrele</button>` : ''}
    <span class="tool-right">
      <label class="sr" for="sort">Ordonare</label>
      <select class="select" id="sort" data-act="sort">${SORTS.map(([k, l]) => `<option value="${k}" ${state.o === k ? 'selected' : ''}>${l}</option>`).join('')}</select>
      <span class="seg" role="group" aria-label="Mod de afișare">
        <button data-act="view" data-val="cards" aria-pressed="${view === 'cards'}" aria-label="Carduri">${ICON.grid}</button>
        <button data-act="view" data-val="list" aria-pressed="${view === 'list'}" aria-label="Listă">${ICON.list}</button>
      </span>
    </span>`;
  slot('fcount').textContent = activeFilterCount() || '';
}

const currentView = () => state.v || 'list';

function renderResults() {
  const list = DB.items.filter(i => matches(i));
  renderToolbar(list.length);
  const view = currentView();
  const block = (items, withDomain) => view === 'cards'
    ? `<div class="grid">${items.map(i => card(i, withDomain)).join('')}</div>`
    : `<div class="list">${LIST_HEAD}${items.map(i => row(i, withDomain)).join('')}</div>`;
  let html;
  if (!list.length) {
    html = `<div class="empty"><h3>Niciun rezultat.</h3><p>Încearcă alt termen de căutare sau elimină unul dintre filtre.</p><p><button class="btn btn-outline" data-act="reset">Șterge filtrele</button></p></div>`;
  } else if (state.o === 'domeniu') {
    html = DB.taxonomy.domenii.map(d => {
      const items = sorted(list.filter(it => it.domeniu === d.key));
      if (!items.length) return '';
      return `<section class="group" aria-labelledby="g-${d.key}">
        <div class="group-head"><h2 id="g-${d.key}">${esc(d.label)}</h2><span class="n">${items.length}</span><p>${esc(d.hint)}</p></div>
        ${block(items, false)}</section>`;
    }).join('');
  } else {
    html = block(sorted(list), true);
  }
  slot('results').innerHTML = html;
}

function renderFilters() {
  slot('side').innerHTML = facetsHTML();
  renderChips();
  if (!slot('sheet').hidden) renderSheet();
}

function renderAll() {
  renderTabs();
  renderFilters();
  renderResults();
  const q = slot('q');
  if (q.value !== state.q) q.value = state.q;
}

/* ---------- layers: detail drawer & filter sheet ---------- */
function openLayer(el) {
  lastFocus = document.activeElement;
  slot('scrim').hidden = false;
  el.hidden = false;
  document.body.classList.add('locked');
  requestAnimationFrame(() => $('[data-autofocus]', el)?.focus());
}
function closeLayers() {
  for (const n of ['drawer', 'sheet', 'scrim']) slot(n).hidden = true;
  document.body.classList.remove('locked');
  lastFocus?.focus?.({ preventScroll: true });
}
const current = () => state.p && DB.items.find(i => i.slug === state.p);
const syncTitle = () => { const it = current(); document.title = it ? `${it.name} — ${title}` : title; };

// A network shows its logo only, named for screen readers and the tooltip; any other link shows the favicon of its host
// (when the profiler stored one) before its label.
function linkOne(l) {
  const open = `href="${esc(l.url)}" target="_blank" rel="noopener"`;
  if (NETWORK[l.role]) return `<a class="net" ${open} title="${esc(l.label)}" aria-label="${esc(l.label)}"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${NETWORK[l.role]}"/></svg></a>`;
  const fav = l.icon ? `<img class="fav" src="${esc(l.icon)}" alt="" width="14" height="14" loading="lazy">` : '';
  return `<a class="lk" ${open} title="${esc(l.url)}">${fav}${esc(l.role === 'web' ? l.url.replace(/^https?:\/\/(www\.)?/, '') : l.label)}</a>`;
}

// Manual links come from curation; links found on the homepage may belong to the author rather than the project.
function linkRows(it) {
  const fmt = ls => `<span class="links">${ls.map(linkOne).join('')}</span>`;
  const man = it.links.filter(l => l.src === 'manual'), site = it.links.filter(l => l.src === 'site');
  return [man.length && ['Linkuri', fmt(man)], site.length && ['Găsite pe site', fmt(site)]];
}

// "★ 12 · 3 forks · 5 issues · 240 commits · 4 contribuitori · ultimul commit 2026-10-14 · MIT": the GitHub facts the
// profiler stored; a part that is missing is left out. The repository's name leads when it is not the "Cod sursă" link above.
function repoRow(it) {
  const r = it.repo;
  if (!r) return null;
  const n = (v, one, many) => v == null ? '' : `${v.toLocaleString('ro-RO')} ${v === 1 ? one : many}`;
  const parts = [r.stars != null && `★ ${r.stars.toLocaleString('ro-RO')}`, n(r.forks, 'fork', 'forks'), n(r.issues, 'issue', 'issues'),
    n(r.commits, 'commit', 'commits'), n(r.contributors, 'contribuitor', 'contribuitori'), r.last && `ultimul commit ${r.last}`,
    r.license, r.language, r.archived && 'arhivat'].filter(Boolean).map(esc);
  const same = it.code && it.code.replace(/\/+$/, '').toLowerCase() === r.url.toLowerCase();
  if (!same) parts.unshift(`<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>`);
  return ['Cod', `<span class="repo mono">${parts.join(' · ')}</span>`];
}

// An author that is an organisation of the catalogue opens its page; any other author is plain text.
const authorLink = a => a.org && BY_SLUG.has(a.org)
  ? `<a href="${hrefFor(a.org)}" data-open="${esc(a.org)}">${esc(a.name)}</a>` : esc(a.name);
const MAX_WORKS = 15;
// Entries (projects and resources) by the same author as `it`; for an organisation, the entries that name it as author.
function sameAuthor(it) {
  const keys = it.kind === 'organizatie' ? [it.slug] : it._akeys;
  return DB.items.filter(i => i !== it && i.kind !== 'organizatie' && i._akeys.some(k => keys.includes(k)))
    .sort((a, b) => rank(a) - rank(b) || byName(a, b));
}
// The organisation behind a project: name, one line about it, and a way into its page.
function orgCard(o) {
  return `<a class="org-card" href="${hrefFor(o.slug)}" data-open="${esc(o.slug)}">
    ${o.icon ? `<img class="fav fav-org" src="${esc(o.icon)}" alt="" width="24" height="24" loading="lazy">` : `<span class="org-mark" aria-hidden="true">${esc(initials(o.name))}</span>`}
    <span class="org-text"><span class="kicker">Organizație</span><strong>${esc(o.name)}</strong>${blurb(o) ? `<span class="org-blurb">${esc(clip(blurb(o), 140))}</span>` : ''}</span>
  </a>`;
}
function worksHTML(it) {
  const works = sameAuthor(it);
  if (!works.length) return '';
  const title = it.kind === 'organizatie' ? 'Proiecte și resurse' : 'De același autor';
  const more = works.length - MAX_WORKS;
  return `<div class="related"><p class="kicker">${title} · ${works.length}</p>${works.slice(0, MAX_WORKS).map(r => row(r, true)).join('')}${more > 0 ? `<p class="small muted">… și încă ${more}</p>` : ''}</div>`;
}

// "Semnalează o problemă": three ways to tell us, each prefilled with the entry's name and address. data/site.json
// (copied into data.json as `site`) says which ones exist: an empty address hides its option.
function flagHTML(it) {
  const site = DB.site || {}, tab = it.kind === 'organizatie' ? 'orgs' : 'proiecte';
  const subject = `Problemă la „${it.name}” (${it.slug})`;
  const body = `Pagina: ${location.origin}${entryPath(it.slug)}\nÎn tabel: fila ${tab}, rândul ${it.row}\n\nCe nu e corect sau lipsește?\n`;
  const q = `${encodeURIComponent(subject)}`, b = `${encodeURIComponent(body)}`;
  const opts = [
    site.sheet && site.tabs?.[tab] != null && [`${site.sheet}#gid=${site.tabs[tab]}&range=A${it.row}`, 'Corectează în tabel',
      `Deschide rândul ${it.row} din fila „${tab}”. Modifici direct; schimbarea e verificată înainte să apară pe site.`],
    site.email && [`mailto:${site.email}?subject=${q}&body=${b}`, 'Trimite un e-mail', 'Mesajul pornește cu numele și adresa paginii.'],
    site.issues && [`${site.issues}?title=${q}&body=${b}`, 'Deschide o problemă pe GitHub', 'Cere cont GitHub; discuția e publică.'],
  ].filter(Boolean);
  if (!opts.length) return '';
  return `<details class="flag"><summary>Semnalează o problemă</summary>
    <p>Ceva lipsește sau nu e corect aici? Alege varianta care îți vine mai la îndemână:</p>
    <ul>${opts.map(([href, label, note]) => `<li><a href="${esc(href)}" target="_blank" rel="noopener">${label}</a><span>${esc(note)}</span></li>`).join('')}</ul>
  </details>`;
}

function renderDetail() {
  const it = current();
  const drawer = slot('drawer');
  syncTitle();
  if (!it) { if (!drawer.hidden) closeLayers(); return; }
  const dom = TAX.domeniu[it.domeniu];
  const st = STATUS[it.status];
  const alive = !isInactive(it);
  const related = DB.items.filter(i => i.kind === it.kind && i.domeniu === it.domeniu && i.slug !== it.slug && !isInactive(i))
    .sort((a, b) => b.tips.filter(t => it.tips.includes(t)).length - a.tips.filter(t => it.tips.includes(t)).length || byName(a, b)).slice(0, 4);
  const dl = [
    it.authors.length && [it.authors.length > 1 ? 'Autori' : 'Autor', it.authors.map(authorLink).join(' · ')],
    it.contact && ['Contact', esc(it.contact)],
    it.url && ['Site', `${alive ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.domain)}</a>` : `<span class="muted">${esc(it.domain)}</span>`}${it.movedFrom ? ` <span class="muted small">(mutat de pe ${esc(it.movedFrom)})</span>` : ''}`],
    ...linkRows(it),
    it.code && ['Cod sursă', `<a href="${esc(it.code)}" target="_blank" rel="noopener">${esc(it.code.replace(/^https?:\/\/(www\.)?/, ''))}</a>`],
    repoRow(it),
    it.wayback && ['Arhivă', `<a href="${esc(it.wayback)}" target="_blank" rel="noopener">Wayback Machine</a>`],
    it.since && ['Vechime', `${esc(age(it))} <span class="muted small mono">· ${esc(ageTitle(it))}</span>`],
    it.updated && ['Actualizat', `${esc(updatedLabel(it))} <span class="muted small mono">· ${esc(it.updated)} după ${esc(UPDATED_SRC[it.updatedSrc] || it.updatedSrc)}</span>`],
    ['Stare', `${statusDot(it)} ${st.label}${it.stale ? ` <span class="muted small">· niciun semn de actualizare după ${it.stale}</span>` : ''}${it.checked ? ` <span class="muted small mono">· verificat ${esc(it.checked)}${it.httpStatus ? ` · HTTP ${it.httpStatus}` : ''}</span>` : ''}`],
  ].filter(Boolean);
  const cta = alive && it.url
    ? `<a class="d-url" href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, ''))}${ICON.out}</a>`
    : it.wayback ? `<a class="btn btn-primary" href="${esc(it.wayback)}" target="_blank" rel="noopener">${ICON.archive}Vezi în arhivă</a>` : '';
  drawer.innerHTML = `
    <div class="d-bar"><span class="kicker">${esc(dom?.label || '')}</span>
      <button class="btn btn-ghost btn-icon" data-act="close" aria-label="Închide" data-autofocus>${ICON.x}</button></div>
    <div class="d-scroll">
      ${it.img || it.icon ? media(it) : ''}
      <div class="d-head${it.icon ? '' : ' no-logo'}">
        ${it.icon ? `<img class="d-logo" src="${esc(it.icon)}" alt="" width="72" height="72">` : ''}
        <div class="d-head-text">
          <h2 id="d-title">${esc(it.name)}</h2>
          ${cta ? `<div class="d-open">${cta}</div>` : ''}
          ${it.tagline ? `<p class="d-tag">${esc(it.tagline)}</p>` : ''}
        </div>
      </div>
      <div class="d-badges">
        <span>${statusDot(it)}${st.label}</span>
        ${felLabel(it) ? `<span>${esc(felLabel(it))}</span>` : ''}
        ${tipLabels(it).filter(l => l !== felLabel(it)).map(l => `<span>${esc(l)}</span>`).join('')}
        ${placeLabel(it) ? `<span>${esc(placeLabel(it))}</span>` : ''}
        ${isFresh(it) ? `<span class="new${isLaunched(it) ? ' launch' : ''}">${isLaunched(it) ? 'lansat recent' : 'nou'} · ${esc(age(it))}</span>` : ''}
        ${it.code ? `<span>${ICON.code}cod deschis</span>` : ''}
      </div>
      ${it.desc ? `<p class="d-desc">${esc(it.desc)}</p>${it.descSrc === 'site' ? '<p class="d-src">Descriere preluată de pe site-ul proiectului.</p>' : ''}` : ''}
      ${it.keywords.length ? `<div class="tags">${it.keywords.map(k => `<button class="tag" data-act="multi" data-key="kw" data-val="${esc(k)}" aria-pressed="${listOf('kw').includes(k)}">#${esc(kwLabel(k))}</button>`).join('')}</div>` : ''}
      ${it.authors.filter(a => a.org && BY_SLUG.has(a.org)).map(a => orgCard(BY_SLUG.get(a.org))).join('')}
      <dl class="dl">${dl.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${worksHTML(it)}
      ${related.length ? `<div class="related"><p class="kicker">Tot din ${esc(dom.short)}</p>${related.map(r => row(r, false)).join('')}</div>` : ''}
      ${flagHTML(it)}
    </div>`;
  if (drawer.hidden) openLayer(drawer);
  else {
    $('.d-scroll', drawer).scrollTop = 0;
    // The re-render dropped the focused element; keep focus inside the drawer.
    if (!drawer.contains(document.activeElement)) $('[data-autofocus]', drawer)?.focus();
  }
}

function renderSheet() {
  const n = DB.items.filter(i => matches(i)).length;
  slot('sheet').innerHTML = `
    <div class="grab" aria-hidden="true"></div>
    <div class="d-bar"><span class="kicker">Filtre</span><button class="btn btn-ghost btn-icon" data-act="close" aria-label="Închide" data-autofocus>${ICON.x}</button></div>
    <div class="d-scroll">${facetsHTML()}</div>
    <div class="d-cta"><button class="btn btn-outline" data-act="reset">Șterge</button><button class="btn btn-primary" data-act="close">Arată ${plural(n, 'rezultat', 'rezultate')}</button></div>`;
}

/* ---------- autocomplete ---------- */
let SUGGEST = [], acItems = [], acIndex = -1;

function buildSuggestions() {
  const out = [];
  for (const d of DB.taxonomy.domenii) out.push({ g: 'Teme', label: d.label, kind: 'tema', val: d.key });
  for (const t of DB.taxonomy.tipuri) out.push({ g: 'Tipuri', label: t.label, kind: 'tip', val: t.key });
  for (const k of new Set(DB.items.flatMap(i => i.keywords))) out.push({ g: 'Cuvinte cheie', label: kwLabel(k), kind: 'kw', val: k });
  for (const c of new Set(DB.items.map(i => i.oras).filter(Boolean))) out.push({ g: 'Orașe', label: c, kind: 'oras', val: c });
  for (const it of DB.items) out.push({ g: 'Proiecte', label: it.name, kind: 'item', val: it.slug, it });
  for (const o of new Set(DB.items.flatMap(i => i._orgs))) out.push({ g: 'Autori', label: o, kind: 'org', val: o });
  for (const s of out) s._n = norm(s.label);
  return out;
}
const GROUP_LIMIT = { Teme: 3, Tipuri: 3, 'Cuvinte cheie': 4, 'Orașe': 3, Proiecte: 6, Autori: 3 };
function scoreOf(n, q) {
  if (n.startsWith(q)) return 0;
  const i = n.indexOf(q);
  if (i < 0) return -1;
  return /[\s\-–·./(&]/.test(n[i - 1]) ? 1 : 2;
}
function countFor(s) {
  const base = DB.items.filter(i => i.kind === state.k && (state.ina || !isInactive(i)));
  if (s.kind === 'tema') return base.filter(i => i.domeniu === s.val).length;
  if (s.kind === 'tip') return base.filter(i => i.tips.includes(s.val)).length;
  if (s.kind === 'kw') return base.filter(i => i.keywords.includes(s.val)).length;
  if (s.kind === 'oras') return base.filter(i => i.oras === s.val).length;
  if (s.kind === 'org') return DB.items.filter(i => i._orgs.includes(s.val)).length;
  return null;
}
function highlight(label, q) {
  const i = norm(label).indexOf(q);
  if (i < 0) return esc(label);
  return esc(label.slice(0, i)) + '<mark>' + esc(label.slice(i, i + q.length)) + '</mark>' + esc(label.slice(i + q.length));
}
function renderAC() {
  const box = slot('ac'), input = slot('q');
  const q = norm(input.value.trim());
  if (q.length < MIN_Q || document.activeElement !== input) { closeAC(); return; }
  const scored = SUGGEST.map(s => ({ s, sc: scoreOf(s._n, q), n: countFor(s) }))
    .filter(x => x.sc >= 0 && x.n !== 0)
    .sort((a, b) => a.sc - b.sc || a.s.label.length - b.s.label.length);
  const groups = {};
  for (const x of scored) (groups[x.s.g] ??= []).length < GROUP_LIMIT[x.s.g] && groups[x.s.g].push(x);
  acItems = Object.keys(GROUP_LIMIT).flatMap(g => groups[g] || []);
  acIndex = -1;
  if (!acItems.length) {
    box.innerHTML = `<div class="ac-hint">Nicio sugestie. Rezultatele de mai jos conțin textul căutat.</div>`;
  } else {
    let html = '', last = '';
    acItems.forEach((x, i) => {
      if (x.s.g !== last) { html += `<div class="ac-group" role="presentation">${x.s.g}</div>`; last = x.s.g; }
      const it = x.s.it;
      const lead = x.s.kind === 'item'
        ? (it.icon ? `<img class="ico" src="${esc(it.icon)}" alt="">` : '<span class="ico blank"></span>') : '';
      const right = x.s.kind === 'item'
        ? (it.kind !== 'proiect' ? TAX.kind[it.kind].label.toLowerCase() : isInactive(it) ? STATUS[it.status].label.toLowerCase() : TAX.domeniu[it.domeniu]?.short || '')
        : x.n;
      html += `<div class="ac-opt" role="option" id="ac-${i}" data-ac="${i}" aria-selected="false">${lead}<span class="l">${highlight(x.s.label, q)}</span><span class="r">${esc(right)}</span></div>`;
    });
    box.innerHTML = html;
  }
  box.hidden = false;
  input.setAttribute('aria-expanded', 'true');
}
function closeAC() {
  slot('ac').hidden = true;
  slot('q').setAttribute('aria-expanded', 'false');
  slot('q').removeAttribute('aria-activedescendant');
  acIndex = -1;
}
function moveAC(d) {
  if (!acItems.length) return;
  acIndex = (acIndex + d + acItems.length) % acItems.length;
  slot('ac').querySelectorAll('.ac-opt').forEach((el, i) => el.setAttribute('aria-selected', i === acIndex));
  const el = $(`#ac-${acIndex}`);
  el?.scrollIntoView({ block: 'nearest' });
  slot('q').setAttribute('aria-activedescendant', `ac-${acIndex}`);
}
function pickAC(i) {
  const s = acItems[i]?.s;
  if (!s) return;
  const input = slot('q');
  input.value = ''; state.q = '';
  closeAC();
  if (s.kind === 'item') {
    writeURL(); renderFilters(); renderResults();
    input.blur();
    state.p = s.val; writeURL(true); renderDetail();
    return;
  }
  if (s.kind === 'tema') state.d = s.val;
  else if (s.kind === 'tip' || s.kind === 'kw') {
    const key = s.kind === 'tip' ? 't' : 'kw';
    if (!listOf(key).includes(s.val)) state[key] = [...listOf(key), s.val].join(',');
  }
  else if (s.kind === 'oras') state.c = s.val;
  else if (s.kind === 'org') state.org = s.val;
  writeURL(); renderAll();
  input.blur();
}

/* ---------- keyboard navigation ---------- */
// j/k or ←/→ step through the results in the order shown; with the drawer open they step the open entry.
const resultEl = slug => [...slot('results').querySelectorAll('[data-open]')].find(el => el.dataset.open === slug);
function reveal(el) {
  const r = el.getBoundingClientRect(), top = slot('hdr').getBoundingClientRect().bottom;
  if (r.top < top || r.bottom > innerHeight) el.scrollIntoView({ block: 'center' });
}
function step(d) {
  const slugs = [...slot('results').querySelectorAll('[data-open]')].map(el => el.dataset.open);
  if (!slugs.length) return;
  const at = state.p || document.activeElement?.closest?.('[data-slot="results"] [data-open]')?.dataset.open;
  const i = slugs.indexOf(at);
  const next = slugs[i < 0 ? (d > 0 ? 0 : slugs.length - 1) : Math.min(Math.max(i + d, 0), slugs.length - 1)];
  const el = resultEl(next);
  if (state.p) {
    if (next === state.p) return;
    state.p = next; writeURL(); renderDetail();
    lastFocus = $('.stretch', el);  // closing the drawer returns focus to the last entry seen
  } else $('.stretch', el).focus({ preventScroll: true });
  reveal(el);
}
// o opens the entry's own site (or its archive): the open entry, else the focused one.
function openOriginal() {
  const slug = state.p || document.activeElement?.closest?.('[data-open]')?.dataset.open;
  const it = slug && DB.items.find(i => i.slug === slug);
  const href = it && extHref(it);
  if (href) window.open(href, '_blank', 'noopener');
}

/* ---------- rotating title ---------- */
// One span, text swapped while it is hidden; the motion lives in CSS (.out / .in, one effect per swap).
const TITLE_FX = ['rise', 'drop', 'flip', 'wipe', 'zoom', 'slide', 'spread'];
function rotateTitle() {
  const next = TITLES.filter(t => t !== title)[(Math.random() * (TITLES.length - 1)) | 0];
  const box = slot('brand'), el = box.firstElementChild;
  box.dataset.fx = TITLE_FX.filter(f => f !== box.dataset.fx)[(Math.random() * (TITLE_FX.length - 1)) | 0];
  el.classList.add('out');
  setTimeout(() => {
    el.textContent = next;
    el.classList.replace('out', 'in');
    el.offsetWidth; // commit the start position before transitioning back
    el.classList.remove('in');
  }, 420);
  title = next;
  syncTitle();
  setTimeout(rotateTitle, 3000 + Math.random() * 2000);
}

/* ---------- events ---------- */
function setFilter(key, val) {
  state[key] = state[key] === val ? '' : val;
  writeURL();
  renderFilters();
  renderResults();
}

document.addEventListener('click', e => {
  const opt = e.target.closest('[data-ac]');
  if (opt) { pickAC(+opt.dataset.ac); return; }
  if (!e.target.closest('[data-slot="search"]')) closeAC();
  if (e.target.closest('a.ext')) return;  // the project's own site: a plain link
  const open = e.target.closest('[data-open]');
  if (open && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) {
    e.preventDefault();
    state.p = open.dataset.open;
    writeURL(true);
    renderDetail();
    return;
  }
  const a = e.target.closest('[data-act]');
  if (!a || a.tagName === 'INPUT' || a.tagName === 'SELECT') return;
  const { act, key, val } = a.dataset;
  if (act === 'set') setFilter(key, val);
  else if (act === 'multi') {
    const l = listOf(key);
    state[key] = (l.includes(val) ? l.filter(x => x !== val) : [...l, val]).join(',');
    if (a.closest('[data-slot="drawer"]')) { state.p = ''; closeLayers(); syncTitle(); }
    writeURL(); renderFilters(); renderResults();
  } else if (act === 'unset') {
    if (key === 't' || key === 'kw') state[key] = listOf(key).filter(x => x !== val).join(',');
    else state[key] = '';
    writeURL(); renderAll();
  } else if (act === 'reset') { for (const k of FILTERS) state[k] = ''; writeURL(); renderAll(); }
  else if (act === 'kind') { state.k = val; state.o = defaultSort(); for (const k of FILTERS) if (k !== 'q') state[k] = ''; writeURL(); renderAll(); }
  else if (act === 'view') { state.v = val; writeURL(); renderResults(); }
  else if (act === 'fs') { store.set('ct.fs', val); applyPrefs(); }
  else if (act === 'theme') { store.set('ct.theme', val); applyPrefs(); }
  else if (act === 'sheet') { renderSheet(); openLayer(slot('sheet')); }
  else if (act === 'close') {
    if (!slot('drawer').hidden && state.p) { state.p = ''; writeURL(); }
    closeLayers();
    syncTitle();
  }
});
// Keep focus in the input while choosing a suggestion with the mouse.
slot('ac').addEventListener('mousedown', e => e.preventDefault());
document.addEventListener('change', e => {
  const { act, key } = e.target.dataset;
  if (act === 'sort') { state.o = e.target.value; seed = Math.random(); writeURL(); renderResults(); }
  else if (act === 'toggle') {
    // "Ascunde inactive" is checked by default, so its URL flag means the opposite.
    state[key] = key === 'ina' ? (e.target.checked ? '' : '1') : (e.target.checked ? '1' : '');
    writeURL(); renderFilters(); renderResults();
  }
});
document.addEventListener('toggle', e => {
  const id = e.target.dataset?.facet;
  if (!id) return;
  e.target.open ? closed.delete(id) : closed.add(id);
  store.set('ct.closed', [...closed]);
}, true);

let qTimer;
const qInput = slot('q');
qInput.addEventListener('input', () => {
  renderAC();
  clearTimeout(qTimer);
  qTimer = setTimeout(() => {
    const prev = query();
    state.q = qInput.value.trim();
    if (query() !== prev) { writeURL(); renderFilters(); renderResults(); }
  }, 150);
});
qInput.addEventListener('focus', renderAC);
qInput.addEventListener('blur', () => setTimeout(closeAC, 120));
qInput.addEventListener('keydown', e => {
  const open = !slot('ac').hidden;
  if (e.key === 'ArrowDown') { e.preventDefault(); open ? moveAC(1) : renderAC(); }
  else if (e.key === 'ArrowUp' && open) { e.preventDefault(); moveAC(-1); }
  else if (e.key === 'Enter') {
    e.preventDefault();
    if (open && acIndex >= 0) pickAC(acIndex);
    else { closeAC(); document.getElementById('results').scrollIntoView({ block: 'start' }); }
  } else if (e.key === 'Escape' && open) { e.stopPropagation(); closeAC(); }
});

document.addEventListener('keydown', e => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (e.key === 'Escape' && !slot('scrim').hidden) { $('[data-act="close"]', slot('drawer').hidden ? slot('sheet') : slot('drawer'))?.click(); return; }
  if ((e.key === '/' && !typing) || (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey))) {
    e.preventDefault();
    qInput.focus(); qInput.select();
  }
  if (e.key === 'Tab' && !slot('scrim').hidden) {
    // Keep focus inside the open layer.
    const layer = slot('drawer').hidden ? slot('sheet') : slot('drawer');
    const f = [...layer.querySelectorAll('a[href], button:not([disabled]), input, select, summary')];
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f.at(-1).focus(); }
    else if (!e.shiftKey && document.activeElement === f.at(-1)) { e.preventDefault(); f[0].focus(); }
  }
  if (typing || e.metaKey || e.ctrlKey || e.altKey || !slot('sheet').hidden || !DB) return;
  if (e.key === 'j' || e.key === 'ArrowRight') { e.preventDefault(); step(1); }
  else if (e.key === 'k' || e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
  else if (e.key === 'o') { e.preventDefault(); openOriginal(); }
});
// Touch: a horizontal swipe on the open entry steps to the next (left) or previous (right) one, like j/k.
let touch = null;
slot('drawer').addEventListener('touchstart', e => {
  // Rows that scroll sideways (link icons, chips) keep their own swipe.
  const scroller = e.composedPath().find(el => el instanceof Element && el !== slot('drawer') && slot('drawer').contains(el)
    && el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX !== 'visible');
  touch = e.touches.length === 1 && !scroller ? { x: e.touches[0].clientX, y: e.touches[0].clientY, t: Date.now() } : null;
}, { passive: true });
slot('drawer').addEventListener('touchend', e => {
  if (!touch) return;
  const dx = e.changedTouches[0].clientX - touch.x, dy = e.changedTouches[0].clientY - touch.y;
  if (Math.abs(dx) > 60 && Math.abs(dx) > 2 * Math.abs(dy) && Date.now() - touch.t < 600) step(dx < 0 ? 1 : -1);
  touch = null;
}, { passive: true });
window.addEventListener('popstate', () => { readURL(); renderAll(); renderDetail(); });

// Below 1024px the header is taller than one row; stick it so only the search and chips stay visible.
function fitHeader() {
  const hdr = slot('hdr'), search = slot('search');
  hdr.style.top = innerWidth < 1024 ? `-${search.offsetTop - parseFloat(getComputedStyle(search).marginTop)}px` : '0px';
}
new ResizeObserver(fitHeader).observe(slot('hdr'));

/* ---------- display preferences: text size and theme ---------- */
// The <head> script in index.html applies them before the first paint; this keeps the footer buttons and the
// browser's theme colour in step. "m" and "system" are the defaults and leave the attributes off.
const THEME_COLOR = { light: '#ffffff', dark: '#272822' };
function applyPrefs() {
  const fs = store.get('ct.fs', 'm'), theme = store.get('ct.theme', 'system'), root = document.documentElement;
  if (fs === 'm') delete root.dataset.fs; else root.dataset.fs = fs;
  if (theme === 'system') delete root.dataset.theme; else root.dataset.theme = theme;
  for (const b of document.querySelectorAll('[data-act="fs"]')) b.setAttribute('aria-pressed', String(b.dataset.val === fs));
  for (const b of document.querySelectorAll('[data-act="theme"]')) b.setAttribute('aria-pressed', String(b.dataset.val === theme));
  for (const m of document.querySelectorAll('meta[name="theme-color"]')) {
    m.dataset.orig ??= m.content;
    m.content = theme === 'system' ? m.dataset.orig : THEME_COLOR[theme];
  }
}
applyPrefs();

/* ---------- boot ---------- */
fetch(ROOT + 'data.json', { cache: 'no-cache' }).then(r => r.json()).then(db => {
  DB = db;
  const map = arr => Object.fromEntries(arr.map(x => [x.key, x]));
  TAX = { domeniu: map(db.taxonomy.domenii), tip: map(db.taxonomy.tipuri), kind: map(db.taxonomy.kinds), fel: map(db.taxonomy.fel) };
  // Paths in the data are relative to the site root; the address bar changes with pushState, so make them absolute.
  const abs = p => p ? ROOT + p : p;
  for (const it of db.items) {
    it.icon = abs(it.icon);
    if (it.img) it.img.src = abs(it.img.src);
    for (const l of it.links) l.icon = abs(l.icon);
    if (!STATUS[it.status]) it.status = 'neverificat';
    it._sort = norm(it.name).replace(/[^a-z0-9]/g, '');
    BY_SLUG.set(it.slug, it);
    it._orgs = it.authors.map(a => a.name);
    // What ties entries together by author: the slug of an organisation, else the written name.
    it._akeys = it.authors.map(a => a.org || norm(a.name));
    it._hay = norm([it.name, it.tagline, it.desc, ...it._orgs, it.domain, it.oras, TAX.domeniu[it.domeniu]?.label, ...tipLabels(it), ...it.keywords.map(kwLabel)].join(' '));
  }
  SUGGEST = buildSuggestions();
  readURL();
  if (current() && !pathSlug()) writeURL();  // an old ?p=<slug> link moves to the entry's own address
  if (DB.checked) slot('checked').textContent = `actualizat: ${DB.checked} · ${DB.items.length} resurse`;
  renderAll();
  renderDetail();
  fitHeader();
  setTimeout(rotateTitle, 3000 + Math.random() * 2000);
});
