"""Clack-style inline TUI primitives (the @clack/prompts / openclaw look).

A gray left-rail of ``│`` connects steps; round symbols mark step state;
``●/○`` render radio options. Rendered with rich for color; raw-mode key
reading drives an interactive, windowed select.
"""
from __future__ import annotations

import itertools
import select as _select
import sys
import termios
import threading
import time
import tty
from typing import Callable, Sequence

from rich.console import Console

console = Console(highlight=False)

# -- clack symbol vocabulary (verbatim from @clack/prompts) ----------------
S_BAR = "│"
S_BAR_START = "┌"
S_BAR_END = "└"
S_STEP_ACTIVE = "◆"
S_STEP_SUBMIT = "◇"
S_STEP_CANCEL = "■"
S_WARN = "▲"
S_RADIO_ACTIVE = "●"
S_RADIO_INACTIVE = "○"
S_INFO = "●"
SPINNER_FRAMES = ["◒", "◐", "◓", "◑"]

# -- palette ---------------------------------------------------------------
GUTTER = "grey42"
ACCENT = "#e0875a"      # warm brand accent for the title
CYAN = "cyan"
GREEN = "green"
YELLOW = "yellow"
RED = "red"
DIM = "grey54"


def clear() -> None:
    sys.stdout.write("\x1b[2J\x1b[3J\x1b[H")
    sys.stdout.flush()


def bar() -> None:
    console.print(f"[{GUTTER}]{S_BAR}[/]")


def intro(title: str) -> None:
    console.print(f"[{GUTTER}]{S_BAR_START}[/]  [{ACCENT} bold]{title}[/]")


def info(label: str, value: str = "") -> None:
    line = f"[{GREEN}]{S_INFO}[/]  {label}"
    if value:
        line += f"  [bold]{value}[/]"
    console.print(line)


def submit(message: str) -> None:
    console.print(f"[{GREEN}]{S_STEP_SUBMIT}[/]  {message}")


def warn(message: str) -> None:
    console.print(f"[{YELLOW}]{S_WARN}[/]  [{YELLOW}]{message}[/]")


def outro(message: str) -> None:
    bar()
    console.print(f"[{GUTTER}]{S_BAR_END}[/]  {message}")


# -- raw key input ---------------------------------------------------------
def read_key() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            if _select.select([fd], [], [], 0.06)[0]:
                seq = sys.stdin.read(2)
                return {
                    "[A": "up", "[B": "down", "[C": "right", "[D": "left",
                }.get(seq, "esc")
            return "esc"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            return "ctrl-c"
        if ch == "\x7f":
            return "backspace"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# -- interactive windowed select -------------------------------------------
def select(
    render_header: Callable[[], None],
    *,
    title: str,
    options: Sequence,
    label_of: Callable[[object], str],
    hint: str = "",
    footer: str = "",
    extra_keys: dict[str, str] | None = None,
    start_index: int = 0,
) -> tuple[str, object, int]:
    """Render a clack select prompt and return ``(action, value, index)``.

    ``action`` is ``"select"`` for Enter, ``"quit"`` for q/esc/ctrl-c, or any
    value mapped in ``extra_keys`` (e.g. ``{"d": "switch"}``).
    """
    extra_keys = extra_keys or {}
    if not options:
        idx = 0
    else:
        idx = max(0, min(start_index, len(options) - 1))

    while True:
        clear()
        render_header()
        bar()
        head = f"[{CYAN}]{S_STEP_ACTIVE}[/]  [bold]{title}[/]"
        if hint:
            head += f"   [{DIM}]{hint}[/]"
        console.print(head)
        bar()

        if not options:
            console.print(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]（空）[/]")
        else:
            win = _window_size(len(options))
            start = _window_start(idx, len(options), win)
            if start > 0:
                console.print(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]↑ 还有 {start} 项[/]")
            for i in range(start, min(start + win, len(options))):
                label = label_of(options[i])
                if i == idx:
                    console.print(
                        f"[{GUTTER}]{S_BAR}[/]  [{GREEN}]{S_RADIO_ACTIVE}[/] {label}"
                    )
                else:
                    console.print(
                        f"[{GUTTER}]{S_BAR}[/]  [{DIM}]{S_RADIO_INACTIVE}[/] "
                        f"[{DIM}]{label}[/]"
                    )
            rest = len(options) - (start + win)
            if rest > 0:
                console.print(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]↓ 还有 {rest} 项[/]")

        console.print(f"[{GUTTER}]{S_BAR_END}[/]  [{DIM}]{footer}[/]")

        key = read_key()
        if key in ("q", "esc", "ctrl-c"):
            return ("quit", None, idx)
        if key == "up" and options:
            idx = (idx - 1) % len(options)
        elif key == "down" and options:
            idx = (idx + 1) % len(options)
        elif key == "enter" and options:
            return ("select", options[idx], idx)
        elif key in extra_keys:
            return (extra_keys[key], options[idx] if options else None, idx)


def _window_size(n: int) -> int:
    avail = console.size.height - 9  # header + step + footer chrome
    return max(4, min(n, avail))


def _window_start(idx: int, n: int, win: int) -> int:
    start = idx - win // 2
    return max(0, min(start, max(0, n - win)))


# -- spinner around a blocking call ----------------------------------------
def with_spinner(render_header: Callable[[], None], message: str, fn: Callable):
    result: dict = {}

    def run():
        result["value"] = fn()

    worker = threading.Thread(target=run)
    worker.start()
    frames = itertools.cycle(SPINNER_FRAMES)
    while worker.is_alive():
        clear()
        render_header()
        bar()
        console.print(f"[{CYAN}]{next(frames)}[/]  {message}")
        bar()
        time.sleep(0.12)
    worker.join()
    return result.get("value")
