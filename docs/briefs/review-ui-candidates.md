# Brief — candidate members in the review interface

Date: 2026-10-27. Baseline: commit `9a18b67`.
Status: done on 2026-10-27 (merged from branch `review-candidates`, v0.42.0).

## 1. Start here

Read `CLAUDE.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md`.
Read `docs/briefs/review-ui.md` and the section "Local review interface" of `docs/DATA-SCHEMA.md`.
Read `scripts/review_ui.py` (the class `Store`, `apply_group`, `apply_member`, `FieldIndex`, `Evidence`), `scripts/templates/review_ui.{html,js,css}`, `scripts/test_review_ui.py` and `scripts/check_review_ui.py`.
Read how an inventory batch writes `selectori_candidati` in `data/taxonomy-v2/inventar-note.json`, and how `scripts/inventory_report.py` lists the candidates (section 5 of the report).

Copy this prompt into the implementation session:

> Implement `docs/briefs/review-ui-candidates.md`.
> Use temporary git copies of the data root for every test and demonstration. Never decide a review item in the real data.
> Stop and report if a step needs a decision that the brief does not make. Finish with the report in section 6.

## 2. Goal

An inventory batch proposes a field as a new member of a reviewed group. Today that proposal is a candidate in `inventar-note.json` (`selectori_candidati`), and the review interface does not show it. So the owner can only confirm candidates in bulk.
The owner asked on 2026-10-27 to see the candidates in the review interface and to decide each one there.

## 3. Decisions

1. **List.** The interface lists the open candidates beside the provider items and the groups. Use one queue, with a count in the navigation, and the group label on each candidate.
2. **Detail.** The detail of a candidate shows the same facts as a group member:
   - the group (label and definition), the projects, names, path, source, role and context;
   - the reach of the selector (`FieldIndex.examples`);
   - its pinned facts with their evidence (`Evidence.view`).

   It also shows the confirmed members of the group, so that the owner can compare.
3. **Actions.**
   - **„Confirm”** moves the selector into the group's `selectors` with `stare` `confirmat` and an optional `nota_editor`, and removes it from `selectori_candidati`. The group keeps its state `revizuit` and its review date, as for the bulk confirmations of 2026-10-27.
   - **„Exclude”** needs a note. The candidate stays in `selectori_candidati` with `stare` `exclus` and `nota_editor`, so that a later batch can see that the owner refused it. An excluded candidate leaves the open queue. The report lists it in a separate line.
   - **„Reset”** brings a candidate back to the values at HEAD, as for the other items. It works only while no commit holds the decision.
4. **Writes.** A decision on a candidate writes two files together: `inventar-concepte.json` and `inventar-note.json`.
   - Use the same rules as the other writes: atomic, byte-stable (`dump_json` with the old bytes), the hash check of the loaded files (the error „stale” on a change), and `refuse_new_errors`.
   - A candidate whose group is missing, or is not `revizuit`, is an error that the page shows. The confirm action refuses it.
   - Identify a candidate by its position and a hash of its selector, so that a stale page cannot decide another candidate.
5. **Report.** `inventory_report.py` lists only the open candidates in section 5, and counts the excluded ones. A batch that proposes a candidate equal to an excluded one must say so; add the check to the report.
6. **The check panel.** It counts the open candidates. `public_diff` stays as it is: a candidate does not change the public build until it is confirmed.
7. **Docs.** Update `docs/DATA-SCHEMA.md` (the keys `stare` and `nota_editor` of a candidate), `CLAUDE.md` (the one line on the review interface: „and the candidate members”) and `data/taxonomy-v2/README.md`, if it names the review interface.

## 4. Limits

- The server stays on 127.0.0.1, and its security headers stay as they are. It never commits.
- Make no network request.
- Test only on temporary git copies of the data root. Never change the real `revizuire.csv`, `relatii.csv`, `inventar-concepte.json` or `inventar-note.json`.
- The real data has no open candidate now: the owner confirmed all 46 on 2026-10-27. The browser check must make its own candidates in a temporary copy.
- No test may pin data that the owner edits.

## 5. Work

1. Implement the decisions of section 3, with unit tests in `scripts/test_review_ui.py`:
   - confirm, exclude and reset;
   - a stale hash, a missing group and a group that is not reviewed;
   - the byte stability of both files;
   - an excluded candidate that a batch proposes again.

   Run a mutation check on each new rule.
2. Extend `scripts/check_review_ui.py`: open the queue, confirm one candidate, exclude one with a note, and reset one, on a temporary copy.
3. Run `node --check scripts/templates/review_ui.js`.
4. Run the full unit suite (1053 tests and 6 skipped before), `validate.py --publication`, `inventory.py --check`, `inventory_report.py --check` and the three package checks.
5. Take two screenshots of the interface on a temporary copy, the queue and a candidate detail, and put them in a temporary folder.
6. Add the activity entry. Flip the backlog item `[~] Show the candidate members in the review interface` to `[x]`.

## 6. Report

Give these items:

- the files and keys that a decision writes;
- the test counts before and after, and the browser check results;
- the paths of the screenshots;
- the commits;
- what you measured and what you assumed.
