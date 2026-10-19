"""Offline tests for scripts/sheets.py and scripts/form.py. Stdlib only; no Google, no network, no credentials.

    python3 scripts/test_sheets_form.py          # or: python3 -m unittest scripts/test_sheets_form.py -v

The Sheet is an in-memory double with the few gspread calls that sheets.py makes. The sync base (the marker commit) is
tested in a temporary git repository. Every mutation runs on a temporary copy; the repository's data is only read.
"""
import contextlib
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import argparse  # noqa: E402
import common  # noqa: E402
import form  # noqa: E402
import sheets  # noqa: E402
import taxonomy_v2  # noqa: E402

ROOT = HERE.parent
DATA = ROOT / "data"
PACKAGE = DATA / "taxonomy-v2"
OVERLAY = PACKAGE / "integrare"
STAMP = "2026-10-19T10:00:00Z"


# ---- A Sheet in memory -----------------------------------------------------------------------------------------

class WorksheetNotFound(Exception):
    """Same name as gspread.exceptions.WorksheetNotFound, which sheets.find_ws matches by name."""


class FakeWorksheet:
    """The calls of gspread.Worksheet that sheets.py makes. Like the API, it refuses a write outside the grid, and it
    keeps cells that a write does not cover (so a missing clear shows up as stale data)."""

    def __init__(self, spreadsheet, title, rows, cols, sid):
        self.spreadsheet, self.title, self.id = spreadsheet, title, sid
        self.row_count, self.col_count = rows, cols
        self.cells: dict[tuple[int, int], str] = {}

    def get_all_values(self):
        filled = [rc for rc, v in self.cells.items() if v != ""]
        if not filled:
            return [[]]
        rows, cols = max(r for r, _ in filled), max(c for _, c in filled)
        grid = [[self.cells.get((r, c), "") for c in range(1, cols + 1)] for r in range(1, rows + 1)]
        if self.spreadsheet.ragged:  # the API leaves out trailing empty cells
            grid = [row[:max((i + 1 for i, v in enumerate(row) if v != ""), default=0)] for row in grid]
        return grid

    def update(self, values, range_name, raw=True):
        assert range_name == "A1" and raw is True, (range_name, raw)
        self.spreadsheet.log.append(("update", self.title))
        if len(values) > self.row_count or max(len(r) for r in values) > self.col_count:
            raise ValueError(f"{self.title}: range exceeds the grid ({self.row_count} x {self.col_count})")
        for i, row in enumerate(values, 1):
            for j, v in enumerate(row, 1):
                assert isinstance(v, str), f"non-text value {v!r}"
                self.cells[(i, j)] = v

    def resize(self, rows=None, cols=None):
        self.spreadsheet.log.append(("resize", self.title))
        self.row_count, self.col_count = rows or self.row_count, cols or self.col_count

    def batch_clear(self, ranges):
        self.spreadsheet.log.append(("clear", self.title))
        for rng in ranges:
            m = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", rng)
            assert m, rng
            col = lambda s: sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(s)))
            c0, r0, c1, r1 = col(m[1]), int(m[2]), col(m[3]), int(m[4])
            for rc in [rc for rc in self.cells if r0 <= rc[0] <= r1 and c0 <= rc[1] <= c1]:
                del self.cells[rc]


class FakeSheet:
    """gspread.Spreadsheet: worksheet(), add_worksheet(), batch_update()."""

    def __init__(self, ragged=False):
        self.ragged, self.sheets, self.requests, self.log, self.touched = ragged, {}, [], [], []

    def worksheet(self, title):
        self.touched.append(title)
        if title not in self.sheets:
            raise WorksheetNotFound(title)
        return self.sheets[title]

    def add_worksheet(self, title, rows, cols):
        assert title not in self.sheets
        self.log.append(("add", title))
        self.sheets[title] = FakeWorksheet(self, title, rows, cols, len(self.sheets) + 1)
        return self.sheets[title]

    def batch_update(self, body):
        self.requests.append(body)

    # helpers for the tests
    def seed(self, title, cols, rows, size=(1000, 26)):
        ws = self.sheets.get(title) or FakeWorksheet(self, title, *size, len(self.sheets) + 1)
        self.sheets[title] = ws
        ws.cells.clear()
        for j, c in enumerate(cols, 1):
            ws.cells[(1, j)] = c
        for i, row in enumerate(rows, 2):
            for j, c in enumerate(cols, 1):
                ws.cells[(i, j)] = row[c]
        return ws

    def table(self, title):
        grid = self.sheets[title].get_all_values()
        return [dict(zip(grid[0], r + [""] * (len(grid[0]) - len(r)))) for r in grid[1:]]

    def edit(self, title, key, col, value, key_col=None):
        """Set one cell, found by the value in the key column (the first column unless given)."""
        ws = self.sheets[title]
        header = {v: c for (r, c), v in ws.cells.items() if r == 1}
        kc = header[key_col] if key_col else 1
        row = next(r for (r, c), v in ws.cells.items() if c == kc and v == key and r > 1)
        ws.cells[(row, header[col])] = value

    def row_of(self, title, key):
        ws = self.sheets[title]
        return next(r for (r, c), v in ws.cells.items() if c == 1 and v == key and r > 1)


def run(fn, *args, **kw):
    """(exit code, stdout, stderr) of a command function. A SheetError propagates."""
    out, err, code = io.StringIO(), io.StringIO(), 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            fn(*args, **kw)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int):
                print(e.code, file=err)
    return code, out.getvalue(), err.getvalue()


# ---- A temporary repository with a copy of the data ------------------------------------------------------------

GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": os.environ["PATH"]}


class Env:
    """A temporary git repository (`repo/`) holding a copy of the v1 files (`repo/data/`) or of the v2 package
    (`repo/data/taxonomy-v2/`, without the classification run). `root` is the data root a command gets."""

    def __init__(self, v2: bool = False, ragged: bool = False, seed: bool = True):
        if not shutil.which("git"):
            raise unittest.SkipTest("git is not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        (self.repo / "data").mkdir(parents=True)
        if v2:
            shutil.copytree(PACKAGE, self.repo / "data" / "taxonomy-v2",
                            ignore=shutil.ignore_patterns("runs", "__pycache__", "catalogue.json"))
            self.root = self.repo / "data" / "taxonomy-v2" / "integrare"
        else:
            for name in ("proiecte.csv", "orgs.csv", "taxonomy.json"):
                shutil.copy(DATA / name, self.repo / "data" / name)
            self.root = self.repo / "data"
        self.sh = FakeSheet(ragged)
        self.git("init", "-q", "-b", "main")
        self.tabs = sheets.tabs_for(self.root)
        if seed and not v2:  # the live Sheet has the v1 tabs, with their header and no rows yet
            for t in self.tabs:
                self.sh.seed(t.name, t.cols, [])
        self.clock_value = STAMP

    def git(self, *args) -> str:
        r = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=self.repo, capture_output=True, text=True, env=GIT_ENV)
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()

    def commit(self, message="c") -> str:
        for t in self.tabs:
            self.git("add", "-f", str(t.path))
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def ctx(self, tabs=None) -> "sheets.Context":
        return sheets.Context(self.sh, self.root, tabs or self.tabs, git=sheets.Git(self.repo), clock=lambda: self.clock_value)

    def tab(self, name) -> "sheets.Tab":
        return next(t for t in self.tabs if t.name == name)

    def rows(self, name):
        return list(csv.DictReader(io.StringIO(self.tab(name).path.read_text(encoding="utf-8"), newline="")))

    def write_rows(self, name, rows):
        common.write_csv(self.tab(name).path, self.tab(name).cols, rows)

    def edit_csv(self, name, key, col, value):
        rows = self.rows(name)
        next(r for r in rows if r[self.tab(name).key] == key)[col] = value
        self.write_rows(name, rows)

    def bytes(self, name) -> bytes:
        return self.tab(name).path.read_bytes()

    def close(self):
        self.tmp.cleanup()


class EnvCase(unittest.TestCase):
    v2 = False

    def setUp(self):
        self.env = Env(v2=self.v2)
        self.addCleanup(self.env.close)
        self.sh = self.env.sh

    def push(self, **kw):
        return run(sheets.cmd_push, self.env.ctx(), **kw)

    def pull(self, **kw):
        return run(sheets.cmd_pull, self.env.ctx(), **kw)

    def diff(self, **kw):
        return run(sheets.cmd_diff, self.env.ctx(), **kw)


# ---- Pure helpers ----------------------------------------------------------------------------------------------

class Helpers(unittest.TestCase):
    def test_modules_import_without_the_google_libraries(self):
        code = ("import sys; sys.path.insert(0, %r); import sheets, form; "
                "bad = [m for m in ('gspread', 'google', 'requests') if m in sys.modules]; assert not bad, bad" % str(HERE))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_cell_notation(self):
        self.assertEqual([sheets.a1(1, 1), sheets.a1(3, 26), sheets.a1(3, 27), sheets.a1(2, 31), sheets.a1(1, 53)],
                         ["A1", "Z3", "AA3", "AE2", "BA1"])

    def test_norm_strips_trailing_spaces_and_carriage_returns_only(self):
        self.assertEqual(sheets.norm("a b  "), "a b")
        self.assertEqual(sheets.norm("  a"), "  a")
        self.assertEqual(sheets.norm("a\r\nb\r\n"), "a\nb\n")
        self.assertEqual(sheets.norm("a \nb"), "a \nb")  # inside a cell only the end is trimmed

    def test_header_error_names_the_difference(self):
        cols = ["a", "b", "c"]
        self.assertEqual(sheets.header_error(["a", "b", "c", "", ""], cols), "")
        self.assertIn("missing 'c'", sheets.header_error(["a", "b"], cols))
        self.assertIn("unknown 'x'", sheets.header_error(["a", "b", "c", "x"], cols))
        self.assertIn("another order", sheets.header_error(["b", "a", "c"], cols))

    def test_sheets_error_names_come_from_the_library_module(self):
        self.assertIsNone(sheets.google_error(ValueError("x")))


# ---- Three-way merge -------------------------------------------------------------------------------------------

TAB = sheets.Tab("t", Path("t.csv"), ["slug", "nume", "descriere"])


def r(slug, nume="n", descriere="d"):
    return {"slug": slug, "nume": nume, "descriere": descriere}


class MergeCases(unittest.TestCase):
    def merge(self, base, head, sheet):
        return sheets.merge3(TAB, base, head, sheet)

    def test_a_cell_only_the_sheet_changed_comes_from_the_sheet(self):
        m = self.merge([r("a")], [r("a")], [r("a", descriere="new")])
        self.assertEqual(m.rows, [r("a", descriere="new")])
        self.assertFalse(m.conflicts)

    def test_a_cell_only_the_repo_changed_stays(self):
        m = self.merge([r("a")], [r("a", descriere="repo")], [r("a")])
        self.assertEqual(m.rows, [r("a", descriere="repo")])
        self.assertFalse(m.conflicts)

    def test_two_cells_of_one_row_changed_on_different_sides_both_stay(self):
        m = self.merge([r("a")], [r("a", nume="repo")], [r("a", descriere="sheet")])
        self.assertEqual(m.rows, [r("a", "repo", "sheet")])

    def test_the_same_change_on_both_sides_is_no_conflict(self):
        m = self.merge([r("a")], [r("a", descriere="x")], [r("a", descriere="x")])
        self.assertEqual((m.rows, m.conflicts), ([r("a", descriere="x")], []))

    def test_a_cell_both_sides_changed_differently_is_a_conflict(self):
        m = self.merge([r("a")], [r("a", descriere="repo")], [r("a", descriere="sheet")])
        self.assertEqual(m.conflicts, [("cell", "a", "descriere", "d", "repo", "sheet")])
        self.assertEqual(m.rows[0]["descriere"], "repo")  # the merged row keeps the repo's value; the command writes nothing

    def test_rows_added_on_each_side_both_stay_the_sheets_row_after_its_predecessor(self):
        m = self.merge([r("a")], [r("a"), r("repo-new")], [r("a"), r("sheet-new")])
        self.assertEqual([x["slug"] for x in m.rows], ["a", "sheet-new", "repo-new"])

    def test_the_same_row_added_on_both_sides_differently_conflicts_only_where_both_have_text(self):
        m = self.merge([], [r("n", "repo", "")], [r("n", "sheet", "text")])
        self.assertEqual([(c[1], c[2]) for c in m.conflicts], [("n", "nume")])
        self.assertEqual(m.rows[0]["descriere"], "text")  # only the Sheet wrote it

    def test_a_row_the_sheet_deleted_goes_when_the_repo_left_it_alone(self):
        self.assertEqual(self.merge([r("a"), r("b")], [r("a"), r("b")], [r("a")]).rows, [r("a")])

    def test_a_row_the_repo_deleted_stays_deleted_when_the_sheet_left_it_alone(self):
        self.assertEqual(self.merge([r("a"), r("b")], [r("a")], [r("a"), r("b")]).rows, [r("a")])

    def test_a_deleted_row_that_the_other_side_changed_is_a_conflict(self):
        m = self.merge([r("a"), r("b")], [r("a"), r("b", "repo")], [r("a")])
        self.assertEqual([(c[0], c[1]) for c in m.conflicts], [("row", "b")])
        m = self.merge([r("a"), r("b")], [r("a")], [r("a"), r("b", "sheet")])
        self.assertEqual([(c[0], c[1]) for c in m.conflicts], [("row", "b")])

    def test_without_a_base_the_sheet_wins_every_difference(self):
        m = self.merge(None, [r("a", "repo"), r("only-repo")], [r("a", "sheet")])
        self.assertEqual(m.rows, [r("a", "sheet")])

    def test_a_row_moved_in_the_sheet_moves_in_the_result_when_the_repo_did_not_move_rows(self):
        m = self.merge([r("a"), r("b"), r("c")], [r("a"), r("b"), r("c")], [r("c"), r("a"), r("b")])
        self.assertEqual([x["slug"] for x in m.rows], ["c", "a", "b"])

    def test_when_both_sides_moved_rows_the_repo_order_wins_with_a_note(self):
        m = self.merge([r("a"), r("b"), r("c")], [r("b"), r("a"), r("c")], [r("c"), r("a"), r("b")])
        self.assertEqual([x["slug"] for x in m.rows], ["b", "a", "c"])
        self.assertTrue(m.notes)

    def test_a_new_row_goes_after_its_predecessor(self):
        m = self.merge([r("a"), r("b"), r("c")], [r("a"), r("b"), r("c")], [r("a"), r("new"), r("b"), r("c")])
        self.assertEqual([x["slug"] for x in m.rows], ["a", "new", "b", "c"])

    def test_cells_are_compared_after_the_trailing_spaces_are_trimmed(self):
        m = self.merge([r("a")], [r("a", descriere="d ")], [r("a")])
        self.assertEqual((m.rows, m.conflicts), ([r("a")], []))

    def test_rows_are_matched_by_the_key_column_of_the_tab(self):
        tab = sheets.Tab("v2-revizuire", Path("x.csv"), ["id", "slug", "propunere"], key="id", label="slug")
        m = sheets.merge3(tab, [{"id": "R1", "slug": "a", "propunere": "p"}], [{"id": "R1", "slug": "a", "propunere": "repo"}],
                          [{"id": "R1", "slug": "a", "propunere": "p"}])
        self.assertEqual(m.rows[0]["propunere"], "repo")


# ---- Round trips through the Sheet double ----------------------------------------------------------------------

class RoundTripV1(EnvCase):
    """The live tabs: header, push, pull. Same commands and headers as before the sync base."""

    def test_push_then_pull_gives_the_same_bytes(self):
        before = {n: self.env.bytes(n) for n in ("proiecte", "orgs")}
        self.env.commit()
        self.assertEqual(self.push()[0], 0)
        self.assertEqual(self.sh.table("proiecte")[0].keys(), dict.fromkeys(common.PROIECTE_COLS).keys())
        self.assertEqual(self.sh.sheets["orgs"].get_all_values()[0], common.ORGS_COLS)
        code, out, _ = self.pull()
        self.assertEqual(code, 0, out)
        self.assertEqual({n: self.env.bytes(n) for n in ("proiecte", "orgs")}, before)

    def test_ragged_rows_from_the_api_read_the_same(self):
        self.env.close()
        self.env = Env(ragged=True)
        self.addCleanup(self.env.close)
        self.sh = self.env.sh
        before = self.env.bytes("proiecte")
        self.env.commit()
        self.push()
        self.assertEqual(self.pull()[0], 0)
        self.assertEqual(self.env.bytes("proiecte"), before)

    def test_special_cells_survive_the_round_trip(self):
        rows = self.env.rows("proiecte")
        special = ['quote "inside" and, comma', "line one\nline two\n\nline four", "ăâîșț ĂÂÎȘȚ – „ghilimele” ✓",
                   "pipe | and:colon", "465", "0123", "=1+1", "'apostrophe", " leading", "", "https://x.ro/a?b=1&c=2"]
        for i, text in enumerate(special):
            rows[i]["descriere"] = text
            rows[i]["nota"] = special[-1 - i]
        self.env.write_rows("proiecte", rows)
        before = self.env.bytes("proiecte")
        self.env.commit()
        self.push()
        pulled = self.sh.table("proiecte")
        self.assertEqual([p["descriere"] for p in pulled[:len(special)]], special)  # the Sheet holds the text as it is
        self.assertEqual(self.pull()[0], 0)
        self.assertEqual(self.env.bytes("proiecte"), before)

    def test_trailing_spaces_and_carriage_returns_in_the_sheet_are_stripped_on_pull(self):
        self.env.commit()
        self.push()
        first = self.env.rows("proiecte")[0]["slug"]
        self.sh.edit("proiecte", first, "nume", "Nume nou  ")
        self.sh.edit("proiecte", self.env.rows("proiecte")[1]["slug"], "descriere", "a\r\nb\r\n")
        self.assertEqual(self.pull()[0], 0)
        rows = self.env.rows("proiecte")
        self.assertEqual((rows[0]["nume"], rows[1]["descriere"]), ("Nume nou", "a\nb\n"))

    def test_the_diff_says_when_only_the_file_format_differs(self):
        self.env.commit()
        self.push()
        rows = self.env.rows("proiecte")
        rows[0]["nota"] = "x  "  # a trailing space in the file, none in the Sheet
        self.env.write_rows("proiecte", rows)
        self.sh.edit("proiecte", rows[0]["slug"], "nota", "x")
        _, out, _ = self.diff()
        self.assertIn("only the file format differs", out)

    def test_empty_trailing_rows_and_blank_rows_are_dropped(self):
        self.env.commit()
        self.push()
        ws = self.sh.sheets["proiecte"]
        last = max(r for (r, _), v in ws.cells.items() if v)
        ws.cells[(last + 2, 1)] = ""  # a blank row in the middle of nothing
        self.assertEqual(self.pull()[0], 0)

    def test_a_swapped_column_order_stops_pull_and_diff_with_a_message(self):
        self.env.commit()
        self.push()
        ws = self.sh.sheets["proiecte"]
        ws.cells[(1, 2)], ws.cells[(1, 3)] = ws.cells[(1, 3)], ws.cells[(1, 2)]
        for fn in (self.pull, self.diff):
            with self.assertRaises(sheets.SheetError) as cm:
                fn()
            self.assertIn("another order", str(cm.exception))

    def test_a_missing_or_unknown_column_stops_pull(self):
        self.env.commit()
        self.push()
        ws = self.sh.sheets["proiecte"]
        ws.cells[(1, 4)] = "scurt"
        with self.assertRaises(sheets.SheetError) as cm:
            self.pull()
        self.assertIn("missing 'descriere_scurta'", str(cm.exception))
        self.assertIn("unknown 'scurt'", str(cm.exception))

    def test_data_to_the_right_of_the_last_column_stops_pull(self):
        self.env.commit()
        self.push()
        self.sh.sheets["orgs"].cells[(3, len(common.ORGS_COLS) + 1)] = "oops"
        with self.assertRaises(sheets.SheetError) as cm:
            self.pull()
        self.assertIn("right of column", str(cm.exception))

    def test_an_empty_tab_stops_pull_instead_of_emptying_the_csv(self):
        self.env.commit()
        self.push()
        self.sh.sheets["orgs"].cells.clear()
        with self.assertRaises(sheets.SheetError) as cm:
            self.pull()
        self.assertIn("no data rows", str(cm.exception))

    def test_every_cell_is_plain_text_row_1_is_frozen_and_the_list_columns_only_suggest(self):
        self.env.commit()
        self.push()
        reqs = [q for body in self.sh.requests for q in body["requests"]]
        width = len(common.PROIECTE_COLS)
        text = [q for q in reqs if "repeatCell" in q and q["repeatCell"]["range"].get("endColumnIndex") == width
                and q["repeatCell"]["fields"] == "userEnteredFormat.numberFormat"]
        self.assertTrue(text)
        self.assertTrue(all(t["repeatCell"]["cell"]["userEnteredFormat"]["numberFormat"]["type"] == "TEXT" for t in text))
        self.assertTrue(any("updateSheetProperties" in q for q in reqs))
        sid = self.sh.sheets["proiecte"].id
        strict = {q["setDataValidation"]["range"]["startColumnIndex"]: q["setDataValidation"]["rule"]["strict"]
                  for q in reqs if "setDataValidation" in q and q["setDataValidation"]["range"]["sheetId"] == sid}
        cols = common.PROIECTE_COLS
        self.assertFalse(strict[cols.index("tip")])  # a comma-separated list: suggest only
        self.assertTrue(strict[cols.index("fel")])

    def test_a_shorter_table_and_a_dropped_column_leave_no_stale_cells(self):
        self.env.commit()
        self.push()
        rows = self.env.rows("orgs")
        self.env.write_rows("orgs", rows[:3])
        self.env.commit("shorter")
        self.assertEqual(self.push()[0], 0)
        self.assertEqual(len(self.sh.table("orgs")), 3)
        ws = self.sh.sheets["orgs"]
        ws.cells[(1, 14)] = "old column"  # a column to the right of the table, as after a column was dropped
        ws.cells[(2, 14)] = "old data"
        self.env.commit("again")
        self.assertEqual(self.push(force=True)[0], 0)
        self.assertEqual(len(ws.get_all_values()[0]), len(common.ORGS_COLS))
        self.assertEqual(self.pull()[0], 0)

    def test_a_write_outside_the_grid_does_not_happen(self):
        self.env.commit()
        self.sh.seed("proiecte", common.PROIECTE_COLS, [], size=(2, 3))  # smaller than the table
        self.sh.seed("orgs", common.ORGS_COLS, [], size=(2, 3))
        self.assertEqual(self.push()[0], 0)  # the double raises when update runs before resize
        self.assertEqual(len(self.sh.table("proiecte")), len(self.env.rows("proiecte")))


class RoundTripV2(EnvCase):
    v2 = True

    def test_the_integration_copy_round_trips_byte_for_byte(self):
        before = self.env.bytes("v2-intrari")
        self.env.commit()
        code, out, err = self.push()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sh.sheets["v2-intrari"].get_all_values()[0],
                         json.loads((PACKAGE / "schema.json").read_text())["headers"]["intrari.csv"])
        self.assertEqual(len(self.sh.table("v2-intrari")), 122)
        code, out, _ = self.pull()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.env.bytes("v2-intrari"), before)

    def test_the_review_queue_is_a_second_optional_tab(self):
        tabs = sheets.tabs_for(self.env.root, ["v2-intrari", "v2-revizuire"])
        self.env.tabs = tabs
        before = self.env.bytes("v2-revizuire")
        self.env.commit()
        self.assertEqual(self.push()[0], 0)
        self.assertEqual(self.sh.table("v2-revizuire")[0]["id"], "R001")
        self.assertEqual(self.pull()[0], 0)
        self.assertEqual(self.env.bytes("v2-revizuire"), before)

    def test_ids_pipes_and_special_text_stay_text(self):
        rows = self.env.rows("v2-intrari")
        rows[0]["teme"] = "subiect:alegeri|subiect:vot"
        rows[0]["descriere"] = 'ghilimele "duble", virgule\nși rânduri noi; ăâîșț'
        rows[1]["arii_acoperite"] = "tara:RO|localitate:iasi"
        rows[2]["slug"] = "465-nou"
        rows[2]["sursa_rand"] = "007"
        self.env.write_rows("v2-intrari", rows)
        before = self.env.bytes("v2-intrari")
        self.env.commit()
        self.push()
        t = self.sh.table("v2-intrari")
        self.assertEqual((t[0]["teme"], t[1]["arii_acoperite"], t[2]["sursa_rand"]), ("subiect:alegeri|subiect:vot", "tara:RO|localitate:iasi", "007"))
        self.assertEqual(self.pull()[0], 0)
        self.assertEqual(self.env.bytes("v2-intrari"), before)

    def test_empty_cells_stay_empty(self):
        self.env.commit()
        self.push()
        self.assertEqual(self.pull()[0], 0)
        rows = self.env.rows("v2-intrari")
        self.assertTrue(any(r["tehnologii"] == "" for r in rows))

    def test_drop_downs_only_suggest_in_cells_that_take_a_list(self):
        self.env.commit()
        self.push()
        cols = self.env.tab("v2-intrari").cols
        rules = {cols[q["setDataValidation"]["range"]["startColumnIndex"]]: q["setDataValidation"]["rule"]
                 for body in self.sh.requests for q in body["requests"] if "setDataValidation" in q}
        for single in ("tip_entitate", "sectiune_url", "subiect_principal", "maturitate", "nivel_acoperire", "clasificare_stare", "incredere"):
            self.assertTrue(rules[single]["strict"], single)
        for multi in ("subiecte", "scopuri", "functionalitati", "formate", "institutii_vizate"):
            self.assertFalse(rules[multi]["strict"], multi)
            values = [v["userEnteredValue"] for v in rules[multi]["condition"]["values"]]
            self.assertTrue(all(":" in v for v in values), multi)  # IDs, never bare labels
        self.assertNotIn("teme", rules)  # too long to suggest
        self.assertEqual([v["userEnteredValue"] for v in rules["subiect_principal"]["condition"]["values"]].count("subiect:alegeri"), 0)  # roots only
        self.assertNotIn("sursa_rand", rules)

    def test_a_swapped_column_order_is_an_error(self):
        self.env.commit()
        self.push()
        ws = self.sh.sheets["v2-intrari"]
        ws.cells[(1, 4)], ws.cells[(1, 5)] = ws.cells[(1, 5)], ws.cells[(1, 4)]
        with self.assertRaises(sheets.SheetError):
            self.pull()
        with self.assertRaises(sheets.SheetError):
            self.diff()


# ---- The sync marker --------------------------------------------------------------------------------------------

class SyncMarker(EnvCase):
    def first_push(self):
        self.commit1 = self.env.commit("c1")
        code, out, err = self.push()
        self.assertEqual(code, 0, err)
        return out

    def slug(self, i=0):
        return self.env.rows("proiecte")[i]["slug"]

    def test_push_writes_the_marker_last_with_commit_hash_and_time(self):
        out = self.first_push()
        rows = {m["tab"]: m for m in self.sh.table("_sync")}
        self.assertEqual(set(rows), {"proiecte", "orgs"})
        self.assertEqual(rows["proiecte"]["commit"], self.commit1)
        self.assertEqual(rows["proiecte"]["sha256"], hashlib.sha256(self.env.bytes("proiecte")).hexdigest())
        self.assertEqual(rows["orgs"]["sha256"], hashlib.sha256(self.env.bytes("orgs")).hexdigest())
        self.assertEqual(rows["proiecte"]["time"], STAMP)
        self.assertEqual(self.sh.sheets["_sync"].get_all_values()[0], ["tab", "commit", "sha256", "time"])
        self.assertIn("sync marker", out)
        last_tab_write = max(i for i, e in enumerate(self.sh.log) if e == ("update", "orgs"))
        marker_write = max(i for i, e in enumerate(self.sh.log) if e == ("update", "_sync"))
        self.assertGreater(marker_write, last_tab_write)

    def test_a_second_push_replaces_the_rows_it_does_not_add_new_ones(self):
        self.first_push()
        self.env.edit_csv("proiecte", self.slug(), "nota", "changed")
        c2 = self.env.commit("c2")
        self.env.clock_value = "2026-10-20T08:00:00Z"
        self.assertEqual(self.push()[0], 0)
        rows = self.sh.table("_sync")
        self.assertEqual(len(rows), 2)
        self.assertEqual({m["commit"] for m in rows}, {c2})
        self.assertEqual({m["time"] for m in rows}, {"2026-10-20T08:00:00Z"})

    def test_a_push_from_an_uncommitted_csv_leaves_the_marker_alone_and_says_so(self):
        self.first_push()
        self.env.edit_csv("proiecte", self.slug(), "nota", "not committed")
        code, out, err = self.push(force=True)
        self.assertEqual(code, 0)
        self.assertIn("marker is not updated", err)
        self.assertEqual({m["commit"] for m in self.sh.table("_sync") if m["tab"] == "proiecte"}, {self.commit1})
        self.assertEqual(self.sh.table("proiecte")[0]["nota"], "not committed")

    def test_pull_keeps_a_repo_edit_that_the_sheet_does_not_have_yet(self):
        """The 'revert' defect: a CSV edit on main, not pushed yet, used to be overwritten by the next pull."""
        self.first_push()
        self.env.edit_csv("proiecte", self.slug(), "nota", "edit on main")
        self.env.commit("c2")  # a push to main whose sheets-push run was skipped
        code, out, _ = self.pull()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.env.rows("proiecte")[0]["nota"], "edit on main")

    def test_pull_takes_a_sheet_edit_and_keeps_an_edit_on_main_in_another_cell(self):
        self.first_push()
        self.env.edit_csv("proiecte", self.slug(0), "nota", "repo")
        self.env.commit("c2")
        self.sh.edit("proiecte", self.slug(0), "nume", "Nume din tabel")
        self.sh.edit("proiecte", self.slug(1), "nota", "alta nota din tabel")
        code, out, _ = self.pull()
        self.assertEqual(code, 0, out)
        rows = self.env.rows("proiecte")
        self.assertEqual((rows[0]["nota"], rows[0]["nume"], rows[1]["nota"]), ("repo", "Nume din tabel", "alta nota din tabel"))
        self.assertIn("the Sheet changed 2 row(s), the repo 1", out)
        self.assertIn("proiecte (Sheet changes since the base): +0 -0 ~2", out)  # the cells of each side are listed
        self.assertIn("proiecte (repo changes since the base): +0 -0 ~1", out)
        self.assertIn("nume: ", out)

    def test_a_cell_both_sides_changed_gives_exit_3_the_list_and_writes_nothing(self):
        self.first_push()
        slug = self.slug()
        self.env.edit_csv("proiecte", slug, "nota", "repo value")
        self.env.commit("c2")
        self.sh.edit("proiecte", slug, "nota", "sheet value")
        self.sh.edit("proiecte", self.slug(1), "nume", "an edit without conflict")
        before = {n: self.env.bytes(n) for n in ("proiecte", "orgs")}
        code, out, err = self.pull()
        self.assertEqual(code, 3)
        self.assertIn(f"! {slug} / nota", out)
        self.assertIn("repo value", out)
        self.assertIn("sheet value", out)
        self.assertIn("Nothing was written", err)
        self.assertEqual({n: self.env.bytes(n) for n in ("proiecte", "orgs")}, before)  # not even the cell without conflict

    def test_diff_lists_the_conflicts_and_the_repo_changes_the_sheet_lacks(self):
        self.first_push()
        slug = self.slug()
        self.env.edit_csv("proiecte", slug, "nota", "repo value")
        self.env.edit_csv("proiecte", self.slug(2), "nota", "repo only")
        self.env.commit("c2")
        self.sh.edit("proiecte", slug, "nota", "sheet value")
        code, out, _ = self.diff()
        self.assertEqual(code, 0)
        self.assertIn("proiecte (in the repo, not in the Sheet yet)", out)
        self.assertIn(self.slug(2), out)
        self.assertIn("1 conflict(s)", out)
        self.assertIn(f"base marker {self.commit1[:7]}", out)

    def test_since_replaces_the_marker_and_lets_the_sheet_win(self):
        self.first_push()
        slug = self.slug()
        self.env.edit_csv("proiecte", slug, "nota", "repo value")
        c2 = self.env.commit("c2")
        self.sh.edit("proiecte", slug, "nota", "sheet value")
        self.assertEqual(self.pull()[0], 3)
        code, out, _ = self.pull(since=c2)  # the repo "has not changed since" c2: every Sheet difference is a Sheet edit
        self.assertEqual(code, 0, out)
        self.assertEqual(self.env.rows("proiecte")[0]["nota"], "sheet value")

    def test_without_a_marker_pull_copies_the_sheet_over_the_csv_and_warns(self):
        self.env.commit()
        self.push(force=True)
        self.sh.sheets.pop("_sync")
        self.sh.edit("proiecte", self.slug(), "nume", "Nume din tabel")
        code, out, err = self.pull()
        self.assertEqual(code, 0)
        self.assertIn("no sync marker", err)
        self.assertEqual(self.env.rows("proiecte")[0]["nume"], "Nume din tabel")

    def test_a_marker_that_does_not_match_the_commit_is_an_error_everywhere_but_force_repairs_it(self):
        self.first_push()
        self.sh.edit("_sync", "proiecte", "sha256", "0" * 64)
        for fn in (self.pull, self.diff, self.push):
            with self.assertRaises(sheets.SheetError) as cm:
                fn()
            self.assertIn("sync marker names commit", str(cm.exception))
        self.assertEqual(self.push(force=True)[0], 0)
        self.assertEqual(self.pull()[0], 0)

    def test_a_marker_commit_that_is_not_in_the_clone_is_an_error(self):
        self.first_push()
        self.sh.edit("_sync", "orgs", "commit", "1" * 40)
        with self.assertRaises(sheets.SheetError):
            self.pull()

    def test_a_deleted_marker_row_makes_that_tab_two_way_again(self):
        self.first_push()
        ws = self.sh.sheets["_sync"]
        row = self.sh.row_of("_sync", "orgs")
        for c in range(1, 5):
            ws.cells[(row, c)] = ""
        self.assertEqual(sheets.read_markers(self.sh).keys(), {"proiecte"})
        code, out, err = self.pull()
        self.assertEqual(code, 0)
        self.assertIn("orgs: no sync marker", err)

    def test_push_stops_when_the_sheet_holds_an_edit_the_repo_does_not_have(self):
        self.first_push()
        self.sh.edit("proiecte", self.slug(), "nume", "edit in the sheet")
        before = self.sh.table("proiecte")
        code, out, err = self.push()
        self.assertEqual(code, 3)
        self.assertIn(self.slug(), out)
        self.assertIn("edit in the sheet", out)
        self.assertEqual(self.sh.table("proiecte"), before)  # nothing written
        self.assertEqual(self.push(force=True)[0], 0)

    def test_push_writes_when_a_pull_request_carried_the_sheet_edit(self):
        self.first_push()
        self.sh.edit("proiecte", self.slug(), "nume", "edit in the sheet")
        self.assertEqual(self.pull()[0], 0)  # the pull request's content ...
        self.env.commit("merge of the pull request")  # ... is merged to main
        code, out, err = self.push()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.sh.table("proiecte")[0]["nume"], "edit in the sheet")

    def test_push_after_skipped_runs_does_not_give_a_false_exit_3(self):
        """sheets-push runs superseded in the queue: the `before` of the next run is not the state the Sheet came from."""
        self.first_push()
        self.env.edit_csv("proiecte", self.slug(0), "nota", "second")
        c2 = self.env.commit("c2")  # its run was superseded; the Sheet still holds c1
        self.env.edit_csv("proiecte", self.slug(1), "nota", "third")
        self.env.commit("c3")
        code, out, _ = self.push(since=c2)  # the old way: `--since <before>`
        self.assertEqual(code, 3, "the old check gives the false exit 3")
        code, out, err = self.push()  # the marker still names c1, the state of the Sheet
        self.assertEqual(code, 0, out + err)
        self.assertEqual([r["nota"] for r in self.sh.table("proiecte")[:2]], ["second", "third"])

    def test_a_new_column_in_the_repo_pushes_without_force(self):
        """Columns changed between the base and now: the base and the Sheet have the old header."""
        self.first_push()
        tab = self.env.tab("orgs")
        old_cols = list(tab.cols)
        new_cols = old_cols + ["extra"]
        tab.cols[:] = new_cols
        rows = [{**r, "extra": f"x-{i}"} for i, r in enumerate(self.env.rows("orgs"))]
        self.env.write_rows("orgs", rows)
        self.env.commit("new column")
        try:
            code, out, err = self.push()
            self.assertEqual(code, 0, out + err)
            self.assertEqual(self.sh.sheets["orgs"].get_all_values()[0], new_cols)
            self.assertEqual(self.sh.table("orgs")[0]["extra"], "x-0")
            self.assertEqual(self.pull()[0], 0)
        finally:
            tab.cols[:] = old_cols

    def test_a_dropped_column_pushes_and_leaves_no_old_column_behind(self):
        self.first_push()
        tab = self.env.tab("orgs")
        old_cols = list(tab.cols)
        tab.cols[:] = old_cols[:-1]
        rows = self.env.rows("orgs")
        self.env.write_rows("orgs", rows)
        self.env.commit("column dropped")
        try:
            code, out, err = self.push()
            self.assertEqual(code, 0, out + err)
            self.assertEqual(self.sh.sheets["orgs"].get_all_values()[0], old_cols[:-1])
        finally:
            tab.cols[:] = old_cols

    def test_a_column_that_a_person_added_to_the_sheet_stops_push(self):
        self.first_push()
        ws = self.sh.sheets["orgs"]
        ws.cells[(1, len(common.ORGS_COLS) + 1)] = "comentarii"
        ws.cells[(2, len(common.ORGS_COLS) + 1)] = "text"
        code, out, _ = self.push()
        self.assertEqual(code, 3)
        self.assertIn("column 'comentarii'", out)
        ws.cells[(2, len(common.ORGS_COLS) + 1)] = ""  # an empty extra column holds nothing to lose
        self.assertEqual(self.push()[0], 0)

    def test_push_reads_columns_by_name_so_a_swapped_header_is_no_false_edit(self):
        self.first_push()
        ws = self.sh.sheets["orgs"]
        for r in range(1, ws.row_count + 1):  # swap columns 2 and 3 with their data
            ws.cells[(r, 2)], ws.cells[(r, 3)] = ws.cells.get((r, 3), ""), ws.cells.get((r, 2), "")
        self.assertEqual(self.push()[0], 0)
        self.assertEqual(ws.get_all_values()[0], common.ORGS_COLS)

    def test_no_marker_push_keeps_the_old_rule_compare_with_the_current_csv(self):
        self.env.commit()
        self.assertEqual(self.push(force=True)[0], 0)
        self.sh.sheets.pop("_sync")
        self.sh.edit("proiecte", self.slug(), "nume", "edit")
        code, out, err = self.push()
        self.assertEqual(code, 3)
        self.assertIn("no sync marker", err)


# ---- v1 and v2 stay apart ---------------------------------------------------------------------------------------

class Separation(unittest.TestCase):
    def test_a_v2_root_refuses_every_live_tab_and_the_form_responses(self):
        env = Env(v2=True)
        self.addCleanup(env.close)
        for name in ("proiecte", "orgs", "propuneri", "_sync"):
            with self.assertRaises(sheets.SheetError) as cm:
                sheets.tabs_for(env.root, [name])
            self.assertIn("refused", str(cm.exception))
            self.assertIn(name, str(cm.exception))

    def test_a_v1_root_refuses_the_v2_tabs(self):
        env = Env()
        self.addCleanup(env.close)
        with self.assertRaises(sheets.SheetError):
            sheets.tabs_for(env.root, ["v2-intrari"])

    def test_a_v2_run_never_asks_the_sheet_for_a_live_tab(self):
        env = Env(v2=True)
        self.addCleanup(env.close)
        env.sh.seed("proiecte", common.PROIECTE_COLS, [{c: "x" for c in common.PROIECTE_COLS}])
        env.sh.seed("orgs", common.ORGS_COLS, [{c: "x" for c in common.ORGS_COLS}])
        before = {t: env.sh.sheets[t].get_all_values() for t in ("proiecte", "orgs")}
        env.commit()
        for fn, kw in ((sheets.cmd_push, {}), (sheets.cmd_diff, {}), (sheets.cmd_pull, {})):
            run(fn, env.ctx(), **kw)
        self.assertFalse({"proiecte", "orgs", "propuneri"} & set(env.sh.touched), env.sh.touched)
        self.assertEqual({t: env.sh.sheets[t].get_all_values() for t in ("proiecte", "orgs")}, before)

    def test_push_creates_the_missing_v2_tab_and_the_marker_tab(self):
        env = Env(v2=True)
        self.addCleanup(env.close)
        env.commit()
        code, out, err = run(sheets.cmd_push, env.ctx())
        self.assertEqual(code, 0, err)
        self.assertEqual(set(env.sh.sheets), {"v2-intrari", "_sync"})
        self.assertEqual([m["tab"] for m in env.sh.table("_sync")], ["v2-intrari"])

    def test_push_does_not_create_a_missing_v1_tab(self):
        env = Env(seed=False)
        self.addCleanup(env.close)
        env.commit()
        with self.assertRaises(sheets.SheetError):
            run(sheets.cmd_push, env.ctx())
        self.assertEqual(env.sh.sheets, {})

    def test_the_two_schemas_keep_separate_marker_rows(self):
        v1, v2 = Env(), Env(v2=True)
        self.addCleanup(v1.close)
        self.addCleanup(v2.close)
        for e in (v1, v2):
            e.sh = v1.sh  # one Sheet for both
        v1.commit()
        v2.commit()
        run(sheets.cmd_push, v1.ctx())
        run(sheets.cmd_push, sheets.Context(v1.sh, v2.root, v2.tabs, git=sheets.Git(v2.repo), clock=lambda: STAMP))
        self.assertEqual(sorted(m["tab"] for m in v1.sh.table("_sync")), ["orgs", "proiecte", "v2-intrari"])


# ---- Validation after pull --------------------------------------------------------------------------------------

class PullCheck(unittest.TestCase):
    def test_v2_pull_check_passes_on_the_unchanged_integration_copy(self):
        env = Env(v2=True)
        self.addCleanup(env.close)
        env.commit()
        run(sheets.cmd_push, env.ctx())
        code, out, err = run(sheets.cmd_pull, env.ctx(), check=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("validate.py", out)

    def v2_bad_cell(self, col, value, expect):
        env = Env(v2=True)
        self.addCleanup(env.close)
        env.commit()
        run(sheets.cmd_push, env.ctx())
        slug = env.rows("v2-intrari")[3]["slug"]
        env.sh.edit("v2-intrari", slug, col, value)
        code, out, err = run(sheets.cmd_pull, env.ctx(), check=True)
        self.assertEqual(code, 1, out + err)
        self.assertIn(expect, out)
        self.assertEqual(env.rows("v2-intrari")[3][col], value)  # the CSV is written first, so the PR can show the error
        return out

    def test_a_label_instead_of_an_id_fails(self):
        self.v2_bad_cell("scopuri", "Transparență", "unknown concept Transparență in scopuri")

    def test_an_id_of_another_scheme_fails(self):
        self.v2_bad_cell("scopuri", "format:harta", "needs the scheme scop")

    def test_a_space_around_the_pipe_fails(self):
        self.v2_bad_cell("functionalitati", "functie:cautare | functie:comparare", "untrimmed list item in functionalitati")

    def test_a_repeated_id_fails(self):
        self.v2_bad_cell("formate", "format:harta|format:harta", "duplicate, blank, or untrimmed list item in formate")

    def test_an_unknown_code_fails(self):
        self.v2_bad_cell("incredere", "foarte-mare", "unknown incredere code")

    def test_a_second_primary_subject_fails(self):
        self.v2_bad_cell("subiect_principal", "subiect:guvernare-democratie|subiect:finante-publice", "allows one value")

    def test_a_topic_in_the_place_of_a_root_subject_fails(self):
        self.v2_bad_cell("subiecte", "subiect:alegeri", "requires top-level subjects")

    def test_v1_pull_check_runs_validate_py(self):
        env = Env()
        self.addCleanup(env.close)
        env.commit()
        run(sheets.cmd_push, env.ctx())
        self.assertEqual(run(sheets.cmd_pull, env.ctx(), check=True)[0], 0)
        slug = env.rows("proiecte")[0]["slug"]
        env.sh.edit("proiecte", slug, "domeniu", "nu-exista")
        code, out, _ = run(sheets.cmd_pull, env.ctx(), check=True)
        self.assertEqual(code, 1)
        self.assertIn("domeniu necunoscut: 'nu-exista'", out)

    def test_pull_without_check_does_not_validate(self):
        env = Env(v2=True)
        self.addCleanup(env.close)
        env.commit()
        run(sheets.cmd_push, env.ctx())
        env.sh.edit("v2-intrari", env.rows("v2-intrari")[3]["slug"], "scopuri", "Transparență")
        self.assertEqual(run(sheets.cmd_pull, env.ctx())[0], 0)


# ---- Workflows --------------------------------------------------------------------------------------------------

def run_blocks(text: str) -> list[str]:
    """The bodies of the `run: |` steps of a workflow file (no YAML parser in the stdlib)."""
    out, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)(?:- )?run: \|\s*$", line)
        if not m:
            continue
        indent, body = len(m[1]) + 2, []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) < indent:
                break
            body.append(nxt[indent:] if nxt.strip() else "")
        out.append("\n".join(body))
    return out


class Workflows(unittest.TestCase):
    pull = (ROOT / ".github/workflows/sheets-pull.yml").read_text(encoding="utf-8")
    push = (ROOT / ".github/workflows/sheets-push.yml").read_text(encoding="utf-8")

    def test_every_shell_step_is_valid_bash(self):
        for name, text in (("sheets-pull", self.pull), ("sheets-push", self.push)):
            blocks = run_blocks(text)
            self.assertTrue(blocks, name)
            for body in blocks:
                body = re.sub(r"\$\{\{[^}]*\}\}", "x", body)
                r = subprocess.run(["bash", "-n"], input=body, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}\n{body}")

    def test_pull_sets_the_commit_status_and_fails_after_the_pull_request(self):
        text = self.pull
        self.assertRegex(text, r"permissions:\n(?:  .*\n)*  statuses: write")
        self.assertIn("gh api repos/${{ github.repository }}/statuses/", text)
        self.assertIn("context='validate / sheets-pull'", text)
        self.assertRegex(text, r"-f state=\"?\$\{?state\}?\"?")
        self.assertIn("fetch-depth: 0", text)  # the marker's commit is older than main's tip
        order = [text.index(s) for s in ("name: Open or update the pull request", "name: Set the commit status")]
        self.assertEqual(order, sorted(order))
        status = text[text.index("name: Set the commit status"):]
        self.assertIn("exit 1", status)
        self.assertNotRegex(status.split("exit 1")[0], r"(?m)^\s+set \+e")

    def test_pull_does_not_hide_a_failed_pull_or_a_conflict(self):
        text = self.pull
        step = text[text.index("name: Read the Sheet"):text.index("name: Check the CSVs")]
        self.assertIn("scripts/sheets.py pull", step)
        self.assertNotIn("set +e", step)  # the default shell stops the job on exit 1 or 3, before any pull request is touched
        self.assertIn("steps.state.outputs.changed == 'false'", text)

    def test_push_uses_the_marker_and_keeps_the_manual_inputs(self):
        text = self.push
        self.assertNotIn("BEFORE", text)
        self.assertNotIn("github.event.before", text)
        self.assertIn("inputs.since", text)
        self.assertIn("inputs.force", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn('"$code" -eq 3', text)

    def test_the_workflows_follow_the_public_root(self):
        """Before the cutover no Sheets workflow names the v2 root (the v1 tabs stay as they are). After it
        (common.PUBLIC_ROOT is the integration copy), both name it and the tab v2-intrari, and none names the v1 CSVs."""
        cut_over = common.PUBLIC_ROOT != common.DATA
        for text in (self.pull, self.push):
            self.assertEqual("--data-dir data/taxonomy-v2/integrare" in text, cut_over)
            self.assertEqual("--tabs v2-intrari" in text, cut_over)
            self.assertEqual("data/proiecte.csv" in text, not cut_over)
            self.assertEqual("data/orgs.csv" in text, not cut_over)


def step_body(text: str, name: str) -> str:
    """The `run: |` body of the step with this name, with the GitHub expressions filled in."""
    start = text.index(f"- name: {name}\n")
    block = run_blocks("\n".join(text[start:].splitlines()[:80]))[0]  # the first run block after the step's name
    return block.replace("${{ github.repository }}", "owner/repo")


class WorkflowShell(unittest.TestCase):
    """Run the shell of the workflow steps with stub commands (uv, gh, python3) and check the exit codes and the calls."""
    pull = (ROOT / ".github/workflows/sheets-pull.yml").read_text(encoding="utf-8")
    push = (ROOT / ".github/workflows/sheets-push.yml").read_text(encoding="utf-8")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "bin").mkdir()
        self.log = self.dir / "calls.log"
        self.out = self.dir / "github_output"
        self.out.touch()

    def stub(self, name: str, body: str):
        path = self.dir / "bin" / name
        path.write_text(f'#!/bin/sh\necho "{name} $*" >> "{self.log}"\n{body}\n', encoding="utf-8")
        path.chmod(0o755)

    def step(self, text, name, env=None):
        full = {"PATH": f"{self.dir / 'bin'}:/usr/bin:/bin", "RUNNER_TEMP": str(self.dir), "GITHUB_OUTPUT": str(self.out),
                "GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "42", **(env or {})}
        r = subprocess.run(["bash", "-e", "-c", step_body(text, name)], capture_output=True, text=True, env=full, cwd=self.dir)
        return r, (self.log.read_text(encoding="utf-8") if self.log.exists() else "")

    def test_a_conflict_fails_the_read_step_with_exit_3_and_an_annotation(self):
        self.stub("uv", 'case "$*" in *diff*) echo "the diff" ;; *pull*) exit 3 ;; esac')
        r, calls = self.step(self.pull, "Read the Sheet")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("::error::Conflict", r.stdout)
        self.assertIn("the diff", r.stdout)

    def test_another_pull_failure_keeps_its_exit_code(self):
        self.stub("uv", 'case "$*" in *pull*) exit 1 ;; esac')
        r, _ = self.step(self.pull, "Read the Sheet")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("::error::Conflict", r.stdout)

    def test_a_failed_diff_stops_the_step_before_pull(self):
        self.stub("uv", 'case "$*" in *diff*) exit 1 ;; esac')
        r, calls = self.step(self.pull, "Read the Sheet")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("pull", calls)

    def test_a_clean_read_succeeds(self):
        self.stub("uv", "exit 0")
        r, calls = self.step(self.pull, "Read the Sheet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("run scripts/sheets.py diff", calls)
        self.assertIn("run scripts/sheets.py pull", calls)

    def test_validate_and_build_record_both_codes_and_never_fail_the_step(self):
        self.stub("python3", 'case "$*" in *validate.py*) echo "boom"; exit 1 ;; *build.py*) exit 2 ;; esac')
        r, _ = self.step(self.pull, "Validate and build")
        self.assertEqual(r.returncode, 0, r.stderr)  # the failure shows later, after the pull request exists
        self.assertEqual(sorted(self.out.read_text().split()), ["build=2", "validate=1"])
        body = (self.dir / "body.md").read_text(encoding="utf-8")
        self.assertIn("cod de ieșire 1", body)
        self.assertIn("cod de ieșire 2", body)

    def status(self, validate, build):
        self.stub("gh", "exit 0")
        return self.step(self.pull, "Set the commit status and fail on errors",
                         {"SHA": "abc123", "VALIDATE": validate, "BUILD": build, "GH_TOKEN": "x"})

    def test_success_sets_the_status_on_the_pull_request_head_and_passes(self):
        r, calls = self.status("0", "0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gh api repos/owner/repo/statuses/abc123", calls)
        self.assertIn("-f state=success", calls)
        self.assertIn("-f context=validate / sheets-pull", calls)
        self.assertIn("-f target_url=https://github.com/owner/repo/actions/runs/42", calls)

    def test_a_failed_validate_sets_the_failure_status_first_and_then_fails_the_job(self):
        for validate, build in (("1", "0"), ("0", "1"), ("1", "1"), ("", "0")):
            self.log.unlink(missing_ok=True)
            r, calls = self.status(validate, build)
            self.assertEqual(r.returncode, 1, (validate, build, r.stderr))
            self.assertIn("-f state=failure", calls, (validate, build))  # the status is set before the step fails
            self.assertIn("::error::", r.stdout)

    def test_the_status_description_fits_the_limit_of_140_characters(self):
        self.status("1", "2")
        description = re.search(r"-f description=(.*)", self.log.read_text(encoding="utf-8"))[1]
        self.assertLessEqual(len(description), 140)

    def test_a_failing_status_call_fails_the_step(self):
        self.stub("gh", "exit 1")
        r, _ = self.step(self.pull, "Set the commit status and fail on errors", {"SHA": "abc", "VALIDATE": "0", "BUILD": "0"})
        self.assertNotEqual(r.returncode, 0)

    def test_the_pull_request_step_reports_the_head_it_pushed(self):
        self.stub("git", 'case "$1" in rev-parse) echo deadbeef ;; esac')
        self.stub("gh", 'case "$*" in "pr list"*) echo "" ;; esac')
        r, calls = self.step(self.pull, "Open or update the pull request", {"BRANCH": "sheets-sync", "TITLE": "t"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sha=deadbeef", self.out.read_text())
        self.assertIn("git push --force origin sheets-sync", calls)
        self.assertIn("gh pr create", calls)

    def test_push_passes_since_and_force_only_when_given_and_reports_exit_3(self):
        self.stub("uv", "exit 3")
        r, calls = self.step(self.push, "Write the CSVs to the Sheet", {"SINCE": "", "FORCE": "false"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("::error::Tabelul are modificări nesincronizate", r.stdout)
        root = "" if common.PUBLIC_ROOT == common.DATA else " --data-dir data/taxonomy-v2/integrare --tabs v2-intrari"
        self.assertEqual(calls.strip(), f"uv run scripts/sheets.py push{root}")  # no --since: the marker is the base
        self.log.unlink()
        self.stub("uv", "exit 0")
        r, calls = self.step(self.push, "Write the CSVs to the Sheet", {"SINCE": "abc", "FORCE": "true"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls.strip(), f"uv run scripts/sheets.py push{root} --since abc --force")

    def test_push_keeps_other_failures_as_they_are(self):
        self.stub("uv", "exit 1")
        r, _ = self.step(self.push, "Write the CSVs to the Sheet", {"SINCE": "", "FORCE": "false"})
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("::error::", r.stdout)


# ---- The v2 Form -----------------------------------------------------------------------------------------------

def args_for(root, **kw):
    """The argparse namespace of form.py for a v2 root."""
    base = dict(apply=False, save=False, json=False, data_dir=root, answer_map=form.ANSWER_MAP, write_map=False, check=False,
                import_file=None, out=None)
    return argparse.Namespace(**{**base, **kw})


class V2Package:
    """A temporary copy of the v2 package, for tests that change the vocabulary."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "taxonomy-v2"
        shutil.copytree(PACKAGE, self.dir, ignore=shutil.ignore_patterns("runs", "__pycache__", "catalogue.json"))
        self.root = self.dir / "integrare"
        self.map = Path(self.tmp.name) / "form-v2.json"

    def edit_concept(self, ident, **cells):
        path = self.dir / "concepte.csv"
        header, rows = taxonomy_v2.read_table(path)
        next(r for r in rows if r["id"] == ident).update(cells)
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def close(self):
        self.tmp.cleanup()


class FormV2Plan(unittest.TestCase):
    pkg = taxonomy_v2.load(OVERLAY)

    def test_the_titles_follow_the_columns_of_intrari_csv(self):
        qs = form.build_questions_v2(self.pkg)
        self.assertEqual([q.title for q in qs], form.TITLES_V2)
        self.assertEqual(len(set(form.TITLES_V2)), 13)
        kinds = {q.title: q.kind for q in qs}
        self.assertEqual((kinds["Ce propui?"], kinds["Subiecte"], kinds["Formate"], kinds["Acoperire"]), ("radio", "checkbox", "checkbox", "radio"))
        self.assertTrue(qs[0].required and qs[1].required and qs[4].required)

    def test_choices_carry_the_vocabulary_labels_and_stable_ids(self):
        choices = form.vocabulary_choices(self.pkg)
        for label, ident in choices["Subiecte"]:
            row = self.pkg.concepts[ident]
            self.assertEqual((row["eticheta_ro"], row["mai_larg"], row["schema"]), (label, "", "subiect"))  # roots only, no topics
        self.assertEqual(len(choices["Subiecte"]), 13)
        for label, ident in choices["Formate"]:
            self.assertEqual((self.pkg.concepts[ident]["eticheta_ro"], self.pkg.concepts[ident]["schema"]), (label, "format"))
        self.assertEqual([i for _, i in choices["Ce propui?"]], list(self.pkg.codes["tip_entitate"]))
        self.assertEqual([i for _, i in choices["Acoperire"]], ["national", "local", "international", "necunoscut"])
        self.assertIn("Drept, justiție și drepturi", [label for label, _ in choices["Subiecte"]])  # a label with a comma

    def test_the_committed_answer_map_covers_the_plan(self):
        stored = form.load_answer_map(form.ANSWER_MAP)
        self.assertIsNotNone(stored, "data/form-v2.json is missing; run form.py --data-dir ... --write-map")
        drift = form.map_drift(self.pkg, form.planned_map(self.pkg), stored)
        self.assertFalse(form.drift_needs_action(drift), drift)
        self.assertEqual(stored["titles"], form.TITLES_V2)
        self.assertIsInstance(stored["version"], int)

    def test_the_batch_body_only_creates_items(self):
        body = form.batch_body(0, None, form.build_questions_v2(self.pkg))
        self.assertEqual([next(iter(r)) for r in body["requests"]], ["createItem"] * 13)
        self.assertNotIn("writeControl", body)

    def test_the_v1_plan_is_untouched(self):
        self.assertEqual(len(form.QUESTIONS), 13)  # the v1 plan is still what --apply uses
        self.assertEqual([q.title for q in form.QUESTIONS], form.TITLES)

    def test_a_v2_root_refuses_apply_and_save_without_asking_for_credentials(self):
        for flag in ("--apply", "--save"):
            r = subprocess.run([sys.executable, str(HERE / "form.py"), "--data-dir", str(OVERLAY), flag], capture_output=True, text=True,
                               env={"PATH": os.environ["PATH"]})
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("not available with a v2 --data-dir", r.stderr)

    def test_the_v2_plan_never_opens_a_google_session(self):
        def boom(*a, **k):
            raise AssertionError("Google was called")
        saved = form.open_session, form.get_form, form.credentials_info
        form.open_session = form.get_form = form.credentials_info = boom
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                form.main_v2(args_for(OVERLAY, json=True, check=True), OVERLAY)
        finally:
            form.open_session, form.get_form, form.credentials_info = saved
        self.assertIn("Nothing is sent to Google", out.getvalue())
        self.assertIn('"createItem"', out.getvalue())

    def test_v2_options_are_refused_on_a_v1_root(self):
        r = subprocess.run([sys.executable, str(HERE / "form.py"), "--data-dir", str(DATA), "--write-map"], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"]})  # the v1 root, whatever the public root is
        self.assertEqual(r.returncode, 1)
        self.assertIn("need a v2 --data-dir", r.stderr)


class FormV2AnswerMap(unittest.TestCase):
    def setUp(self):
        self.p = V2Package()
        self.addCleanup(self.p.close)

    def write_map(self, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            form.main_v2(args_for(self.p.root, answer_map=self.p.map, write_map=True, **kw), self.p.root)
        return json.loads(self.p.map.read_text(encoding="utf-8"))

    def test_write_map_creates_version_1_and_is_idempotent(self):
        first = self.write_map()
        self.assertEqual(first["version"], 1)
        again = self.write_map()
        self.assertEqual(again, first)

    def test_a_renamed_label_keeps_its_old_row_and_raises_the_version(self):
        self.write_map()
        self.p.edit_concept("format:harta", eticheta_ro="Hartă interactivă")
        stored = form.load_answer_map(self.p.map)
        pkg = taxonomy_v2.load(self.p.root)
        drift = form.map_drift(pkg, form.planned_map(pkg), stored)
        self.assertEqual([d[1] for d in drift["new"]], ["Hartă interactivă"])
        self.assertEqual([d[1:] for d in drift["kept"]], [("Hartă", "format:harta")])
        data = self.write_map()
        self.assertEqual(data["version"], 2)
        self.assertEqual((data["answers"]["Formate"]["Hartă"], data["answers"]["Formate"]["Hartă interactivă"]), ("format:harta", "format:harta"))
        model = form.load_model(pkg, self.p.map)  # a response from before the rename still imports to the same ID
        old = form.import_response(model, {"Ce propui?": "Proiect", "Nume": "Vechi", "Formate": "Hartă", "Subiecte": "Sănătate"}, 2, set())
        self.assertEqual(old.row["formate"], "format:harta")
        new = form.import_response(model, {"Ce propui?": "Proiect", "Nume": "Nou", "Formate": "Hartă interactivă"}, 3, set())
        self.assertEqual(new.row["formate"], "format:harta")

    def test_a_label_that_maps_to_another_id_is_never_overwritten(self):
        data = self.write_map()
        data["answers"]["Formate"]["Hartă"] = "format:ghid"
        self.p.map.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()):
            self.write_map()
        self.assertIn("must keep its ID", str(cm.exception))
        self.assertEqual(json.loads(self.p.map.read_text())["answers"]["Formate"]["Hartă"], "format:ghid")

    def test_check_exits_1_when_a_label_is_new(self):
        self.write_map()
        self.p.edit_concept("format:harta", eticheta_ro="Hartă interactivă")
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()):
            form.main_v2(args_for(self.p.root, answer_map=self.p.map, check=True), self.p.root)
        self.assertEqual(cm.exception.code, 1)

    def test_a_retired_concept_leaves_the_form_but_not_the_map(self):
        self.write_map()
        self.p.edit_concept("format:api", statut="retras")
        pkg = taxonomy_v2.load(self.p.root)
        self.assertNotIn("format:api", [i for _, i in form.vocabulary_choices(pkg)["Formate"]])
        drift = form.map_drift(pkg, form.planned_map(pkg), form.load_answer_map(self.p.map))
        self.assertEqual([d[1:] for d in drift["dead"]], [("API oferit", "format:api")])
        model = form.load_model(pkg, self.p.map)
        done = form.import_response(model, {"Ce propui?": "Proiect", "Nume": "X", "Formate": "API oferit"}, 2, set())
        self.assertEqual(done.row["formate"], "")  # an ID that is no longer offered is not copied
        self.assertTrue(any("no longer offers" in p for p in done.problems))

    def test_a_map_without_a_kind_section_is_drift(self):
        data = self.write_map()
        del data["kind_section"]["campanie"]
        self.p.map.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        pkg = taxonomy_v2.load(self.p.root)
        drift = form.map_drift(pkg, form.planned_map(pkg), form.load_answer_map(self.p.map))
        self.assertEqual([d[0] for d in drift["sections"]], ["campanie"])

    def test_an_organisation_must_stay_in_its_own_section(self):
        data = self.write_map()
        data["kind_section"]["organizatie"] = "resursa"
        self.p.map.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        pkg = taxonomy_v2.load(self.p.root)
        drift = form.map_drift(pkg, form.planned_map(pkg), form.load_answer_map(self.p.map))
        self.assertEqual([d[0] for d in drift["sections"]], ["organizatie"])


def resp(**by_title):
    """A response row of `propuneri`: every title empty, then the given answers (keys: the title with _ for spaces)."""
    names = {"Ce_propui": "Ce propui?", "Nume": "Nume", "Pe_scurt": "Pe scurt", "Descriere": "Descriere", "Adresa_URL": "Adresa (URL)",
             "Alte_linkuri": "Alte linkuri", "Subiecte": "Subiecte", "Formate": "Formate", "Acoperire": "Acoperire", "Oras": "Oraș",
             "Autor": "Autor", "Emailul_tau": "E-mailul tău", "Altceva": "Altceva?"}
    assert sorted(names.values()) == sorted(form.TITLES_V2)
    row = {t: "" for t in form.TITLES_V2}
    row["Timestamp"] = "19/10/2026 12:00:00"
    for k, v in by_title.items():
        row[names[k]] = v
    return row


class FormV2Import(unittest.TestCase):
    pkg = taxonomy_v2.load(OVERLAY)
    model = form.load_model(pkg, form.ANSWER_MAP)

    def one(self, taken=None, number=2, **answers):
        return form.import_response(self.model, resp(**answers), number, set(self.pkg.entries) if taken is None else taken)

    def good(self, **answers):
        done = self.one(**answers)
        self.assertIsNotNone(done.row, done.problems)
        return done

    def test_one_clear_subject_gives_a_proposed_entry_with_ids(self):
        done = self.good(Ce_propui="Proiect", Nume="Harta Școlilor Ținute", Pe_scurt="Școlile pe hartă", Adresa_URL="https://harta.example.ro",
                         Subiecte="Educație și cultură", Formate="Hartă, Registru sau bază de date", Acoperire="Național", Autor="Ana Pop",
                         Altceva="vezi și alt site")
        row = done.row
        self.assertEqual((row["slug"], row["tip_entitate"], row["sectiune_url"]), ("harta-scolilor-tinute", "proiect", "proiect"))
        self.assertEqual((row["subiect_principal"], row["subiecte"]), ("subiect:educatie-cultura", "subiect:educatie-cultura"))
        self.assertEqual(row["formate"], "format:harta|format:registru")
        self.assertEqual((row["nivel_acoperire"], row["arii_acoperite"]), ("national", "tara:RO"))
        self.assertEqual((row["clasificare_stare"], row["incredere"]), ("propus", "mica"))
        self.assertEqual((row["nume"], row["descriere_scurta"], row["autor_original"], row["nota"]),
                         ("Harta Școlilor Ținute", "Școlile pe hartă", "Ana Pop", "Formular: vezi și alt site"))
        self.assertEqual((row["sursa_fisier"], row["sursa_rand"], row["teme"], row["scopuri"]), ("", "", "", ""))
        self.assertIn("rândul 2 (19/10/2026 12:00:00)", row["nota_clasificare"])
        self.assertEqual(list(row), self.pkg.schema["headers"]["intrari.csv"])

    def test_a_label_with_a_comma_is_one_subject_not_two(self):
        done = self.good(Ce_propui="Proiect", Nume="Ceva", Subiecte="Drept, justiție și drepturi")
        self.assertEqual((done.row["subiect_principal"], done.row["clasificare_stare"]), ("subiect:drept-justitie", "propus"))
        self.assertEqual(form.split_choices("Drept, justiție și drepturi, Finanțe publice, Sănătate", self.model.answers["Subiecte"]),
                         (["Drept, justiție și drepturi", "Finanțe publice", "Sănătate"], []))

    def test_several_subjects_leave_the_primary_one_to_the_editor(self):
        done = self.good(Ce_propui="Proiect", Nume="Ceva", Subiecte="Drept, justiție și drepturi, Finanțe publice")
        row = done.row
        self.assertEqual((row["clasificare_stare"], row["subiect_principal"], row["subiecte"]), ("de-revizuit", "", ""))
        self.assertIn("subiect:drept-justitie|subiect:finante-publice", row["nota_clasificare"])

    def test_no_subject_is_a_review_state(self):
        done = self.good(Ce_propui="Proiect", Nume="Ceva")
        self.assertEqual(done.row["clasificare_stare"], "de-revizuit")
        self.assertIn("Fără subiect", done.row["nota_clasificare"])

    def test_an_unknown_label_is_reported_and_left_out_never_guessed(self):
        done = self.good(Ce_propui="Proiect", Nume="Ceva", Subiecte="Sănătate", Formate="Hartă, harta, Altceva ciudat", Acoperire="Planetar")
        self.assertEqual(done.row["formate"], "format:harta")  # "harta" (no diacritic) is not "Hartă"
        text = "\n".join(done.problems)
        self.assertIn("'harta'", text)
        self.assertIn("'Altceva ciudat'", text)
        self.assertIn("'Planetar'", text)
        self.assertEqual(done.row["nivel_acoperire"], "necunoscut")
        self.assertIn("Etichetă necunoscută", done.row["nota_clasificare"])

    def test_an_unknown_kind_or_no_name_or_a_taken_slug_skips_the_row(self):
        self.assertIsNone(self.one(Ce_propui="Altceva", Nume="X").row)
        self.assertIsNone(self.one(Ce_propui="Proiect", Nume="  ").row)
        done = self.one(Ce_propui="Proiect", Nume="465")  # the slug of an existing entry
        self.assertIsNone(done.row)
        self.assertIn("exists already", done.problems[-1])
        taken = set()
        self.assertIsNotNone(self.one(taken=taken, Ce_propui="Proiect", Nume="Dublu").row)
        self.assertIsNone(self.one(taken=taken, Ce_propui="Proiect", Nume="Dublu").row)  # twice in one batch

    def test_the_kind_decides_the_section(self):
        for label, kind, section in (("Organizație", "organizatie", "organizatie"), ("Publicație", "publicatie", "resursa"),
                                     ("Set de date", "set-date", "resursa"), ("Campanie", "campanie", "resursa")):
            row = self.good(Ce_propui=label, Nume=f"Test {kind}", Subiecte="Sănătate").row
            self.assertEqual((row["tip_entitate"], row["sectiune_url"]), (kind, section))

    def test_local_coverage_needs_a_known_place_else_the_level_is_unknown(self):
        row = self.good(Ce_propui="Proiect", Nume="Local 1", Subiecte="Sănătate", Acoperire="Local", Oras="Iași").row
        self.assertEqual((row["nivel_acoperire"], row["arii_acoperite"], row["localitate_originala"]), ("local", "localitate:iasi", "Iași"))
        row = self.good(Ce_propui="Proiect", Nume="Local 2", Subiecte="Sănătate", Acoperire="Local", Oras="IASI").row  # case and diacritics
        self.assertEqual(row["arii_acoperite"], "localitate:iasi")
        done = self.good(Ce_propui="Proiect", Nume="Local 3", Subiecte="Sănătate", Acoperire="Local", Oras="Cluj-Napoca")
        self.assertEqual((done.row["nivel_acoperire"], done.row["arii_acoperite"], done.row["localitate_originala"]), ("necunoscut", "", "Cluj-Napoca"))
        self.assertIn("Cluj-Napoca", done.row["nota_clasificare"])
        self.assertTrue(any("arii.csv" in p for p in done.problems))

    def test_an_empty_coverage_stays_unknown_and_links_are_split(self):
        row = self.good(Ce_propui="Proiect", Nume="Linkuri", Subiecte="Sănătate",
                        Alte_linkuri="https://github.com/a/b\nhttps://www.facebook.com/x, https://t.me/y").row
        self.assertEqual(row["nivel_acoperire"], "necunoscut")
        self.assertEqual(row["linkuri"], "https://github.com/a/b https://www.facebook.com/x https://t.me/y")

    def test_the_proposers_email_is_not_copied(self):
        done = self.good(Ce_propui="Proiect", Nume="Cu mail", Subiecte="Sănătate", Emailul_tau="persoana@example.com")
        self.assertNotIn("persoana@example.com", "".join(done.row.values()))
        self.assertTrue(any("e-mail is not copied" in p for p in done.problems))

    def test_slugify(self):
        self.assertEqual(form.slugify("Ședința Ținută în Iași!"), "sedinta-tinuta-in-iasi")
        self.assertEqual(form.slugify("  ***  "), "")

    def test_imported_rows_pass_the_package_checks(self):
        copy = V2Package()
        self.addCleanup(copy.close)
        responses = [
            resp(Ce_propui="Proiect", Nume="Școli pe hartă", Adresa_URL="https://scoli.example.ro", Subiecte="Educație și cultură",
                 Formate="Hartă, Ghid", Acoperire="Național"),
            resp(Ce_propui="Organizație", Nume="Asociația Exemplu", Adresa_URL="https://exemplu.example.ro", Subiecte="Societate civilă"),
            resp(Ce_propui="Publicație", Nume="Raport despre apă", Subiecte="Mediu și energie", Formate="Raport sau cercetare"),
            resp(Ce_propui="Proiect", Nume="Local Iași", Subiecte="Comunități și teritoriu", Acoperire="Local", Oras="Iași"),
            resp(Ce_propui="Proiect", Nume="Local necunoscut", Subiecte="Sănătate", Acoperire="Local", Oras="Alt oraș"),
            resp(Ce_propui="Proiect", Nume="Fără subiect"),
            resp(Ce_propui="Proiect", Nume="Două subiecte", Subiecte="Sănătate, Finanțe publice", Formate="Hartă, nu-exista"),
        ]
        taken, rows = set(self.pkg.entries), []
        for n, r in enumerate(responses, 2):
            done = form.import_response(self.model, r, n, taken)
            self.assertIsNotNone(done.row, done.problems)
            rows.append(done.row)
        path = copy.root / "intrari.csv"
        header, existing = taxonomy_v2.read_table(path)
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
            w.writeheader()
            w.writerows(existing + rows)
        errors, summary = taxonomy_v2.check(copy.root)
        self.assertEqual(errors, [])
        self.assertEqual(summary["entries"], 122 + len(rows))

    def test_the_cli_import_writes_rows_reports_problems_and_never_touches_intrari_csv(self):
        before = (OVERLAY / "intrari.csv").read_bytes()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src, out = Path(tmp.name) / "propuneri.csv", Path(tmp.name) / "rows.csv"
        header = ["Timestamp", *form.TITLES_V2, "Untitled Question"]
        with src.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
            w.writeheader()
            w.writerow({**resp(Ce_propui="Proiect", Nume="Primul", Subiecte="Sănătate", Formate="Hartă"), "Untitled Question": "x"})
            w.writerow({**resp(Ce_propui="Nu știu", Nume="Al doilea"), "Untitled Question": ""})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = form.cmd_import(self.model, src, out)
        self.assertEqual(code, 1)  # one row skipped
        self.assertIn("1 entry mapped, 1 row(s) skipped", err.getvalue())
        self.assertIn("unknown answer to «Ce propui?»", err.getvalue())
        _, rows = taxonomy_v2.read_table(out)
        self.assertEqual([r["slug"] for r in rows], ["primul"])
        self.assertEqual((OVERLAY / "intrari.csv").read_bytes(), before)

    def test_the_cli_import_stops_when_a_title_column_is_missing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "propuneri.csv"
        src.write_text("Timestamp,Ce propui?,Nume\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            form.cmd_import(self.model, src, None)
        self.assertIn(f"Version {self.model.version} of the answer map", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
