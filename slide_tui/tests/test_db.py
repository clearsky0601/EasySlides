import sqlite3
import tempfile
import unittest
from pathlib import Path

from slide_tui import db


def _make_db(path: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE slideapp_slide ("
        "id INTEGER PRIMARY KEY, title TEXT, category TEXT, "
        "lock INTEGER, version INTEGER, sort_order INTEGER, content TEXT)"
    )
    conn.executemany(
        "INSERT INTO slideapp_slide "
        "(id, title, category, lock, version, sort_order, content) "
        "VALUES (?, ?, ?, ?, ?, ?, '')",
        rows,
    )
    conn.commit()
    conn.close()


class ListSlidesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "db.sqlite3"
        _make_db(self.db, [
            (2, "Beta", "cat", 0, 3, 5),
            (1, "Alpha", "", 1, 0, 1),
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def test_orders_by_sort_then_id(self):
        rows = db.list_slides(self.db)
        self.assertEqual([r.id for r in rows], [1, 2])  # sort_order 1 then 5

    def test_fields_and_lock_flag(self):
        rows = {r.id: r for r in db.list_slides(self.db)}
        self.assertTrue(rows[1].is_locked)
        self.assertFalse(rows[2].is_locked)
        self.assertEqual(rows[2].title, "Beta")
        self.assertEqual(rows[2].category, "cat")

    def test_unlock_sets_lock_zero(self):
        db.unlock_slide(self.db, 1)
        rows = {r.id: r for r in db.list_slides(self.db)}
        self.assertFalse(rows[1].is_locked)

    def test_missing_table_returns_empty(self):
        empty = Path(self.tmp.name) / "empty.sqlite3"
        sqlite3.connect(empty).close()
        self.assertEqual(db.list_slides(empty), [])

    def test_legacy_schema_without_category_sort(self):
        legacy = Path(self.tmp.name) / "legacy.sqlite3"
        conn = sqlite3.connect(legacy)
        conn.execute(
            "CREATE TABLE slideapp_slide "
            "(id INTEGER PRIMARY KEY, title TEXT, content TEXT, "
            "lock INTEGER, version INTEGER)"
        )
        conn.execute(
            "INSERT INTO slideapp_slide (id, title, content, lock, version) "
            "VALUES (7, 'Legacy', '', 0, 2)"
        )
        conn.commit()
        conn.close()
        rows = db.list_slides(legacy)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, 7)
        self.assertEqual(rows[0].category, "")   # defaulted
        self.assertEqual(rows[0].sort_order, 0)  # defaulted


class DiscoverDbsTests(unittest.TestCase):
    def test_finds_root_and_archive_default_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "archive").mkdir()
            (root / "db.sqlite3").touch()
            (root / "other.sqlite3").touch()
            (root / "archive" / "db.sqlite3").touch()

            found = db.discover_dbs(root)
            names = [str(p.relative_to(root)) for p in found]
            self.assertEqual(names[0], "db.sqlite3")  # default first
            self.assertIn("other.sqlite3", names)
            self.assertIn("archive/db.sqlite3", names)
            self.assertEqual(len(found), 3)


class DisplayNameTests(unittest.TestCase):
    def test_repo_relative_disambiguates_same_basename(self):
        root = db.REPO_ROOT
        self.assertEqual(db.display_name(root / "db.sqlite3"), "db.sqlite3")
        self.assertEqual(
            db.display_name(root / "archive" / "db.sqlite3"), "archive/db.sqlite3"
        )

    def test_outside_repo_falls_back_to_basename(self):
        self.assertEqual(db.display_name(Path("/tmp/elsewhere.sqlite3")),
                         "elsewhere.sqlite3")


if __name__ == "__main__":
    unittest.main()
