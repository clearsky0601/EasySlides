#!/usr/bin/env python3
"""Safe CRUD helper for the EazySlides `slideapp_slide` table.

Reads/writes slide content via files or stdin so Markdown with quotes,
newlines, and `:::` directives never needs shell escaping. The DB path
defaults to `db.sqlite3` found by walking up from the current directory.

Usage:
  slide_db.py list [--category NAME]
  slide_db.py get <id> [-o out.md]            # print content (or write to file)
  slide_db.py create --title T --category C --file content.md [--publish] [--sort N]
  slide_db.py update <id> --file content.md   # also: --title T --category C
  slide_db.py delete <id>
  slide_db.py publish <id>                     # set lock = 0 (public)
  slide_db.py categories
  slide_db.py render <id>                      # re-render via convert_and_cache (needs venv)

Notes:
  - --file - reads content from stdin.
  - Add --db PATH to point at a specific sqlite file.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def find_db(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            sys.exit(f"DB not found: {p}")
        return p
    cur = Path.cwd()
    for d in (cur, *cur.parents):
        cand = d / "db.sqlite3"
        if cand.exists():
            return cand
    sys.exit("Could not locate db.sqlite3 (use --db PATH)")


def read_content(file_arg: str) -> str:
    if file_arg == "-":
        return sys.stdin.read()
    return Path(file_arg).read_text(encoding="utf-8")


def connect(args) -> sqlite3.Connection:
    conn = sqlite3.connect(find_db(args.db))
    conn.row_factory = sqlite3.Row
    return conn


def cmd_list(args):
    conn = connect(args)
    sql = "SELECT id, title, category, lock, version, sort_order FROM slideapp_slide"
    params: list = []
    if args.category:
        sql += " WHERE category = ?"
        params.append(args.category)
    sql += " ORDER BY id"
    for r in conn.execute(sql, params):
        vis = "public" if r["lock"] == 0 else "locked"
        print(f"{r['id']:>4}  [{vis:<6}] v{r['version']}  ({r['category'] or '-'})  {r['title']}")
    conn.close()


def cmd_get(args):
    conn = connect(args)
    row = conn.execute(
        "SELECT content FROM slideapp_slide WHERE id = ?", (args.id,)
    ).fetchone()
    conn.close()
    if row is None:
        sys.exit(f"No slide with id {args.id}")
    if args.out:
        Path(args.out).write_text(row["content"], encoding="utf-8")
        print(f"Wrote slide {args.id} content to {args.out}")
    else:
        sys.stdout.write(row["content"])


def cmd_create(args):
    content = read_content(args.file)
    conn = connect(args)
    cur = conn.execute(
        "INSERT INTO slideapp_slide "
        "(title, content, created_at, updated_at, lock, version, category, sort_order, "
        "html_cache, content_hash) "
        "VALUES (?, ?, datetime('now'), datetime('now'), ?, 0, ?, ?, '', '')",
        (args.title, content, 0 if args.publish else 1, args.category, args.sort),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    print(f"Inserted slide id={new_id} (lock={'0/public' if args.publish else '1/locked'})")


def cmd_update(args):
    conn = connect(args)
    exists = conn.execute(
        "SELECT 1 FROM slideapp_slide WHERE id = ?", (args.id,)
    ).fetchone()
    if exists is None:
        conn.close()
        sys.exit(f"No slide with id {args.id}")
    sets = ["updated_at = datetime('now')"]
    params: list = []
    if args.file:
        sets.append("content = ?")
        params.append(read_content(args.file))
    if args.title is not None:
        sets.append("title = ?")
        params.append(args.title)
    if args.category is not None:
        sets.append("category = ?")
        params.append(args.category)
    params.append(args.id)
    conn.execute(f"UPDATE slideapp_slide SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    print(f"Updated slide id={args.id}")


def cmd_delete(args):
    conn = connect(args)
    cur = conn.execute("DELETE FROM slideapp_slide WHERE id = ?", (args.id,))
    conn.commit()
    n = cur.rowcount
    conn.close()
    print(f"Deleted {n} row(s) for id={args.id}")


def cmd_publish(args):
    conn = connect(args)
    cur = conn.execute("UPDATE slideapp_slide SET lock = 0 WHERE id = ?", (args.id,))
    conn.commit()
    n = cur.rowcount
    conn.close()
    print(f"Published (unlocked) {n} row(s) for id={args.id}")


def cmd_categories(args):
    conn = connect(args)
    for r in conn.execute(
        "SELECT id, name, position FROM slideapp_slidecategory ORDER BY position"
    ):
        print(f"{r['id']:>4}  pos={r['position']:<4} {r['name']}")
    conn.close()


def cmd_render(args):
    """Re-render through the real pipeline so html_cache refreshes."""
    import os
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eazy_slides.settings")
    django.setup()
    from slideapp.models import Slide  # noqa: E402
    from slideapp.html_converter import convert_and_cache  # noqa: E402

    s = Slide.objects.get(id=args.id)
    convert_and_cache(s, s.content)
    print(f"Re-rendered slide id={args.id} (hash={s.content_hash})")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", help="path to db.sqlite3 (default: search upward)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="list slides")
    s.add_argument("--category")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("get", help="print a slide's content")
    s.add_argument("id", type=int)
    s.add_argument("-o", "--out", help="write content to file instead of stdout")
    s.set_defaults(func=cmd_get)

    s = sub.add_parser("create", help="create a slide from a content file")
    s.add_argument("--title", required=True)
    s.add_argument("--category", default="")
    s.add_argument("--file", required=True, help="content file ('-' for stdin)")
    s.add_argument("--publish", action="store_true", help="set lock=0 (public)")
    s.add_argument("--sort", type=int, default=0)
    s.set_defaults(func=cmd_create)

    s = sub.add_parser("update", help="update a slide")
    s.add_argument("id", type=int)
    s.add_argument("--file", help="new content file ('-' for stdin)")
    s.add_argument("--title")
    s.add_argument("--category")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("delete", help="delete a slide")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("publish", help="unlock (make public)")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_publish)

    s = sub.add_parser("categories", help="list categories")
    s.set_defaults(func=cmd_categories)

    s = sub.add_parser("render", help="re-render via Django pipeline (run with .venv)")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_render)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
