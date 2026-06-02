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

    def test_category_ref_name_takes_precedence(self):
        modern = Path(self.tmp.name) / "modern.sqlite3"
        conn = sqlite3.connect(modern)
        conn.execute(
            "CREATE TABLE slideapp_slidecategory ("
            "id INTEGER PRIMARY KEY, name TEXT, position INTEGER)"
        )
        conn.execute(
            "CREATE TABLE slideapp_slide ("
            "id INTEGER PRIMARY KEY, title TEXT, category TEXT, "
            "category_ref_id INTEGER, lock INTEGER, version INTEGER, "
            "sort_order INTEGER, content TEXT)"
        )
        conn.execute(
            "INSERT INTO slideapp_slidecategory (id, name, position) "
            "VALUES (1, '现代分类', 0)"
        )
        conn.execute(
            "INSERT INTO slideapp_slide "
            "(id, title, category, category_ref_id, lock, version, "
            "sort_order, content) "
            "VALUES (9, 'Modern', 'legacy', 1, 0, 1, 0, '')"
        )
        conn.commit()
        conn.close()

        rows = db.list_slides(modern)
        self.assertEqual(rows[0].category, "现代分类")

    def test_lists_persisted_categories(self):
        modern = Path(self.tmp.name) / "categories.sqlite3"
        conn = sqlite3.connect(modern)
        conn.execute(
            "CREATE TABLE slideapp_slidecategory ("
            "id INTEGER PRIMARY KEY, name TEXT, position INTEGER)"
        )
        conn.executemany(
            "INSERT INTO slideapp_slidecategory (id, name, position) VALUES (?, ?, ?)",
            [(1, "B", 2), (2, "A", 1)],
        )
        conn.commit()
        conn.close()

        categories = db.list_categories(modern)
        self.assertEqual([c.name for c in categories], ["A", "B"])

    def test_missing_categories_table_returns_empty(self):
        self.assertEqual(db.list_categories(self.db), [])


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


class SlideContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "db.sqlite3"
        conn = sqlite3.connect(self.db)
        conn.execute(
            "CREATE TABLE slideapp_slide ("
            "id INTEGER PRIMARY KEY, title TEXT, category TEXT, "
            "lock INTEGER, version INTEGER, sort_order INTEGER, content TEXT)"
        )
        conn.execute(
            "INSERT INTO slideapp_slide "
            "(id, title, category, lock, version, sort_order, content) "
            "VALUES (1, 'Alpha', '', 0, 0, 1, '# heading\nbody text')"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_content_is_loaded(self):
        rows = db.list_slides(self.db)
        self.assertEqual(rows[0].content, "# heading\nbody text")

    def test_blob_content_is_decoded_to_str(self):
        # 现实数据：个别幻灯片的 content 列被存成了 BLOB（bytes），
        # SlideRow.content 必须始终是 str，否则 TUI 拼接标题+正文时崩溃。
        blob_db = Path(self.tmp.name) / "blob.sqlite3"
        conn = sqlite3.connect(blob_db)
        conn.execute(
            "CREATE TABLE slideapp_slide ("
            "id INTEGER PRIMARY KEY, title TEXT, category TEXT, "
            "lock INTEGER, version INTEGER, sort_order INTEGER, content TEXT)"
        )
        conn.execute(
            "INSERT INTO slideapp_slide "
            "(id, title, category, lock, version, sort_order, content) "
            "VALUES (1, 'Blob', '', 0, 0, 1, ?)",
            ("# 标题\n正文内容".encode("utf-8"),),
        )
        conn.commit()
        conn.close()
        rows = db.list_slides(blob_db)
        self.assertIsInstance(rows[0].content, str)
        self.assertEqual(rows[0].content, "# 标题\n正文内容")

    def test_content_defaults_empty_on_legacy_without_column(self):
        legacy = Path(self.tmp.name) / "legacy.sqlite3"
        conn = sqlite3.connect(legacy)
        conn.execute(
            "CREATE TABLE slideapp_slide "
            "(id INTEGER PRIMARY KEY, title TEXT, lock INTEGER, version INTEGER)"
        )
        conn.execute(
            "INSERT INTO slideapp_slide (id, title, lock, version) "
            "VALUES (1, 'NoContent', 0, 0)"
        )
        conn.commit()
        conn.close()
        rows = db.list_slides(legacy)
        self.assertEqual(rows[0].content, "")


if __name__ == "__main__":
    unittest.main()
