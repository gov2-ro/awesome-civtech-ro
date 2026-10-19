"""Check the isolated taxonomy package. Stdlib only; production data is never written.

python3 data/taxonomy-v2/validate.py
python3 data/taxonomy-v2/validate.py --baseline --export
python3 data/taxonomy-v2/validate.py --root data/taxonomy-v2/integrare --baseline

--root selects another package root or an overlay (default: this folder).
--baseline also proves that the copy retained every source entry and text field.
--export refreshes catalogue.json in the selected root, after all checks pass.
--publication adds the public-build gate: every entry accepted, no open high-priority review item.
The checks live in scripts/taxonomy_v2.py, which scripts/validate.py --data-dir also uses.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
import taxonomy_v2  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=HERE)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--publication", action="store_true")
    args = parser.parse_args()
    errors, summary = taxonomy_v2.check(args.root, baseline=args.baseline, publication=args.publication)
    for error in errors:
        print("ERROR:", error)
    if args.export and not errors:
        taxonomy_v2.write_export(args.root)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"{len(errors)} errors")
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
