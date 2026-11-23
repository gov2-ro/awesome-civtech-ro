"""Fixture cards and a temporary data root for the tests and the browser check of the data-set card (docs/briefs/data-set-card-build.md).

The real `integrare/fise-date.csv` has a header only. `make_root` builds a temporary package whose files are symbolic links to the real ones, except
`integrare/`, which is a copy with the fixture rows in `fise-date.csv`. No test writes into the real data root.
"""
import shutil
from pathlib import Path

import common
from common import CARD_COLS, write_csv

REAL = common.PUBLIC_ROOT.parent


def card(**values) -> dict:
    """One row of `fise-date.csv`; a column that the caller leaves out is empty."""
    return {c: values.get(c, "") for c in CARD_COLS}


# One card on `sicap-ai` (two access codes, three identifiers, one key variable) and one on an entry with no inventory fields (`textdelege`).
SICAP = card(id="S001", slug="sicap-ai", set="Achiziții directe din SEAP", furnizor="seap-sicap", inregistrare="o achiziție directă", granularitate="achizitie-directa",
             acces="web|api-cheie", url_acces="|https://api.sicap.ai/v1/openapi", identificatori="cui:autoritate-contractanta|cui:furnizor|cpv:obiect",
             variabile_cheie="cpv", dovada="https://sicap.ai/|https://api.sicap.ai/v1/openapi", baza="observat", verificat_la="2026-11-20", stare="acceptat")
NO_FIELDS = card(id="S002", slug="textdelege", set="Legile României cu istoricul articolelor", furnizor="portal-legislativ", inregistrare="un articol dintr-un act normativ",
                 perioada="1990–", acces="fisier", url_acces="https://github.com/lexifina/romania-law", identificatori="", dovada="https://github.com/lexifina/romania-law/blob/main/DATA.md",
                 baza="declarat", verificat_la="2026-11-21", nota_metoda="Textul vine din Monitorul Oficial; istoricul este reconstruit din modificări.", stare="acceptat")
FIXTURE = [SICAP, NO_FIELDS]


def make_root(tmp: Path, cards: list[dict] | None = None) -> Path:
    """The integration root of a temporary package under `tmp`, with `cards` (default: the two fixture cards) as the rows of `fise-date.csv`."""
    package = Path(tmp) / "taxonomy-v2"
    package.mkdir(parents=True)
    for source in REAL.iterdir():
        if source.name == "integrare":
            shutil.copytree(source, package / "integrare")
        else:
            (package / source.name).symlink_to(source.resolve())
    root = package / "integrare"
    write_csv(root / common.CARDS_FILE, CARD_COLS, FIXTURE if cards is None else cards)
    return root
