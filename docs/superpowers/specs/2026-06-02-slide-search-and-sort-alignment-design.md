# 幻灯片搜索 + public 排序对齐 设计文档

> 日期：2026-06-02 · 状态：已批准，待实现

## 1. 目标

1. 给 Web 管理主页（`index.html`）、公开主页（`public_slides.html`）、TUI（`slide_tui/`）三处都加上**按标题 + 正文**的搜索能力。
2. 把公开主页的排序 UI **对齐到管理主页**（两者后端排序逻辑本就一致，差的只是前端控件形态）。

## 2. 背景与现状

### 后端排序（已经一致，不动）
`slideapp/views.py` 里 `index` 和 `public_slides` 都通过：
- `SORT_OPTIONS`（`manual / updated_desc / updated_asc / created_desc / created_asc`）
- `get_sort(request)` 读 `?sort=` 参数
- 模板 context 都带 `sort` 和 `sort_options`

所以**排序的数据逻辑无需改动**，差异纯在模板的 sortbar 标记。

### 前端 sortbar 差异
- **管理页**：分段控件「手动 / 修改时间 / 创建时间」3 段 + 一个独立的**方向切换**按钮（`.sort-dir`，显示「晚 → 早 / 早 → 晚」）。字段与方向分离。`updated_desc`/`updated_asc` 共用「修改时间」段的 active，`created_desc`/`created_asc` 共用「创建时间」段的 active。
- **公开页**：5 个独立图标按钮（手动 / 改时间↓ / 改时间↑ / 创建↓ / 创建↑）平铺，CSS 类是 `.sort-btn`。

### 数据规模（决定采用纯客户端方案）
当前 43 张幻灯片，正文合计 ~140KB（单张最大 17KB，公开的 21 张合计 ~100KB）。体量小到可以把全部正文嵌入页面后做纯客户端即时过滤，无需新增后端接口或改 DB schema / 渲染管线 / 缓存。

## 3. 总体方案

三处都用**内存/客户端过滤**（标题 + 正文，大小写不敏感）：
- 零新增后端 URL / view。
- 零数据库 schema 改动。
- 不碰 `html_converter` / `md_util` / `RENDER_VERSION` / 缓存。

## 4. 详细设计

### 4.1 共享片段 `slideapp/templates/_toolbar.html`（新建）

两个模板的 sortbar 用 `?sort=...` 相对链接、与具体 URL 无关，markup 可以完全共用。新建一个自带 `<style>` 和 `<script>` 的片段，包含**排序栏（分段控件 + 方向切换）+ 搜索框**两块两页共用的内容。`index.html` 与 `public_slides.html` 各 `{% include "_toolbar.html" %}` 一次。

片段内容：
- **排序栏**：直接采用管理页现有的 `.segmented` / `.seg` / `.sort-dir` 标记与 active 条件逻辑（依赖 context 中的 `sort` 变量，两页都有）。
- **搜索框**：一个 `<input type="search">` + 清除按钮 + 命中计数（「匹配 N 张」）。
- 片段自带 `<style>`（`.segmented`、`.seg`、`.sort-dir`、搜索框相关类）和 `<script>`（搜索过滤逻辑）。`<style>`/`<script>` 置于 `<body>` 内合法。

布局：搜索框与排序栏同处一行（`sortbar` 容器内），排序栏在左、搜索框在右（窄屏自动换行）。

### 4.2 卡片注入可搜索文本

两个模板的每张 `.slide-card` 增加属性：
```
data-search="{{ slide.title }} {{ slide.content }}"
```
（Django 模板自动转义引号等，安全。）搜索 JS 取该属性 `.toLowerCase()` 后做 `includes` 匹配。

注意：管理页卡片是 `<article class="slide-card">`，公开页是 `<a class="slide-card">`，二者都加 `data-search` 即可，JS 用 `.slide-card` 通配。

### 4.3 搜索 JS 行为（片段内，通用）

- 监听搜索框 `input`，debounce ~80ms。
- 关键词为空：所有卡片、lane 复位为可见，计数清空。
- 非空：遍历 `.slide-card[data-search]`，命中则可见、否则 `display:none`；遍历每个 `.lane`，若其内可见卡片数为 0 则整条 lane `display:none`（含 Inbox/未分类 lane）；顶部计数显示「匹配 N 张」。
- 清除按钮：清空输入并复位。
- **不改动 DOM 顺序**，只切换可见性 —— 因此与管理页的拖拽排序互不干扰（搜索态下用户本就不应拖拽，且复位后顺序不变）。

### 4.4 删除冗余

- 删除 `public_slides.html` 旧的 5 按钮 sortbar markup 及其 `.sort-btn` CSS。
- 删除 `index.html` 内已移入 `_toolbar.html` 的 sortbar markup 与 `.segmented`/`.seg`/`.sort-dir`/`.sort-label`/`.sortbar` 等 CSS（迁移到片段，避免两处重复）。
- 管理页**独有**的顶部 actions（新建分类 / 新建幻灯片 / 切库 / 公开页 / 注销）保持原样留在 `index.html`，**不**进片段。

### 4.5 TUI 搜索

**`slide_tui/db.py`**
- `_WANTED_COLUMNS` 加入 `"content"`。
- `SlideRow` dataclass 增加 `content: str` 字段（仅内存使用，不参与列表显示）。
- `list_slides` 的 SELECT 自然带上 content（按现有 `select` 列表构造逻辑）。

**`slide_tui/clack.py::select`**
- 新增可选参数 `filter_of: Callable[[object], str] | None = None`。
- 当提供 `filter_of` 时，支持按 `/` 进入「过滤模式」：底部出现 `搜索: <query>▌` 输入行；可打印字符追加到 query，`backspace` 删字符，`esc` 退出过滤模式并清空 query，`enter` 选中当前高亮项。
- 过滤模式下，可见 `options` = 原 `options` 中 `filter_of(o).lower()` 包含 `query.lower()` 的子集；高亮索引在过滤后子集上移动。命中为空时显示「无匹配」提示。
- hint 文案追加 `/ 搜索`。
- 非过滤模式行为保持不变（向后兼容，`filter_of=None` 时与现状完全一致）。

**`slide_tui/app.py`**
- 调用 `clack.select` 时传入 `filter_of=lambda row: (row.title + " " + row.content).lower()`。
- 过滤与现有分类 tab 叠加：先 `_visible_rows()`（按分类），再交给 select 内部按 query 过滤。

## 5. 测试

- **Python 单测**：现有 `slideapp` 38 测须全绿（本方案不改渲染管线，预期不受影响）。
- **TUI 单测**：`slide_tui/tests` 须全绿；为 `clack.select` 的过滤逻辑（query 匹配、backspace、esc 清空、空结果）补充用例；为 `db.SlideRow` 含 content 补充/调整断言。
- **手动验证**：管理页 / 公开页搜索即时过滤、lane 隐藏、计数、清除复位；public 排序 UI 与管理页一致（分段 + 方向切换可用）；TUI `/` 搜索 + 分类叠加。

## 6. 取舍与边界

- **纯客户端**：数据量小，体验最佳（即时、无刷新、离线可用），完全规避渲染/缓存风险。
- **增长上限**：若将来涨到数百张 / 数 MB，再切换为 debounced AJAX 搜索接口——这是预留的演进点。
- **正文含 markdown 噪音**：搜索原始 markdown（含 `#`、`:::` 等符号），不做剥离以保持简单；用户搜普通词仍能命中。
- **页面体积**：管理页 `data-search` 全量嵌入约 +140KB（公开页约 +100KB），gzip 后远小于此，可接受。

## 7. 文档同步

本改动**不涉及** jyyslide-md 语法变化，因此 `SLIDE_SYNTAX.md` / `AGENTS.md` / `.claude/agents/slides-maker.md` 三处**无需**改动。`RENDER_VERSION` 无需 bump。
