# Site structure and entity lookup preview

The preview adds structure observations to each project's existing profile.
It also adds `/entitati/`, an exact identifier lookup over observed records.
All source collection remains separate from the site-health profiler.

## Build and open

```sh
python3 scripts/build.py --with-structure --site-dir /tmp/civtech-entity-preview
python3 -m http.server 8784 --bind 127.0.0.1 -d /tmp/civtech-entity-preview
```

Open these local pages:

- [Antibiotice by CUI](http://127.0.0.1:8784/entitati/?namespace=ro:cui&value=1973096).
- [MAE by CUI](http://127.0.0.1:8784/entitati/?namespace=ro:cui&value=4266863).
- [București territory by SIRUTA](http://127.0.0.1:8784/entitati/?namespace=ro:siruta&value=179132).
- [România Transparentă project profile](http://127.0.0.1:8784/proiect/romania-transparenta/).

The default build replays the five tracked recipes without network requests or ignored caches.
It includes eleven observed records and four accepted correspondences as of 2026-10-30.
It reads the durable owner decisions in `data/taxonomy-v2/structura/decisions.json`.
The build never changes those decisions.

To include a broader discovery store, supply its directory:

```sh
python3 scripts/build.py --with-structure \
  --structure-store /tmp/civtech-structure-catalogue \
  --site-dir /tmp/civtech-entity-preview
```

The build checks that store and reads it without changes.
Only records and observations for selected catalogue entries reach the preview.
The catalogue URL must still match the store's project URL.
The durable repository decision file remains the identity review source.
A store's own decision file does not override it.

The flag requires a v2 root and an output directory outside the repository.
It cannot write the public `site/` directory.
A build without the flag removes old lookup outputs and structure payloads from that output directory.
The existing inventory preview can use the same build through `--with-inventory`.

## Project profile

The **Structura site-ului** panel contains:

- **Secțiuni și colecții**: labelled collections, with section links where an exact listing URL is known.
- **Tipare URL**: templates, variable namespaces, collection context and observation status.
- **Endpointuri API**: method, URL template, collection uses and separate declared/observed access facts.
- Source links, observation times and SHA-256 receipts for each declaration.

A data collection does not imply a distinct website section.
The panel only links a section when a retained listing pattern establishes its URL.
Placeholders remain text. They never become links to fabricated entity pages.
A missing project profile reports that the site is not yet included.
An empty pattern or API list means no included observation, not absence on the source site.

## Identifier lookup

A lookup scope includes the namespace and issuer.
A local scope also includes its project.
Values match exactly after trimming the user's surrounding input spaces.
The lookup preserves leading zeroes, case, prefixes and punctuation.
An unknown or ambiguous namespace in a shared URL produces an explicit message.

The lookup shows observed records and direct accepted counterparts.
It does not expand a chain of accepted pairs into an inferred entity cluster.
Two records with the same identifier can appear without a confirmed link.
The interface only labels a correspondence confirmed when an explicit accepted assertion supports it.
Conflicts suppress that confirmation.
Hidden catalogue entries and links with a missing endpoint stay out of the preview.

Profile URLs are derived from typed templates and labelled accordingly.
They are not live availability checks.
The igov Antibiotice record has a source locator, but no invented frontend detail URL.
The București SIRUTA pair remains separate from institution CUI `4267117`.

The page keeps its search in URL parameters and supports Back, Forward and Reload.
It loads one local payload and makes no requests to source projects.
Source links only open when a person follows them.
The projection excludes raw extracts, filesystem paths, request journals and editorial notes.
Observation times do not establish legal validity periods.

## Checks

```sh
python3 -m unittest discover -s scripts -p 'test_structure_site.py'
uv run scripts/check_structure_preview.py http://127.0.0.1:8784/
```

The browser checks include desktop, mobile, direct project URLs, local IDs, territory separation, error recovery and non-transitive lookup.
The [implementation report](reports/site-structure-preview.md) records the measured build.
