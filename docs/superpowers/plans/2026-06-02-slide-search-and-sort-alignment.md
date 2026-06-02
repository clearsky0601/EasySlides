# 幻灯片搜索 + public 排序对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Web 管理页、公开页、TUI 三处加上"标题+正文"搜索，并把公开页排序 UI 对齐到管理页。

**Architecture:** 纯客户端/内存过滤，零新增后端接口、零 DB schema 改动。Web 端抽一个共享模板片段 `_toolbar.html`（排序栏 + 搜索框，自带 CSS/JS），两个页面 `{% include %}`；卡片注入 `data-search`。TUI 给 `clack.select` 加一个可选过滤模式，`db.SlideRow` 增加 `content` 字段。

**Tech Stack:** Django 模板 / 原生 JS；Python `slide_tui`（rich + raw 键盘）；测试用 Django `manage.py test` 与 `unittest`。

**对应 spec:** `docs/superpowers/specs/2026-06-02-slide-search-and-sort-alignment-design.md`

---

## File Structure

- `slide_tui/db.py` — 修改：`SlideRow` + `_WANTED_COLUMNS` + `list_slides` 构造增加 `content`。
- `slide_tui/clack.py` — 修改：`select()` 增加 `filter_of` 参数与 `/` 过滤模式；新增 `from rich.markup import escape` 导入。
- `slide_tui/app.py` — 修改：`_slide_step` 的 `clack.select(...)` 调用传入 `filter_of` 并在 hint 加 `/ 搜索`。
- `slideapp/templates/_toolbar.html` — 新建：排序栏（分段控件 + 方向切换）+ 搜索框 + 自带 `<style>`/`<script>`。
- `slideapp/templates/index.html` — 修改：用 `{% include %}` 替换内联 sortbar；卡片加 `data-search`；删除迁移走的 sort CSS。
- `slideapp/templates/public_slides.html` — 修改：用 `{% include %}` 替换 5 按钮 sortbar；卡片加 `data-search`；删除 `.sort-btn` 等旧 CSS。
- `slideapp/tests.py` — 修改：新增视图测试，验证两页都含搜索框与 `data-search`。
- `slide_tui/tests/test_db.py` / `test_clack.py` — 修改：新增 content / 过滤模式测试。

---

## Task 1: TUI `db.py` — `SlideRow` 增加 content 字段

**Files:**
- Modify: `slide_tui/db.py:17-24`（SlideRow）、`slide_tui/db.py:69`（_WANTED_COLUMNS）、`slide_tui/db.py:136-148`（构造）
- Test: `slide_tui/tests/test_db.py`

- [ ] **Step 1: 写失败测试**

在 `slide_tui/tests/test_db.py` 末尾（`if __name__` 之前，若无则直接追加）新增一个测试类。注意现有 `_make_db` 把 content 硬编码为 `''`，所以这里自建一个带真实 content 的 fixture：

```python
class SlideContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "db.sqlite3"
        conn = sqlite3.connect(self.db)
        conn.execute(
            "CREATE TABLE slideapp_slide ("
            "id INTEGER PRIMARY KEY, title TEXT, category TEXT, "
            "lock INTEGER, version INTEGER, sort_order INTEGER, content TEXT)"
        )
        conn.execute(
            "INSERT INTO slideapp_slide "
            "(id, title, category, lock, version, sort_order, content) "
            "VALUES (1, 'Alpha', '', 0, 0, 1, '# heading\\nbody text')"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_content_is_loaded(self):
        rows = db.list_slides(self.db)
        self.assertEqual(rows[0].content, "# heading\nbody text")

    def test_content_defaults_empty_on_legacy_without_column(self):
        legacy = Path(self.tmp.name) / "legacy.sqlite3"
        conn = sqlite3.connect(legacy)
        conn.execute(
            "CREATE TABLE slideapp_slide "
            "(id INTEGER PRIMARY KEY, title TEXT, lock INTEGER, version INTEGER)"
        )
        conn.execute(
            "INSERT INTO slideapp_slide (id, title, lock, version) "
            "VALUES (1, 'NoContent', 0, 0)"
        )
        conn.commit()
        conn.close()
        rows = db.list_slides(legacy)
        self.assertEqual(rows[0].content, "")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest slide_tui.tests.test_db -v`
Expected: FAIL —— `TypeError: __init__() got an unexpected keyword argument` 或 `AttributeError: 'SlideRow' object has no attribute 'content'`（取决于实现顺序；总之红）。

- [ ] **Step 3: 给 `SlideRow` 加字段**

`slide_tui/db.py` 的 dataclass 改为（在 `sort_order` 后加 `content`，给默认值以兼容旧调用点）：

```python
@dataclass(frozen=True)
class SlideRow:
    id: int
    title: str
    category: str
    lock: int           # 1 = locked/private, 0 = public
    version: int
    sort_order: int
    content: str = ""

    @property
    def is_locked(self) -> bool:
        return bool(self.lock)
```

- [ ] **Step 4: 把 content 加进 SELECT 白名单**

`slide_tui/db.py:69` 改为：

```python
_WANTED_COLUMNS = ("id", "title", "category", "lock", "version", "sort_order", "content")
```

- [ ] **Step 5: 构造 SlideRow 时带上 content**

`slide_tui/db.py` 的 `list_slides` 末尾循环里，`SlideRow(...)` 增加一行（放在 `sort_order=...` 之后）：

```python
            SlideRow(
                id=d["id"],
                title=d.get("title") or "",
                category=d.get("category") or "",
                lock=d.get("lock", 0) or 0,
                version=d.get("version", 0) or 0,
                sort_order=d.get("sort_order", 0) or 0,
                content=d.get("content") or "",
            )
```

- [ ] **Step 6: 跑测试确认通过**

Run: `.venv/bin/python -m unittest slide_tui.tests.test_db -v`
Expected: PASS（新增 2 测 + 原有全绿）。

- [ ] **Step 7: 提交**

```bash
git add slide_tui/db.py slide_tui/tests/test_db.py
git commit -m "feat(tui): SlideRow 增加 content 字段供搜索使用"
```

---

## Task 2: TUI `clack.select` — 增加 `/` 过滤模式

**Files:**
- Modify: `slide_tui/clack.py:18`（新增 import）、`slide_tui/clack.py:156-235`（整段重写 `select`）
- Test: `slide_tui/tests/test_clack.py`

- [ ] **Step 1: 写失败测试**

在 `slide_tui/tests/test_clack.py` 的 `SelectNavigationTests` 类后新增一个类。`/` 进入过滤，输入 `b` 过滤到含 "b" 的项，回车选中：

```python
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
        # 输入 "ban" 过滤到 "banana"（原始索引 2），回车选中
        action, value, idx = self._run(
            ["/", "b", "a", "n", "enter"],
            ["apple", "cherry", "banana"],
        )
        self.assertEqual(action, "select")
        self.assertEqual(value, "banana")
        self.assertEqual(idx, 2)

    def test_backspace_widens_filter(self):
        # "z" 无匹配 → backspace 删掉 → 回车选中当前高亮（第一个 apple）
        action, value, idx = self._run(
            ["/", "z", "backspace", "enter"],
            ["apple", "banana"],
        )
        self.assertEqual(action, "select")
        self.assertEqual(value, "apple")

    def test_esc_exits_filter_without_quitting(self):
        # 过滤态下 esc 退出过滤并清空，再回车选中高亮项（不退出 select）
        action, value, idx = self._run(
            ["/", "b", "esc", "enter"],
            ["apple", "banana"],
        )
        self.assertEqual(action, "select")
        self.assertEqual(value, "apple")

    def test_slash_inert_without_filter_of(self):
        # 不传 filter_of 时，"/" 不进入过滤模式，被当普通键忽略；回车选中第一个
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest slide_tui.tests.test_clack -v`
Expected: FAIL —— `select() got an unexpected keyword argument 'filter_of'`。

- [ ] **Step 3: 新增 escape 导入**

`slide_tui/clack.py` 顶部 import 区（约第 18 行，`from rich.console import Console` 旁）加一行：

```python
from rich.markup import escape
```

- [ ] **Step 4: 重写 `select`**

把 `slide_tui/clack.py` 中**整个 `select` 函数**（从 `def select(` 到它的 `finally: _show_cursor()` 结束）替换为下面版本。新增 `filter_of` 参数；非过滤态行为与原先一致（`shown` 即 `options`），过滤态下用 `query` 子集渲染、`/` 进入、可打印字符累加、`backspace` 删字符、`esc` 清空退出、`enter` 返回**原始**索引：

```python
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
    filter_of: Callable[[object], str] | None = None,
) -> tuple[str, object, int]:
    """Render a clack select prompt and return ``(action, value, index)``.

    ``action`` is ``"select"`` for Enter, ``"quit"`` for q/esc/ctrl-c, or any
    value mapped in ``extra_keys`` (e.g. ``{"d": "switch"}``).

    When ``filter_of`` is given, pressing ``/`` enters a filter mode: typed
    characters narrow the options to those whose ``filter_of(option)`` contains
    the query (case-insensitive). In filter mode Enter returns the *original*
    index into ``options``; Esc clears the query and leaves filter mode.
    """
    extra_keys = extra_keys or {}
    base = list(options)
    filtering = False
    query = ""

    def shown_options() -> list:
        if not filtering or not query:
            return base
        q = query.lower()
        return [o for o in base if q in filter_of(o).lower()]

    idx = max(0, min(start_index, len(base) - 1)) if base else 0

    clear()
    try:
        while True:
            shown = shown_options()
            idx = max(0, min(idx, len(shown) - 1)) if shown else 0

            _begin_repaint()
            render_header()
            bar()
            head = f"[{CYAN}]{S_STEP_ACTIVE}[/]  [bold]{title}[/]"
            active_hint = "↵ 选中 · ⌫ 删字 · esc 取消搜索" if filtering else hint
            if active_hint:
                head += f"   [{DIM}]{active_hint}[/]"
            print_line(head)
            bar()
            if render_before_options is not None:
                render_before_options()

            if not shown:
                msg = "无匹配" if filtering else "（空）"
                print_line(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]{msg}[/]")
            else:
                win = _window_size(len(shown))
                start = _window_start(idx, len(shown), win)
                has_scroll = len(shown) > win
                if has_scroll and start > 0:
                    print_line(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]↑ 还有 {start} 项[/]")
                elif has_scroll:
                    bar()
                for i in range(start, min(start + win, len(shown))):
                    label = label_of(shown[i])
                    if i == idx:
                        print_line(
                            f"[{GUTTER}]{S_BAR}[/]  [{GREEN}]{S_RADIO_ACTIVE}[/] {label}"
                        )
                    else:
                        print_line(
                            f"[{GUTTER}]{S_BAR}[/]  [{DIM}]{S_RADIO_INACTIVE}[/] "
                            f"[{DIM}]{label}[/]"
                        )
                rest = len(shown) - (start + win)
                if has_scroll and rest > 0:
                    print_line(f"[{GUTTER}]{S_BAR}[/]  [{DIM}]↓ 还有 {rest} 项[/]")
                elif has_scroll:
                    bar()

            if filtering:
                print_line(
                    f"[{GUTTER}]{S_BAR}[/]  [{CYAN}]搜索:[/] {escape(query)}[reverse] [/]"
                )
                print_line(f"[{GUTTER}]{S_BAR_END}[/]  [{DIM}]{footer}[/]")
            else:
                print_line(f"[{GUTTER}]{S_BAR_END}[/]  [{DIM}]{footer}[/]")
            _end_repaint()

            key = read_key()

            if filtering:
                if key == "ctrl-c":
                    return ("quit", None, 0)
                if key == "esc":
                    filtering = False
                    query = ""
                    idx = 0
                elif key == "enter":
                    if shown:
                        sel = shown[idx]
                        return ("select", sel, base.index(sel))
                elif key == "backspace":
                    query = query[:-1]
                    idx = 0
                elif key == "up":
                    if shown:
                        idx = (idx - 1) % len(shown)
                elif key == "down":
                    if shown:
                        idx = (idx + 1) % len(shown)
                elif len(key) == 1 and key.isprintable():
                    query += key
                    idx = 0
                continue

            if key in ("q", "esc", "ctrl-c"):
                return ("quit", None, idx)
            if key == "/" and filter_of is not None:
                filtering = True
                query = ""
                idx = 0
            elif key in ("up", "k") and shown:
                idx = (idx - 1) % len(shown)
            elif key in ("down", "j") and shown:
                idx = (idx + 1) % len(shown)
            elif key == "enter" and shown:
                return ("select", shown[idx], idx)
            elif key in extra_keys:
                return (extra_keys[key], shown[idx] if shown else None, idx)
    finally:
        _show_cursor()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m unittest slide_tui.tests.test_clack -v`
Expected: PASS（新增 4 测 + 原有导航测试仍绿，因为 `filter_of=None` 时逻辑等价于原实现）。

- [ ] **Step 6: 提交**

```bash
git add slide_tui/clack.py slide_tui/tests/test_clack.py
git commit -m "feat(tui): clack.select 支持 / 进入过滤模式"
```

---

## Task 3: TUI `app.py` — 接入 filter_of

**Files:**
- Modify: `slide_tui/app.py:182-197`（`_slide_step` 里的 `clack.select` 调用）

- [ ] **Step 1: 传入 filter_of 并更新 hint**

`slide_tui/app.py` 的 `_slide_step` 中 `clack.select(...)` 调用，把 `hint` 文案加上 `/ 搜索`，并新增 `filter_of` 参数：

```python
        action, value, self._slide_index = clack.select(
            self._render_header,
            title="选择幻灯片",
            options=visible_rows,
            label_of=self._slide_label,
            hint="/ 搜索 · h/l 分类 · j/k/↑↓ 移动 · ↵ 预览 · d 切库 · r 刷新 · q 退出",
            footer="↵ 在浏览器打开 /public 预览",
            extra_keys={
                "d": "switch",
                "r": "refresh",
                "h": "prev_category",
                "l": "next_category",
            },
            start_index=self._slide_index,
            render_before_options=self._render_category_tabs,
            filter_of=lambda row: (row.title + " " + row.content).lower(),
        )
```

- [ ] **Step 2: 跑全部 TUI 测试确认无回归**

Run: `.venv/bin/python -m unittest discover -s slide_tui/tests -t .`
Expected: OK（全绿）。

- [ ] **Step 3: 手动冒烟（可选，需交互终端）**

启动 `./tui.sh`，按 `/`，输入关键字，确认列表实时收窄、`↵` 能打开预览、`esc` 退出搜索。若无交互终端可跳过，靠单测保证逻辑。

- [ ] **Step 4: 提交**

```bash
git add slide_tui/app.py
git commit -m "feat(tui): 幻灯片列表接入 / 标题+正文搜索"
```

---

## Task 4: Web — 新建共享片段 `_toolbar.html`

**Files:**
- Create: `slideapp/templates/_toolbar.html`

> 该片段自带 `<style>`/`<script>`，包含两页共用的"排序栏（分段控件 + 方向切换）+ 搜索框"。排序栏 markup 取自 `index.html` 现有的 `.segmented`/`.sort-dir` 实现，依赖 context 里的 `sort` 变量（两页都有）。搜索 JS 通用操作 `.slide-card[data-search]` 与 `.lane`。

- [ ] **Step 1: 创建片段文件**

新建 `slideapp/templates/_toolbar.html`，内容如下（完整，不要省略）：

```html
{% comment %}两页共用的工具栏：排序分段控件 + 方向切换 + 即时搜索框。依赖 context 变量 sort。{% endcomment %}
<style>
    .toolbar {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        margin: 0 0 14px;
    }
    .toolbar .sort-label { color: var(--muted); font-size: 12px; }
    .toolbar .segmented {
        display: inline-flex;
        align-items: stretch;
        border: 1px solid var(--line-strong);
        background: var(--panel);
        overflow: hidden;
    }
    .toolbar .seg {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 0 13px;
        min-height: 34px;
        font-size: 13px;
        color: var(--accent-strong, var(--accent));
        text-decoration: none;
        transition: background 0.15s ease, color 0.15s ease;
    }
    .toolbar .seg + .seg { border-left: 1px solid var(--line-strong); }
    .toolbar .seg svg { width: 15px; height: 15px; }
    .toolbar .seg:hover { background: var(--accent-soft); }
    .toolbar .seg.active { background: var(--accent); color: #fffdf8; }
    .toolbar .sort-dir {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 0 13px;
        min-height: 34px;
        font-size: 13px;
        color: var(--accent-strong, var(--accent));
        text-decoration: none;
        border: 1px solid var(--line-strong);
        background: var(--panel);
        transition: background 0.15s ease, border-color 0.15s ease;
    }
    .toolbar .sort-dir svg { width: 15px; height: 15px; }
    .toolbar .sort-dir:hover { background: var(--accent-soft); border-color: var(--accent); }

    .toolbar .search {
        margin-left: auto;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border: 1px solid var(--line-strong);
        background: var(--panel);
        padding: 0 8px;
        min-height: 34px;
    }
    .toolbar .search svg { width: 15px; height: 15px; color: var(--muted); }
    .toolbar .search input {
        border: 0;
        background: transparent;
        outline: none;
        color: var(--ink);
        width: 200px;
        min-height: 32px;
        font: inherit;
    }
    .toolbar .search-clear {
        border: 0;
        background: transparent;
        color: var(--muted);
        cursor: pointer;
        font-size: 16px;
        line-height: 1;
        padding: 2px 4px;
        display: none;
    }
    .toolbar .search-clear.show { display: inline-flex; }
    .toolbar .search-count { color: var(--muted); font-size: 12px; min-width: 0; }
    @media (max-width: 860px) {
        .toolbar .search { margin-left: 0; flex: 1; }
        .toolbar .search input { flex: 1; width: auto; }
    }
</style>

<nav class="toolbar" aria-label="排序与搜索">
    <span class="sort-label">排序</span>
    <div class="segmented">
        <a class="seg {% if sort == 'manual' %}active{% endif %}" href="?sort=manual">
            <svg viewBox="0 0 24 24"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg>
            手动
        </a>
        <a class="seg {% if sort == 'updated_desc' or sort == 'updated_asc' %}active{% endif %}" href="?sort=updated_desc">
            <svg viewBox="0 0 24 24"><path d="M12 8v5l3 2"/><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 3v6h-6"/></svg>
            修改时间
        </a>
        <a class="seg {% if sort == 'created_desc' or sort == 'created_asc' %}active{% endif %}" href="?sort=created_desc">
            <svg viewBox="0 0 24 24"><path d="M8 2v4"/><path d="M16 2v4"/><path d="M3 10h18"/><path d="M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2"/></svg>
            创建时间
        </a>
    </div>
    {% if sort == 'updated_desc' %}
    <a class="sort-dir" href="?sort=updated_asc" title="改为从早到晚">
        <svg viewBox="0 0 24 24"><path d="M12 5v14"/><path d="M6 13l6 6 6-6"/></svg>晚 → 早
    </a>
    {% elif sort == 'updated_asc' %}
    <a class="sort-dir" href="?sort=updated_desc" title="改为从晚到早">
        <svg viewBox="0 0 24 24"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg>早 → 晚
    </a>
    {% elif sort == 'created_desc' %}
    <a class="sort-dir" href="?sort=created_asc" title="改为从早到晚">
        <svg viewBox="0 0 24 24"><path d="M12 5v14"/><path d="M6 13l6 6 6-6"/></svg>晚 → 早
    </a>
    {% elif sort == 'created_asc' %}
    <a class="sort-dir" href="?sort=created_desc" title="改为从晚到早">
        <svg viewBox="0 0 24 24"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg>早 → 晚
    </a>
    {% endif %}

    <div class="search">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
        <input type="search" id="slide-search" placeholder="搜索标题或正文" autocomplete="off" aria-label="搜索幻灯片">
        <button type="button" class="search-clear" id="slide-search-clear" aria-label="清除搜索">×</button>
        <span class="search-count" id="slide-search-count"></span>
    </div>
</nav>

<script>
(function () {
    const input = document.getElementById('slide-search');
    const clearBtn = document.getElementById('slide-search-clear');
    const countEl = document.getElementById('slide-search-count');
    if (!input) return;
    const cards = Array.from(document.querySelectorAll('.slide-card[data-search]'));
    const lanes = Array.from(document.querySelectorAll('.lane'));

    function apply(q) {
        q = q.trim().toLowerCase();
        clearBtn.classList.toggle('show', q.length > 0);
        if (!q) {
            cards.forEach(c => { c.style.display = ''; });
            lanes.forEach(l => { l.style.display = ''; });
            countEl.textContent = '';
            return;
        }
        let matched = 0;
        cards.forEach(c => {
            const hit = (c.getAttribute('data-search') || '').toLowerCase().includes(q);
            c.style.display = hit ? '' : 'none';
            if (hit) matched++;
        });
        lanes.forEach(l => {
            const visible = l.querySelectorAll('.slide-card[data-search]:not([style*="display: none"])').length;
            l.style.display = visible > 0 ? '' : 'none';
        });
        countEl.textContent = '匹配 ' + matched + ' 张';
    }

    let timer = null;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => apply(input.value), 80);
    });
    clearBtn.addEventListener('click', () => {
        input.value = '';
        apply('');
        input.focus();
    });
})();
</script>
```

- [ ] **Step 2: 提交**

```bash
git add slideapp/templates/_toolbar.html
git commit -m "feat(web): 新增共享工具栏片段（排序+搜索）"
```

---

## Task 5: Web — `public_slides.html` 接入片段、卡片加 data-search、清理旧 sortbar

**Files:**
- Modify: `slideapp/templates/public_slides.html`
- Test: `slideapp/tests.py`

- [ ] **Step 1: 写失败的视图测试**

在 `slideapp/tests.py` 末尾（`if __name__` 之前，若无则文件尾）追加。`/public/` 无需登录：

```python
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
        # 正文进入了可搜索属性
        self.assertContains(resp, "正文关键词")
```

> 注：`Slide` 走 `slides` 库（见 `db_router.py`），故声明 `databases`。若运行时报数据库别名相关错误，把 `databases` 改成 `"__all__"`。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python manage.py test slideapp.tests.SearchToolbarViewTests -v 2`
Expected: FAIL —— 断言 `id="slide-search"` 不在响应中（public 页还没有搜索框）。

- [ ] **Step 3: 用 include 替换旧 sortbar**

`slideapp/templates/public_slides.html` 中，删除整段 `<nav class="sortbar" ...>…</nav>`（约 214-231 行的 5 个 `.sort-btn` 按钮），替换为：

```html
    {% include "_toolbar.html" %}
```

- [ ] **Step 4: 给两处卡片加 data-search**

把未分类与分类两处的卡片开标签：

```html
                    <a class="slide-card" href="{% url 'public_edit_slide' slide.id %}">
```

都改为：

```html
                    <a class="slide-card" data-search="{{ slide.title }} {{ slide.content }}" href="{% url 'public_edit_slide' slide.id %}">
```

（两处都改：未分类 lane 与 `{% for category %}` lane 内各一处。）

- [ ] **Step 5: 删除已无用的旧 CSS**

`public_slides.html` 的 `<style>` 里删除 `.sortbar`、`.sort-label`、`.sort-btn`、`.sort-btn:hover, .sort-btn.active` 这几条规则（已由片段接管；`.sort-note`、`.slide-count` 仍被 lane-header 使用，保留）。

- [ ] **Step 6: 跑测试确认通过**

Run: `.venv/bin/python manage.py test slideapp.tests.SearchToolbarViewTests -v 2`
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add slideapp/templates/public_slides.html slideapp/tests.py
git commit -m "feat(web): 公开页接入共享工具栏与搜索，对齐排序 UI"
```

---

## Task 6: Web — `index.html` 接入片段、卡片加 data-search、清理迁走的 CSS

**Files:**
- Modify: `slideapp/templates/index.html`
- Test: `slideapp/tests.py`（沿用 Task 5 的测试类，新增 index 用例）

- [ ] **Step 1: 写失败的视图测试**

在 `SearchToolbarViewTests` 类里新增方法（index 需登录）：

```python
    def test_index_page_has_search(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user("tester", password="pw")
        self.client.force_login(user)
        Slide.objects.create(title="管理可见", content="管理正文", lock=True)
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="slide-search"')
        self.assertContains(resp, 'data-search=')
```

> User 表在 `default` 库；类已声明 `databases = {"default", "slides"}`，可同时建用户与幻灯片。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python manage.py test slideapp.tests.SearchToolbarViewTests.test_index_page_has_search -v 2`
Expected: FAIL —— index 页还没有 `id="slide-search"`。

- [ ] **Step 3: 用 include 替换内联 sortbar**

`slideapp/templates/index.html` 中删除整段 `<nav class="sortbar" aria-label="排序">…</nav>`（约 533-566 行的 segmented + sort-dir 整块），替换为：

```html
    {% include "_toolbar.html" %}
```

- [ ] **Step 4: 给两处卡片加 data-search**

把未分类与分类两处的卡片开标签：

```html
                    <article class="slide-card" draggable="{% if sort == 'manual' %}true{% else %}false{% endif %}" data-slide-id="{{ slide.id }}">
```

都改为（在 `data-slide-id` 后加 `data-search`）：

```html
                    <article class="slide-card" draggable="{% if sort == 'manual' %}true{% else %}false{% endif %}" data-slide-id="{{ slide.id }}" data-search="{{ slide.title }} {{ slide.content }}">
```

（两处都改：未分类 lane 与 `{% for category %}` lane 内各一处。）

- [ ] **Step 5: 删除迁走的旧 CSS**

`index.html` 的 `<style>` 里删除以下已迁入片段、不再被使用的规则：`.sortbar`、`.sort-label`、`.segmented`、`.segmented .seg`、`.segmented .seg + .seg`、`.segmented .seg svg`、`.segmented .seg:hover`、`.segmented .seg.active`、`.sort-dir`、`.sort-dir svg`、`.sort-dir:hover`。

> 不要动 `.slide-card`、`.lane`、`body[data-sort-mode]` 等仍在用的规则。删除后用浏览器肉眼核对排序栏样式与原先一致。

- [ ] **Step 6: 跑测试确认通过 + 全量回归**

Run: `.venv/bin/python manage.py test slideapp -v 1`
Expected: OK —— 原 38 测 + 新增 web 视图测试全绿。

- [ ] **Step 7: 提交**

```bash
git add slideapp/templates/index.html slideapp/tests.py
git commit -m "feat(web): 管理页接入共享工具栏与搜索"
```

---

## Task 7: 全量验证与手动核对

**Files:** 无（仅验证）

- [ ] **Step 1: 跑全部 Python 测试**

Run: `.venv/bin/python manage.py test slideapp`
Expected: OK（≥38 + 新增）。

- [ ] **Step 2: 跑全部 TUI 测试**

Run: `.venv/bin/python -m unittest discover -s slide_tui/tests -t .`
Expected: OK。

- [ ] **Step 3: 手动核对 Web（启动服务）**

启动 `./start_local.sh`（端口 10001），用浏览器核对：
- `/`（登录后）与 `/public/`：排序栏外观一致（分段「手动/修改时间/创建时间」+ 方向切换），点击切换排序仍工作。
- 搜索框输入关键词：卡片即时过滤、空 lane 隐藏、显示"匹配 N 张"、× 清除复位。
- 管理页手动排序模式下，清空搜索后仍可拖拽（顺序未被搜索破坏）。

- [ ] **Step 4: 确认文档无需同步**

本改动不涉及 jyyslide-md 语法，`SLIDE_SYNTAX.md` / `AGENTS.md` / `slides-maker.md` 无需改，`RENDER_VERSION` 无需 bump（spec 第 7 节）。无需提交。

---

## Self-Review 记录

- **Spec 覆盖**：搜索（Web×2 + TUI）= Task 1/2/3/4/5/6；public 排序对齐 = Task 4（共享片段）+ Task 5/6（替换旧 sortbar）；共享 `_toolbar.html` = Task 4；删冗余 CSS = Task 5/6；文档无需同步 = Task 7 Step 4。无遗漏。
- **占位符**：无 TBD/TODO；所有代码步骤含完整代码。
- **类型一致**：`SlideRow.content`（Task 1）↔ `app.py` 的 `row.content`（Task 3）↔ `filter_of`（Task 2 参数名）一致；`#slide-search` / `data-search` 在片段（Task 4）与两模板（Task 5/6）与测试（Task 5/6）中拼写一致。
```
