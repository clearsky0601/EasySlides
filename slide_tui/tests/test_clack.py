import unittest
from unittest import mock

from slide_tui import clack


class EscapeSequenceTests(unittest.TestCase):
    def test_xterm_arrow_keys(self):
        self.assertEqual(clack._decode_escape_sequence("[A"), "up")
        self.assertEqual(clack._decode_escape_sequence("[B"), "down")

    def test_application_cursor_arrow_keys(self):
        self.assertEqual(clack._decode_escape_sequence("OA"), "up")
        self.assertEqual(clack._decode_escape_sequence("OB"), "down")

    def test_modified_arrow_keys(self):
        self.assertEqual(clack._decode_escape_sequence("[1;2A"), "up")
        self.assertEqual(clack._decode_escape_sequence("[1;2B"), "down")


class SelectNavigationTests(unittest.TestCase):
    def test_jk_move_selection(self):
        keys = iter(["j", "j", "k", "enter"])

        with (
            mock.patch.object(clack, "clear"),
            mock.patch.object(clack, "_begin_repaint"),
            mock.patch.object(clack, "_end_repaint"),
            mock.patch.object(clack, "_show_cursor"),
            mock.patch.object(clack, "_clear_current_line"),
            mock.patch.object(clack.console, "print"),
            mock.patch.object(clack, "read_key", side_effect=lambda: next(keys)),
        ):
            action, value, idx = clack.select(
                lambda: None,
                title="Pick",
                options=["first", "second", "third"],
                label_of=str,
            )

        self.assertEqual(action, "select")
        self.assertEqual(value, "second")
        self.assertEqual(idx, 1)

    def test_arrow_keys_still_move_selection(self):
        keys = iter(["down", "up", "enter"])

        with (
            mock.patch.object(clack, "clear"),
            mock.patch.object(clack, "_begin_repaint"),
            mock.patch.object(clack, "_end_repaint"),
            mock.patch.object(clack, "_show_cursor"),
            mock.patch.object(clack, "_clear_current_line"),
            mock.patch.object(clack.console, "print"),
            mock.patch.object(clack, "read_key", side_effect=lambda: next(keys)),
        ):
            action, value, idx = clack.select(
                lambda: None,
                title="Pick",
                options=["first", "second"],
                label_of=str,
            )

        self.assertEqual(action, "select")
        self.assertEqual(value, "first")
        self.assertEqual(idx, 0)

    def test_extra_keys_return_action(self):
        keys = iter(["l"])

        with (
            mock.patch.object(clack, "clear"),
            mock.patch.object(clack, "_begin_repaint"),
            mock.patch.object(clack, "_end_repaint"),
            mock.patch.object(clack, "_show_cursor"),
            mock.patch.object(clack, "_clear_current_line"),
            mock.patch.object(clack.console, "print"),
            mock.patch.object(clack, "read_key", side_effect=lambda: next(keys)),
        ):
            action, value, idx = clack.select(
                lambda: None,
                title="Pick",
                options=["first", "second"],
                label_of=str,
                extra_keys={"l": "next_category"},
            )

        self.assertEqual(action, "next_category")
        self.assertEqual(value, "first")
        self.assertEqual(idx, 0)

    def test_render_before_options_hook_runs(self):
        keys = iter(["enter"])
        hook = mock.Mock()

        with (
            mock.patch.object(clack, "clear"),
            mock.patch.object(clack, "_begin_repaint"),
            mock.patch.object(clack, "_end_repaint"),
            mock.patch.object(clack, "_show_cursor"),
            mock.patch.object(clack, "_clear_current_line"),
            mock.patch.object(clack.console, "print"),
            mock.patch.object(clack, "read_key", side_effect=lambda: next(keys)),
        ):
            clack.select(
                lambda: None,
                title="Pick",
                options=["first"],
                label_of=str,
                render_before_options=hook,
            )

        hook.assert_called_once()


class SelectFilterTests(unittest.TestCase):
    def _run(self, keys, options, **kw):
        it = iter(keys)
        with (
            mock.patch.object(clack, "clear"),
            mock.patch.object(clack, "_begin_repaint"),
            mock.patch.object(clack, "_end_repaint"),
            mock.patch.object(clack, "_show_cursor"),
            mock.patch.object(clack, "_clear_current_line"),
            mock.patch.object(clack.console, "print"),
            mock.patch.object(clack, "read_key", side_effect=lambda: next(it)),
        ):
            return clack.select(
                lambda: None,
                title="Pick",
                options=options,
                label_of=str,
                filter_of=lambda o: o,
                **kw,
            )

    def test_slash_filters_then_enter_returns_original_index(self):
        action, value, idx = self._run(
            ["/", "b", "a", "n", "enter"],
            ["apple", "cherry", "banana"],
        )
        self.assertEqual(action, "select")
        self.assertEqual(value, "banana")
        self.assertEqual(idx, 2)

    def test_backspace_widens_filter(self):
        action, value, idx = self._run(
            ["/", "z", "backspace", "enter"],
            ["apple", "banana"],
        )
        self.assertEqual(action, "select")
        self.assertEqual(value, "apple")

    def test_esc_exits_filter_without_quitting(self):
        action, value, idx = self._run(
            ["/", "b", "esc", "enter"],
            ["apple", "banana"],
        )
        self.assertEqual(action, "select")
        self.assertEqual(value, "apple")

    def test_slash_inert_without_filter_of(self):
        it = iter(["/", "enter"])
        with (
            mock.patch.object(clack, "clear"),
            mock.patch.object(clack, "_begin_repaint"),
            mock.patch.object(clack, "_end_repaint"),
            mock.patch.object(clack, "_show_cursor"),
            mock.patch.object(clack, "_clear_current_line"),
            mock.patch.object(clack.console, "print"),
            mock.patch.object(clack, "read_key", side_effect=lambda: next(it)),
        ):
            action, value, idx = clack.select(
                lambda: None, title="Pick",
                options=["apple", "banana"], label_of=str,
            )
        self.assertEqual((action, value), ("select", "apple"))


if __name__ == "__main__":
    unittest.main()
