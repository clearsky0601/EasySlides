---
name: easy-slides
description: 在 EasySlides 项目中创建、编辑、管理 jyy 风格的 Reveal.js 幻灯片（jyyslide-md 方言），直接读写 SQLite `db.sqlite3` 的 slideapp_slide 表。Use when the user wants to make / write / edit / 创建 / 修改 / 生成 slides 或幻灯片 in this repo, draft jyy 风格 presentations, manage the slideapp_slide table, publish/unlock a slide, or work with jyyslide-md Markdown syntax (分隔符 / :::columns / :::tip / timeline / KaTeX 等).
---

# easy-slides

在本项目（EasySlides，Django + Reveal.js）里创建和管理 jyy 风格幻灯片。内容用 jyyslide-md 方言 Markdown 编写，经 Python-Markdown → HTML → Reveal.js 渲染，存在项目根 `db.sqlite3` 的 `slideapp_slide` 表。画布 1024×768；Tailwind CSS 内嵌；KaTeX 渲染公式；`codehilite` 做代码高亮。

## 语法权威：先读 SLIDE_SYNTAX.md

**仓库根的 `SLIDE_SYNTAX.md` 是 jyyslide-md 语法的唯一权威。生成或修改任何幻灯片内容前必须先读它**（涵盖分隔符体系、front-matter、`:::` 指令、图片/表格/代码/数学、Tailwind 布局、页面模板、写作风格）。本 SKILL.md 只保留最易错的核心规则与操作流程，不重复完整语法，避免与权威文档产生漂移。

### 分隔符体系（最易错，务必记牢）

解析器靠**字符串 split**，每个分隔符必须**独占一行且前后各有一个空行**（真实的 `\n<sep>\n`）。

| 分隔符 | 含义 |
|---|---|
| `---`（3 个 `-`） | 水平切分（大章节 PART） |
| `----`（4 个 `-`） | 垂直切分（子页） |
| `++++`（4 个 `+`） | 渐变页（Auto-Animate） |
| `--`（2 个 `-`） | Fragment（逐步揭示） |
| `+++++`（5 个 `+`） | Front-Matter 分隔符（仅文档开头一次） |
| `<hr>` | 视觉空行（不是分割线！） |

**绝对禁区**：
- 分隔符关键字不得作为正文文字出现（正文里别写 3 个以上连续 `-`/`+`）。
- 禁止 Setext 标题（标题下跟 `===` 或 `---`）——会被当分隔符。所有标题用 `#`/`##`。
- 普通 Markdown 的 `---` 分隔线不可用，用 `<hr>` 替代。
- `:::` 指令（`columns / note / tip / warning / danger / success / notes / incremental / timeline`）必须在单张幻灯片内闭合，不能跨 `---`/`----`（跨页降级为普通 Markdown，不报错）。未知关键字按原文输出。

其余语法细节一律以 `SLIDE_SYNTAX.md` 为准。

## 数据库操作：用 scripts/slide_db.py

**不要手写 `sqlite3 "..."` 或内联 Python 拼 SQL** —— content 里的引号、换行、`:::` 极易把 shell 命令撑爆。统一用本 skill 的 `scripts/slide_db.py`，它从文件/stdin 读内容，自动向上查找 `db.sqlite3`，并正确填充 NOT NULL 的 `html_cache`/`content_hash`（留空，首次访问页面时由渲染管线回填）。

```bash
SD=.claude/skills/easy-slides/scripts/slide_db.py

python3 $SD list                        # 列出全部幻灯片（id / 可见性 / 版本 / 分类 / 标题）
python3 $SD list --category demo        # 按分类过滤
python3 $SD categories                  # 列出分类表
python3 $SD get <id>                    # 打印内容到 stdout
python3 $SD get <id> -o /tmp/s.md       # 内容写入文件（方便先读后改）

# 创建：先把 Markdown 写进文件，再插入
python3 $SD create --title "标题" --category demo --file /tmp/slide.md
python3 $SD create --title "标题" --category demo --file /tmp/slide.md --publish   # 直接公开(lock=0)

# 更新：覆盖内容 / 改标题 / 改分类（任意组合）
python3 $SD update <id> --file /tmp/slide.md
python3 $SD update <id> --title "新标题" --category ClaudeCode
cat /tmp/slide.md | python3 $SD update <id> --file -   # stdin

python3 $SD publish <id>                # 解锁公开（lock=0）
python3 $SD delete <id>                 # 软删除进回收站（web 端可恢复）
python3 $SD delete <id> --purge         # 彻底删除（不可恢复）
```

写入大段内容的标准姿势：用 heredoc 或 Write 工具先落到 `/tmp/slide.md`，再 `create`/`update --file`。

新建的幻灯片默认 `lock=1`（私有）；公开用 `--publish` 或事后 `publish <id>`。

### 渲染相关（可选）

幻灯片在网页首次访问时自动渲染并缓存。若需立即强制重渲（如语法管线刚改过），用 venv 跑（`render` 会 `django.setup()`，须让项目根在 `PYTHONPATH` 上，否则报 `No module named 'easy_slides'`）：

```bash
PYTHONPATH=. .venv/bin/python .claude/skills/easy-slides/scripts/slide_db.py render <id>
```

它走 `slideapp.html_converter.convert_and_cache`，刷新 `html_cache` 与 `content_hash`。（`list`/`get`/`create`/`update` 等纯 SQLite 操作不需要 `PYTHONPATH`，只有 `render` 需要。）

## 工作流程

### 创建新幻灯片
1. **确认主题**：主题、目标受众、预计时长。
2. **读 `SLIDE_SYNTAX.md`**（如尚未在本会话读过）。
3. **生成大纲**：封面 → 目录 → 3–5 个 PART → Thanks，与用户确认后再写正文。
4. **生成完整 Markdown**，严格遵循 jyyslide-md 语法与下方自检清单。
5. **写入临时文件 → `slide_db.py create`**。
6. **告知 ID**，建议访问 `http://localhost:10001/` 预览（起服务：`./start_local.sh`）。

### 编辑现有幻灯片
1. `slide_db.py get <id> -o /tmp/s.md` 读出内容。
2. 与用户确认要改什么。
3. 改 `/tmp/s.md` → `slide_db.py update <id> --file /tmp/s.md`。
4. 报告修改摘要。

## 生成前自检清单

- [ ] 分隔符（`---`/`----`/`++++`/`--`/`+++++`）独占一行且前后各有空行？
- [ ] 正文里没有意外的 3 个以上连续 `-` 或 `+`？
- [ ] 没有使用 Setext 标题？
- [ ] 每个 `---` 后第一页是 H1 大章节封面（只放两行 `#`）？
- [ ] 每个 `----` 后子页以 `##` 开头？
- [ ] 代码块都标了语言？
- [ ] 图片用 `<img>` 控制了对齐和大小？
- [ ] 表格表头分隔行完整？
- [ ] `:::columns` / `:::column` / 收尾 `:::` 都独占一行，且整块在同一张幻灯片内闭合（未跨 `---`/`----`）？
- [ ] 用到的 `:::` 关键字拼写正确（拼错会按普通文本输出、看不到样式）？
- [ ] `:::incremental` 块里确实包了一个 list？`:::timeline` 行符合 `- DATE: EVENT`？
- [ ] 子页内容不过满（超一屏就拆页或用 `--` 渐进揭示）？
- [ ] 以 Thanks / Q&A 页收尾？

## 写作风格（jyy 风格速记）

简短（每条 bullet 一句话，标题 ≤ 16 字）；先结论后论据；善用 `> blockquote` 放金句/提示/出处；善用对照表做概念辨析；代码块能直接复制运行 + 1–3 条说明；emoji 点缀每页 ≤ 1 个放在章节标题尾；专有名词保留英文（Context Window / MCP 等）。完整风格规则见 `SLIDE_SYNTAX.md`。

## 同步约束（改语法时务必遵守）

项目 CLAUDE.md 要求：任何语法/文档变动须**三处同步** —— `SLIDE_SYNTAX.md`、`AGENTS.md`、`.claude/agents/slides-maker.md`（后两者 byte-level 一致）。本 skill 刻意**不**复制完整语法、只引用 `SLIDE_SYNTAX.md`，因此不构成第四个同步点；若语法变动，仍只需维护那三处。
