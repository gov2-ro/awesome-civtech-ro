#!/usr/bin/env python3
"""Apply evidence-backed structure recipes or render the identity review queue. Offline only."""
import argparse
import json
from pathlib import Path

from common import PUBLIC_ROOT, load_catalogue
from structure_curation import apply_recipe, report
from structure_state import StructureError, atomic, check, load, locked, read, require, save

REPO = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply','report'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--recipe', type=Path, action='append', default=[])
    parser.add_argument('--json', action='store_true', help='print a machine-readable review queue')
    parser.add_argument('--decisions',type=Path,help='read a separate durable owner decision file; never modify it')
    args = parser.parse_args(argv)
    try:
        root = args.out.resolve()
        require(root != REPO and root != REPO/'docs', 'Select a dedicated structure output.')
        require(not any(root.is_relative_to(p) for p in [REPO/'site',REPO/'data',REPO/'docs/reports/site-structure-pilot']), 'Select an isolated structure output.')
        if args.action == 'apply':
            require(not args.decisions,'A separate owner decision file is read in report mode only.')
            require(bool(args.recipe), 'Supply at least one --recipe.')
            catalogue = {e['slug']:e for e in load_catalogue(PUBLIC_ROOT)}
            with locked(root):
                store = load(root)
                for path in args.recipe:
                    recipe = read(path)
                    require(recipe.get('project_slug') in catalogue, 'Recipe project is absent from the catalogue.')
                    require(recipe.get('input_url') == catalogue[recipe['project_slug']]['url'], 'Recipe URL differs from the catalogue URL.')
                    updated = apply_recipe(store,root,recipe,path.resolve())
                    check(updated,root)
                    save(updated,root)
                    store = updated
        else:
            require(not args.recipe, 'Report mode does not apply recipes.')
            require((root/'store.json').exists(), 'Structure store does not exist.')
            store = load(root)
        decision_path=args.decisions or root/'decisions.json'
        decisions = read(decision_path) if decision_path.exists() else []
        require(isinstance(decisions,list),'Owner decisions must be a list.')
        require(len({d['assertion_id'] for d in decisions})==len(decisions),'Duplicate owner decision IDs.')
        require(all(d.get('state') in {'accepted','rejected','deferred'} for d in decisions),'Unknown owner decision state.')
        known={a['id'] for a in store['assertions']}
        queue = report(store,[d for d in decisions if d['assertion_id'] in known])
        queue['unapplied_decisions']=[d['assertion_id'] for d in decisions if d['assertion_id'] not in known]
        if args.json:
            print(json.dumps(queue,ensure_ascii=False,indent=2))
        else:
            print(f"Curation: {queue['projects']} projects, {queue['records']} records, {len(queue['links'])} identity proposals.")
            print(f"Review queue: {len(queue['conflicts'])} conflicts, {len(queue['gaps'])} sample gaps.")
            for link in queue['links']:
                projects=' / '.join(subject['project'] for subject in link['subjects'])
                print(f"{link['id']}: {link['state']}; {projects}" + ('; identity conflict' if link['conflict'] else ''))
            for slug in queue['declared_without_samples']:
                print(f'{slug}: identifier declarations without record samples')
        return 0
    except (StructureError,ValueError,OSError,KeyError,TypeError) as exc:
        print(f'Curation: {exc}',file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
