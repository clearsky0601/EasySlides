import socket
import unittest
from pathlib import Path
from unittest import mock

from slide_tui.server import DaphneServer


class CommandConstructionTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path("/tmp/fake-repo")
        self.srv = DaphneServer(self.repo, port=10099)

    def test_command_uses_python_m_daphne(self):
        cmd = self.srv._command()
        # Must go through `python -m daphne`, never the broken console script.
        self.assertIn("-m", cmd)
        self.assertIn("daphne", cmd)
        self.assertNotIn("bin/daphne", " ".join(cmd))
        self.assertIn("easy_slides.asgi:application", cmd)
        self.assertIn("10099", cmd)

    def test_env_sets_resolved_slides_db(self):
        env = self.srv._env(Path("archive/db.sqlite3"))
        self.assertTrue(env["SLIDES_DB"].endswith("archive/db.sqlite3"))
        self.assertTrue(Path(env["SLIDES_DB"]).is_absolute())


class PortDetectionTests(unittest.TestCase):
    def test_port_in_use_true_when_listening(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as lst:
            lst.bind(("127.0.0.1", 0))
            lst.listen(1)
            port = lst.getsockname()[1]
            srv = DaphneServer(Path("/tmp"), port=port)
            self.assertTrue(srv.port_in_use())

    def test_port_in_use_false_when_free(self):
        # Bind to grab a free port, then release it before checking.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as lst:
            lst.bind(("127.0.0.1", 0))
            port = lst.getsockname()[1]
        srv = DaphneServer(Path("/tmp"), port=port)
        self.assertFalse(srv.port_in_use())


class SwitchGuardTests(unittest.TestCase):
    def test_switch_refuses_when_external_server_present(self):
        srv = DaphneServer(Path("/tmp"), port=10099)
        with mock.patch.object(srv, "port_in_use", return_value=True):
            ok, msg = srv.switch(Path("db.sqlite3"))
        self.assertFalse(ok)
        self.assertIn("外部服务", msg)


if __name__ == "__main__":
    unittest.main()
