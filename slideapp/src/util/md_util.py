import re
import uuid
from typing import List, Union


_MATH_PATTERN = re.compile(
    r"(\$\$[\s\S]*?\$\$)"
    r"|"
    r"(\$(?!\s)(?:[^\$\\]|\\.)*(?<!\s)\$)",
)


def _protect_math(md: str):
    placeholders: dict[str, str] = {}

    def _replace(m: re.Match) -> str:
        token = m.group(0)
        key = f"\x00MATH{uuid.uuid4().hex}\x00"
        placeholders[key] = token
        return key

    safe = _MATH_PATTERN.sub(_replace, md)
    return safe, placeholders


def _restore_math(html: str, placeholders: dict[str, str]) -> str:
    for key, original in placeholders.items():
        html = html.replace(key, original)
    return html


_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_COLUMNS_OPEN_RE = re.compile(r"^\s*:::\s*columns(?:\s+([\d\s/]+?))?\s*$")
_COLUMN_OPEN_RE = re.compile(r"^\s*:::\s*column\s*$")
_DIRECTIVE_CLOSE_RE = re.compile(r"^\s*:::\s*$")


def _build_columns_html(ratio: str, columns_md: List[str]) -> str:
    nums = [int(n) for n in re.findall(r"\d+", ratio or "")]
    n = len(columns_md)
    if not nums:
        nums = [1] * n
    elif len(nums) < n:
        nums = nums + [1] * (n - len(nums))
    nums = nums[:n]
    template = " ".join(f"{x}fr" for x in nums)
    parts = []
    for col_md in columns_md:
        inner = md_to_html(col_md)
        parts.append(f'<div class="md-column">{inner}</div>')
    style = f"grid-template-columns: {template};"
    return (
        f'<div class="md-columns" style="{style}">' + "".join(parts) + "</div>"
    )


def _protect_columns(md: str):
    """Replace ``::: columns ... :::`` blocks with raw HTML placeholders.

    Returns (safe_md, placeholders dict). The placeholder is a block-level
    ``<div data-cols-placeholder="UUID"></div>`` so Python-Markdown passes it
    through as raw HTML without wrapping it in ``<p>``.

    On unclosed / malformed input, the original lines are restored as-is so
    the slide degrades to plain Markdown instead of raising.
    """

    placeholders: dict[str, str] = {}
    lines = md.split("\n")
    out: List[str] = []
    state = "outside"  # outside | in_columns | in_column
    in_code = False
    fence_char = None
    ratio = ""
    columns: List[str] = []
    current_col: List[str] = []
    pending: List[str] = []  # raw lines since opener, for fallback restore

    for line in lines:
        m_fence = _FENCE_RE.match(line)

        if in_code:
            # inside fenced code: never match directives; just record the line
            if state == "outside":
                out.append(line)
            else:
                pending.append(line)
                if state == "in_column":
                    current_col.append(line)
            if m_fence and m_fence.group(1)[0] == fence_char:
                in_code = False
                fence_char = None
            continue

        if m_fence:
            in_code = True
            fence_char = m_fence.group(1)[0]
            if state == "outside":
                out.append(line)
            else:
                pending.append(line)
                if state == "in_column":
                    current_col.append(line)
            continue

        if state == "outside":
            m = _COLUMNS_OPEN_RE.match(line)
            if m:
                state = "in_columns"
                ratio = (m.group(1) or "").strip()
                columns = []
                pending = [line]
            else:
                out.append(line)
            continue

        if state == "in_columns":
            pending.append(line)
            if _COLUMN_OPEN_RE.match(line):
                state = "in_column"
                current_col = []
            elif _DIRECTIVE_CLOSE_RE.match(line):
                if columns:
                    html = _build_columns_html(ratio, columns)
                    key = f'<div data-cols-placeholder="{uuid.uuid4().hex}"></div>'
                    placeholders[key] = html
                    out.append("")
                    out.append(key)
                    out.append("")
                else:
                    # opener + immediate closer with no inner columns: degrade
                    out.extend(pending)
                state = "outside"
                pending = []
                ratio = ""
                columns = []
            # else: stray content between column children — kept only in pending
            continue

        if state == "in_column":
            pending.append(line)
            if _DIRECTIVE_CLOSE_RE.match(line):
                columns.append("\n".join(current_col))
                current_col = []
                state = "in_columns"
            else:
                current_col.append(line)
            continue

    if state != "outside":
        # unclosed block at EOF — degrade
        out.extend(pending)

    return "\n".join(out), placeholders


def _restore_columns(html: str, placeholders: dict) -> str:
    for key, value in placeholders.items():
        html = html.replace(key, value)
    return html


def process_images(content, func):
    """处理Markdown类型字符串中的图片链接, 返回处理过图片链接部分的Markdown字符串

    Args:
        content (_type_): Markdown类型字符串
        func (_type_): 处理图片链接的函数, 该函数接受图片链接字符串, 返回一个(有关图片链接的新串, 是否有错误)的元组
    """

    def modify(match):
        # 下面是黑盒魔法
        tar = match.group()
        pre, mid, suf = str(), str(), str()
        if tar[-1] == ")":
            pre = tar[: tar.index("(") + 1]
            mid = tar[tar.index("(") + 1 : -1]
            suf = tar[-1]
        else:
            mid = re.search(r'src="([^"]*)"', tar).group(1)
            pre, suf = tar.split(mid)

        link = mid
        # 黑盒魔法结束
        new_name, err = func(link)
        return pre + (new_name if err is False else link) + suf

    patten = r"!\[.*?\]\(((?:[^()]|\([^()]*\))*)\)|<img.*?src=[\'\"]([^\'\"]*)[\'\"].*?>"
    return re.sub(patten, modify, content)


###

from markdown import markdown
from markdown import Extension
from markdown.blockprocessors import BlockProcessor
import xml.etree.ElementTree as etree


def md_to_html(md: str) -> str:
    class BoxBlockProcessor(BlockProcessor):
        first = True

        def run(self, parent, blocks):
            if self.first:
                self.first = False
                e = etree.SubElement(parent, "div")
                self.parser.parseBlocks(e, blocks)
                for _ in range(0, len(blocks)):
                    blocks.pop(0)
                return True
            return False

    class BoxExtension(Extension):
        def extendMarkdown(self, md):
            md.parser.blockprocessors.register(BoxBlockProcessor(md.parser), "box", 175)

    extensions: List[Union[str, BoxExtension]] = [
        BoxExtension(),
        "meta",
        "fenced_code",
        "codehilite",
        "extra",
        "attr_list",
        "tables",
        "toc",
    ]
    safe_md, math_placeholders = _protect_math(md)
    safe_md, col_placeholders = _protect_columns(safe_md)
    html = markdown(safe_md, extensions=extensions)
    html = _restore_columns(html, col_placeholders)
    return _restore_math(html, math_placeholders)
