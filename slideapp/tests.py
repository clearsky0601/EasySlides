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
        self.assertIn("data-md-directive=", safe)
        self.assertNotIn(":::", safe)
        # restore puts the actual columns HTML back
        restored = _restore_columns(safe, placeholders)
        self.assertIn('class="md-columns"', restored)
        self.assertIn('class="md-column"', restored)


class AdmonitionTests(SimpleTestCase):
    def test_each_kind_has_default_title_and_icon(self):
        cases = [
            ("note", "📝", "提示"),
            ("tip", "💡", "技巧"),
            ("warning", "⚠️", "警告"),
            ("danger", "🚫", "危险"),
            ("success", "✅", "成功"),
        ]
        for kind, icon, title in cases:
            md = f"::: {kind}\nbody\n:::\n"
            html = md_to_html(md)
            self.assertIn(f"admonition-{kind}", html, kind)
            self.assertIn(icon, html, kind)
            self.assertIn(title, html, kind)
            self.assertIn("body", html, kind)

    def test_custom_title_overrides_default(self):
        md = "::: warning 操作不可逆\n请三思\n:::\n"
        html = md_to_html(md)
        self.assertIn("操作不可逆", html)
        self.assertNotIn("警告", html)

    def test_admonition_body_renders_markdown(self):
        md = "::: tip\n- one\n- two\n\n**bold** text\n:::\n"
        html = md_to_html(md)
        self.assertIn("<ul>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_unknown_directive_degrades(self):
        md = "::: noexist\nbody\n:::\n"
        html = md_to_html(md)
        # the literal ::: text should pass through to the rendered HTML
        self.assertIn(":::", html)
        self.assertNotIn("admonition-", html)


class NotesDirectiveTests(SimpleTestCase):
    def test_renders_reveal_notes_aside(self):
        md = "::: notes\n讲到这里提醒自己\n:::\n"
        html = md_to_html(md)
        self.assertIn('<aside class="notes">', html)
        self.assertIn("讲到这里提醒自己", html)

    def test_inner_markdown_rendered(self):
        md = "::: notes\n- a\n- b\n:::\n"
        html = md_to_html(md)
        self.assertIn("<ul>", html)
        self.assertIn("<li>a</li>", html)


class IncrementalDirectiveTests(SimpleTestCase):
    def test_each_li_gets_fragment_class(self):
        md = "::: incremental\n- 一\n- 二\n- 三\n:::\n"
        html = md_to_html(md)
        self.assertEqual(html.count('class="fragment"'), 3)
        self.assertIn('data-fragment-index="1"', html)
        self.assertIn('data-fragment-index="2"', html)
        self.assertIn('data-fragment-index="3"', html)

    def test_non_list_body_does_not_raise(self):
        md = "::: incremental\nnot a list\n:::\n"
        html = md_to_html(md)
        self.assertIn("not a list", html)
        self.assertNotIn('class="fragment"', html)

    def test_ordered_list_supported(self):
        md = "::: incremental\n1. step one\n2. step two\n:::\n"
        html = md_to_html(md)
        self.assertEqual(html.count('class="fragment"'), 2)


class TimelineDirectiveTests(SimpleTestCase):
    def test_basic_three_items(self):
        md = (
            "::: timeline\n"
            "- 2023.06: 立项\n"
            "- 2024.01: MVP\n"
            "- 2025.03: 大改版\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn('class="md-timeline"', html)
        self.assertEqual(html.count("timeline-date"), 3)
        self.assertIn("2023.06", html)
        self.assertIn("立项", html)

    def test_chinese_full_width_colon_accepted(self):
        md = "::: timeline\n- 2024：里程碑\n:::\n"
        html = md_to_html(md)
        self.assertIn("2024", html)
        self.assertIn("里程碑", html)

    def test_event_can_contain_markdown(self):
        md = "::: timeline\n- 2024: **重大** [发布](https://example.com)\n:::\n"
        html = md_to_html(md)
        self.assertIn("<strong>重大</strong>", html)
        self.assertIn("href=\"https://example.com\"", html)
        # URL colon must not be picked as the separator
        self.assertIn("2024", html)
        self.assertNotIn(">https</span>", html)

    def test_time_of_day_date_keeps_internal_colon(self):
        # regression: `14:30: event` must parse as date=14:30 / event=event
        md = "::: timeline\n- 14:30: 下午活动\n:::\n"
        html = md_to_html(md)
        self.assertIn(">14:30</span>", html)
        self.assertIn(">下午活动</span>", html)

    def test_event_starting_with_word_colon_value_is_not_eaten(self):
        # regression: the markdown ``meta`` extension was silently swallowing
        # any recursive call whose body started with ``Key: Value``.
        md = "::: timeline\n- 14:30: 下午活动\n:::\n"
        html = md_to_html(md)
        # event must actually be rendered, not empty
        self.assertIn(">下午活动</span>", html)


class NestedDirectiveTests(SimpleTestCase):
    def test_admonition_nested_in_admonition(self):
        # regression: dict-iteration order in _restore_directives lost the
        # inner placeholder after the outer one had been substituted.
        md = (
            "::: tip 外层\n"
            "外层文字\n\n"
            "::: warning 内层\n"
            "内层文字\n"
            ":::\n\n"
            "回到外层\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn("admonition-tip", html)
        self.assertIn("admonition-warning", html)
        # outer wraps inner
        self.assertLess(html.find("admonition-tip"), html.find("admonition-warning"))
        # no leftover placeholder div
        self.assertNotIn("data-md-directive=", html)

    def test_columns_nested_in_admonition(self):
        md = (
            "::: tip\n"
            "::: columns 1/1\n"
            "::: column\nA\n:::\n"
            "::: column\nB\n:::\n"
            ":::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn("admonition-tip", html)
        self.assertIn("md-columns", html)
        self.assertNotIn("data-md-directive=", html)


class TierBExtensionTests(SimpleTestCase):
    def test_footnote(self):
        md = "结论需要引用[^1]。\n\n[^1]: 出处\n"
        html = md_to_html(md)
        self.assertIn("footnote", html)
        self.assertIn("出处", html)

    def test_def_list(self):
        md = "RAG\n:   Retrieval-Augmented Generation\n"
        html = md_to_html(md)
        self.assertIn("<dl>", html)
        self.assertIn("<dt>RAG</dt>", html)


class TierCExtensionTests(SimpleTestCase):
    def test_mark(self):
        html = md_to_html("==高亮==文字")
        self.assertIn("<mark>高亮</mark>", html)

    def test_subscript(self):
        html = md_to_html("H~2~O")
        self.assertIn("<sub>2</sub>", html)

    def test_superscript(self):
        html = md_to_html("E=mc^2^")
        self.assertIn("<sup>2</sup>", html)

    def test_tasklist(self):
        md = "- [x] done\n- [ ] todo\n"
        html = md_to_html(md)
        self.assertIn("task-list-item", html)

    def test_emoji_renders_as_unicode(self):
        html = md_to_html(":rocket: launch")
        self.assertIn("🚀", html)
        # ensure we did NOT fall back to the CDN image
        self.assertNotIn("cdnjs.cloudflare.com", html)


class DirectiveIsolationTests(SimpleTestCase):
    """New directives must not fire inside code fences."""

    def test_admonition_in_code_fence_is_literal(self):
        md = "```text\n::: tip\nhello\n:::\n```\n"
        html = md_to_html(md)
        self.assertNotIn("admonition-tip", html)
        self.assertIn("::: tip", html)

    def test_columns_still_work_alongside_other_directives(self):
        md = (
            "::: tip\n小贴士\n:::\n"
            "\n"
            "::: columns 1/1\n"
            "::: column\nleft\n:::\n"
            "::: column\nright\n:::\n"
            ":::\n"
        )
        html = md_to_html(md)
        self.assertIn("admonition-tip", html)
        self.assertIn("md-columns", html)


from django.test import TestCase
from .models import Slide


class SearchToolbarViewTests(TestCase):
    databases = {"default", "slides"}

    def test_public_page_has_search_and_data_search(self):
        Slide.objects.create(title="可见幻灯片", content="正文关键词", lock=False)
        resp = self.client.get("/public/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="slide-search"')
        self.assertContains(resp, 'data-search=')
        self.assertContains(resp, "正文关键词")

    def test_index_page_has_search(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user("tester", password="pw")
        self.client.force_login(user)
        Slide.objects.create(title="管理可见", content="管理正文", lock=True)
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="slide-search"')
        self.assertContains(resp, 'data-search=')


class SoftDeleteTests(TestCase):
    databases = {"default", "slides"}

    def setUp(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user("deleter", password="pw")
        self.client.force_login(user)
        self.slide = Slide.objects.create(title="软删测试", content="# 软删测试", lock=False)

    def test_delete_moves_to_trash_and_hides_everywhere(self):
        resp = self.client.post(f"/delete/{self.slide.id}/")
        self.assertEqual(resp.status_code, 200)
        self.slide.refresh_from_db()
        self.assertIsNotNone(self.slide.deleted_at)
        # index 与 public 列表都不可见
        self.assertNotContains(self.client.get("/"), "软删测试")
        self.assertNotContains(self.client.get("/public/"), "软删测试")
        # 公开浏览页 404
        self.assertEqual(
            self.client.get(f"/public/edit/{self.slide.id}/").status_code, 404)
        # 编辑页 404
        self.assertEqual(
            self.client.get(f"/edit/{self.slide.id}/").status_code, 404)
        # 回收站可见
        self.assertContains(self.client.get("/trash/"), "软删测试")

    def test_restore_brings_slide_back(self):
        self.client.post(f"/delete/{self.slide.id}/")
        resp = self.client.post(f"/trash/{self.slide.id}/restore/")
        self.assertEqual(resp.status_code, 200)
        self.slide.refresh_from_db()
        self.assertIsNone(self.slide.deleted_at)
        self.assertContains(self.client.get("/"), "软删测试")

    def test_purge_deletes_permanently(self):
        self.client.post(f"/delete/{self.slide.id}/")
        resp = self.client.post(f"/trash/{self.slide.id}/purge/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Slide.objects.filter(id=self.slide.id).exists())

    def test_restore_requires_deleted_state(self):
        # 未删除的幻灯片不能走恢复/彻底删除接口
        self.assertEqual(
            self.client.post(f"/trash/{self.slide.id}/restore/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/trash/{self.slide.id}/purge/").status_code, 404)


class PresentSlideTests(TestCase):
    databases = {"default", "slides"}

    def test_public_slide_presentable_by_anyone(self):
        slide = Slide.objects.create(title="公开演示", content="# 公开演示", lock=False)
        resp = self.client.get(f"/present/{slide.id}/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Reveal.initialize", html)
        self.assertIn("RevealNotes", html)

    def test_locked_slide_hidden_from_anonymous(self):
        slide = Slide.objects.create(title="私有演示", content="# 私有演示", lock=True)
        self.assertEqual(self.client.get(f"/present/{slide.id}/").status_code, 404)

    def test_locked_slide_presentable_when_logged_in(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user("presenter", password="pw")
        self.client.force_login(user)
        slide = Slide.objects.create(title="私有演示", content="# 私有演示", lock=True)
        self.assertEqual(self.client.get(f"/present/{slide.id}/").status_code, 200)


class UploadImageTests(TestCase):
    databases = {"default", "slides"}

    def setUp(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user("uploader", password="pw")
        self.client.force_login(user)

    def _upload(self, name, content, content_type):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post("/upload_image/", {"image": f})

    def test_rejects_non_whitelisted_type(self):
        resp = self._upload("evil.svg", b"<svg/>", "image/svg+xml")
        self.assertEqual(resp.status_code, 400)
        resp = self._upload("fake.png", b"text", "text/plain")
        self.assertEqual(resp.status_code, 400)

    def test_rejects_oversize(self):
        from slideapp.views import MAX_IMAGE_SIZE
        resp = self._upload("big.png", b"0" * (MAX_IMAGE_SIZE + 1), "image/png")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("10MB", resp.json()["error"])

    def test_accepts_png_and_ignores_original_extension(self):
        import os as _os
        from django.conf import settings as _settings
        resp = self._upload("photo.txt", b"\x89PNG fake", "image/png")
        self.assertEqual(resp.status_code, 200)
        url = resp.json()["url"]
        self.assertTrue(url.endswith(".png"))
        # 清理测试产生的文件
        _os.remove(_os.path.join(_settings.MEDIA_ROOT, "uploads", _os.path.basename(url)))
