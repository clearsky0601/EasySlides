"""Unit tests for the ``::: columns`` directive added to md_util.

These tests target ``md_to_html`` directly — no Django HTTP layer needed —
because the directive lives entirely inside the Markdown rendering pipeline.
"""

import re

from django.test import SimpleTestCase

from slideapp.src.util.md_util import (
    _protect_columns,
    _restore_columns,
    md_to_html,
)


def _grid_template(html: str) -> str:
    m = re.search(r'grid-template-columns:\s*([^"]+?);', html)
    return m.group(1).strip() if m else ""


def _column_count(html: str) -> int:
    return len(re.findall(r'class="md-column"', html))


class ColumnsBasicTests(SimpleTestCase):
    def test_two_column_explicit_ratio(self):
        md = (
            "::: columns 40/60\n"
            "::: column\n"
            "left\n"
            ":::\n"
            "::: column\n"
            "right\n"
            ":::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn('class="md-columns"', html)
        self.assertEqual(_column_count(html), 2)
        self.assertEqual(_grid_template(html), "40fr 60fr")
        self.assertIn("left", html)
        self.assertIn("right", html)

    def test_default_ratio_equal_split(self):
        md = (
            "::: columns\n"
            "::: column\na\n:::\n"
            "::: column\nb\n:::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertEqual(_grid_template(html), "1fr 1fr")

    def test_three_columns(self):
        md = (
            "::: columns 30/30/40\n"
            "::: column\na\n:::\n"
            "::: column\nb\n:::\n"
            "::: column\nc\n:::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertEqual(_column_count(html), 3)
        self.assertEqual(_grid_template(html), "30fr 30fr 40fr")

    def test_inner_markdown_is_rendered(self):
        md = (
            "::: columns 1/1\n"
            "::: column\n"
            "- item 1\n"
            "- item 2\n"
            ":::\n"
            "::: column\n"
            "**bold**\n"
            ":::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn("<ul>", html)
        self.assertIn("<li>item 1</li>", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_image_in_column(self):
        md = (
            "::: columns 1/1\n"
            "::: column\nleft\n:::\n"
            "::: column\n"
            "![alt](http://example.com/x.png)\n"
            ":::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn('src="http://example.com/x.png"', html)


class ColumnsIsolationTests(SimpleTestCase):
    """Tokens inside code fences or math must NOT be parsed as directives."""

    def test_columns_inside_fenced_code_block_is_literal(self):
        md = (
            "```text\n"
            "::: columns 40/60\n"
            "::: column\n"
            "should stay literal\n"
            ":::\n"
            ":::\n"
            "```\n"
        )
        html = md_to_html(md)
        self.assertNotIn('class="md-columns"', html)
        self.assertIn("::: columns 40/60", html)

    def test_columns_inside_tilde_fence_is_literal(self):
        md = (
            "~~~\n"
            "::: columns\n"
            "::: column\nx\n:::\n"
            ":::\n"
            "~~~\n"
        )
        html = md_to_html(md)
        self.assertNotIn('class="md-columns"', html)

    def test_directive_close_inside_column_code_block(self):
        # the ::: inside the inner code block must NOT close the column
        md = (
            "::: columns 1/1\n"
            "::: column\n"
            "```text\n"
            ":::\n"
            "```\n"
            ":::\n"
            "::: column\nB\n:::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertEqual(_column_count(html), 2)

    def test_dollar_math_with_colon_token_survives(self):
        md = (
            "Inline math $a:::b$ should be preserved.\n"
            "\n"
            "::: columns 1/1\n"
            "::: column\n$x^2$\n:::\n"
            "::: column\nright\n:::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn("$a:::b$", html)
        self.assertIn("$x^2$", html)
        self.assertEqual(_column_count(html), 2)


class ColumnsDegradationTests(SimpleTestCase):
    """Malformed input must not raise; it should fall back to raw markdown."""

    def test_unclosed_columns_block_does_not_raise(self):
        md = (
            "::: columns 40/60\n"
            "::: column\n"
            "orphan\n"
            ":::\n"
            # no closing ::: for the columns wrapper
        )
        html = md_to_html(md)
        # No columns div should appear — the literal text is degraded
        self.assertNotIn('class="md-columns"', html)
        self.assertIn("orphan", html)

    def test_empty_columns_block_degrades(self):
        md = (
            "::: columns\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertNotIn('class="md-columns"', html)

    def test_text_outside_block_is_preserved(self):
        md = (
            "before\n"
            "\n"
            "::: columns 1/1\n"
            "::: column\nleft\n:::\n"
            "::: column\nright\n:::\n"
            ":::\n"
            "\n"
            "after\n"
        )
        html = md_to_html(md)
        self.assertIn("before", html)
        self.assertIn("after", html)
        self.assertIn('class="md-columns"', html)


class ColumnsPlaceholderTests(SimpleTestCase):
    """Internal protect/restore round-trip."""

    def test_protect_and_restore_round_trip(self):
        md = (
            "::: columns 1/2\n"
            "::: column\nA\n:::\n"
            "::: column\nB\n:::\n"
            ":::\n"
        )
        safe, placeholders = _protect_columns(md)
        self.assertEqual(len(placeholders), 1)
        # placeholder must be a single self-contained div
        self.assertIn("data-cols-placeholder=", safe)
        self.assertNotIn(":::", safe)
        # restore puts the actual columns HTML back
        restored = _restore_columns(safe, placeholders)
        self.assertIn('class="md-columns"', restored)
        self.assertIn('class="md-column"', restored)
