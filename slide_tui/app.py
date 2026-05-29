"""Clack-style slide previewer (the openclaw / @clack/prompts look).

Flow: an intro banner with the current database pinned on top, a select
prompt of slides (Enter opens the /public preview, auto-unlocking locked
ones), and a `d`-key sub-flow to switch databases (restarting daphne).
"""
from __future__ import annotations

import webbrowser

from slide_tui import clack, db
from slide_tui.clack import console
from slide_tui.db import REPO_ROOT, SlideRow
from slide_tui.server import DaphneServer


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


class SlidePreviewer:
    def __init__(self) -> None:
        self.server = DaphneServer(REPO_ROOT)
        self.dbs = db.discover_dbs()
        self.current_db = self.dbs[0] if self.dbs else None
        self.rows: list[SlideRow] = []
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
        console.print(
            f"[grey42]{clack.S_BAR}[/]        [grey54]{self.current_db}  ·  "
            f"{len(self.rows)} 张幻灯片[/]"
        )
        if self.server.warning:
            console.print(f"[grey42]{clack.S_BAR}[/]")
            clack.warn(self.server.warning)
        if self.flash:
            console.print(f"[grey42]{clack.S_BAR}[/]")
            clack.submit(self.flash)

    # -- data --------------------------------------------------------------
    def _reload(self) -> None:
        if self.current_db is not None:
            self.rows = db.list_slides(self.current_db)

    def _slide_label(self, row: SlideRow) -> str:
        mark = "[yellow]🔒[/]" if row.is_locked else "[green]🌐[/]"
        title = _truncate(row.title or "(无标题)", 38)
        meta = f"[grey54]v{row.version}[/]"
        if row.category:
            meta += f" [grey54]· {row.category}[/]"
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
        action, value, self._slide_index = clack.select(
            self._render_header,
            title="选择幻灯片",
            options=self.rows,
            label_of=self._slide_label,
            hint="↑↓ 移动 · ↵ 预览 · d 切库 · r 刷新 · q 退出",
            footer="↵ 在浏览器打开 /public 预览",
            extra_keys={"d": "switch", "r": "refresh"},
            start_index=self._slide_index,
        )
        if action == "quit":
            return False
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
        name = _truncate(db.display_name(path), 24)
        return f"{name:<24} [grey54]{size_str:>8} · {count} 张[/] {marker}"


def main() -> None:
    try:
        SlidePreviewer().run()
    except KeyboardInterrupt:
        clack.clear()
        clack.outro("[grey54]已中断[/]")


if __name__ == "__main__":
    main()
