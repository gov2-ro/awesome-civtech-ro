"""docs/DATA-SCHEMA.md names every column that the scripts read or write. Stdlib only.

    python3 scripts/test_docs.py
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402

ROOT = HERE.parent
TEXT = (ROOT / "docs" / "DATA-SCHEMA.md").read_text(encoding="utf-8")


class DataSchemaDoc(unittest.TestCase):
    def missing(self, cols: list[str]) -> list[str]:
        return [c for c in cols if f"`{c}`" not in TEXT]

    def test_v1_and_observation_columns(self):
        for name in ("PROIECTE_COLS", "ORGS_COLS", "PROFIL_COLS", "MENTIUNI_COLS", "ETICHETE_COLS", "FORBIDDEN_COLS"):
            self.assertEqual(self.missing(getattr(common, name)), [], name)

    def test_v2_headers(self):
        for path in (ROOT / "data/taxonomy-v2/schema.json", ROOT / "data/taxonomy-v2/integrare/pachet.json"):
            for table, cols in json.loads(path.read_text(encoding="utf-8"))["headers"].items():
                self.assertEqual(self.missing(cols), [], f"{path.name}: {table}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
