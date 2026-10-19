# Taxonomy v2 for CivTech România — audit and proposal

## Context

The owner wants to add a batch of pages from mariuscomper.uk (data journalism, explainers, tools; summaries
exist in `~/devbox/mc-i/summaries/`). Two worries: (1) volume — mariuscomper.uk has 1121 pieces, 113 in
"Stat, bani și viață publică", which would double the list and drown the tools; (2) the current
classification is the owner's first sketch and does not scale to sectors, multi-domain entries, or
content that is "educational / infotainment" rather than practical.

The deliverable now is an **audit + proposal** (a spec), not code. Implementation goes to a Sonnet brief
after the owner picks the options.

## Audit — what exists (measured 2026-10-19, 109 entries + 13 orgs)

Facets today (`data/taxonomy.json`): `fel` (6, maps to 3 tabs), `domenii` (12, single-valued),
`tipuri` (9, multi-valued), `acoperire` (3), `civictech` (boolean), open `cuvinte` (47 distinct).

Findings:
1. **Domain is single-valued.** 109/109 entries have exactly one domain. Cross-domain entries are forced
   (banii-nostri: money + politics; harta-firmelor: integrity + money; transparenta-eu; romania-transparenta).
   Orgs: 9/13 are `civic`, so the facet tells nothing about orgs (EFOR covers 7 areas).
2. **No public-policy sectors.** No health, education, transport, housing/urbanism, social protection/labour,
   culture/heritage, security/defence. Symptoms: sanatate-mintala, evermed, verifica-psiholog → `servicii`;
   e-cutremur, dupa-cutremur → `mediu`; hybrid-war monitors → `altele`; aiparte-research → `date`.
   mariuscomper.uk content (water, rail, schools, hospitals, pensions, urbanism) would mostly land in `altele`.
3. **`local` means two things**: a domain and an `acoperire` value (breaks "one word, one meaning").
4. **Format leaks into subject.** `date` is a mechanism (open data), not a subject: monitor-social,
   unde-locuiesc-romanii, ins-gov2 are demography/social statistics filed under `date`.
5. **`tipuri` mixes three axes**: format (hartă, vizualizare, bază de date), function (monitorizare,
   instrument), and relation (serviciu). Only 1 of 109 entries uses more than one type. `ghid` exists in
   both `tipuri` and `fel`; `campanie` is a `fel` and an ignored keyword.
6. **`civictech` (0/1/empty) conflates producer and inclusion.** It cannot say "made by a public
   institution" vs "by a journalist" vs "by an NGO" — which is exactly what decides whether a
   mariuscomper.uk piece (individual author, data journalism) belongs.
7. **No practical-vs-understanding axis.** A complaint tool (domnule-primar) and a quiz (testvot) differ
   only by `tip`; nothing lets a visitor say "show me things I can use".
8. **Keywords mix technology (ai ×17, api, mcp), institutions (anaf, parlament, primării) and topics.**
9. **No crosswalk to any standard**, while `data/international.csv` seeds a planned international mirror.
10. Form limit: the Domeniu help text is already 772 chars; more domains need grouping.

Prior research found: `~/devbox/semar` gives a useful *model* (facet = question asked of each item;
vocabulary is closed, authority or open; proposals vs decisions — same as `review.py` suggestions vs the
editor). `~/devbox/mc-i/taxonomii/README.md` recommends EuroVoc microthesauri (unverified licence/RO labels).
mc-i has its own 13 categories / 6 project types (`journalism-summary-prompt.md`). No survey of standards.

## Proposal — a faceted scheme (library practice: facets, not one tree)

Each facet answers one question; keys stay Romanian; each key carries crosswalk codes so the data
can federate. Standards are used as **crosswalks, not as the UI vocabulary** (EuroVoc has ~7 000
concepts; COFOG 10 divisions; SDG 17 — none fits a 150-entry directory as-is).

| Facet | Question | Values (draft) | Cardinality | Standard crosswalk |
|---|---|---|---|---|
| **Temă** (`domeniu`) | What is it about? | 2 groups. *Democrație & guvernare*: bani publici, politică & alegeri, integritate, justiție & drepturi, media & informare, transparență & date deschise, stat digital, societate civilă & participare. *Politici publice*: sănătate, educație, protecție socială & muncă, mediu & energie, urbanism, locuire & transport, siguranță, urgențe & apărare, economie & fiscalitate, cultură & patrimoniu, servicii publice & formalități. Plus `altele`. | 1–3, main first (like `tip`) | COFOG division, OGP policy area, SDG, EuroVoc domain |
| **Scop** (new) | What do you do with it? | folosești (rezolvi ceva), verifici/urmărești, înțelegi (explicații, educație), participi (petiții, campanii, voluntariat) | 1, optional 2nd | Knight: open gov / community action |
| **Format** (`tip`, cleaned) | What form does it take? | aplicație/instrument, calculator/simulare, hartă, vizualizare/dashboard, bază de date/registru, date/API, ghid, articol/investigație, joc/test, curs, colecție/listă | 1–3 | schema.org type, DCMI Type |
| **Autor** (replaces `civictech`) | Who made it? | ONG, voluntari/individual, presă/jurnaliști, academic/cercetare, instituție publică, companie | 1 | Candid PCS org type; ICNPO for orgs |
| **Stadiu** (from `stare` + keyword `prototip`) | How mature? | prototip/experiment, activ, arhivat, offline | 1 | — |
| **Acoperire** | Where? | național, județean/local (+ `oras`), internațional | 1 | SIRUTA later |
| **Cuvinte** | Free tags | open; alias/ignora as now | n | EuroVoc concepts later |

The owner's "research & experiments" idea maps to **Scop = înțelegi** plus **Stadiu = experiment**,
and to a separate **tab** for content (see the open decision on placement).

Volume control (curation policy, in CONTRIBUTING.md): a piece enters only if it (a) concerns
institutions, public money, rights, participation, public services or public-interest data, (b) concerns
Romania, (c) shows sources/method, (d) is not news-pegged trivia. One author's pieces group under the
author (existing "De același autor"); tools enter individually, explainers enter the content tab.

Interop outputs (cheap, later): `taxonomy.json` keys get `cofog`, `ogp`, `sdg`, `schema` fields;
`build.py` emits schema.org JSON-LD per entry page and a SKOS export of the taxonomy.

## Decisions taken (2026-10-19)

- **Placement:** a 4th tab for content, working name "Explicații & investigații" (kind `analiza`,
  path `/analiza/<slug>/`). Tools that you use (calculators, practical guides) stay in Proiecte.
  `fel` gains `explicatie`, `investigatie`, `simulare`/`experiment`; `articol` and `cercetare` move here
  from "Resurse & liste", which keeps lists, guides and campaigns.
- **Scope:** faceted v2, as in the table above.
- **URLs:** 20 pages, all with a summary in `~/devbox/mc-i/summaries/`. Draft placement (owner reviews):
  - **Proiecte** (tools, Scop = folosești/verifici): codurbanism (ghid, urbanism), cat-de-tare
    (instrument, siguranță & urgențe), biografia-localitatii (instrument, date), unde-locuiesc
    (instrument, urbanism), ani-de-pensie (calculator, protecție socială), ce-face-statul-cu-1000-de-lei
    (calculator, bani publici), achizitii-directe-ti-2026 (dashboard, bani publici; its index title is
    broken, "What Nolan Changed…", so the name comes from the page).
  - **Explicații & investigații** (Scop = înțelegi): statul-digital, complet-online (stat digital);
    prima-cifra, pe-datorie (bani publici / integritate); trei-din-patru (educație); orasul-care-se-intinde,
    constru-pentru-cine, de-unde-vine-apa (urbanism & locuire / utilități); unde-se-termina-asfaltul
    (transport); ultima-noapte-pib, recontorizarea (economie); pensie-din-bursa (protecție socială);
    tuneluri-feroviare (transport — weakest civic fit; owner confirms or drops).
  - `autor` = Marius Comper for all 20, so "De același autor" groups them; `civictech`/Autor type =
    individual / data journalism.

## Steps

1. Opus writes `docs/specs/taxonomy.md` (this audit + chosen proposal + crosswalk tables to COFOG,
   OGP policy areas, SDG, schema.org, and the mc-i categories/types) and the owner reviews the final
   value lists; adds BACKLOG items; ACTIVITY entry; minor version bump (a spec is a deliverable).
2. Opus writes a Sonnet brief `docs/briefs/taxonomy-v2.md`: `taxonomy.json` changes, `common.py` columns,
   `validate.py` (multi-domain, new facets), `build.py` (`domeniu` → list, "Pe domenii" groups by main
   domain, JSON-LD), `site/app.js` (facet filters, `it.domeniu` → `it.domenii`), `form.py`, DATA-SCHEMA,
   CONTRIBUTING; a one-off migration that re-tags the 122 rows (reviewed by the owner).
3. Mariuscomper import (after the taxonomy lands): add the 20 rows to `proiecte.csv` from
   `~/devbox/mc-i/index.csv` + `summaries/<slug>.json` (`rezultat.minimal`/title → `descriere_scurta`,
   `rezultat.extins` joined → `descriere`; categorii/tip_proiect → domeniu/format crosswalk), with the
   placement above; then `uv run scripts/profile.py --only <the 20 slugs>`. Uses the `add-new-url`
   skill's conventions.

## Verification

`python3 scripts/validate.py`, `python3 scripts/build.py`, preview with
`python3 -m http.server -d site 8000`: filters per facet, "Pe domenii" grouping, an entry page with
JSON-LD, the new tab count.
