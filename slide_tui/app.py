"""Clack-style slide previewer (the openclaw / @clack/prompts look).

Flow: an intro banner with the current database pinned on top, a select
prompt of slides (Enter opens the /public preview, auto-unlocking locked
ones), and a `d`-key sub-flow to switch databases (restarting daphne).
"""
from __future__ import annotations

import webbrowser

from rich.markup import escape

from slide_tui import clack, db
from slide_tui.db import REPO_ROOT, SlideRow
from slide_tui.server import DaphneServer

ALL_CATEGORIES = "__all__"
UNCATEGORIZED = ""


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


class SlidePreviewer:
    def __init__(self) -> None:
        self.server = DaphneServer(REPO_ROOT)
        self.dbs = db.discover_dbs()
        self.current_db = self.dbs[0] if self.dbs else None
        self.rows: list[SlideRow] = []
        self.categories: list[str] = [ALL_CATEGORIES]
        self._category_index = 0
        self._slide_indices: dict[str, int] = {}
        self.flash: str | None = None
        self._slide_index = 0

    # -- header (always shows the current DB on top) ----------------------
    def _render_header(self) -> None:
        clack.intro("EasySlides · 幻灯片预览器")
        clack.bar()
        if self.current_db is None:
            clack.warn("未找到任何 .sqlite3 数据库")
            return
        clack.info(
            "数据库",
            f"{db.display_name(self.current_db)}  ·  {self.server.status_line()}",
        )
        clack.print_line(
            f"[grey42]{clack.S_BAR}[/]        [grey54]{self.current_db}  ·  "
            f"{len(self.rows)} 张幻灯片[/]"
        )
        if self.server.warning:
            clack.print_line(f"[grey42]{clack.S_BAR}[/]")
            clack.warn(self.server.warning)
        if self.flash:
            clack.print_line(f"[grey42]{clack.S_BAR}[/]")
            clack.submit(self.flash)

    # -- data --------------------------------------------------------------
    def _reload(self) -> None:
        if self.current_db is not None:
            self.rows = db.list_slides(self.current_db)
            self._sync_categories()

    def _sync_categories(self) -> None:
        if self.current_db is None:
            self.categories = [ALL_CATEGORIES]
            self._category_index = 0
            return
        current = self._current_category()
        persisted = [c.name for c in db.list_categories(self.current_db)]
        from_rows = [row.category for row in self.rows if row.category]
        names = list(dict.fromkeys([*persisted, *from_rows]))
        self.categories = [ALL_CATEGORIES, *names]
        if any(not row.category for row in self.rows):
            self.categories.append(UNCATEGORIZED)
        if current not in self.categories:
            self._category_index = 0
        else:
            self._category_index = self.categories.index(current)
        self._slide_index = self._clamped_slide_index()

    def _current_category(self) -> str:
        if not self.categories:
            return ALL_CATEGORIES
        idx = max(0, min(self._category_index, len(self.categories) - 1))
        return self.categories[idx]

    def _category_label(self, category: str) -> str:
        if category == ALL_CATEGORIES:
            return "全部"
        if category == UNCATEGORIZED:
            return "未分类"
        return category

    def _category_count(self, category: str) -> int:
        if category == ALL_CATEGORIES:
            return len(self.rows)
        if category == UNCATEGORIZED:
            return sum(1 for row in self.rows if not row.category)
        return sum(1 for row in self.rows if row.category == category)

    def _visible_rows(self) -> list[SlideRow]:
        category = self._current_category()
        if category == ALL_CATEGORIES:
            return self.rows
        if category == UNCATEGORIZED:
            return [row for row in self.rows if not row.category]
        return [row for row in self.rows if row.category == category]

    def _clamped_slide_index(self) -> int:
        rows = self._visible_rows()
        if not rows:
            return 0
        saved = self._slide_indices.get(self._current_category(), self._slide_index)
        return max(0, min(saved, len(rows) - 1))

    def _move_category(self, delta: int) -> None:
        if len(self.categories) <= 1:
            return
        self._slide_indices[self._current_category()] = self._slide_index
        self._category_index = (self._category_index + delta) % len(self.categories)
        self._slide_index = self._clamped_slide_index()
        self.flash = None

    def _render_category_tabs(self) -> None:
        if len(self.categories) <= 1:
            return
        parts = []
        for i, category in enumerate(self.categories):
            label = escape(self._category_label(category))
            count = self._category_count(category)
            if i == self._category_index:
                parts.append(f"[reverse bold {clack.ACCENT}] {label} {count} [/]")
            else:
                parts.append(f"[grey54] {label} {count} [/]")
        clack.print_line(f"[grey42]{clack.S_BAR}[/]  " + "  ".join(parts))
        clack.bar()

    def _slide_label(self, row: SlideRow) -> str:
        mark = "[yellow]🔒[/]" if row.is_locked else "[green]🌐[/]"
        title = escape(_truncate(row.title or "(无标题)", 38))
        meta = f"[grey54]v{row.version}[/]"
        if row.category and self._current_category() == ALL_CATEGORIES:
            meta += f" [grey54]· {escape(row.category)}[/]"
        return f"[grey54]#{row.id:<4}[/] {mark}  {title}   {meta}"

    # -- server ------------------------------------------------------------
    def _start_server(self) -> None:
        if self.current_db is None:
            return
        clack.with_spinner(
            self._render_header,
            f"启动服务（{db.display_name(self.current_db)}）…",
            lambda: self.server.start(self.current_db),
        )

    # -- main loop ---------------------------------------------------------
    def run(self) -> None:
        if self.current_db is None:
            clack.clear()
            self._render_header()
            clack.outro("[red]请在仓库根目录运行[/]")
            return
        self._reload()
        self._start_server()
        try:
            while True:
                if not self._slide_step():
                    break
        finally:
            clack.with_spinner(
                self._render_header, "停止服务…", self.server.stop
            )
            clack.clear()
            clack.intro("EasySlides · 幻灯片预览器")
            clack.outro("[grey54]已退出，再见 👋[/]")

    def _slide_step(self) -> bool:
        visible_rows = self._visible_rows()
        self._slide_index = self._clamped_slide_index()
        action, value, self._slide_index = clack.select(
            self._render_header,
            title="选择幻灯片",
            options=visible_rows,
            label_of=self._slide_label,
            hint="h/l 分类 · j/k/↑↓ 移动 · ↵ 预览 · d 切库 · r 刷新 · q 退出",
            footer="↵ 在浏览器打开 /public 预览",
            extra_keys={
                "d": "switch",
                "r": "refresh",
                "h": "prev_category",
                "l": "next_category",
            },
            start_index=self._slide_index,
            render_before_options=self._render_category_tabs,
        )
        self._slide_indices[self._current_category()] = self._slide_index
        if action == "quit":
            return False
        if action == "prev_category":
            self._move_category(-1)
            return True
        if action == "next_category":
            self._move_category(1)
            return True
        if action == "refresh":
            self._reload()
            self.flash = "已刷新列表"
            return True
        if action == "switch":
            self._switch_db_step()
            return True
        if action == "select" and value is not None:
            self._open_preview(value)
        return True

    def _open_preview(self, row: SlideRow) -> None:
        if self.current_db is None:
            return
        if row.is_locked:
            db.unlock_slide(self.current_db, row.id)
            self._reload()
            note = "（已自动解锁）"
        else:
            note = ""
        url = f"http://localhost:{self.server.port}/public/edit/{row.id}/"
        webbrowser.open(url)
        title = _truncate(row.title or "(无标题)", 30)
        if not self.server.port_in_use():
            self.flash = f"[yellow]服务未运行，预览可能打不开[/] · #{row.id}"
        else:
            self.flash = f"已打开预览 #{row.id} {title}{note}\n[grey54]   {url}[/]"

    def _switch_db_step(self) -> None:
        if len(self.dbs) <= 1:
            self.flash = "只发现一个数据库，无可切换项"
            return
        start = self.dbs.index(self.current_db) if self.current_db in self.dbs else 0
        action, value, _ = clack.select(
            self._render_header,
            title="切换数据库",
            options=self.dbs,
            label_of=self._db_label,
            hint="↑↓ 移动 · ↵ 确认 · q 返回",
            footer="↵ 确认切换（将重启后端服务）",
            start_index=start,
        )
        if action != "select" or value is None or value == self.current_db:
            return
        self.current_db = value
        self._category_index = 0
        self._slide_indices.clear()
        self._slide_index = 0
        self._reload()
        ok_msg = clack.with_spinner(
            self._render_header,
            f"以 {db.display_name(value)} 重启服务…",
            lambda: self.server.switch(value),
        )
        ok, msg = ok_msg if ok_msg else (False, "切库失败")
        self.flash = msg if ok else f"[yellow]{msg}[/]"

    def _db_label(self, path) -> str:
        try:
            size = path.stat().st_size
            size_str = f"{size / 1024 / 1024:.1f} MB" if size >= 1024 * 1024 else f"{size / 1024:.0f} KB"
        except OSError:
            size_str = "?"
        count = len(db.list_slides(path))
        marker = "[green](当前)[/]" if self.current_db and path.resolve() == self.current_db.resolve() else ""
        name = escape(_truncate(db.display_name(path), 24))
        return f"{name:<24} [grey54]{size_str:>8} · {count} 张[/] {marker}"


def main() -> None:
    try:
        SlidePreviewer().run()
    except KeyboardInterrupt:
        clack.clear()
        clack.outro("[grey54]已中断[/]")


if __name__ == "__main__":
    main()
