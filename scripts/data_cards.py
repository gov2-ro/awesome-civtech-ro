"""The data-set card (docs/specs/data-set-card.md): the checks of `fise-date.csv` for validate.py, and the payload that build.py puts in `data.json`.

`card_problems` is a pure function of the rows and a context; `card_context` reads the context from a data root. The HTML of a card is in entry_page.py.
Nothing here writes a file or makes a request.
"""
import json
import re
from datetime import date
from pathlib import Path

from common import (CARD_BASES, CARD_BASIS_LABELS, CARD_COLS, CARD_ID, CARD_IDENTIFIER_LABELS, CARD_IDENTIFIERS, CARD_KEY_VARIABLES_MAX, CARD_OWN_PROVIDER,
                    CARD_STATES, PUBLIC_ROOT, card_identifier, card_items, load_cards, observation_paths, provider_table, providers_path, read_csv, read_providers)

URL = re.compile(r"^https?://[^\s/$.?#][^\s]*\.[^\s]+$", re.I)
PERIOD = re.compile(r"^\d{4}(?:[–-](?:\d{4})?)?$")  # `2007–2025`, `2019–` (still updated) or one year
SET_LENGTH = 80
STALE_DAYS = 365
OWN_PROVIDER_NAME = "autorul intrării"
DERIVED = "iesire-derivata"  # `categorie` of a group of `inventar-concepte.json` that is a calculated value


def recipe_namespaces(root: Path) -> dict[str, set[str]]:
    """{slug: ids of the namespaces} of the structure recipes (`structura/recipes/*.json`, key `project_slug`). An entry without a recipe is not a key."""
    found: dict[str, set[str]] = {}
    for path in sorted((Path(root).parent / "structura" / "recipes").glob("*.json")):
        recipe = json.loads(path.read_text(encoding="utf-8"))
        found.setdefault(recipe["project_slug"], set()).update(n["id"] for n in recipe.get("namespaces", []))
    return found


def read_concepts(root: Path) -> dict[str, dict]:
    """{id: group} of `inventar-concepte.json`, the groups of variables that the finder shows."""
    path = Path(root).parent / "inventar-concepte.json"
    return {c["id"]: c for c in json.loads(path.read_text(encoding="utf-8")).get("concepte", [])} if path.exists() else {}


def read_entry_fields(root: Path) -> dict[str, list[dict]]:
    """{slug: [field]} from `observatii/inventare/campuri.csv`, a field in the shape that `group_hits` reads (name, path, role, source) plus the source address."""
    path = observation_paths(root)["profile"].parent / "inventare" / "campuri.csv"
    found: dict[str, list[dict]] = {}
    if path.exists():
        for r in read_csv(path):
            field = {"name": r["nume"], "path": r["cale"], "role": r["rol"], "source": r["sursa_id"], "url": r["url"]}
            for slug in r["proiecte"].split("|"):
                found.setdefault(slug, []).append(field)
    return found


def card_context(root: Path = PUBLIC_ROOT, package=None, scope: dict | None = None) -> dict:
    """What `card_problems` needs from a root. `package` is a loaded `taxonomy_v2.Package`; `scope` is `common.inventory_scope` of the entries.
    `fields` and `concepts` are the generated inventory and the dictionary of groups; a root without them has no key variable that exists."""
    import taxonomy_v2
    from common import inventory_scope, load_catalogue
    root = Path(root)
    pkg = package or taxonomy_v2.load(root)
    providers: dict[str, set[str]] = {}
    for name, row in provider_table(read_providers(providers_path(root))).items():
        providers.setdefault(row["furnizor"], set()).add(name)
    relations: dict[str, list[tuple[str, str]]] = {}
    for r in pkg.tables.get("relatii.csv", []):
        name = r["obiect_literal"] or r["obiect"]
        if r["predicat"] == "date_din" and name:
            relations.setdefault(r["subiect"], []).append((name, r["stare"]))
    return {"slugs": set(pkg.entries), "scope": scope if scope is not None else inventory_scope(load_catalogue(root), root), "providers": providers,
            "relations": relations, "codes": {lst: {c for c, row in codes.items() if row["statut"] != "retras"} for lst, codes in pkg.codes.items()},
            "recipes": recipe_namespaces(root), "concepts": read_concepts(root), "fields": read_entry_fields(root)}


def group_matches(slug: str, gid: str, context: dict) -> bool:
    """True when the group reaches at least one field of the entry, by the one matching rule of the finder (`inventory_site.group_hits`)."""
    from inventory_site import group_hits
    cache = context.setdefault("_hits", {})
    if slug not in cache:
        fields = context["fields"].get(slug, [])
        sources = [{"id": s, "url": u} for s, u in dict.fromkeys((f["source"], f["url"]) for f in fields)]
        cache[slug] = {c["id"] for c, _ in group_hits(slug, fields, sources, list(context["concepts"].values()))}
    return gid in cache[slug]


def key_variable_problems(slug: str, item: str, context: dict) -> list[str]:
    """Why one item of `variabile_cheie` does not exist for the entry: an empty list when it does. An item is a group id, or `<sursa_id>#<path>` of `campuri.csv`."""
    if "#" in item:
        source, _, path = item.partition("#")
        if not any(f["source"] == source and f["path"] == path for f in context["fields"].get(slug, [])):
            return [f"variabilă cheie {item}: nu este un câmp al intrării în campuri.csv"]
    elif item not in context["concepts"]:
        return [f"variabilă cheie {item}: nu este un grup din inventar-concepte.json"]
    elif not group_matches(slug, item, context):
        return [f"variabilă cheie {item}: niciun câmp al intrării nu se potrivește cu grupul"]
    return []


def card_problems(rows: list[dict], context: dict, today: date | None = None) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """([(line, message)] errors, [(line, message)] warnings) of `fise-date.csv` (spec section 8). `rows` start at line 2; the header is checked before.
    Errors: an id that is missing, invalid or twice; an unknown slug; a missing `set` or `furnizor`; a provider that is not accepted and not `autor`; a code outside its
    list (`granularitate`, `acces`, `cod` and `rol` of `identificatori`, `baza`, `stare`); `url_acces` and `acces` of different lengths; an address that is no http(s) URL; a `local`
    identifier whose namespace is not in the recipe of the entry; more than six key variables, or one that does not exist for the entry; an accepted card without `inregistrare`,
    `dovada` or `verificat_la`; a date that is not ISO; a card on an entry out of the inventory scope.
    Warnings: no `date_din` relation of the entry to the provider, or only a proposed one; a derived variable without `nota_metoda`; `verificat_la` older than 365 days;
    a `set` over 80 characters; a `perioada` that is no year, no range and not empty."""
    today = today or date.today()
    errors: list[tuple[int, str]] = []
    warnings: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    codes = context["codes"]
    for line, r in enumerate(rows, 2):
        ident = r["id"] or "?"
        err = lambda msg, line=line, ident=ident: errors.append((line, f"{ident}: {msg}"))
        warn = lambda msg, line=line, ident=ident: warnings.append((line, f"{ident}: {msg}"))
        if not CARD_ID.match(r["id"]):
            err("id invalid (S001, S002, …)")
        elif r["id"] in seen:
            err(f"id duplicat (și în linia {seen[r['id']]})")
        seen.setdefault(r["id"], line)
        slug = r["slug"]
        if slug not in context["slugs"]:
            err(f"slug necunoscut: {slug!r}")
        elif context["scope"].get(slug):
            err(f"{slug}: intrarea este în afara ariei inventarului ({context['scope'][slug]}); nu are fișă de set")
        if not r["set"]:
            err("lipsește set")
        elif len(r["set"]) > SET_LENGTH:
            warn(f"set are {len(r['set'])} caractere; sub {SET_LENGTH} se citește mai ușor")
        provider = r["furnizor"]
        if not provider:
            err("lipsește furnizor")
        elif provider != CARD_OWN_PROVIDER and provider not in context["providers"]:
            err(f"furnizor {provider!r} nu este un furnizor acceptat în furnizori.csv și nu este {CARD_OWN_PROVIDER!r}")
        elif provider != CARD_OWN_PROVIDER and slug in context["slugs"]:
            relation = [state for name, state in context["relations"].get(slug, []) if name in context["providers"][provider]]
            if not relation:
                warn(f"{slug}: nicio relație date_din cu furnizorul {provider}")
            elif "acceptat" not in relation:
                warn(f"{slug}: relația date_din cu furnizorul {provider} este doar propusă")
        if r["granularitate"] and r["granularitate"] not in codes.get("granularitate_set", ()):
            err(f"granularitate necunoscută: {r['granularitate']!r}")
        access = card_items(r["acces"])
        for code in access:
            if code not in codes.get("acces_set", ()):
                err(f"cod de acces necunoscut: {code!r}")
        urls = card_items(r["url_acces"])
        if urls and len(urls) != len(access):
            err(f"url_acces are {len(urls)} elemente, acces are {len(access)}")
        for url in [*urls, *card_items(r["dovada"])]:
            if url and not URL.match(url):
                err(f"adresă invalidă: {url!r}")
        for item in card_items(r["identificatori"]):
            code, rest = card_identifier(item)
            if code not in CARD_IDENTIFIERS:
                err(f"cod de identificator necunoscut: {code!r} ({', '.join(CARD_IDENTIFIERS)})")
            elif code == "local":
                if slug in context["slugs"] and rest not in context["recipes"].get(slug, ()):
                    err(f"identificator {item}: {'spațiul de nume nu este în rețeta structurii intrării' if slug in context['recipes'] else 'intrarea nu are rețetă de structură'}")
            elif rest not in codes.get("rol_identificator", ()):
                err(f"identificator {item}: rol necunoscut sau lipsă: {rest!r}")
        keys = card_items(r["variabile_cheie"])
        if len(keys) > CARD_KEY_VARIABLES_MAX:
            err(f"variabile_cheie are {len(keys)} elemente; cel mult {CARD_KEY_VARIABLES_MAX}")
        for item in keys:
            if slug in context["slugs"]:
                for msg in key_variable_problems(slug, item, context):
                    err(msg)
            concept = context["concepts"].get(item)
            if concept and concept.get("categorie") == DERIVED and not r["nota_metoda"]:
                warn(f"variabila derivată {item} are nevoie de nota_metoda (cum se calculează)")
        if r["baza"] and r["baza"] not in CARD_BASES:
            err(f"baza necunoscută: {r['baza']!r} ({', '.join(CARD_BASES)})")
        if r["stare"] not in CARD_STATES:
            err(f"stare necunoscută: {r['stare']!r} ({', '.join(CARD_STATES)})")
        if r["perioada"] and not PERIOD.match(r["perioada"]):
            warn(f"perioada {r['perioada']!r}: scrie 2007–2025, 2019– sau lasă gol")
        checked = None
        if r["verificat_la"]:
            try:
                checked = date.fromisoformat(r["verificat_la"])
            except ValueError:
                err(f"verificat_la nu este o dată ISO: {r['verificat_la']!r}")
        if checked and (today - checked).days > STALE_DAYS:
            warn(f"verificat_la {r['verificat_la']} este mai vechi de {STALE_DAYS} de zile")
        if r["stare"] == "acceptat":
            for column in ("inregistrare", "dovada", "verificat_la"):
                if not r[column]:
                    err(f"un rând acceptat are nevoie de {column}")
    return errors, warnings


def header_problem(header: list[str]) -> str:
    """A message when the header of `fise-date.csv` differs from `CARD_COLS`, else an empty string."""
    missing, extra = [c for c in CARD_COLS if c not in header], [c for c in header if c not in CARD_COLS]
    return "; ".join(x for x in (f"lipsesc coloanele: {', '.join(missing)}" if missing else "", f"coloane necunoscute: {', '.join(extra)}" if extra else "") if x)


# --- The build: the accepted cards of an entry, as `data.json` shows them ----------------------------------------------------------------------------------

def label_of(codes: dict, lst: str, code: str) -> str:
    return (codes.get(lst, {}).get(code) or {}).get("eticheta_ro", code)


def card_payload(card: dict, codes: dict, provider_names: dict[str, str], concepts: dict[str, dict], field_names: dict | None = None) -> dict:
    """One accepted card as an item of `datasets` (spec section 5): the columns of 4.1 but `nota`, with the codes resolved to their labels so that every page reads
    the same words. `codes` is `Package.codes`; `provider_names` is {furnizor: display name}; `concepts` is `read_concepts`."""
    access_codes, urls = card_items(card["acces"]), card_items(card["url_acces"])
    urls = urls or [""] * len(access_codes)
    identifiers = []
    for item in card_items(card["identificatori"]):
        code, rest = card_identifier(item)
        entry = {"code": code, "codeLabel": CARD_IDENTIFIER_LABELS.get(code, code)}
        if code == "local":
            entry |= {"role": "", "roleLabel": "", "namespace": rest}
        else:
            entry |= {"role": rest, "roleLabel": label_of(codes, "rol_identificator", rest)}
        identifiers.append(entry)
    keys = []
    for item in card_items(card["variabile_cheie"]):
        if "#" in item:
            source, _, path = item.partition("#")
            # the field's own name (`risk_score`), not its path (`$.date[].restant_lei`); `field_names` is {(sursa_id, path): nume} of campuri.csv
            keys.append({"source": source, "path": path, "label": (field_names or {}).get((source, path)) or path})
        else:
            keys.append({"id": item, "label": (concepts.get(item) or {}).get("label", item)})
    provider = card["furnizor"]
    own = provider == CARD_OWN_PROVIDER
    return {
        "id": card["id"], "set": card["set"],
        "provider": {"id": provider, "name": OWN_PROVIDER_NAME if own else provider_names.get(provider, provider), "anchor": "" if own else f"f-{provider}"},
        "record": card["inregistrare"],
        "grain": {"code": card["granularitate"], "label": label_of(codes, "granularitate_set", card["granularitate"])} if card["granularitate"] else None,
        "period": card["perioada"],
        "access": [{"code": c, "label": label_of(codes, "acces_set", c), "url": u} for c, u in zip(access_codes, urls)],
        "identifiers": identifiers, "keyVariables": keys, "methodNote": card["nota_metoda"], "evidence": card_items(card["dovada"]),
        "basis": card["baza"], "basisLabel": CARD_BASIS_LABELS.get(card["baza"], ""), "checked": card["verificat_la"],
    }


def cards_by_entry(root: Path, pkg) -> dict[str, list[dict]]:
    """{slug: [payload]} of the accepted cards of a root, each list in `id` order. An entry without an accepted card is not a key."""
    rows = sorted(load_cards(root, accepted_only=True), key=lambda r: r["id"])
    if not rows:
        return {}
    names = {row["furnizor"]: row["nume"] for row in provider_table(read_providers(providers_path(root))).values()}
    concepts = read_concepts(root)
    field_names = {(f["source"], f["path"]): f["name"] for fields in read_entry_fields(root).values() for f in fields}
    found: dict[str, list[dict]] = {}
    for r in rows:
        found.setdefault(r["slug"], []).append(card_payload(r, pkg.codes, names, concepts, field_names))
    return found
