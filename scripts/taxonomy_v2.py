"""Taxonomy v2 data package: file resolution, loading, structural checks and the editorial JSON export. Stdlib only.

A package root holds schema.json and the tables that it lists (data/taxonomy-v2/). An overlay root, such as an
integration copy, holds pachet.json and its own entry-level tables; it takes every other file from its base package.
schema.json is the structural contract: headers, keys and field rules. Code values, labels and order live in
valori.csv, link roles in roluri-linkuri.csv, and host lookup in gazde-linkuri.csv. Nothing here writes into source/,
reference/ or observatii/; export() writes only catalogue.json in the selected root.
"""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

OVERLAY = "pachet.json"
ID = re.compile(r"^[a-z][a-z0-9-]*:[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ROLE_ID = re.compile(r"^[a-z]+$")  # the role part of a "rol:URL" token in `linkuri`
HOST = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
OBSERVATIONS = ("profil.csv", "mentiuni.csv", "mentiuni_etichete.csv")
# `clasificare_stare` of an entry that stays in the data and out of the public build. The publication gate accepts it.
HIDDEN = "ascuns"
# `relatie_date` of an entry with nothing to extract (a guide, a course, a campaign, an article, a list of links).
NO_DATA = "fara-date"
# Keys that draft.1 kept in JSON and draft.2 moved to CSV. Their presence is a second editorial source.
MOVED_SETTINGS = {"sectiuni": "valori.csv (lista sectiune_url)", "roluri_linkuri": "roluri-linkuri.csv și gazde-linkuri.csv"}
MOVED_SCHEMA = {"enums": "valori.csv", "relation_predicates": "valori.csv (lista relatie_predicat)",
                "concept_fields": "field_rules"}
# Columns of intrari.csv that keep the original v1 record, compared with the source snapshot by --baseline.
PRESERVED = {"nume": "nume", "descriere_scurta": "descriere_scurta", "descriere": "descriere", "url": "url", "linkuri": "linkuri",
             "localitate_originala": "oras", "autor_original": "autor", "contact": "contact", "civictech_original": "civictech",
             "stare": "stare", "nota": "nota"}


class PackageError(Exception):
    """The root is not a readable v2 package (missing file, bad JSON, bad overlay)."""


def values(cell: str) -> list[str]:
    """A v2 list cell: IDs separated by `|`, no spaces. Empty means unknown or not applicable."""
    return cell.split("|") if cell else []


def http_evidence(value: str) -> bool:
    """An evidence link must open an HTTP page. Malformed links are validation errors."""
    try:
        url = urlsplit(value)
        return url.scheme in ("http", "https") and bool(url.hostname) and not any(c.isspace() for c in value)
    except ValueError:
        return False


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_v2(root: Path) -> bool:
    return (Path(root) / "schema.json").exists() or (Path(root) / OVERLAY).exists()


class Files:
    """Where each file of a package root lives. In an overlay, `local_files` come from the overlay and the rest from
    its base; the base must be a full package, never another overlay."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.overlay = None
        self.base = self.root
        if (self.root / OVERLAY).exists():
            self.overlay = json.loads((self.root / OVERLAY).read_text(encoding="utf-8"))
            self.base = (self.root / self.overlay["base"]).resolve()
            if (self.base / OVERLAY).exists() or not (self.base / "schema.json").exists():
                raise PackageError(f"{OVERLAY}: base {self.base} is not a full package")
            if (self.root / "schema.json").exists():
                raise PackageError(f"{OVERLAY}: an overlay takes schema.json from its base, not from {self.root}")
        elif not (self.root / "schema.json").exists():
            raise PackageError(f"{self.root}: no schema.json or {OVERLAY}")

    def local(self, name: str) -> bool:
        return self.overlay is None or name.split("/")[0] in self.overlay["local_files"]

    def path(self, name: str) -> Path:
        return (self.root if self.local(name) else self.base) / name

    @property
    def observations(self) -> Path:
        return self.path("observatii")


def read_table(path: Path) -> tuple[list[str], list[dict]]:
    """Header and rows of one CSV, values unchanged. A row of the wrong width has None in it."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


class Package:
    """Every table of one root, read once. `problems` collects structural failures found while reading."""

    def __init__(self, root: Path):
        self.files = Files(root)
        self.problems: list[str] = []
        read_json = lambda name: json.loads(self.files.path(name).read_text(encoding="utf-8"))
        try:
            self.schema = read_json("schema.json")
            self.settings = read_json("setari.json")
        except (OSError, json.JSONDecodeError) as e:
            raise PackageError(str(e)) from e
        self.manifest = read_json("manifest.json") if self.files.path("manifest.json").exists() else {}
        self.versions = read_json("versiuni.json") if self.files.path("versiuni.json").exists() else []
        self.tables: dict[str, list[dict]] = {}
        # An overlay can add tables of its own (a change log, vocabulary proposals); it declares their headers.
        headers = {**self.schema["headers"], **(self.files.overlay or {}).get("headers", {})}
        for name, columns in headers.items():
            path = self.files.path(name)
            if not path.exists():
                self.problems.append(f"{name}: missing file")
                self.tables[name] = []
                continue
            header, rows = read_table(path)
            if header != columns:
                self.problems.append(f"{name}: header differs from schema.json")
            for n, row in enumerate(rows, 2):
                if None in row or any(v is None for v in row.values()):
                    self.problems.append(f"{name}:{n}: row width differs from the header")
            self.tables[name] = rows
        self.codes: dict[str, dict[str, dict]] = {}
        for row in sorted(self.tables.get("valori.csv", []), key=lambda r: (r["lista"], _int(r["ordine"]))):
            self.codes.setdefault(row["lista"], {})[row["cod"]] = row
        self.roles = {r["id"]: r for r in sorted(self.tables.get("roluri-linkuri.csv", []), key=lambda r: _int(r["ordine"]))}
        self.hosts = {r["gazda"]: r["rol"] for r in self.tables.get("gazde-linkuri.csv", [])}
        self.concepts = {r["id"]: r for r in self.tables.get("concepte.csv", [])}
        self.areas = {r["id"]: r for r in self.tables.get("arii.csv", [])}
        self.entries = {r["slug"]: r for r in self.tables.get("intrari.csv", [])}

    @property
    def version(self) -> str:
        return self.schema["version"]

    def rules(self, table: str) -> dict:
        return self.schema.get("field_rules", {}).get(table, {})

    def label(self, lst: str, code: str, lang: str = "ro") -> str:
        row = self.codes.get(lst, {}).get(code)
        return row[f"eticheta_{lang}"] if row else code

    def link_roles(self) -> list[dict]:
        """The roles in the v1 settings shape, [{key, label, hosts}], in their editorial order."""
        hosts: dict[str, list[str]] = {}
        for host, role in self.hosts.items():
            hosts.setdefault(role, []).append(host)
        return [{"key": k, "label": r["eticheta_ro"], "hosts": hosts.get(k, [])} for k, r in self.roles.items() if r["statut"] != "retras"]

    def sections(self) -> list[dict]:
        return [{"key": k, "label": r["eticheta_ro"]} for k, r in self.codes.get("sectiune_url", {}).items() if r["statut"] != "retras"]

    def ancestors(self, ident: str) -> set[str]:
        """Every broader concept of `ident`, transitively (cycle-safe)."""
        out, todo = set(), list(values(self.concepts.get(ident, {}).get("mai_larg", "")))
        while todo:
            parent = todo.pop()
            if parent in self.concepts and parent not in out:
                out.add(parent)
                todo += values(self.concepts[parent]["mai_larg"])
        return out

    def roots(self, ident: str) -> set[str]:
        """The top-level subjects above `ident` (itself when it has no broader concept)."""
        chain = self.ancestors(ident) | {ident}
        return {c for c in chain if c in self.concepts and not self.concepts[c]["mai_larg"]}


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def load(root) -> Package:
    return Package(Path(root))


def check(root, baseline: bool = False, publication: bool = False, package: "Package | None" = None) -> tuple[list[str], dict]:
    """Structural errors of the package at `root`, and a summary of its counts. `baseline` also proves that the copy
    preserves the source snapshots; `publication` adds the public-build gate (accepted classifications only).
    A detached overlay (pachet.json has `detached`, see integrare.py) is editorial: it stops proving the initial state,
    so `baseline` does not apply to it. `package` is a package already loaded (and changed in memory) from `root`: the review
    tool checks a decision before it writes the file."""
    pkg = package if package is not None else load(root)
    baseline = baseline and not (pkg.files.overlay or {}).get("detached")
    errors = list(pkg.problems)
    fail = errors.append
    schema, settings = pkg.schema, pkg.settings
    for key, where in MOVED_SCHEMA.items():
        if key in schema:
            fail(f"schema.json: `{key}` duplicates {where}; keep one editable source")
    for key in settings:
        if key in MOVED_SETTINGS:
            fail(f"setari.json: `{key}` duplicates {MOVED_SETTINGS[key]}; keep one editable source")
        elif key not in schema.get("settings_keys", []):
            fail(f"setari.json: unknown key `{key}`")
    if pkg.versions and pkg.versions[-1]["version"] != pkg.version:
        fail(f"versiuni.json: the last version is not schema.json's {pkg.version}")
    if errors:
        return errors, {}

    for name, key in schema["keys"].items():
        seen = set()
        for n, row in enumerate(pkg.tables[name], 2):
            ident = tuple(row[k] for k in key)
            if not all(ident) or ident in seen:
                fail(f"{name}:{n}: missing or duplicate {'+'.join(key)}: {'|'.join(ident)!r}")
            seen.add(ident)

    lifecycle = set(schema["lifecycle_status"])
    referenced = {r["list"] for rules in schema["field_rules"].values() for r in rules.values() if r.get("kind") == "code"}
    for lst in referenced - set(pkg.codes):
        fail(f"valori.csv: schema.json refers to the missing code list `{lst}`")
    for lst in set(pkg.codes) - referenced:
        fail(f"valori.csv: code list `{lst}` is not referenced by schema.json")
    for lst, codes in pkg.codes.items():
        orders = Counter(r["ordine"] for r in codes.values())
        for code, row in codes.items():
            if code != code.strip() or "|" in code:
                fail(f"valori.csv {lst}: untrimmed code or list separator in {code!r}")
            if orders[row["ordine"]] > 1:
                fail(f"valori.csv {lst}: duplicate order {row['ordine']}")
    for rid in pkg.roles:
        if not ROLE_ID.fullmatch(rid):
            fail(f"roluri-linkuri.csv: role ID {rid!r} cannot appear in a `rol:URL` link token")
    if "web" not in pkg.roles:
        fail("roluri-linkuri.csv: the fallback role `web` is missing")
    for host in pkg.hosts:
        if not HOST.fullmatch(host):
            fail(f"gazde-linkuri.csv: {host!r} is not a plain lowercase host (no scheme, path, or wildcard)")

    def field(table: str, ident: str, col: str, cell: str, rule: dict, row: dict):
        kind, where = rule.get("kind"), f"{table} {ident}"
        if not cell:
            allow = rule.get("empty_allowed_when", {})
            if (rule.get("required") or rule.get("min_items", 0) > 0) and not any(row.get(k) in v for k, v in allow.items()):
                fail(f"{where}: {col} is required")
            return
        if kind == "code":
            code = pkg.codes.get(rule["list"], {}).get(cell)
            if code is None:
                fail(f"{where}: unknown {col} code {cell!r} (list {rule['list']})")
            elif code["statut"] == "retras":
                fail(f"{where}: {col} uses the retired code {cell!r}")
        elif kind == "lifecycle":
            if cell not in lifecycle:
                fail(f"{where}: invalid {col} {cell!r}")
        elif kind == "integer":
            if not cell.isdigit():
                fail(f"{where}: {col} must be an integer")
        elif kind == "slug":
            if not SLUG.fullmatch(cell):
                fail(f"{where}: invalid slug")
        elif kind == "role":
            if cell not in pkg.roles:
                fail(f"{where}: unknown link role {cell!r}")
        elif kind in ("concept", "area", "concept_ref", "text_list"):
            items = values(cell)
            if len(items) != len(set(items)) or any(not x or x != x.strip() for x in items):
                fail(f"{where}: duplicate, blank, or untrimmed list item in {col}")
            if rule.get("max_items") == 1 and len(items) > 1:
                fail(f"{where}: {col} allows one value, found {len(items)}")
            elif rule.get("max_items") is not None and len(items) > rule["max_items"]:
                fail(f"{where}: {col} allows at most {rule['max_items']} values")
            if kind == "area":
                for x in items:
                    if x not in pkg.areas:
                        fail(f"{where}: unknown area {x}")
            elif kind in ("concept", "concept_ref"):
                for x in items:
                    concept = pkg.concepts.get(x)
                    if concept is None:
                        fail(f"{where}: unknown concept {x} in {col}")
                        continue
                    scheme = rule.get("scheme") or (row["schema"] if rule.get("same_scheme") else None)
                    if scheme and concept["schema"] != scheme:
                        fail(f"{where}: {col} needs the scheme {scheme}, found {x}")
                    if kind == "concept" and concept["statut"] == "retras":
                        fail(f"{where}: assignment uses a retired concept: {x}")
                    if rule.get("level") == "root" and concept["mai_larg"]:
                        fail(f"{where}: {col} requires top-level subjects, found {x}")
                    if rule.get("level") == "narrower" and not concept["mai_larg"]:
                        fail(f"{where}: {col} requires narrower subjects, found {x}")

    for table, rules in schema["field_rules"].items():
        key = schema["keys"].get(table, [None])
        for n, row in enumerate(pkg.tables.get(table, []), 2):
            ident = "|".join(row[k] for k in key) if key[0] else str(n)
            for col, rule in rules.items():
                field(table, ident, col, row[col], rule, row)

    for slug, row in pkg.entries.items():
        for tok in re.split(r"[\s|]+|,(?=\s|$)", row["linkuri"].strip()):
            m = re.match(r"^([a-z]+):(https?://.+)$", tok)
            if m and m.group(1) not in pkg.roles:
                fail(f"intrari.csv {slug}: unknown link role {m.group(1)!r}")

    preferred = set()
    for ident, row in pkg.concepts.items():
        if not ID.fullmatch(ident) or ident.split(":")[0] != row["schema"]:
            fail(f"concepte.csv: invalid ID or scheme: {ident}")
        for lang in ("ro", "en"):
            label = (row["schema"], lang, row["eticheta_" + lang].casefold())
            if label in preferred:
                fail(f"concepte.csv {ident}: duplicate preferred label in the same scheme")
            preferred.add(label)
    _acyclic(pkg.concepts, "mai_larg", "concepte.csv", fail)
    for ident, row in pkg.areas.items():
        if row["cod_iso_3166_1"] and not re.fullmatch(r"[A-Z]{2}", row["cod_iso_3166_1"]):
            fail(f"arii.csv {ident}: invalid country code")
    _acyclic(pkg.areas, "parinte", "arii.csv", fail)

    for slug, row in pkg.entries.items():
        subjects = set(values(row["subiecte"]))
        if row["subiect_principal"] and row["subiect_principal"] not in subjects:
            fail(f"intrari.csv {slug}: primary subject missing from subiecte")
        if subjects and not row["subiect_principal"]:
            fail(f"intrari.csv {slug}: subiecte without a primary subject")
        for topic in values(row["teme"]):
            if topic in pkg.concepts and not pkg.roots(topic) <= subjects:
                fail(f"intrari.csv {slug}: topic root missing from subiecte: {topic}")
        chosen = [pkg.areas[x] for x in values(row["arii_acoperite"]) if x in pkg.areas]
        if row["nivel_acoperire"] == "local" and not any(a["tip"] in ("judet", "localitate") for a in chosen):
            fail(f"intrari.csv {slug}: local coverage needs a locality or county")
        if row["tip_entitate"] == "organizatie" and row["sectiune_url"] != "organizatie":
            fail(f"intrari.csv {slug}: organisation URL section differs")
        if row.get("detaliere_date"):
            if not http_evidence(row.get("dovada_detaliere", "")):
                fail(f"intrari.csv {slug}: a data breakdown needs an HTTP evidence URL")
        if row["tip_organizatie"] and row["tip_entitate"] != "organizatie":
            fail(f"intrari.csv {slug}: organisation type on a non-organisation")
        # The relation to data describes a project or a resource. A package without the column (an older run) has none.
        relation = row.get("relatie_date", "")
        if relation and row["tip_entitate"] == "organizatie":
            fail(f"intrari.csv {slug}: relatie_date on an organisation (only a project or a resource has one)")
        if relation == NO_DATA and row.get("detaliere_date"):
            fail(f"intrari.csv {slug}: relatie_date {NO_DATA} excludes detaliere_date")

    for row in pkg.tables.get("relatii.csv", []):
        if row["subiect"] not in pkg.entries or (row["obiect"] and row["obiect"] not in pkg.entries):
            fail(f"relatii.csv {row['id']}: unknown endpoint")
        if bool(row["obiect"]) == bool(row["obiect_literal"]):
            fail(f"relatii.csv {row['id']}: choose one object ID or literal")
        if row["predicat"] != "atribuit_in_sursa" and row["stare"] == "acceptat" and not row["valoare_sursa"]:
            fail(f"relatii.csv {row['id']}: an accepted role needs source evidence")
        if row["predicat"] == "date_din" and row["stare"] == "acceptat":
            if not http_evidence(row["valoare_sursa"]):
                fail(f"relatii.csv {row['id']}: a data source needs an HTTP evidence URL")
    for row in pkg.tables.get("revizuire.csv", []):
        if row["slug"] not in pkg.entries:
            fail(f"revizuire.csv {row['id']}: unknown entry {row['slug']}")
        if row["stare"] in ("acceptat", "respins") and not row["decizie_editor"]:
            fail(f"revizuire.csv {row['id']}: a closed item needs an editor decision")
        # A technical closure needs no editorial decision: it says why in `motiv` and never carries a decision of the editor.
        if row["stare"] == "tehnic" and (not row["motiv"].strip() or row["decizie_editor"].strip()):
            fail(f"revizuire.csv {row['id']}: a technical closure needs a reason (motiv) and no editor decision")
    if pkg.files.overlay is None:
        for row in pkg.tables.get("atribuiri-initiale.csv", []):
            if row["slug"] not in pkg.entries or row["concept"] not in pkg.concepts:
                fail("atribuiri-initiale.csv: unknown entry or concept")
    for row in pkg.tables.get("corespondente-v1.csv", []):
        for x in values(row["concepte_candidate"]):
            if x not in pkg.concepts:
                fail(f"corespondente-v1.csv {row['termen_original']}: unknown concept {x}")
    response = pkg.files.path("reference/eurovoc-response.json")
    official = json.loads(response.read_text(encoding="utf-8"))["results"]["bindings"] if response.exists() else []
    official_labels = {r["concept"]["value"]: (r.get("ro", {}).get("value", ""), r["en"]["value"]) for r in official}
    seen_maps = set()
    for row in pkg.tables.get("mapari-externe.csv", []):
        mapping = (row["concept_local"], row["uri_tinta"])
        if mapping in seen_maps:
            fail(f"mapari-externe.csv: duplicate mapping {mapping}")
        seen_maps.add(mapping)
        if row["concept_local"] not in pkg.concepts:
            fail(f"mapari-externe.csv: unknown local concept {row['concept_local']}")
        if row["vocabular"] == "EuroVoc" and official_labels.get(row["uri_tinta"]) != (row["eticheta_tinta_ro"], row["eticheta_tinta_en"]):
            fail(f"mapari-externe.csv: identifier/labels do not match the official snapshot: {mapping}")

    sources = _check_snapshots(pkg, fail)
    _check_observations(pkg, sources, baseline, fail)
    if baseline:
        _check_baseline(pkg, sources, fail)
    if publication:
        hidden = {slug for slug, row in pkg.entries.items() if row["clasificare_stare"] == HIDDEN}
        for slug, row in pkg.entries.items():
            if row["clasificare_stare"] not in ("acceptat", HIDDEN):
                fail(f"publication: {slug} has the classification state {row['clasificare_stare']!r}, not acceptat or {HIDDEN}")
        for row in pkg.tables.get("revizuire.csv", []):
            # Only `deschis` blocks the gate. A technical closure (`tehnic`) never counts, whatever its priority.
            # An item of a hidden entry never counts: that entry does not reach the public site.
            if row["stare"] == "deschis" and row["prioritate"] == "mare" and row["slug"] not in hidden:
                fail(f"publication: {row['slug']} has the open high-priority review item {row['id']}")

    entries = pkg.entries.values()
    summary = {
        "schema_version": pkg.version, "root": str(pkg.files.root), "overlay": pkg.files.overlay is not None,
        "detached": (pkg.files.overlay or {}).get("detached"),
        "entries": len(pkg.entries), "concepts": len(pkg.concepts), "code_lists": len(pkg.codes),
        "codes": sum(len(c) for c in pkg.codes.values()), "link_roles": len(pkg.roles), "link_hosts": len(pkg.hosts),
        "relations": len(pkg.tables.get("relatii.csv", [])), "review_items": len(pkg.tables.get("revizuire.csv", [])),
        "open_review_items": sum(r["stare"] == "deschis" for r in pkg.tables.get("revizuire.csv", [])),
        "technical_review_items": sum(r["stare"] == "tehnic" for r in pkg.tables.get("revizuire.csv", [])),
        "classification_states": dict(Counter(r["clasificare_stare"] for r in entries)),
        "without_primary_subject": sum(not r["subiect_principal"] for r in entries),
        "maturity": dict(Counter(r["maturitate"] or "-" for r in entries)),
        "external_mappings": len(pkg.tables.get("mapari-externe.csv", [])),
        "primary_subjects": dict(Counter(r["subiect_principal"] or "-" for r in entries)),
    }
    return errors, summary


def _acyclic(nodes: dict, parent_field: str, name: str, fail):
    visiting, visited = set(), set()

    def visit(ident):
        if ident in visiting:
            fail(f"{name} {parent_field}: hierarchy cycle at {ident}")
            return
        if ident in visited:
            return
        visiting.add(ident)
        for parent in values(nodes[ident][parent_field]):
            if parent in nodes:
                visit(parent)
        visiting.remove(ident)
        visited.add(ident)

    for ident in nodes:
        visit(ident)


def _check_snapshots(pkg: Package, fail) -> dict[str, list[dict]]:
    """Hash the immutable source and reference snapshots; return the source CSV rows by file name."""
    out = {}
    for ref in pkg.manifest.get("references", []):
        if sha256(pkg.files.path(ref["path"])) != ref["sha256"]:
            fail(f"{ref['path']}: immutable reference snapshot changed")
    for src in pkg.manifest.get("sources", []):
        snapshot = pkg.files.path(src["snapshot"])
        if sha256(snapshot) != src["sha256"]:
            fail(f"{src['snapshot']}: immutable source snapshot changed")
        if snapshot.suffix == ".csv":
            out[snapshot.name] = read_table(snapshot)[1]
    return out


def _check_observations(pkg: Package, sources: dict, baseline: bool, fail):
    for name in OBSERVATIONS:
        observation = pkg.files.observations / name
        if not observation.exists():
            if name in sources:
                fail(f"observatii/{name}: missing working observation table")
            continue
        header, rows = read_table(observation)
        if sources.get(name) and header != list(sources[name][0]):
            fail(f"observatii/{name}: headers differ from the source observation schema")
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            fail(f"observatii/{name}: row width differs from its header")
        if baseline and observation.read_bytes() != pkg.files.path(f"source/{name}").read_bytes():
            fail(f"baseline: observations differ from source/{name}")


def source_row(pkg: Package, sources: dict, row: dict) -> dict | None:
    """The original v1 record of an entry, by its source identity (file + CSV record number, header = 1)."""
    try:
        found = sources[row["sursa_fisier"]][int(row["sursa_rand"]) - 2]
    except (KeyError, ValueError, IndexError):
        return None
    return found if found["slug"] == row["slug"] else None


def _check_baseline(pkg: Package, sources: dict, fail):
    originals = {r["slug"]: r for name in ("proiecte.csv", "orgs.csv") for r in sources.get(name, [])}
    if set(pkg.entries) != set(originals):
        fail(f"baseline: entry slugs differ from the {len(originals)} source entries")
    for slug, row in pkg.entries.items():
        original = source_row(pkg, sources, row)
        if original is None:
            fail(f"baseline {slug}: invalid source row reference")
            continue
        for dest, src in PRESERVED.items():
            if row[dest] != original.get(src, ""):
                fail(f"baseline {slug}: original value differs in {dest}")
    for row in originals.values():
        for col in ("domeniu", "tip", "cuvinte"):
            for token in (row.get(col, "") or "").split("|" if col == "domeniu" else ","):
                if token.strip() and not any(c["camp_original"] == col and c["termen_original"] == token.strip()
                                             for c in pkg.tables.get("corespondente-v1.csv", [])):
                    fail(f"baseline: no crosswalk for {col}={token.strip()}")
    # The initial assignment ledger describes the base package's own intrari.csv, not an overlay's.
    if pkg.files.overlay is None:
        for row in pkg.tables.get("atribuiri-initiale.csv", []):
            if row["concept"] not in values(pkg.entries.get(row["slug"], {}).get(row["camp"], "")):
                fail(f"baseline: initial assignment absent from entry {row['slug']}")


def entry_json(pkg: Package, row: dict) -> dict:
    """One intrari.csv row with list fields as arrays and single-valued concept fields as a string or null."""
    rules = pkg.rules("intrari.csv")
    out = {}
    for col, value in row.items():
        rule = rules.get(col, {})
        if rule.get("kind") in ("concept", "area") and rule.get("max_items") == 1:
            out[col] = value or None
        elif rule.get("kind") in ("concept", "area"):
            out[col] = values(value)
        else:
            out[col] = value
    return out


def export(root) -> dict:
    """The complete editorial export (catalogue.json): every table, plus the settings that consumers expect,
    assembled from the CSV code lists. A generated copy, never an editorial source."""
    pkg = load(root)
    lists = ("mai_larg", "asociate", "alternative_ro")
    data = {
        "schema_version": pkg.version, "status": "editorial_proposal", "snapshot_date": pkg.manifest.get("created", ""),
        "entries": [entry_json(pkg, r) for r in pkg.entries.values()],
        "concepts": [{k: values(v) if k in lists else v for k, v in r.items()} for r in pkg.concepts.values()],
        "areas": pkg.tables["arii.csv"], "relations": pkg.tables["relatii.csv"],
        "external_mappings": pkg.tables["mapari-externe.csv"],
        "code_lists": {lst: [{"cod": c, **{k: r[k] for k in ("eticheta_ro", "eticheta_en", "definitie_ro", "statut")}}
                             for c, r in codes.items()] for lst, codes in pkg.codes.items()},
        "settings": {"sectiuni": pkg.sections(), "roluri_linkuri": pkg.link_roles(), "site": pkg.settings["site"]},
    }
    if pkg.files.overlay is not None:
        data["overlay"] = {k: v for k, v in pkg.files.overlay.items() if k in ("purpose", "base", "local_files", "source_run")}
    return data


def write_export(root):
    path = Files(root).root / "catalogue.json"
    path.write_text(json.dumps(export(root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
