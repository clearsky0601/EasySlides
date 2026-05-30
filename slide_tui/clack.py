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

_ESCAPE_FINAL_KEYS = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
}

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


def _begin_repaint() -> None:
    sys.stdout.write("\x1b[?25l\x1b[H")
    sys.stdout.flush()


def _end_repaint() -> None:
    sys.stdout.write("\x1b[J")
    sys.stdout.flush()


def _show_cursor() -> None:
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


def _clear_current_line() -> None:
    sys.stdout.write("\r\x1b[2K")


def print_line(markup: str = "") -> None:
    for line in str(markup).splitlines() or [""]:
        _clear_current_line()
        console.print(line, no_wrap=True, overflow="crop")


def bar() -> None:
    print_line(f"[{GUTTER}]{S_BAR}[/]")


def intro(title: str) -> None:
    print_line(f"[{GUTTER}]{S_BAR_START}[/]  [{ACCENT} bold]{title}[/]")


def info(label: str, value: str = "") -> None:
    line = f"[{GREEN}]{S_INFO}[/]  {label}"
    if value:
        line += f"  [bold]{value}[/]"
    print_line(line)


def submit(message: str) -> None:
    for i, line in enumerate(str(message).splitlines() or [""]):
        prefix = f"[{GREEN}]{S_STEP_SUBMIT}[/]  " if i == 0 else f"[{GUTTER}]{S_BAR}[/]     "
        print_line(f"{prefix}{line}")


def warn(message: str) -> None:
    print_line(f"[{YELLOW}]{S_WARN}[/]  [{YELLOW}]{message}[/]")


def outro(message: str) -> None:
    bar()
    print_line(f"[{GUTTER}]{S_BAR_END}[/]  {message}")


# -- raw key input ---------------------------------------------------------
def read_key() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            return _read_escape_key(fd)
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            return "ctrl-c"
        if ch == "\x7f":
            return "backspace"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_escape_key(fd: int, timeout: float = 0.06) -> str:
    """Decode common terminal escape sequences for navigation keys."""
    seq = ""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and len(seq) < 8:
        remaining = max(0, deadline - time.monotonic())
        if not _select.select([fd], [], [], remaining)[0]:
            break
        seq += sys.stdin.read(1)
        key = _decode_escape_sequence(seq)
        if key != "esc":
            return key
    return "esc"


def _decode_escape_sequence(seq: str) -> str:
    if seq.startswith("[") and seq[-1:] in _ESCAPE_FINAL_KEYS:
        return _ESCAPE_FINAL_KEYS[seq[-1]]
    if seq.startswith("O") and seq[-1:] in _ESCAPE_FINAL_KEYS:
        return _ESCAPE_FINAL_KEYS[seq[-1]]
    return "esc"


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
    render_before_options: Callable[[], None] | None = None,
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

    clear()
    try:
        while True:
            _begin_repaint()
            render_header()
            bar()
            head = f"[{CYAN}]{S_STEP_ACTIVE}[/]  [bold]{title}[/]"
            if hint:
                head += f"   [{DIM}]{hint}[/]"
            print_line(head)
            bar()
            if render_before_options is not None:
                render_before_options()

            if not options:
                print_line(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]（空）[/]")
            else:
                win = _window_size(len(options))
                start = _window_start(idx, len(options), win)
                has_scroll = len(options) > win
                if has_scroll and start > 0:
                    print_line(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]↑ 还有 {start} 项[/]")
                elif has_scroll:
                    bar()
                for i in range(start, min(start + win, len(options))):
                    label = label_of(options[i])
                    if i == idx:
                        print_line(
                            f"[{GUTTER}]{S_BAR}[/]  [{GREEN}]{S_RADIO_ACTIVE}[/] {label}"
                        )
                    else:
                        print_line(
                            f"[{GUTTER}]{S_BAR}[/]  [{DIM}]{S_RADIO_INACTIVE}[/] "
                            f"[{DIM}]{label}[/]"
                        )
                rest = len(options) - (start + win)
                if has_scroll and rest > 0:
                    print_line(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]↓ 还有 {rest} 项[/]")
                elif has_scroll:
                    bar()

            print_line(f"[{GUTTER}]{S_BAR_END}[/]  [{DIM}]{footer}[/]")
            _end_repaint()

            key = read_key()
            if key in ("q", "esc", "ctrl-c"):
                return ("quit", None, idx)
            if key in ("up", "k") and options:
                idx = (idx - 1) % len(options)
            elif key in ("down", "j") and options:
                idx = (idx + 1) % len(options)
            elif key == "enter" and options:
                return ("select", options[idx], idx)
            elif key in extra_keys:
                return (extra_keys[key], options[idx] if options else None, idx)
    finally:
        _show_cursor()


def _window_size(n: int) -> int:
    # Keep the rendered frame shorter than the terminal. The slide previewer
    # has a multi-line header, category tabs, and optional scroll indicators;
    # overflowing the terminal would make the terminal scroll mid-repaint.
    avail = console.size.height - 14
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
        print_line(f"[{CYAN}]{next(frames)}[/]  {message}")
        bar()
        time.sleep(0.12)
    worker.join()
    return result.get("value")
