"""Manage a daphne subprocess so DB switches actually take effect.

To serve a different sqlite file Django must be (re)started with
``SLIDES_DB`` pointing at it. This wraps that lifecycle.

NOTE: we invoke ``<venv>/bin/python -m daphne`` rather than the
``<venv>/bin/daphne`` console script — the latter's shebang points at an old,
no-longer-existing interpreter path and would fail with "bad interpreter".
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from slide_tui.db import display_name

DEFAULT_PORT = 10001
ASGI_APP = "easy_slides.asgi:application"
STARTUP_TIMEOUT = 12.0  # seconds to wait for the port to come up


class DaphneServer:
    def __init__(self, repo_root: Path, port: int = DEFAULT_PORT) -> None:
        self.repo_root = repo_root
        self.port = port
        self.current_db: Path | None = None
        self._proc: subprocess.Popen | None = None
        self._owned = False  # True only when *we* spawned the running server
        self.warning: str | None = None

    # -- introspection -----------------------------------------------------
    def port_in_use(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.4)
            return sock.connect_ex(("127.0.0.1", self.port)) == 0

    @property
    def managed(self) -> bool:
        return self._owned and self._proc is not None and self._proc.poll() is None

    def status_line(self) -> str:
        if self.managed:
            name = display_name(self.current_db) if self.current_db else "?"
            return f"运行中(托管) · DB={name}"
        if self.port_in_use():
            return f"外部服务 :{self.port}(未托管)"
        return "已停止"

    # -- command construction (kept pure for testing) ----------------------
    def _python(self) -> str:
        venv_py = self.repo_root / ".venv" / "bin" / "python"
        return str(venv_py) if venv_py.exists() else sys.executable

    def _command(self) -> list[str]:
        return [
            self._python(), "-m", "daphne",
            "-b", "127.0.0.1", "-p", str(self.port),
            ASGI_APP,
        ]

    def _env(self, db: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["SLIDES_DB"] = str(Path(db).resolve())
        return env

    # -- lifecycle ---------------------------------------------------------
    def start(self, db: Path) -> bool:
        """Start a managed server for ``db``. Returns True if we own it."""
        if self.port_in_use():
            self._owned = False
            self.warning = f"端口 :{self.port} 已被外部进程占用，无法托管/切库"
            return False
        self.warning = None
        self._proc = subprocess.Popen(
            self._command(),
            cwd=str(self.repo_root),
            env=self._env(db),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._owned = True
        self.current_db = Path(db)
        if not self._wait_until_up():
            self.warning = "daphne 启动超时（检查端口 / 依赖）"
        return True

    def _wait_until_up(self) -> bool:
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                return False  # process died
            if self.port_in_use():
                return True
            time.sleep(0.2)
        return False

    def switch(self, db: Path) -> tuple[bool, str]:
        """Restart the managed server pointing at ``db``."""
        if not self._owned:
            if self.port_in_use():
                return False, f"外部服务占用 :{self.port}，无法切库"
        self.stop()
        ok = self.start(db)
        if not ok:
            return False, self.warning or "切库失败"
        if self.warning:
            return False, self.warning
        return True, f"已切换到 {display_name(db)}"

    def stop(self) -> None:
        if self._proc is not None and self._owned:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._proc = None
        self._owned = False
