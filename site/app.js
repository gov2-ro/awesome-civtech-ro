'use strict';
// The v2 browser code: it reads data.json with schemaVersion 2 (taxonomy v2 facets). It is a fork of site/app.js;
// scripts/build.py copies it over app.js in a v2 --site-dir, and it replaces site/app.js at the source cutover.

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
// The three status groups of STATUS, as the facet `st` offers them.
const STATE_GROUPS = [['activ', 'Activ'], ['inactiv', 'Inactiv'], ['neconfirmat', 'Neconfirmat']];
const SORTS = [['subiect', 'Pe subiecte'], ['az', 'A–Z'], ['top', 'Active și relevante'], ['relevanta', 'Relevanță'], ['nou', 'Apărute recent (prima urmă)'], ['recent', 'Actualizate recent'], ['random', 'Aleatoriu']];
// What the two date columns and their sorts mean. `since` is the first trace the profiler observed (a web archive capture,
// the creation of the code repository, or the first TLS certificate of the domain); it is not the date the project launched.
const DATE_HELP = {
  since: 'Prima urmă observată: arhivă web, depozit de cod sau certificat TLS. Nu este data lansării. Z = zile, L = luni, A = ani de atunci.',
  updated: 'Ultima actualizare observată: depozit de cod, feed, WordPress, sitemap, antet de server sau arhivă web. Z = zile, L = luni, A = ani de atunci.',
};
const SORT_HELP = { nou: DATE_HELP.since, recent: DATE_HELP.updated };
const MIN_Q = 3;
// ina=1 shows inactive projects (hidden by default; st=inactiv shows them too); a and s are kept for URLs but have no UI for now.
// dat (the relation to data, in the two groups of vocabulary.dataGroups: `cu-date` and `fara-date`) and st (the status group) are facets
// in the pattern of ent: comma-separated values, OR within the facet, under "Mai multe filtre".
// The facets hold comma-separated concept or area IDs: OR within a facet, AND between facets.
// d, t, kw and c are v1 bookmarks (domain, types, keywords, city): they keep their v1 meaning through each entry's
// `legacy` fields and show as their own pills; they are never translated into the new facets.
const DEFAULTS = { k: 'proiect', q: '', subj: '', topic: '', cap: '', fmt: '', source: '', coverage: '', area: '', purpose: '', tech: '', inst: '', ent: '', orgt: '', dat: '', st: '',
  d: '', t: '', kw: '', c: '', org: '', a: '', s: '', cod: '', civ: '', nou: '', ina: '', v: '', o: '', p: '' };
const FACETS = ['subj', 'topic', 'cap', 'fmt', 'source', 'coverage', 'area', 'purpose', 'tech', 'inst', 'ent', 'orgt', 'dat', 'st'];
const MORE = ['coverage', 'area', 'purpose', 'tech', 'inst', 'ent', 'orgt', 'dat', 'st'];  // under "Mai multe filtre"
const LEGACY = ['d', 't', 'kw', 'c'];
// The "classifications are proposals" notices (toolbar and detail panel); hidden for now. build.py has its own switch.
const DRAFT_NOTE = false;
const MULTI = [...FACETS, 't', 'kw'];
const FILTERS = ['q', ...FACETS, ...LEGACY, 'org', 'a', 's', 'cod', 'civ', 'nou', 'ina'];
// The concept scheme behind each facet (its title comes from the scheme's label in data.json).
const SCHEME_OF = { subj: 'subiect', topic: 'subiect', cap: 'functie', fmt: 'format', purpose: 'scop', tech: 'tehnologie', inst: 'institutie', orgt: 'organizatie' };
const FIELD = { subj: 'subjects', topic: 'topics', cap: 'capabilities', fmt: 'formats', area: 'areas', purpose: 'purposes', tech: 'technologies',
  inst: 'institutions', orgt: 'organisationTypes' };
// A first observed trace this recent counts as fresh; this recent again, as the newest (never as a confirmed launch).
const FRESH_DAYS = 183, NEWEST_DAYS = 60;

let DB = null, TAX = null, seed = Math.random();
const BY_SLUG = new Map(), CONCEPT = new Map(), AREA = new Map();
let title = TITLES[0];
const state = { ...DEFAULTS };
// First visit: "Subiect" is open. Once a visitor toggles a facet, their choice is stored and wins.
const closed = new Set(store.get('ct2.closed', ['cap', 'fmt', 'source', 'area', 'more', 'optiuni']));
let lastFocus = null;
const expandedOptions = new Set();

// The group of an entry's relation to data. data.json holds the groups (common.DATA_GROUPS in scripts/common.py): the code lists of each group, the empty
// value in `fara-date`. The browser keeps no list of its own, so the facet and the scope of /date/ cannot drift apart. dataRelation keeps the four codes.
const dataGroup = code => {
  const groups = DB.vocabulary.dataGroups || [];
  return (groups.find(g => g.codes.includes(code || '')) || groups.find(g => g.codes.includes('')))?.key;
};
const isInactive = it => STATUS[it.status].group === 'inactiv';
const listOf = key => state[key] ? state[key].split(',') : [];
// Inactive entries show when the visitor asks for them: ina=1, or a status facet that selects `inactiv` (st=inactiv).
const showsInactive = () => !!state.ina || listOf('st').includes('inactiv');
const kwLabel = k => k.replace(/-/g, ' ');
// The v1 words of an entry (category, types, keywords, town). Free-text search reads them, so that a v1 search still
// finds the same entries; they are never shown or used as classification.
const legacyWords = ({ legacy: l = {} }) => [TAX.dom[l.domeniu]?.label, ...(l.tips || []).map(t => TAX.tip[t]?.label),
  ...(l.keywords || []).map(kwLabel), l.oras].filter(Boolean);
const query = () => state.q.length >= MIN_Q ? state.q : '';
const label = id => CONCEPT.get(id)?.label || AREA.get(id)?.label || id;
// A facet's visible title: the scheme label, with the few that differ by tab or have no scheme.
function facetTitle(key) {
  if (key === 'cap' && state.k === 'organizatie') return 'Activități';
  return { topic: 'Subiect', area: 'Acoperire geografică', source: 'Surse de date', coverage: 'Acoperire', ent: 'Tip de intrare', dat: 'Date', st: 'Stare' }[key] || TAX.scheme[SCHEME_OF[key]]?.label || key;
}
// Match explicit coverage and its parents. National coverage does not imply a local assignment.
const areaUp = id => { const out = []; for (let a = AREA.get(id); a?.parent; a = AREA.get(a.parent)) out.push(a.parent); return out; };
const appliesIn = (it, id) => it.areas.some(a => a === id || areaUp(a).includes(id));
// One value of a facet, for one entry: subjects include the roots of its topics; a topic includes its narrower topics.
const has = (it, key, val) => key === 'area' ? appliesIn(it, val) : it._f[key].has(val);
function ancestors(id) {
  const out = [];
  for (let todo = [...(CONCEPT.get(id)?.broader || [])]; todo.length;) {
    const b = todo.pop();
    if (!out.includes(b)) { out.push(b); todo.push(...(CONCEPT.get(b)?.broader || [])); }
  }
  return out;
}

/* ---------- URL state ---------- */
// Projects read best grouped by subject; the short org/resource lists read best flat.
const defaultSort = () => state.k === 'proiect' ? 'subiect' : 'az';
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
  if (state.source) state.source = [...new Set(listOf('source').map(sourceLabel))].join(',');
  if (!state.p) state.p = pathSlug();
  // An entry from the address alone (no kind in the query) opens on its own tab: an organisation, not the project list.
  if (state.p && !u.has('k')) { const it = BY_SLUG.get(state.p); if (it) state.k = it.kind; }
  if (state.o === 'domeniu') state.o = 'subiect';  // a v1 bookmark of the grouped view
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
  for (const key of FACETS) if (skip !== key && state[key] && !listOf(key).some(v => has(it, key, v))) return false;
  const old = it.legacy || {};
  if (skip !== 'd' && state.d && old.domeniu !== state.d) return false;
  if (skip !== 't' && state.t && !listOf('t').some(t => (old.tips || []).includes(t))) return false;
  if (skip !== 'kw' && state.kw && !listOf('kw').some(k => (old.keywords || []).includes(k))) return false;
  if (skip !== 'c' && state.c && old.oras !== state.c) return false;
  if (skip !== 'org' && state.org && !it._orgs.includes(state.org)) return false;
  if (skip !== 'a' && state.a && it.coverageLevel !== state.a) return false;
  if (skip !== 's' && state.s && STATUS[it.status].group !== state.s) return false;
  if (skip !== 'cod' && state.cod && !it.code) return false;
  if (skip !== 'civ' && state.civ && !it.civictech) return false;
  if (skip !== 'nou' && state.nou && !isFresh(it)) return false;
  // The status facet counts its own options without this rule, or `inactiv` would show 0 and could not be chosen.
  if (skip !== 'ina' && skip !== 'st' && !showsInactive() && isInactive(it)) return false;
  const q = query();
  if (q) {
    const terms = norm(q).split(/\s+/).filter(Boolean);
    if (!terms.every(t => it._hay.includes(t))) return false;
  }
  return true;
}
const kindItems = () => DB.items.filter(i => i.kind === state.k);
// Entries per option of one facet: the other facets apply, this facet's own selection does not. Each entry counts once
// per option, also when several of its concepts lead to that option.
function facetCounts(key, options) {
  const base = DB.items.filter(i => matches(i, key)), c = {};
  for (const o of options) c[o] = base.filter(i => has(i, key, o)).length;
  return c;
}
const activeFilterCount = () => ['d', 'c', 'org', 'a', 's', 'cod', 'civ', 'nou', 'ina'].filter(k => state[k]).length
  + MULTI.reduce((n, k) => n + listOf(k).length, 0);
const rank = it => ({ activ: 0, neconfirmat: 1, inactiv: 2 })[STATUS[it.status].group];
const byName = (a, b) => a._sort.localeCompare(b._sort);
// Last sign of life: the last update, or the first observed trace when that is later. A recent first trace thus
// sorts like a recent update. Entries with neither go last.
const lastSign = it => [it.updated, isNewest(it) ? it.since : ''].sort().at(-1) || '';
// "Active și relevante": the build's relevance score, discounted by time since the last sign of life
// (half-life ~8 months; unknown counts as old), plus a small bump for a first trace in the last 60 days.
function topScore(it) {
  const d = lastSign(it);
  const recency = d ? Math.exp(-daysSince(d) / 365) : .25;
  return it.score * (.5 + .5 * recency) + (isNewest(it) ? 8 : 0);
}
function sorted(list) {
  if (state.o === 'random') {
    const r = it => Math.sin(it.id * 9301 + seed * 49297) % 1;
    return [...list].sort((a, b) => r(a) - r(b));
  }
  if (state.o === 'top') return [...list].sort((a, b) => topScore(b) - topScore(a) || byName(a, b));
  if (state.o === 'subiect') return [...list].sort((a, b) => rank(a) - rank(b) || lastSign(b).localeCompare(lastSign(a)) || byName(a, b));
  if (state.o === 'relevanta') return [...list].sort((a, b) => b.score - a.score || byName(a, b));
  // Entries with no observed first trace go last.
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
// An entity type that differs from its tab says so (a publication on the resources tab); the usual one says nothing.
const entLabel = it => it.entityType !== it.kind && it.entityType !== 'organizatie' ? TAX.ent[it.entityType]?.label || '' : '';
// Local entries name their places. With a place filter on, a national entry says that it applies there as national.
const placeLabel = it => it.coverageLevel === 'local'
  ? it.areas.filter(a => /^(localitate|judet):/.test(a)).map(label).join(', ') || 'Local'
  : state.area && it.coverageLevel !== 'necunoscut' ? TAX.cov[it.coverageLevel]?.label || '' : '';
// About three useful classifications per row: a topic, a format, a capability. The detail panel has them all.
const badgeIds = it => [['topic', it.topics[0]], ['fmt', it.formats[0]], ['cap', it.capabilities[0]]].filter(([, id]) => id);
const badgesHTML = it => badgeIds(it).map(([key, id]) => `<span title="${esc(facetTitle(key))}"><span class="vh">${esc(facetTitle(key))}: </span>${esc(label(id))}</span>`).join('');
function metaLine(it, withDomain, withFormat = false) {
  const st = STATUS[it.status];
  const parts = [...new Set([entLabel(it), withFormat && it.formats[0] ? label(it.formats[0]) : '', placeLabel(it)])];
  if (withDomain) parts.unshift(it.primarySubject ? label(it.primarySubject) : '');
  let html = parts.filter(Boolean).map(esc).join(' · ');
  if (st.group !== 'activ') html += ` <span class="status-tag ${st.cls}">· ${st.label}</span>`;
  else if (it.stale) html += ` <span class="status-tag warn">· neactualizat din ${it.stale}</span>`;
  return html;
}
const statusDot = it => `<span class="dot ${STATUS[it.status].cls}" title="${STATUS[it.status].label}"></span>`;
// A code link says that the source is public; a licence is a separate fact (the detail panel shows it when known).
const codeTag = it => it.code ? `<span class="code-tag" title="Cod sursă public">${ICON.code}cod</span>` : '';
// "Apărut recent" says what was observed: the first trace of the entry on the web is recent. It does not say when it launched.
const newTag = it => !isFresh(it) ? ''
  : `<span class="code-tag new-tag${isNewest(it) ? ' launch' : ''}" title="${esc(sinceTitle(it))}">apărut recent</span>`;
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
// "Fresh": the first observed trace is less than FRESH_DAYS old, by the same date the "Prima urmă" column shows.
const isFresh = it => !!it.since && daysSince(it.since) < FRESH_DAYS;
const isNewest = it => !!it.since && daysSince(it.since) < NEWEST_DAYS;
const ago = d => daysSince(d) < 1 ? 'azi' : `acum ${span(daysSince(d))}`;
const ageShort = it => it.since ? shortSpan(daysSince(it.since)) : '';
const updatedShort = it => it.updated ? shortSpan(daysSince(it.updated)) : '';
const sinceLabel = it => it.since ? ago(it.since) : '';
const updatedLabel = it => it.updated ? ago(it.updated) : '';
const UPDATED_SRC = { cod: 'ultimul push în depozitul de cod', feed: 'cel mai nou articol din feed', wordpress: 'ultima modificare în WordPress',
  sitemap: 'sitemap', server: 'antetul Last-Modified', arhiva: 'ultima arhivare Wayback' };
const SINCE_SRC = { arhiva: 'prima arhivare Wayback', cod: 'crearea depozitului de cod', certificat: 'primul certificat TLS al domeniului' };
const ageTitle = it => !it.since ? 'Necunoscut' : it.sinceSrc ? `${it.since} · după ${SINCE_SRC[it.sinceSrc] || it.sinceSrc}` : it.since;
const sinceTitle = it => it.since ? `Prima urmă observată ${sinceLabel(it)}: ${ageTitle(it)}. Nu este data lansării.` : 'Nicio urmă observată';
const updatedTitle = it => it.updated ? `${it.updated} · după ${UPDATED_SRC[it.updatedSrc] || it.updatedSrc}` : 'Necunoscut';
// The list columns show "13A", "2L", "9Z": the column headers explain the letters (DATE_HELP), and screen readers get the words.
const sideDate = (short, words) => `<span aria-hidden="true">${esc(short || '—')}</span><span class="vh">${esc(words)}</span>`;

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
      <div class="meta">${metaLine(it, withDomain, true)}</div>
      <h3>${nameLink(it)}</h3>
      ${blurb(it) ? `<p class="tagline">${esc(blurb(it))}</p>` : ''}
      <div class="foot">${statusDot(it)}${extLink(it, `<span class="dom">${esc(it.domain)}</span>`)}${newTag(it)}${codeTag(it)}${inventoryTag(it)}</div>
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
  const dates = [sinceLabel(it) && `prima urmă ${sinceLabel(it)}`, updatedLabel(it) && `actualizat ${updatedLabel(it)}`].filter(Boolean).join(' · ');
  return `<div class="row${isInactive(it) ? ' inactive' : ''}" data-open="${it.slug}"${hint(it)}>
    ${thumb(it)}
    <div class="row-main">
      <div class="row-title">${logo(it)}${nameLink(it)} ${statusDot(it)} ${newTag(it)} ${codeTag(it)} ${extLink(it, '', 'ext-m')}</div>
      ${blurb(it) ? `<div class="row-tag">${esc(blurb(it))}</div>` : ''}
      ${desc ? `<div class="row-desc">${esc(clip(desc, 160))}</div>` : ''}
      ${badgeIds(it).length || it.inventory?.count ? `<div class="row-kw">${badgesHTML(it)}${inventoryTag(it)}</div>` : ''}
      <div class="meta meta-m">${[metaLine(it, withDomain), dates && esc(dates)].filter(Boolean).join(' · ')}</div>
    </div>
    <div class="row-side row-links">${rowLinks(it)}</div>
    <div class="row-side" title="${esc(sinceTitle(it))}">${sideDate(ageShort(it), it.since ? `prima urmă observată ${sinceLabel(it)}` : 'prima urmă necunoscută')}</div>
    <div class="row-side${it.updatedSrc === 'arhiva' ? ' faint' : ''}" title="${esc(updatedTitle(it))}">${sideDate(updatedShort(it), it.updated ? `actualizat ${updatedLabel(it)}` : 'actualizare necunoscută')}</div>
    <div class="row-side">${extLink(it, `<span class="dom">${esc(it.domain)}</span>`)}</div>
  </div>`;
}
const LIST_HEAD = `<div class="list-head" aria-hidden="true"><span>Proiect</span><span>Linkuri</span><span title="${esc(DATE_HELP.since)}">Prima urmă</span><span title="${esc(DATE_HELP.updated)}">Actualizat</span><span>Site</span></div>`;

/* ---------- filters ---------- */
function renderTabs() {
  // Counters show what is alive, not what was ever catalogued.
  const c = {};
  for (const it of DB.items) if (!isInactive(it)) c[it.kind] = (c[it.kind] || 0) + 1;
  slot('tabs').innerHTML = DB.vocabulary.kinds.map(k =>
    `<button class="tab" data-act="kind" data-val="${k.key}" ${state.k === k.key ? 'aria-current="page"' : ''}>${esc(k.label)}<span class="n">${c[k.key] || 0}</span></button>`
  ).join('') + (DB.inventoryPreview ? '<a class="tab" href="date/">Inventar de date ↗</a>' : '');
}

// The options of a facet on this tab: values some entry here has, plus the selected ones. Hidden when unused.
function optionsOf(key) {
  const mine = kindItems(), sel = listOf(key), seen = new Set(sel);
  if (key === 'area') for (const it of mine) for (const a of it.areas) [a, ...areaUp(a)].forEach(x => seen.add(x));
  else if (key === 'source' || key === 'coverage') for (const it of mine) for (const v of it._f[key]) seen.add(v);
  else if (key === 'ent') for (const it of mine) seen.add(it.entityType);
  else for (const it of mine) for (const v of it._f[key]) seen.add(v);
  let opts = [...seen];
  // Topics follow the chosen subjects: only the branches under them, plus what is already selected.
  if (key === 'topic' && state.subj) opts = opts.filter(t => sel.includes(t) || listOf('subj').some(s => ancestors(t).includes(s)));
  if (key === 'subj') return opts;
  if (key === 'ent') return DB.vocabulary.entityTypes.map(t => t.key).filter(x => seen.has(x));
  const n = {};
  for (const it of mine) for (const v of it._f[key]) n[v] = (n[v] || 0) + 1;
  return opts.sort((a, b) => (n[b] || 0) - (n[a] || 0) || label(a).localeCompare(label(b), 'ro'));
}
const COVERAGE_LABELS = { national: 'Totaluri naționale', 'national-local': 'Național · date pe județe sau localități',
  local: 'Local · orașe sau județe', international: 'Internațional',
  'national-unknown': 'Național · detaliere neverificată', necunoscut: 'Acoperire necunoscută' };
const DETAIL_LABELS = { 'agregat-national': 'Totaluri naționale', judete: 'Pe județe', localitati: 'Pe localități', 'judete-localitati': 'Pe județe și localități' };
const coverageKey = it => it.coverageLevel === 'national'
  ? (it.dataDetail === 'agregat-national' ? 'national' : it.dataDetail ? 'national-local' : 'national-unknown') : it.coverageLevel;
// Keep the recorded providers intact; compact labels group related providers in the UI.
const SOURCE_LABELS = {
  'Institutul Național de Statistică (INS)': 'INS',
  'Ministerul Dezvoltării (MDLPA)': 'MDLPA',
  'Administrația Prezidențială': 'Adm. Prez',
  'Monitorul Oficial': 'MO',
  'Camera Deputaților': 'Parlament', 'Senatul României': 'Parlament',
  'CDep': 'Parlament', 'Senat': 'Parlament',
  'Banca Națională a României (BNR)': 'BNR',
  'Oficiul Național al Registrului Comerțului (ONRC)': 'ONRC',
  'Autoritatea pentru Digitalizarea României (ADR)': 'ADR',
  'Guvernul României': 'Guvern', 'Consiliul Uniunii Europene': 'Consiliul UE',
};
const sourceLabel = name => SOURCE_LABELS[name] || name;
const sourceGroups = sources => {
  const groups = new Map();
  for (const s of sources) {
    const name = sourceLabel(s.name);
    if (!groups.has(name)) groups.set(name, { name, names: [], evidence: new Set() });
    groups.get(name).names.push(s.name);
    groups.get(name).evidence.add(s.evidence);
  }
  return [...groups.values()];
};
const optLabel = (key, v) => key === 'coverage' ? COVERAGE_LABELS[v] || v : key === 'ent' ? TAX.ent[v]?.label || v
  : key === 'dat' ? TAX.dat[v]?.label || v : key === 'st' ? STATE_GROUPS.find(([g]) => g === v)?.[1] || v : label(v);

// A facet with a selection stays open, so that its choice is never hidden.
function facet(id, title, body, selected = false) {
  return `<details class="facet" data-facet="${id}" ${closed.has(id) && !selected ? '' : 'open'}><summary><span class="kicker">${title}</span></summary>${body}</details>`;
}
function tagsHTML(key, options, counts) {
  const sel = listOf(key);
  options = [...options].sort((a, b) => (counts[b] || 0) - (counts[a] || 0) || optLabel(key, a).localeCompare(optLabel(key, b), 'ro'));
  const hidden = options.filter(v => (counts[v] || 0) <= 3 && !sel.includes(v));
  const shown = expandedOptions.has(key) ? options : options.filter(v => !hidden.includes(v));
  return `<div class="tags" role="group" aria-label="${esc(facetTitle(key))}">${shown.map(val => {
    const on = sel.includes(val), n = counts[val] || 0, def = CONCEPT.get(val)?.def;
    return `<a class="tag" role="button" ${!n && !on ? 'aria-disabled="true"' : 'href="#"'} data-act="multi" data-key="${key}" data-val="${esc(val)}" aria-pressed="${on}"${def ? ` title="${esc(def)}"` : ''}>${esc(optLabel(key, val))}<span class="n">${n}</span></a>`;
  }).join(' ')}</div>${hidden.length ? `<p class="fmore"><button class="linkbtn" data-act="more-options" data-key="${key}" aria-expanded="${expandedOptions.has(key)}">${expandedOptions.has(key) ? 'Mai puține' : `Mai multe (${hidden.length})`}</button></p>` : ''}`;
}
// A facet needs a control when it offers a choice: two or more options, or a selection to undo.
const useful = (key, options) => options.length > 1 || listOf(key).length > 0;
function facetsHTML() {
  const out = [];
  for (const key of ['subj', 'cap', 'source', 'fmt']) {
    const options = optionsOf(key);
    if (!useful(key, options)) continue;
    out.push(facet(key, facetTitle(key), tagsHTML(key, options, facetCounts(key, options)), !!state[key]));
  }
  const more = MORE.filter(k => k !== 'orgt' || state.k === 'organizatie').map(key => {
    const options = optionsOf(key);
    return useful(key, options) ? `<div class="subfacet"><p class="kicker">${esc(facetTitle(key))}</p>${tagsHTML(key, options, facetCounts(key, options))}</div>` : '';
  }).join('');
  if (more) out.push(facet('more', 'Mai multe filtre', more, MORE.some(k => state[k])));

  const has = (pred) => kindItems().some(pred);
  const toggles = [];
  const toggle = (key, text, checked, n, disabled = false) => toggles.push(`<label class="toggle"><input type="checkbox" data-act="toggle" data-key="${key}" ${checked ? 'checked' : ''}${disabled ? ' disabled' : ''}><span class="l">${text}</span>${n != null ? `<span class="n">${n}</span>` : ''}</label>`);
  if (has(i => i.code) && has(i => !i.code)) toggle('cod', 'Doar cu cod sursă public', state.cod, DB.items.filter(i => matches(i, 'cod') && i.code).length);
  if (has(isFresh) && has(i => !isFresh(i))) toggle('nou', 'Doar proiecte apărute recent', state.nou, DB.items.filter(i => matches(i, 'nou') && isFresh(i)).length);
  // With st=inactiv the status facet already shows the inactive entries: the toggle is off and cannot hide them.
  if (has(isInactive)) toggle('ina', 'Ascunde proiecte inactive', !showsInactive(), null, listOf('st').includes('inactiv'));
  if (has(i => i.civictech) && has(i => !i.civictech)) toggle('civ', 'Doar proiecte civtech', state.civ, DB.items.filter(i => matches(i, 'civ') && i.civictech).length);
  if (toggles.length) out.push(facet('optiuni', 'Opțiuni', toggles.join('')));
  out.push('<p class="fhelp">În același filtru: oricare dintre opțiuni. Între filtre: toate condițiile. Numerele arată câte intrări are fiecare opțiune, cu celelalte filtre aplicate.</p>');
  return out.join('');
}

function renderChips() {
  const subj = optionsOf('subj').filter(v => !CONCEPT.get(v)?.broader.length || listOf('subj').includes(v)), c = facetCounts('subj', subj), sel = listOf('subj');
  subj.sort((a, b) => c[b] - c[a] || label(a).localeCompare(label(b), 'ro'));
  const total = DB.items.filter(i => matches(i, 'subj')).length;
  const chip = (val, text, n, on) => `<button class="chip" data-act="${val ? 'multi' : 'clear'}" data-key="subj" data-val="${esc(val)}" aria-pressed="${on}">${esc(text)}<span class="n">${n || 0}</span></button>`;
  slot('chips').innerHTML = chip('', 'Toate', total, !sel.length) + subj.filter(v => c[v] > 3 || sel.includes(v)).map(v => chip(v, label(v), c[v], sel.includes(v))).join('');
}

function renderToolbar(n) {
  const pills = [];
  const pill = (key, val, text) => pills.push(`<button class="pill" data-act="unset" data-key="${key}" data-val="${esc(val)}" aria-label="Elimină filtrul ${esc(text)}">${esc(text)}${ICON.x}</button>`);
  for (const key of FACETS) for (const v of listOf(key)) pill(key, v, `${facetTitle(key)}: ${optLabel(key, v)}`);
  // v1 bookmarks keep their old meaning and say so.
  if (state.d) pill('d', '', `Domeniu (v1): ${TAX.dom[state.d]?.short || state.d}`);
  for (const t of listOf('t')) pill('t', t, `Tip (v1): ${TAX.tip[t]?.label || t}`);
  for (const k of listOf('kw')) pill('kw', k, `#${kwLabel(k)} (v1)`);
  if (state.c) pill('c', '', `Oraș (v1): ${state.c}`);
  if (state.org) pill('org', '', state.org);
  if (state.a) pill('a', '', TAX.cov[state.a]?.label || state.a);
  if (state.s) pill('s', '', state.s);
  if (state.cod) pill('cod', '', 'Cod public');
  if (state.civ) pill('civ', '', 'Civtech');
  if (state.nou) pill('nou', '', 'Apărute recent');
  if (state.ina) pill('ina', '', 'Inclusiv inactive');
  if (query()) pill('q', '', `„${state.q}”`);
  const view = currentView();
  slot('toolbar').innerHTML = `
    ${DB.draft && DRAFT_NOTE ? '<p class="draft-note">Previzualizare: clasificările sunt propuneri, încă neacceptate de editor.</p>' : ''}
    <span class="count"><b>${n}</b> ${n === 1 ? 'rezultat' : 'rezultate'}</span>
    ${pills.length ? `<span class="active">${pills.join('')}</span><button class="linkbtn" data-act="reset">Șterge filtrele</button>` : ''}
    <span class="tool-right">
      <label class="sr" for="sort">Ordonare</label>
      <select class="select" id="sort" data-act="sort">${SORTS.map(([k, l]) => `<option value="${k}" ${state.o === k ? 'selected' : ''}${SORT_HELP[k] ? ` title="${esc(SORT_HELP[k])}"` : ''}>${l}</option>`).join('')}</select>
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
  } else if (state.o === 'subiect' && state.subj) {
    // Filtered by subject: one flat list under the chosen subjects, so that an entry found through a secondary
    // subject never hides under an unrelated primary heading.
    const head = listOf('subj').map(label).join(' sau ');
    html = `<section class="group" aria-labelledby="g-subj">
      <div class="group-head"><h2 id="g-subj">${esc(head)}</h2><span class="n">${list.length}</span><p>inclusiv intrările pentru care este un subiect secundar</p></div>
      ${block(sorted(list), true)}</section>`;
  } else if (state.o === 'subiect') {
    // Unfiltered: every entry once, under its primary subject; entries without one come last.
    const groups = [...DB.vocabulary.subjectOrder.map(id => [id, label(id), '']), ['', 'Fără subiect stabilit', 'clasificare incompletă: sursele nu stabilesc subiectul']];
    html = groups.map(([id, text, hint], n) => {
      const items = sorted(list.filter(it => (it.primarySubject || '') === id));
      if (!items.length) return '';
      return `<section class="group" aria-labelledby="g-${n}">
        <div class="group-head"><h2 id="g-${n}">${esc(text)}</h2><span class="n">${items.length}</span>${hint ? `<p>${esc(hint)}</p>` : ''}</div>
        ${block(items, false)}</section>`;
    }).join('');
  } else {
    html = block(sorted(list), true);
  }
  slot('results').innerHTML = html;
}

// Re-rendering the filters replaces their buttons; give the focus back to the same control, wherever it was.
function renderFilters() {
  const a = document.activeElement, where = a?.closest?.('[data-slot]')?.dataset.slot;
  const sel = a?.dataset?.act && ['act', 'key', 'val'].filter(k => k in a.dataset).map(k => `[data-${k}="${CSS.escape(a.dataset[k])}"]`).join('');
  // The toggle event comes later than a quick click after opening a facet: read the open state from the page itself.
  for (const d of document.querySelectorAll(`[data-slot="${where === 'sheet' ? 'sheet' : 'side'}"] details[data-facet]`)) d.open ? closed.delete(d.dataset.facet) : closed.add(d.dataset.facet);
  slot('side').innerHTML = facetsHTML();
  renderChips();
  if (!slot('sheet').hidden) renderSheet();
  if (sel && where && !document.contains(a)) slot(where)?.querySelector(sel)?.focus({ preventScroll: true });
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

/* ---------- title, address and share metadata ---------- */
// scripts/build.py writes a head for the home page and one for each entry page. Opening or closing an entry changes the
// address in the page, so the tags that name the address follow it. The home values live here because a page loaded at an
// entry's address carries that entry's head: keep them in step with site/index.html (scripts/check_preview.py compares them).
const HOME = { share: 'Colecție proiecte CivTech', text: 'Director de instrumente civice, date deschise și proiecte de bună guvernare din România.',
  image: 'img/share.png', w: 1106, h: 558, alt: 'Colecție proiecte CivTech — civtech.gov2.ro' };
const NO_TEXT = 'Colecție de instrumente civice, date deschise și proiecte de bună guvernare din România.';  // an entry with no text, as in build.py
const SITE = ($('link[rel="canonical"]')?.href || '').replace(new RegExp(`(${KINDS})/[^/]*/?$`), '');
const META = [['link[rel="canonical"]', 'href', 'url'], ['meta[property="og:url"]', 'content', 'url'], ['meta[name="description"]', 'content', 'text'],
  ['meta[property="og:title"]', 'content', 'share'], ['meta[name="twitter:title"]', 'content', 'share'],
  ['meta[property="og:description"]', 'content', 'text'], ['meta[name="twitter:description"]', 'content', 'text'],
  ['meta[property="og:image"]', 'content', 'image'], ['meta[name="twitter:image"]', 'content', 'image'],
  ['meta[property="og:image:width"]', 'content', 'w'], ['meta[property="og:image:height"]', 'content', 'h'], ['meta[property="og:image:alt"]', 'content', 'alt']];
let metaFor = pathSlug();  // the entry whose head the page holds now ('' for the home page)
function syncMeta(it) {
  const pic = it?.img && it.img.kind !== 'logo' ? it.img : null;
  const v = it
    ? { url: `${SITE}${it.kind}/${it.slug}/`, share: `${it.name} — CivTech România`, text: clip(it.desc || it.tagline || '', 200) || NO_TEXT,
      image: SITE + (pic ? pic.src.slice(ROOT.length) : HOME.image), w: pic ? pic.w : HOME.w, h: pic ? pic.h : HOME.h, alt: it.name }
    : { url: SITE, share: HOME.share, text: HOME.text, image: SITE + HOME.image, w: HOME.w, h: HOME.h, alt: HOME.alt };
  for (const [sel, attr, key] of META) $(sel)?.setAttribute(attr, v[key]);
}
function syncTitle() {
  const it = current();
  document.title = it ? `${it.name} — ${title}` : title;
  if ((it?.slug || '') !== metaFor) { metaFor = it?.slug || ''; syncMeta(it); }
}

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
  // The licence has its own row: public code is not necessarily open source.
  const parts = [r.stars != null && `★ ${r.stars.toLocaleString('ro-RO')}`, n(r.forks, 'fork', 'forks'), n(r.issues, 'issue', 'issues'),
    n(r.commits, 'commit', 'commits'), n(r.contributors, 'contribuitor', 'contribuitori'), r.last && `ultimul commit ${r.last}`,
    r.language, r.archived && 'arhivat'].filter(Boolean).map(esc);
  const same = it.code && it.code.replace(/\/+$/, '').toLowerCase() === r.url.toLowerCase();
  if (!same) parts.unshift(`<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>`);
  return ['Cod', `<span class="repo mono">${parts.join(' · ')}</span>`];
}

// An attribution that is an organisation of the catalogue opens its page; any other name is plain text.
const authorLink = a => a.org && BY_SLUG.has(a.org)
  ? `<a href="${hrefFor(a.org)}" data-open="${esc(a.org)}">${esc(a.name)}</a>` : esc(a.name);
// Attributions by role: an accepted role gets its own heading ("Creat de"); an unconfirmed one stays neutral, because
// the old `autor` cell never said who created, published, funded or maintains an entry.
function attributionRows(it) {
  const groups = new Map();
  for (const a of it.attributions) {
    const head = a.accepted ? TAX.pred[a.role]?.label || a.role : 'Atribuire';
    groups.set(head, [...(groups.get(head) || []), a]);
  }
  return [...groups].map(([head, as]) => [head, as.map(authorLink).join(' · ') + (head === 'Atribuire' ? ' <span class="muted small">· rol neconfirmat</span>' : '')]);
}
const MAX_WORKS = 15;
// Entries (projects and resources) with the same attribution as `it`; for an organisation, the entries that name it.
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
  const title = it.kind === 'organizatie' ? 'Proiecte și resurse atribuite' : 'Cu aceeași atribuire';
  const more = works.length - MAX_WORKS;
  return `<div class="related"><p class="kicker">${title} · ${works.length}</p>${works.slice(0, MAX_WORKS).map(r => row(r, true)).join('')}${more > 0 ? `<p class="small muted">… și încă ${more}</p>` : ''}</div>`;
}

// "Semnalează o problemă": three ways to tell us, each prefilled with the entry's name and address. data/site.json
// (copied into data.json as `site`) says which ones exist: an empty address hides its option.
function flagHTML(it) {
  // The entry's row in the Sheet: the v2 tab once it exists, until then the v1 tab that still holds its text (see build.py).
  const site = DB.site || {}, { tab, row } = it.sheet || {};
  const subject = `Problemă la „${it.name}” (${it.slug})`;
  const body = `Pagina: ${location.origin}${entryPath(it.slug)}\n${tab ? `În tabel: fila ${tab}, rândul ${row}\n` : ''}\nCe nu e corect sau lipsește?\n`;
  const q = `${encodeURIComponent(subject)}`, b = `${encodeURIComponent(body)}`;
  const opts = [
    site.sheet && tab && site.tabs?.[tab] != null && [`${site.sheet}#gid=${site.tabs[tab]}&range=A${row}`, 'Corectează în tabel',
      `Deschide rândul ${row} din fila „${tab}”. Modifici direct; schimbarea e verificată înainte să apară pe site.`],
    site.email && [`mailto:${site.email}?subject=${q}&body=${b}`, 'Trimite un e-mail', 'Mesajul pornește cu numele și adresa paginii.'],
    site.issues && [`${site.issues}?title=${q}&body=${b}`, 'Deschide o problemă pe GitHub', 'Cere cont GitHub; discuția e publică.'],
  ].filter(Boolean);
  if (!opts.length) return '';
  return `<details class="flag"><summary>Semnalează o problemă</summary>
    <p>Ceva lipsește sau nu e corect aici? Alege varianta care îți vine mai la îndemână:</p>
    <ul>${opts.map(([href, label, note]) => `<li><a href="${esc(href)}" target="_blank" rel="noopener">${label}</a><span>${esc(note)}</span></li>`).join('')}</ul>
  </details>`;
}

/* ---------- data inventory preview ---------- */
const INV_CACHE = new Map(), INV_STATE = new Map();
let inventoryIntent = '';
const INV_ROLES = { 'camp-date': 'Date', dimensiune: 'Dimensiuni', 'parametru-api': 'Intrări API',
  'corp-cerere': 'Conținut cerere API', 'camp-raspuns': 'Răspunsuri API', 'model-de-date': 'Modele de date',
  'camp-dictionar': 'Dicționar de date', 'coloana-sql': 'Coloane în baza de date', 'camp-model': 'Câmpuri de model', 'cod-enumerare': 'Coduri și valori',
  'camp-exemplu': 'Exemple în documentație', masura: 'Măsuri', 'camp-folosit-de-pagina': 'Folosite de pagină', 'colectie-cu-chei': 'Colecții indexate' };
const INV_BASIS = { schema: 'Descris în schemă', metadata: 'Descris în metadate', sample: 'Observat în date', header: 'Antet CSV',
  code: 'Declarat în codul sursă', table: 'Antet de tabel HTML', doctable: 'Declarat în tabel de documentație', doctext: 'Declarat în textul documentației',
  pagecode: 'Folosit în codul paginii', docexample: 'Exemplu în documentație', apidoc: 'Declarat în documentația API', doclist: 'Declarat în lista de coloane din documentație', dblist: 'Declarat în lista bazei de date', editor: 'adăugat de editor' };
const INV_LOCATIONS = { query: 'filtru', path: 'în URL', header: 'în antet', cookie: 'cookie' };
const INV_TYPES = { string: 'Text', integer: 'Număr întreg', number: 'Număr', boolean: 'Da / Nu', null: 'Valoare nulă', text: 'Text în tabel',
  'forma-numerica': 'Arată ca număr (text)', 'forma-de-data': 'Arată ca dată (text)',
  object: 'Obiect', array: 'Listă', geo: 'Arie geografică', time: 'Perioadă', indicator: 'Indicator', unit: 'Unitate de măsură' };
function inventoryState(slug) {
  if (!INV_STATE.has(slug)) {
    const q = query(), keywords = norm(BY_SLUG.get(slug)?.inventory?.keywords);
    INV_STATE.set(slug, { q: q && norm(q).split(/\s+/).every(t => keywords.includes(t)) ? q : '', role: '', source: '', limit: 8 });
  }
  return INV_STATE.get(slug);
}
const inventoryTag = it => it.inventory?.count ? `<button class="inventory-tag" data-act="inventory" data-val="${esc(it.slug)}" title="Inventar parțial de date" aria-label="Deschide inventarul de date pentru ${esc(it.name)}">Inventar de date</button>` : '';
function inventoryHTML(it) {
  const inv = it.inventory;
  if (!inv) return '';
  const docs = inv.docs.length ? `<nav class="inv-docs" aria-label="Documentația proiectului">${inv.docs.map(d => `<a href="${esc(d.url)}" target="_blank" rel="noopener" title="${esc(d.title)}">${esc(clip(d.label, 48))}${ICON.out}</a>`).join('')}</nav>` : '';
  return `<section class="d-inventory" data-inventory-root="${esc(it.slug)}" aria-labelledby="inventory-title">
    <div class="inv-heading"><h3 id="inventory-title">Date &amp; metodă</h3>${inv.count ? '<span class="inv-status">Inventar parțial</span>' : ''}</div>
    ${inv.count ? `<p class="inv-intro">${plural(inv.count, 'câmp sau parametru', 'câmpuri și parametri')} · ${plural(inv.sources, 'fișier consultat', 'fișiere consultate')}</p>
      <p class="inv-note">Extrase automat din sursele de mai jos. Proiectul poate folosi și alte date.</p>
      ${inv.stale ? `<p class="inv-note inv-stale">${plural(inv.stale, 'sursă are', 'surse au')} ultima reîmprospătare eșuată. Datele afișate provin dintr-o consultare anterioară.</p>` : ''}
      <div class="inv-examples">${inv.examples.map(name => `<button data-act="inventory-example" data-slug="${esc(it.slug)}" data-val="${esc(name)}"><code>${esc(name)}</code></button>`).join('')}</div>
      ${inv.page ? `<p class="inv-all"><a href="${esc(inv.page)}">Toate variabilele <span aria-hidden="true">→</span></a></p>` : ''}
      ${docs}
      <details class="inv-details" data-inv-panel data-slug="${esc(it.slug)}" ${inventoryIntent === it.slug ? 'open' : ''}>
        <summary>Explorează câmpurile <span aria-hidden="true">↗</span></summary>
        <div class="inv-body" data-inventory-body></div>
      </details>` : '<p class="inv-note">Documentația este disponibilă. Câmpurile de date nu sunt încă inventariate aici.</p>'}
    ${!inv.count ? docs : ''}
  </section>`;
}
function inventoryType(field) {
  const raw = field.declaredType || (field.observedTypes.length ? field.observedTypes : field.semanticType);
  const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
  return values.length ? values.map(t => INV_TYPES[t] || t).join(' / ') : 'Tip neprecizat';
}
function inventoryDatasets(sources) {
  const sets = sources.filter(s => s.dataset);
  if (!sets.length) return '';
  const row = s => {
    const d = s.dataset, range = d.period && (d.period[0] || d.period[1]) ? `${d.period[0] ?? '?'}–${d.period[1] ?? '?'}` : '';
    return `<li><strong>${esc(d.code)}</strong> ${esc(d.name || '')}
      <span class="inv-note">${[range && `perioadă ${range} (calculată de API)`, d.levels?.length && `niveluri: ${d.levels.map(esc).join(', ')}`, d.units?.length && `unitate declarată: ${d.units.map(esc).join(' / ')}`,
        d.updated && `actualizat ${esc(d.updated)}`, d.licence ? '' : 'licență nedeclarată'].filter(Boolean).join(' · ')}</span>
      <a href="${esc(s.url)}" target="_blank" rel="noopener">Metadate${ICON.out}</a></li>`;
  };
  return `<details class="inv-datasets"><summary>${plural(sets.length, 'set de date descris', 'seturi de date descrise')}</summary>
    <p class="inv-note">Metadate citite de la ins.gov2.ro, o oglindă a TEMPO. Perioada poate fi mai scurtă decât în sursa originală. ${sets[0].dataset.basis ? `<span class="inv-basis">${esc(sets[0].dataset.basis)}</span>` : ''}</p><ul>${sets.map(row).join('')}</ul></details>`;
}
// Data sets that a page declares about itself: the sets that it lists (title, category, description, related reports) and the sets that it declares with schema.org
// (name, period, licence, base). A description is cut in the payload; the page `date/<slug>/` holds the whole text. Each source names the basis of its facts.
function inventoryFacts(sources, page) {
  const listed = sources.filter(s => s.facts);
  if (!listed.length) return '';
  const total = listed.reduce((n, s) => n + (s.facts.sets?.length || 0) + (s.facts.schema?.length || 0), 0);
  const link = (url, text) => `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)}${ICON.out}</a>`;
  const listedSet = x => `<li class="inv-set"><strong>${esc(x.title)}</strong>${x.category ? ` <span class="inv-note">${esc(x.category)}</span>` : ''}
    ${x.description ? `<span class="inv-note">${esc(x.description)}</span>` : ''}
    ${x.reports?.length ? `<span class="inv-note">Rapoarte: ${x.reports.map(r => link(r.url, r.text)).join(', ')}</span>` : ''}</li>`;
  const schemaSet = x => `<li class="inv-set"><strong>${esc(x.name || 'Set de date')}</strong>
    ${x.period ? `<span class="inv-note">perioadă ${esc(x.period)}</span>` : ''}
    ${x.licence ? `<span class="inv-note">licență ${x.licence.url ? link(x.licence.url, x.licence.name) : esc(x.licence.name)}</span>` : ''}
    ${x.basedOn?.length ? `<span class="inv-note">bazat pe: ${x.basedOn.map(u => link(u, u)).join(', ')}</span>` : ''}</li>`;
  return `<details class="inv-datasets inv-facts"><summary>${plural(total, 'set de date declarat de sursă', 'seturi de date declarate de surse')}</summary>
    ${listed.map(s => `<p class="inv-note">${esc(s.title)} <span class="inv-basis">${esc(s.facts.basis)}</span></p><ul>${[...(s.facts.sets || []).map(listedSet), ...(s.facts.schema || []).map(schemaSet)].join('')}</ul>`).join('')}
    ${page && listed.some(s => s.facts.sets?.some(x => x.description?.endsWith('…'))) ? `<p class="inv-note">Descrierile lungi sunt tăiate aici. Pagina <a href="${esc(page)}">Toate variabilele</a> le are întregi.</p>` : ''}</details>`;
}
// A source that declares a licence for its files gets the credit it asks for, next to the names and descriptions copied from it.
function inventoryCredits(sources) {
  const credited = sources.filter(s => s.licence);
  return credited.map(s => `<p class="inv-note">Nume de câmpuri și descrieri preluate din <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(new URL(s.url).hostname)}${ICON.out}</a>, licență ${s.licence.url ? `<a href="${esc(s.licence.url)}" target="_blank" rel="noopener">${esc(s.licence.name)}${ICON.out}</a>` : esc(s.licence.name)}${s.licence.attribution ? ` · ${esc(s.licence.attribution)}` : ''}.</p>`).join('');
}
function inventoryControls(panel, data) {
  const state = inventoryState(data.slug), body = $('[data-inventory-body]', panel);
  const roles = [...new Set(data.fields.map(f => f.role))];
  body.innerHTML = `<div class="inv-controls">
    <label class="inv-search-label">Caută în câmpuri<input type="search" data-inv="q" value="${esc(state.q)}" placeholder="Nume, semnificație sau tip…" aria-controls="inventory-fields" autocomplete="off"></label>
    <div class="inv-selects">
      <label>Informații<select data-inv="role"><option value="">Toate câmpurile</option>${roles.map(role => `<option value="${esc(role)}" ${state.role === role ? 'selected' : ''}>${esc(INV_ROLES[role] || role)}</option>`).join('')}</select></label>
      <label>Sursă<select data-inv="source"><option value="">Toate sursele</option>${data.sources.map(s => `<option value="${esc(s.id)}" ${state.source === s.id ? 'selected' : ''}>${esc(s.title)}</option>`).join('')}</select></label>
    </div></div>${inventoryDatasets(data.sources)}${inventoryFacts(data.sources, BY_SLUG.get(data.slug)?.inventory?.page)}${inventoryCredits(data.sources)}<p class="inv-count" data-inventory-count role="status" aria-live="polite" tabindex="-1"></p>
    <ul class="inv-fields" id="inventory-fields" data-inventory-fields></ul><div data-inventory-more></div>`;
  renderInventoryRows(panel);
}
function renderInventoryRows(panel) {
  const data = INV_CACHE.get(panel.dataset.slug)?.data;
  if (!data) return;
  const state = inventoryState(data.slug), sources = Object.fromEntries(data.sources.map(s => [s.id, s]));
  const terms = norm(state.q).trim().split(/\s+/).filter(Boolean);
  const found = data.fields.filter(f => (!state.role || f.role === state.role) && (!state.source || f.source === state.source) && terms.every(t => f._hay.includes(t)));
  const visible = found.slice(0, state.limit);
  $('[data-inventory-count]', panel).textContent = found.length ? `${visible.length} din ${plural(found.length, 'câmp', 'câmpuri')}` : 'Niciun câmp nu corespunde căutării.';
  $('[data-inventory-fields]', panel).innerHTML = visible.map(f => {
    const source = sources[f.source];
    return `<li class="inv-field">
      <div class="inv-field-heading"><code>${esc(f.name)}</code><span class="inv-type">${esc(inventoryType(f))}${f.unit ? ` · ${esc(f.unit)}` : ''}</span></div>
      ${f.description ? `<p class="inv-description">${esc(f.description)}</p>` : ''}
      ${f.also?.length ? `<p class="inv-values">Documentat și în ${f.also.slice(0, 1).map(a => `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title || 'documentația API')}${ICON.out}</a>${a.description ? `: ${esc(a.description)}` : ''}`).join('')}${f.also.length > 1 ? ` (${f.also.length} mențiuni)` : ''}</p>` : ''}
      ${f.enum?.length ? `<p class="inv-values">Alternative declarate: ${f.enum.slice(0, 12).map(v => `<code>${esc(v)}</code>`).join(' ')}${f.enum.length > 12 ? ' …' : ''}</p>` : ''}
      ${f.formula ? `<p class="inv-values">Formulă declarată: <code>${esc(f.formula)}</code></p>` : ''}
      ${f.period ? `<p class="inv-values">Perioadă declarată: ${esc(f.period)}</p>` : ''}
      <div class="inv-field-meta"><span>${esc(INV_ROLES[f.role] || f.role)}${f.location ? ` · ${esc(INV_LOCATIONS[f.location] || f.location)}` : ''}</span><span class="inv-basis inv-basis-${esc(f.basis)}">${esc(INV_BASIS[f.basis] || f.basis)}</span>${f.group ? `<span>${esc(clip(f.group, 40))}${Number.isInteger(f.rows) ? ` · ${plural(f.rows, 'rând', 'rânduri')}` : ''}</span>` : ''}${f.operations.length > 1 ? `<span>${plural(f.operations.length, 'operație API', 'operații API')}</span>` : ''}
        ${source ? `<a href="${esc(source.url)}" target="_blank" rel="noopener" title="${esc(source.title)}">Vezi sursa${ICON.out}</a>` : ''}</div>
      <details class="inv-reference"><summary>Context și referință</summary><code>${esc(f.path)}</code>
        ${f.reference ? `<p class="inv-pointer">${esc(f.reference)}</p>` : ''}
        ${f.contexts?.length > 1 ? `<p>${plural(f.contexts.length, 'referință în schemă', 'referințe în schemă')} cu acest nume și tip.</p>` : ''}
        ${f.operations.length ? `<p class="inv-operations">${f.operations.map(op => `<code>${esc(op)}</code>`).join('')}</p>` : ''}
        ${source ? `<p>${esc(source.title)}${source.checked ? ` · ${source.savedByOwner ? 'copie salvată de proprietar la' : 'consultat la'} ${esc(source.checked)}` : ''}</p>` : ''}
        ${source?.refreshFailed ? `<p class="inv-stale">Ultima reîmprospătare a eșuat${source.refreshFailed.date ? ` la ${esc(source.refreshFailed.date)}` : ''}${source.refreshFailed.status ? ` (HTTP ${esc(source.refreshFailed.status)})` : ''}. Informațiile pot fi vechi.</p>` : ''}
      </details></li>`;
  }).join('');
  $('[data-inventory-more]', panel).innerHTML = visible.length < found.length
    ? `<button class="btn btn-outline inv-more" data-act="inventory-more" data-slug="${esc(data.slug)}">Mai multe câmpuri (${found.length - visible.length})</button>`
    : !found.length ? `<button class="linkbtn" data-act="inventory-clear" data-slug="${esc(data.slug)}">Șterge căutarea și filtrele</button>` : '';
}
async function loadInventory(panel, retry = false) {
  const slug = panel.dataset.slug, it = BY_SLUG.get(slug), body = $('[data-inventory-body]', panel);
  if (!it?.inventory?.url) return;
  if (retry) INV_CACHE.delete(slug);
  let record = INV_CACHE.get(slug);
  if (!record) {
    record = { status: 'loading' };
    record.promise = (async () => {
      try {
        const response = await fetch(ROOT + it.inventory.url);
        if (!response.ok) throw new Error('inventory HTTP ' + response.status);
        const data = await response.json();
        if (data.slug !== slug || !Array.isArray(data.fields) || !Array.isArray(data.sources)) throw new Error('invalid inventory');
        for (const f of data.fields) f._hay = norm([f.name, f.path, f.description, inventoryType(f), f.declaredType, f.observedTypes, INV_BASIS[f.basis], f.unit, f.enum, f.formula, f.group, f.period].join(' '));
        record.status = 'ready'; record.data = data;
      } catch { record.status = 'failed'; }
    })();
    INV_CACHE.set(slug, record);
  }
  if (record.status === 'loading') body.innerHTML = '<p class="inv-note" role="status">Se încarcă inventarul…</p>';
  await record.promise;
  if (!panel.isConnected) return;
  if (record.status === 'ready') {
    inventoryControls(panel, record.data);
    if (retry) $('[data-inv="q"]', panel)?.focus();
  } else {
    body.innerHTML = `<div class="inv-error" role="status"><p>Inventarul nu a putut fi încărcat.</p><button class="btn btn-outline" data-act="inventory-retry" data-slug="${esc(slug)}">Încearcă din nou</button></div>`;
    if (retry) $('[data-act="inventory-retry"]', panel)?.focus();
  }
}
function openInventory(slug, example) {
  if (example != null) {
    const state = inventoryState(slug);
    Object.assign(state, { q: example, role: '', source: '', limit: 8 });
  }
  inventoryIntent = slug;
  if (state.p !== slug || slot('drawer').hidden) {
    state.p = slug; writeURL(true); renderDetail();
  }
  const section = $('[data-inventory-root]', slot('drawer'));
  if (!section) return;
  const panel = $('[data-inv-panel]', section);
  if (!panel) return;
  panel.open = true;
  loadInventory(panel);
  section.scrollIntoView({ block: 'start', behavior: 'auto' });
  inventoryIntent = '';
}
document.addEventListener('toggle', e => {
  if (e.target.matches?.('[data-inv-panel]') && e.target.open) loadInventory(e.target);
}, true);
document.addEventListener('input', e => {
  if (e.target.dataset.inv !== 'q') return;
  const panel = e.target.closest('[data-inv-panel]');
  Object.assign(inventoryState(panel.dataset.slug), { q: e.target.value, limit: 8 });
  renderInventoryRows(panel);
});
document.addEventListener('change', e => {
  if (!['role', 'source'].includes(e.target.dataset.inv)) return;
  const panel = e.target.closest('[data-inv-panel]');
  Object.assign(inventoryState(panel.dataset.slug), { [e.target.dataset.inv]: e.target.value, limit: 8 });
  renderInventoryRows(panel);
});

// The full classification, in four groups. Every concept is a button that filters the list by it.
function classHTML(it) {
  const tag = (key, id) => `<button class="tag" data-act="multi" data-key="${key}" data-val="${esc(id)}" aria-pressed="${listOf(key).includes(id)}"${CONCEPT.get(id)?.def ? ` title="${esc(CONCEPT.get(id).def)}"` : ''}>${esc(label(id))}</button>`;
  const tags = (key, ids) => ids.length ? `<span class="tags">${ids.map(id => tag(key, id)).join('')}</span>` : '';
  const others = it.subjects.filter(s => s !== it.primarySubject);
  const place = it.coverageLevel === 'necunoscut' && !it.areas.length ? 'necunoscută'
    : [TAX.cov[it.coverageLevel]?.label, ...it.areas.map(label)].filter(Boolean).join(' · ');
  const org = it.kind === 'organizatie';
  const groups = [
    ['Despre ce', [it.primarySubject && ['Subiect', tags('subj', [it.primarySubject])], others.length && ['Și', tags('subj', others)],
      it.topics.length && ['Teme', tags('subj', it.topics)], it.institutions.length && ['Instituții vizate', tags('inst', it.institutions)]]],
    [org ? 'Ce face' : 'Ce oferă', [it.capabilities.length && [facetTitle('cap'), tags('cap', it.capabilities)],
      it.formats.length && ['Format', tags('fmt', it.formats)], it.technologies.length && ['Tehnologie', tags('tech', it.technologies)],
      it.organisationTypes.length && ['Tip', tags('orgt', it.organisationTypes)],
      it.maturity && ['Maturitate', esc(label(it.maturity))]]],
    ['Surse de date', sourceGroups(it.dataSources).map(s => ['', [...s.evidence].map(url => `<a href="${esc(url)}" title="${esc(s.names.join(' · '))}" target="_blank" rel="noopener">${esc(s.name)}</a>`).join(' · ')])],
    ['Scop civic', [it.purposes.length && ['Scop', tags('purpose', it.purposes)]]],
    ['Acoperire', [['Unde se aplică', esc(place)], it.dataDetail && ['Detalierea datelor', `<a href="${esc(it.dataDetailEvidence)}" target="_blank" rel="noopener">${esc(DETAIL_LABELS[it.dataDetail] || it.dataDetail)}</a>`]]],
  ].map(([title, rows]) => [title, rows.filter(Boolean)]).filter(([, rows]) => rows.length);
  if (!it.primarySubject) groups.unshift(['Clasificare', [['', '<span class="muted">Sursele disponibile nu stabilesc încă subiectul acestei intrări.</span>']]]);
  return `<div class="d-class">${groups.map(([title, rows]) => `<section><p class="kicker">${title}</p><dl class="dl">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl></section>`).join('')}
    ${DB.draft && DRAFT_NOTE ? '<p class="small muted">Clasificare propusă, neverificată încă de editor.</p>' : ''}</div>`;
}

function structureHTML(it) {
  if (!DB.structurePreview) return '';
  const structure = it.structure;
  if (!structure) return `<section class="structure-profile"><h3>Structura site-ului</h3><p class="small muted">Structura acestui site nu este încă inclusă în previzualizare.</p><a href="${ROOT}entitati/">Caută o entitate între proiecte →</a></section>`;
  const kinds = {detail:'Pagină de entitate', listing:'Listă', search:'Căutare', document:'Document', unknown:'Tip necunoscut'};
  const applicability = {historical:'Observație păstrată', stale:'Sursă nereconfirmată', current:'Observație disponibilă', unknown:'Actualitate necunoscută'};
  const declared = {unspecified:'Nespecificat', anonymous:'Fără autentificare declarată', authenticated:'Autentificare declarată'};
  const observed = {unknown:'Neverificat', anonymous:'Acces fără autentificare observat', authenticated:'Autentificare observată'};
  const evidence = sources => `<details><summary>Surse și data observației</summary><ul>${sources.map(s => `<li>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>` : 'Sursă locală'} · <time>${esc(s.observedAt)}</time><br><code class="structure-hash">SHA-256 ${esc(s.sha256)}</code></li>`).join('')}</ul></details>`;
  return `<section class="structure-profile" data-structure-profile><h3>Structura site-ului</h3>
    <p class="small muted">Inventar parțial. Tiparele și endpointurile sunt declarații sau observații păstrate. Disponibilitatea lor actuală nu este garantată.</p>
    <h4>Secțiuni și colecții (${structure.collections.length})</h4>
    <ul>${structure.collections.map(c => {
      const listings = structure.patterns.filter(p => p.collectionId === c.id && p.kind === 'listing' && !p.url.includes('{'));
      return `<li><strong>${esc(c.label)}</strong>${listings.map(p => ` · <a href="${esc(p.url)}" target="_blank" rel="noopener">Deschide secțiunea</a>`).join('')}${evidence(c.sources)}</li>`;
    }).join('')}</ul>
    <details data-structure-patterns><summary>Tipare URL (${structure.patterns.length})</summary>
      <ul>${structure.patterns.map(p => `<li><code>${esc(p.url)}</code><span class="small muted structure-meta">${esc(p.collection)} · ${esc(kinds[p.kind] || p.kind)} · ${esc(applicability[p.applicability] || p.applicability)}</span>
        ${p.variables.length ? `<span class="small structure-meta">${p.variables.map(v => `${esc(v.name)}: ${esc(v.namespace || 'identificator necunoscut')}`).join(' · ')}</span>` : ''}${evidence(p.sources)}</li>`).join('')}</ul>
    </details>
    <details data-structure-apis><summary>Endpointuri API (${structure.operations.length})</summary>
      <ul>${structure.operations.map(o => `<li><code>${esc(o.method)} ${esc(o.url)}</code><span class="small muted structure-meta">${esc(o.collections.join(' · '))}</span>
        <span class="small structure-meta">Acces declarat: ${esc(declared[o.declaredSecurity] || o.declaredSecurity)}. Acces observat: ${esc(observed[o.observedSecurity] || o.observedSecurity)}.</span>
        ${o.unresolvedParameters ? '<span class="small structure-warning">Parametri incompleți; verificarea API este oprită.</span>' : ''}${evidence(o.sources)}</li>`).join('')}</ul>
    </details>
    <p><a href="${ROOT}entitati/">Caută o entitate între proiecte →</a></p>
  </section>`;
}

function renderDetail() {
  const it = current();
  const drawer = slot('drawer');
  syncTitle();
  if (!it) { if (!drawer.hidden) closeLayers(); return; }
  const subject = it.primarySubject ? label(it.primarySubject) : '';
  const st = STATUS[it.status];
  const alive = !isInactive(it);
  const shared = i => i.topics.filter(t => it.topics.includes(t)).length;
  const related = !it.primarySubject ? [] : DB.items.filter(i => i.kind === it.kind && i._f.subj.has(it.primarySubject) && i.slug !== it.slug && !isInactive(i))
    .sort((a, b) => (b.primarySubject === it.primarySubject) - (a.primarySubject === it.primarySubject) || shared(b) - shared(a) || byName(a, b)).slice(0, 4);
  const dl = [
    ...attributionRows(it),
    it.contact && ['Contact', esc(it.contact)],
    it.url && ['Site', `${alive ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.domain)}</a>` : `<span class="muted">${esc(it.domain)}</span>`}${it.movedFrom ? ` <span class="muted small">(mutat de pe ${esc(it.movedFrom)})</span>` : ''}`],
    ...linkRows(it),
    it.code && ['Cod sursă', `<a href="${esc(it.code)}" target="_blank" rel="noopener">${esc(it.code.replace(/^https?:\/\/(www\.)?/, ''))}</a>`],
    repoRow(it),
    it.repo?.license && ['Licență', esc(it.repo.license)],
    it.wayback && ['Arhivă', `<a href="${esc(it.wayback)}" target="_blank" rel="noopener">Wayback Machine</a>`],
    it.since && ['Prima urmă observată', `${esc(sinceLabel(it))} <span class="muted small mono">· ${esc(ageTitle(it))}</span> <span class="muted small">· nu este data lansării</span>`],
    it.updated && ['Actualizat', `${esc(updatedLabel(it))} <span class="muted small mono">· ${esc(it.updated)} după ${esc(UPDATED_SRC[it.updatedSrc] || it.updatedSrc)}</span>`],
    ['Stare', `${statusDot(it)} ${st.label}${it.stale ? ` <span class="muted small">· niciun semn de actualizare după ${it.stale}</span>` : ''}${it.checked ? ` <span class="muted small mono">· verificat ${esc(it.checked)}${it.httpStatus ? ` · HTTP ${it.httpStatus}` : ''}</span>` : ''}`],
  ].filter(Boolean);
  const cta = alive && it.url
    ? `<a class="d-url" href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, ''))}${ICON.out}</a>`
    : it.wayback ? `<a class="btn btn-primary" href="${esc(it.wayback)}" target="_blank" rel="noopener">${ICON.archive}Vezi în arhivă</a>` : '';
  drawer.innerHTML = `
    <div class="d-bar"><span class="kicker">${esc(subject)}</span>
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
        ${entLabel(it) ? `<span>${esc(entLabel(it))}</span>` : ''}
        ${placeLabel(it) ? `<span>${esc(placeLabel(it))}</span>` : ''}
        ${isFresh(it) ? `<span class="new${isNewest(it) ? ' launch' : ''}" title="${esc(sinceTitle(it))}">apărut recent · ${esc(sinceLabel(it))}</span>` : ''}
        ${it.code ? `<span>${ICON.code}cod public</span>` : ''}
      </div>
      ${it.desc ? `<p class="d-desc">${esc(it.desc)}</p>${it.descSrc === 'site' ? '<p class="d-src">Descriere preluată de pe site-ul proiectului.</p>' : ''}` : ''}
      ${inventoryHTML(it)}
      ${structureHTML(it)}
      ${classHTML(it)}
      ${it.attributions.filter(a => a.org && BY_SLUG.has(a.org)).map(a => orgCard(BY_SLUG.get(a.org))).join('')}
      <dl class="dl">${dl.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${worksHTML(it)}
      ${related.length ? `<div class="related"><p class="kicker">Tot din ${esc(subject)}</p>${related.map(r => row(r, false)).join('')}</div>` : ''}
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
  const top = $('.d-scroll', slot('sheet'))?.scrollTop || 0;
  slot('sheet').innerHTML = `
    <div class="grab" aria-hidden="true"></div>
    <div class="d-bar"><span class="kicker">Filtre</span><button class="btn btn-ghost btn-icon" data-act="close" aria-label="Închide" data-autofocus>${ICON.x}</button></div>
    <div class="d-scroll">${facetsHTML()}</div>
    <div class="d-cta"><button class="btn btn-outline" data-act="reset">Șterge</button><button class="btn btn-primary" data-act="close">Arată ${plural(n, 'rezultat', 'rezultate')}</button></div>`;
  $('.d-scroll', slot('sheet')).scrollTop = top;
}

/* ---------- autocomplete ---------- */
let SUGGEST = [], acItems = [], acIndex = -1;

// Concept suggestions carry their facet in the label ("Subiect: Inteligență artificială" is not "Tehnologie: Folosește AI").
// Each one is found by its Romanian and English labels and its alternative labels, without diacritics.
const FACET_OF_SCHEME = { scop: 'purpose', functie: 'cap', format: 'fmt', tehnologie: 'tech', institutie: 'inst', organizatie: 'orgt' };
const AC_GROUPS = { Subiecte: 3, Teme: 4, Funcționalități: 3, Formate: 3, Tehnologii: 2, Scopuri: 2, Surse: 3, Instituții: 2, Zone: 3, Proiecte: 6, Autori: 3 };
const GROUP_OF = { subj: 'Subiecte', topic: 'Teme', source: 'Surse', cap: 'Funcționalități', fmt: 'Formate', tech: 'Tehnologii', purpose: 'Scopuri', inst: 'Instituții', orgt: 'Instituții', area: 'Zone' };
function buildSuggestions() {
  const out = [];
  for (const c of DB.vocabulary.concepts) {
    const key = c.scheme === 'subiect' ? 'subj' : FACET_OF_SCHEME[c.scheme];
    if (!key) continue;  // maturity is shown, not filtered
    out.push({ g: GROUP_OF[key], label: c.label, kind: key, val: c.id, names: [c.label, c.labelEn, ...c.alt] });
  }
  for (const s of sourceGroups(DB.items.flatMap(i => i.dataSources)))
    out.push({ g: 'Surse', label: s.name, kind: 'source', val: s.name, names: [s.name, ...s.names] });
  for (const a of DB.vocabulary.areas) out.push({ g: 'Zone', label: a.label, kind: 'area', val: a.id, names: [a.label] });
  for (const it of DB.items) out.push({ g: 'Proiecte', label: it.name, kind: 'item', val: it.slug, it, names: [it.name] });
  for (const o of new Set(DB.items.flatMap(i => i._orgs))) out.push({ g: 'Autori', label: o, kind: 'org', val: o, names: [o] });
  for (const s of out) s._n = [...new Set(s.names.filter(Boolean).map(norm))];
  return out;
}
const GROUP_LIMIT = AC_GROUPS;
function scoreOf(names, q) {
  let best = -1, via = '';
  for (const n of names) {
    const i = n.indexOf(q);
    const sc = i < 0 ? -1 : i === 0 ? 0 : /[\s\-–·./(&]/.test(n[i - 1]) ? 1 : 2;
    if (sc >= 0 && (best < 0 || sc < best)) { best = sc; via = n; }
  }
  return [best, via];
}
function countFor(s) {
  const base = DB.items.filter(i => i.kind === state.k && (showsInactive() || !isInactive(i)));
  if (s.kind === 'org') return DB.items.filter(i => i._orgs.includes(s.val)).length;
  if (s.kind === 'item') return null;
  return base.filter(i => has(i, s.kind, s.val)).length;
}
function highlight(label, q) {
  const i = norm(label).indexOf(q);
  if (i < 0) return esc(label);
  return esc(label.slice(0, i)) + '<mark>' + esc(label.slice(i, i + q.length)) + '</mark>' + esc(label.slice(i + q.length));
}
function renderAC() {
  const box = slot('ac'), input = slot('q');
  const q = norm(input.value.trim());
  if (!DB || q.length < MIN_Q || document.activeElement !== input) { closeAC(); return; }
  const scored = SUGGEST.map(s => { const [sc, via] = scoreOf(s._n, q); return { s, sc, via, n: sc < 0 ? 0 : countFor(s) }; })
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
        ? (it.kind !== 'proiect' ? TAX.kind[it.kind].label.toLowerCase() : isInactive(it) ? STATUS[it.status].label.toLowerCase() : it.primarySubject ? label(it.primarySubject) : '')
        : x.n;
      // A concept found by another name (an English label or a synonym) shows that name too.
      const shown = FACETS.includes(x.s.kind) ? `${esc(facetTitle(x.s.kind))}: ${highlight(x.s.label, q)}${x.via !== norm(x.s.label) ? ` <span class="muted">(${esc(x.s.names.find(n => norm(n) === x.via) || '')})</span>` : ''}` : highlight(x.s.label, q);
      html += `<div class="ac-opt" role="option" id="ac-${i}" data-ac="${i}" aria-selected="false">${lead}<span class="l">${shown}</span><span class="r">${esc(right)}</span></div>`;
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
  if (FACETS.includes(s.kind)) {
    if (!listOf(s.kind).includes(s.val)) state[s.kind] = [...listOf(s.kind), s.val].join(',');
  }
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
  const inv = e.target.closest('[data-act^="inventory"]');
  if (inv) {
    e.preventDefault();
    const action = inv.dataset.act, slug = inv.dataset.slug || inv.dataset.val;
    if (action === 'inventory' || action === 'inventory-example') openInventory(slug, action === 'inventory-example' ? inv.dataset.val : null);
    else {
      const panel = inv.closest('[data-inv-panel]');
      if (action === 'inventory-retry') loadInventory(panel, true);
      else if (action === 'inventory-more') {
        inventoryState(slug).limit += 20; renderInventoryRows(panel);
        ($('[data-act="inventory-more"]', panel) || $('[data-inventory-count]', panel))?.focus();
      } else if (action === 'inventory-clear') {
        Object.assign(inventoryState(slug), { q: '', role: '', source: '', limit: 8 });
        inventoryControls(panel, INV_CACHE.get(slug).data); $('[data-inv="q"]', panel)?.focus();
      }
    }
    return;
  }
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
  if (a.matches('a[role="button"]')) e.preventDefault();
  if (a.getAttribute('aria-disabled') === 'true') return;
  const { act, key, val } = a.dataset;
  if (act === 'retry') { boot(true); return; }
  if (!DB && act !== 'fs' && act !== 'theme') return;  // nothing to act on until the data has loaded
  if (act === 'set') setFilter(key, val);
  else if (act === 'multi') {
    const l = listOf(key);
    state[key] = (l.includes(val) ? l.filter(x => x !== val) : [...l, val]).join(',');
    if (a.closest('[data-slot="drawer"]')) { state.p = ''; closeLayers(); syncTitle(); }
    writeURL(); renderFilters(); renderResults();
  } else if (act === 'unset') {
    if (MULTI.includes(key)) state[key] = listOf(key).filter(x => x !== val).join(',');
    else state[key] = '';
    writeURL(); renderAll();
  } else if (act === 'clear') { state[key] = ''; writeURL(); renderFilters(); renderResults(); }
  else if (act === 'reset') { for (const k of FILTERS) state[k] = ''; writeURL(); renderAll(); }
  else if (act === 'kind') { state.k = val; state.o = defaultSort(); for (const k of FILTERS) if (k !== 'q') state[k] = ''; writeURL(); renderAll(); }
  else if (act === 'view') { state.v = val; writeURL(); renderResults(); }
  else if (act === 'fs') { store.set('ct.fs', val); applyPrefs(); }
  else if (act === 'theme') { store.set('ct.theme', val); applyPrefs(); }
  else if (act === 'more-options') { expandedOptions.has(key) ? expandedOptions.delete(key) : expandedOptions.add(key); renderFilters(); }
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
  store.set('ct2.closed', [...closed]);
}, true);

let qTimer;
const qInput = slot('q');
qInput.addEventListener('input', () => {
  if (!DB) return;
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
  if (e.key === ' ' && e.target.matches('a.tag[role="button"][href]')) {
    e.preventDefault();
    e.target.click();
    return;
  }
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (e.key === 'Escape' && !slot('scrim').hidden) { $('[data-act="close"]', slot('drawer').hidden ? slot('sheet') : slot('drawer'))?.click(); return; }
  if (slot('scrim').hidden && ((e.key === '/' && !typing) || (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey)))) {
    e.preventDefault();
    qInput.focus(); qInput.select();
  }
  if (e.key === 'Tab' && !slot('scrim').hidden) {
    // Keep focus inside the open layer.
    const layer = slot('drawer').hidden ? slot('sheet') : slot('drawer');
    // Controls inside a closed <details> are not rendered; they cannot take the focus.
    const f = [...layer.querySelectorAll('a[href], button:not([disabled]), input, select, summary')].filter(el => el.getClientRects().length && !el.closest('details:not([open]) > :not(summary)'));
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
window.addEventListener('popstate', () => { if (DB) { readURL(); renderAll(); renderDetail(); } });

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
// A load that fails (no connection, a server error, unreadable data) says so, offers a retry, and links to the three static
// lists: they need neither data.json nor scripts. After a retry that fails again, the focus goes to the new button.
function loadFailed(byUser) {
  DB = null;
  slot('results').innerHTML = `<div class="empty" role="alert">
    <h3>Nu am putut încărca lista.</h3>
    <p>Verifică conexiunea la internet și încearcă din nou.</p>
    <p><button class="btn btn-outline" data-act="retry">Încearcă din nou</button></p>
    <p>Până atunci, citește listele simple: <a href="${ROOT}proiect/">proiecte</a> · <a href="${ROOT}organizatie/">organizații</a> · <a href="${ROOT}resursa/">resurse</a>.</p>
  </div>`;
  if (byUser) $('[data-act="retry"]', slot('results'))?.focus();
}

async function boot(byUser = false) {
  if (byUser) slot('results').innerHTML = '<div class="empty" role="status"><p>Se încarcă…</p></div>';
  let db;
  try {
    const r = await fetch(ROOT + 'data.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(`data.json: HTTP ${r.status}`);
    db = await r.json();
  } catch { loadFailed(byUser); return; }
  if (!String(db.schemaVersion || '').startsWith('2.')) {
    slot('results').innerHTML = '<div class="empty"><h3>Date incompatibile.</h3><p>Această pagină citește datele taxonomiei v2.</p></div>';
    return;
  }
  try { start(db); } catch (e) {
    console.error(e);
    BY_SLUG.clear(); CONCEPT.clear(); AREA.clear();
    loadFailed(byUser);
  }
}

function start(db) {
  DB = db;
  document.querySelector('[data-structure-link]')?.remove();
  if (db.structurePreview) {
    const link = document.createElement('a');
    link.href = ROOT + 'entitati/'; link.textContent = 'Entități'; link.className = 'hdr-link';
    link.dataset.structureLink = ''; link.title = 'Caută o entitate între proiecte';
    document.querySelector('.hdr-links')?.prepend(link);
  }
  if (db.inventoryPreview) slot('q').placeholder = 'Caută proiect, subiect sau câmp…';
  const map = arr => Object.fromEntries(arr.map(x => [x.key, x]));
  const v = db.vocabulary;
  for (const c of v.concepts) CONCEPT.set(c.id, c);
  for (const a of v.areas) AREA.set(a.id, a);
  TAX = { kind: map(v.kinds), ent: map(v.entityTypes), dat: map(v.dataGroups || []), cov: map(v.coverage), pred: map(v.predicates), scheme: map(v.schemes),
    dom: map(db.legacyTaxonomy.domenii), tip: map(db.legacyTaxonomy.tipuri) };
  // Paths in the data are relative to the site root; the address bar changes with pushState, so make them absolute.
  const abs = p => p ? ROOT + p : p;
  const names = id => { const c = CONCEPT.get(id) || AREA.get(id); return c ? [c.label, c.labelEn, ...(c.alt || [])] : []; };
  for (const it of db.items) {
    it.icon = abs(it.icon);
    if (it.img) it.img.src = abs(it.img.src);
    for (const l of it.links) l.icon = abs(l.icon);
    if (!STATUS[it.status]) it.status = 'neverificat';
    it._sort = norm(it.name).replace(/[^a-z0-9]/g, '');
    BY_SLUG.set(it.slug, it);
    // Facet values for matching: subjects include the roots of the topics; a topic includes its broader topics,
    // so that choosing a broad topic finds the entries assigned to its narrower ones.
    const up = it.topics.flatMap(ancestors);
    it._f = Object.fromEntries(FACETS.filter(k => FIELD[k]).map(k => [k, new Set(it[FIELD[k]])]));
    for (const a of up) (CONCEPT.get(a)?.broader.length ? it._f.topic : it._f.subj).add(a);
    for (const t of it._f.topic) it._f.subj.add(t);
    it.dataSources ||= [];
    it._f.source = new Set(it.dataSources.map(s => sourceLabel(s.name)));
    it._f.coverage = new Set([coverageKey(it)]);
    it._f.ent = new Set([it.entityType]);
    it._f.dat = new Set([dataGroup(it.dataRelation)].filter(Boolean));
    it._f.st = new Set([STATUS[it.status].group]);
    it._orgs = it.attributions.map(a => a.name);
    // What ties entries together by attribution: the slug of an organisation, else the written name.
    it._akeys = it.attributions.map(a => a.org || norm(a.name));
    const concepts = [...new Set([...it._f.subj, ...it._f.topic, ...['cap', 'fmt', 'purpose', 'tech', 'inst', 'orgt'].flatMap(k => [...it._f[k]])])];
    it._hay = norm([it.name, it.tagline, it.desc, it.inventory?.keywords, ...it.dataSources.map(s => s.name), ...it._orgs, it.domain, TAX.ent[it.entityType]?.label, ...it.areas.flatMap(names),
      ...concepts.flatMap(names), ...legacyWords(it)].join(' '));
  }
  SUGGEST = buildSuggestions();
  readURL();
  if (current() && !pathSlug()) writeURL();  // an old ?p=<slug> link moves to the entry's own address
  if (DB.checked) slot('checked').textContent = `actualizat: ${DB.checked} · ${DB.items.length} resurse`;
  renderAll();
  renderDetail();
  fitHeader();
  setTimeout(rotateTitle, 3000 + Math.random() * 2000);
}

boot();
