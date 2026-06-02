"""Raw-sqlite3 data access for the slide previewer.

Deliberately Django-free: the TUI must read slide lists from *any* sqlite file
and toggle locks without binding Django to a single database. Mirrors the
connection style of ``.claude/skills/easy-slides/scripts/slide_db.py``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_NAME = "db.sqlite3"


@dataclass(frozen=True)
class SlideRow:
    id: int
    title: str
    category: str
    lock: int           # 1 = locked/private, 0 = public
    version: int
    sort_order: int
    content: str = ""

    @property
    def is_locked(self) -> bool:
        return bool(self.lock)


@dataclass(frozen=True)
class CategoryRow:
    name: str
    position: int


def display_name(path: Path) -> str:
    """Repo-relative name so e.g. ``db.sqlite3`` and ``archive/db.sqlite3`` differ."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return p.name


def discover_dbs(repo_root: Path | None = None) -> list[Path]:
    """All ``*.sqlite3`` files in the repo root and ``archive/``, db.sqlite3 first."""
    root = repo_root or REPO_ROOT
    found: list[Path] = []
    seen: set[Path] = set()
    for directory in (root, root / "archive"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.sqlite3")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(path)

    def sort_key(p: Path) -> tuple[int, str]:
        # Default main DB at repo root sorts first.
        is_default = p.name == DEFAULT_DB_NAME and p.parent.resolve() == root.resolve()
        return (0 if is_default else 1, str(p))

    return sorted(found, key=sort_key)


_WANTED_COLUMNS = ("id", "title", "category", "lock", "version", "sort_order", "content")


def _connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def list_slides(db: Path) -> list[SlideRow]:
    """Return all slides, tolerant of schema variations across sqlite files.

    Backups can predate migrations (missing ``category`` / ``sort_order`` …),
    so we select only the columns that exist and default the rest. A file with
    no ``slideapp_slide`` table yields an empty list rather than raising, so the
    TUI can show an explanatory message.
    """
    conn = _connect(db)
    try:
        cols = _table_columns(conn, "slideapp_slide")
        if "id" not in cols:
            return []
        has_categories = (
            "category_ref_id" in cols
            and _table_exists(conn, "slideapp_slidecategory")
        )
        select = [c for c in _WANTED_COLUMNS if c in cols]
        if has_categories:
            select = [
                (
                    f"s.{c}"
                    if c != "category"
                    else "COALESCE(sc.name, s.category, '') AS category"
                )
                for c in select
            ]
        order = "sort_order, id" if "sort_order" in cols else "id"
        if has_categories:
            order = f"s.{order.replace(', ', ', s.')}"
            rows = conn.execute(
                f"""
                SELECT {', '.join(select)}
                FROM slideapp_slide s
                LEFT JOIN slideapp_slidecategory sc ON sc.id = s.category_ref_id
                ORDER BY {order}
                """
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {', '.join(select)} FROM slideapp_slide ORDER BY {order}"
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    result = []
    for row in rows:
        d = dict(row)
        result.append(
            SlideRow(
                id=d["id"],
                title=d.get("title") or "",
                category=d.get("category") or "",
                lock=d.get("lock", 0) or 0,
                version=d.get("version", 0) or 0,
                sort_order=d.get("sort_order", 0) or 0,
                content=d.get("content") or "",
            )
        )
    return result


def list_categories(db: Path) -> list[CategoryRow]:
    """Return persisted categories, tolerant of old databases without the table."""
    conn = _connect(db)
    try:
        if not _table_exists(conn, "slideapp_slidecategory"):
            return []
        cols = _table_columns(conn, "slideapp_slidecategory")
        if "name" not in cols:
            return []
        position_expr = "position" if "position" in cols else "0"
        rows = conn.execute(
            f"""
            SELECT name, {position_expr} AS position
            FROM slideapp_slidecategory
            ORDER BY position, name
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [
        CategoryRow(name=(row["name"] or ""), position=row["position"] or 0)
        for row in rows
        if row["name"]
    ]


def unlock_slide(db: Path, slide_id: int) -> None:
    """Set ``lock = 0`` so ``/public/edit/<id>/`` can serve the slide."""
    conn = _connect(db)
    try:
        conn.execute("UPDATE slideapp_slide SET lock = 0 WHERE id = ?", (slide_id,))
        conn.commit()
    finally:
        conn.close()
