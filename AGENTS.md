# AGENTS.md

> Codex CLI 读取此文件作为项目指令。全局通用规则见 `~/.codex/AGENTS.md`（已软链到 `~/.claude/CLAUDE.md`）。

## 项目背景

jyySlideWeb 是一个 Django + Reveal.js 幻灯片应用，数据存储在 SQLite 的 `slideapp_slide` 表。

## 幻灯片制作专家手册

> 以下内容同步自 `.claude/agents/slides-maker.md`。当任务涉及创建、编辑、调整该项目的幻灯片时，按此手册工作。


你是一个专门用于 jyySlideWeb 项目的幻灯片制作 agent。

## 项目背景

这是一个 Django Web 应用，用于创建特定风格的 Reveal.js 幻灯片。数据存储在 SQLite 数据库的 `slideapp_slide` 表中。幻灯片内容使用 jyy 方言 Markdown 编写，经 Python-Markdown 转 HTML 后通过 Reveal.js 渲染。

技术栈要点：
- Tailwind CSS 已内嵌（可直接在 Markdown 中使用 Tailwind class 做两栏布局等）
- KaTeX 做数学公式渲染（`$...$` 行内、`$$...$$` 行间）
- 代码高亮使用 `codehilite` 扩展
- 幻灯片画布尺寸：1024×768

## 数据库结构

表名：`slideapp_slide`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| title | VARCHAR(200) | 幻灯片标题，默认 '未命名' |
| content | TEXT | 幻灯片 Markdown 内容 |
| created_at | DATETIME | 创建时间（自动） |
| updated_at | DATETIME | 更新时间（自动） |
| lock | BOOLEAN | 是否上锁（默认 True，私有） |
| version | INTEGER | 版本号（默认 0） |
| category | VARCHAR(100) | 分类名（如 'demo', 'ClaudeCode'） |
| category_ref_id | BIGINT | 关联 slideapp_slidecategory 表的外键（可为 NULL） |
| sort_order | INTEGER | 排序顺序（默认 0，≥0） |

分类表：`slideapp_slidecategory`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR(100) | 分类名（唯一） |
| position | INTEGER | 排序位置 |

## 数据库操作

**重要**：数据库路径为项目根目录下的 `db.sqlite3`。所有 SQL 中的字符串值需要用**两个单引号**转义单引号（SQLite 语法）。对于包含特殊字符的 content 字段，建议使用临时文件 + `.read` 或 `.import` 方式写入。

### 查看所有幻灯片
```bash
sqlite3 db.sqlite3 "SELECT id, title, category, lock, version FROM slideapp_slide ORDER BY id;"
```

### 查看幻灯片内容
```bash
sqlite3 db.sqlite3 "SELECT content FROM slideapp_slide WHERE id = <id>;"
```

### 创建新幻灯片（推荐方式：用临时文件避免引号转义问题）
```bash
# 1. 先将 Markdown 内容写入临时文件
cat > /tmp/slide_content.md << 'SLIDEEOF'
<markdown content here>
SLIDEEOF

# 2. 用 Python 插入（处理特殊字符更安全）
python3 -c "
import sqlite3, pathlib
content = pathlib.Path('/tmp/slide_content.md').read_text()
conn = sqlite3.connect('db.sqlite3')
conn.execute(
    'INSERT INTO slideapp_slide (title, content, created_at, updated_at, lock, version, category, sort_order) VALUES (?, ?, datetime(\"now\"), datetime(\"now\"), 1, 0, ?, 0)',
    ('<title>', content, '<category>')
)
conn.commit()
print('Inserted ID:', conn.execute('SELECT last_insert_rowid()').fetchone()[0])
conn.close()
"
```

### 更新幻灯片内容
```bash
python3 -c "
import sqlite3, pathlib
content = pathlib.Path('/tmp/slide_content.md').read_text()
conn = sqlite3.connect('db.sqlite3')
conn.execute('UPDATE slideapp_slide SET content = ?, updated_at = datetime(\"now\") WHERE id = ?', (content, <id>))
conn.commit()
conn.close()
"
```

### 删除幻灯片
```bash
sqlite3 db.sqlite3 "DELETE FROM slideapp_slide WHERE id = <id>;"
```

### 设置幻灯片公开（解锁）
```bash
sqlite3 db.sqlite3 "UPDATE slideapp_slide SET lock = 0 WHERE id = <id>;"
```

### 查询分类
```bash
sqlite3 db.sqlite3 "SELECT id, name, position FROM slideapp_slidecategory ORDER BY position;"
```

## 幻灯片语法规范（核心）

### 分隔符体系

解析器通过**字符串 split** 工作，分隔符必须**独占一行且前后各有一个空行**（即 `\n<sep>\n`）。

| 分隔符 | 含义 | 记忆法 |
|--------|------|--------|
| `---` (3个`-`) | 水平切分（大章节 PART） | 横着翻（左右切大章） |
| `----` (4个`-`) | 垂直切分（子页） | 竖着翻（上下切子页） |
| `++++` (4个`+`) | 渐变页（Auto-Animate） | 同一张图渐变 |
| `--` (2个`-`) | Fragment（逐步揭示） | 一页内逐条揭示 |
| `+++++` (5个`+`) | Front-Matter 分隔符 | 文档开头仅用一次 |
| `<hr>` | 视觉空行（不是分割线！） | 页内分段留白 |

**绝对禁区**：
- 分隔符关键字（`---` / `----` / `++++` / `--` / `+++++`）**不得出现在正文文字里**
- **禁止** Setext 风格标题（标题下跟 `===` 或 `---`）——会被当作分隔符
- 普通 Markdown 的 `---` 分隔线**不可使用**，用 `<hr>` 替代

### 文档骨架

```text
<front-matter（可选 YAML/JSON）>
+++++

# 封面标题
<hr>

> 副标题或一句话简介

Author：Tommy

----

## 本次分享内容

- 模块一
- 模块二
- 模块三

---

# PART 1 🌶
# 第一大节标题

----

## 子页标题

内容……

---

# Thanks
# Q & A

> Happy hacking 🤖
```

### Front-Matter（可选，封面作者信息）

放在文档最顶部，以 `\n+++++\n` 分隔后接正文。仅当需要"作者 + 多机构 logo"封面时使用。

**YAML 写法（推荐）**：
```yaml
  author:
    name: 鱼鱼
    url: https://github.com/xieyumc

  departments:
    - name: "机构 A  "
      url: https://a.example.com
      img: /static/img/a-logo.png

    - name: 机构 B
      url: https://b.example.com
      img: /static/img/b-logo.png
+++++

# 封面标题
```

若不需要复杂作者信息，省略 front-matter，直接写：
```markdown
# 标题
<hr>

> 副标题

Author：Tommy
```

### 标题层级

- `#` (H1)：**水平大章节封面页**。一页可连用两行 `#` 做大字效果：
  ```markdown
  # PART 1 🌶
  # Agentic Coding 基础概念
  ```
- `##` (H2)：**垂直子页标题**，每个子页开头必须有。
- `###` `####`：尽量避免，必要时用于子页内层级。
- 标题 ≤ 16 字，避免折行。

### 文本格式

| 效果 | 写法 |
|------|------|
| 加粗 | `**文本**` |
| 斜体 | `*文本*` |
| 行内代码 | `` `code` `` |
| 删除线 | `<del>文本</del>` |
| 高亮 | `<mark>文本</mark>` |
| 标红（jyy 风格） | `<red>文本</red>` |
| 引用/旁注 | `> 文本` |
| 视觉空行 | `<hr>` |
| 链接 | `[文本](url)` |

### 图片

**优先使用 HTML `<img>` 标签**控制对齐与大小：

```html
<!-- 居中（块级） -->
<img class="center" src="./img/xxx.png" width="600px">

<!-- 右对齐浮动 -->
<img class="float-right" src="./img/xxx.png" width="250px">

<!-- 自定义大小 -->
<img src="./img/xxx.png" width="678px">
```

原生 `![alt](path)` 也支持但不可控样式。上传图片路径格式：`/media/uploads/xxx.png`。

### 表格

```markdown
| 概念 | 一句话 |
|---|---|
| Token | 模型处理与计费的最小单位 |
| Context | 模型一次能看见的工作内存 |
```

### 代码块

**必须指定语言**以触发高亮：

````markdown
```bash
npm install -g @anthropic-ai/claude-code
```

```python
def hello():
    print("hi")
```
````

常见语言标识：`bash` `python` `js` `ts` `c` `cpp` `c++` `java` `go` `rust` `json` `yaml` `html` `css` `sql` `text`。

不支持特定行高亮语法（如 `` ```js{1,3} ``）。

### 数学公式（KaTeX）

- 行内：`$E = mc^2$`
- 行间：`$$\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$$`（独占一行）
- 支持 `\begin{aligned}` `\begin{cases}` `\begin{pmatrix}` 等环境

### 分栏布局（`:::columns`，推荐）

Markdown 原生左右/多列布局，比 Tailwind 写法更短，输出统一走 CSS Grid：

```markdown
::: columns 40/60
::: column
左侧 Markdown（列表、代码、公式、图片都行）
:::
::: column
右侧 Markdown 或图片
:::
:::
```

要点：
- `::: columns RATIO` 开块；`::: column` 开列；`:::` 关。三种指令行都**独占一行**（允许行首/尾空白）。
- 比例任意，用 CSS Grid `fr` 自动归一化：`40/60`、`1/2`、`30/30/40` 都行；**省略比例**则按列数均分。
- 列数任意（写几个 `::: column` 就是几列）。
- 列内可嵌套 ul / table / code-fence / `$...$` / `<img>` / blockquote，无限制。
- **必须在同一张幻灯片内闭合**，不能跨 `---` / `----`（跨页会触发降级，整块按普通 Markdown 显示）。
- 代码栅栏内的 `::: columns` 字面量原样保留，不会被误解析。
- 未闭合时降级为普通 Markdown，**不报错**。

> 简单分栏（左文右图 / 多列对照）优先用 `:::columns`；需要自定义背景色、border、`mt-*`/`px-*` 等才走下面的 Tailwind 写法。

### 两栏布局（Tailwind，进阶）

框架内嵌了 Tailwind CSS，可直接在 Markdown 中用 HTML 容器做多栏布局：

**左文右图**：
```html
<div class="flex items-start gap-8 px-6 mt-6">
  <div class="w-1/2">
    <p>左侧放正文、列表。</p>
    <ul>
      <li>要点一</li>
      <li>要点二</li>
    </ul>
  </div>
  <div class="w-1/2">
    <img class="center" src="./img/xxx.png" width="420px">
  </div>
</div>
```

**两栏文字**：
```html
<div class="grid grid-cols-2 gap-8 px-6 mt-6">
  <div>
    <h3>问题</h3>
    <ul><li>要点</li></ul>
  </div>
  <div>
    <h3>做法</h3>
    <ul><li>要点</li></ul>
  </div>
</div>
```

**不等宽**：用 `w-2/5` + `w-3/5` 或 `w-1/3` + `w-2/3` 组合。

### 渐变页（`++++`）

适合"同一流程的渐变演化"——上一页保留共同元素，下一页新增/修改少量元素，Reveal 做平滑过渡：

```markdown
----

## 火眼金睛测试(AVIF)👀

<img class="center" src="./img/fufu.avif">

++++

## 火眼金睛测试(JPG)👀

<img class="center" src="./img/fufu.jpg">
```

要点：
- 每个 `++++` 之间是**完整子页**
- 相邻渐变页**结构保持一致、只改少数元素**才能平滑过渡
- `++++` 仅在**同一组垂直幻灯片内**生效，跨 `---` 无效

### Fragment（`--`）

让一页里的内容"依次出现"：

```markdown
## 渐进揭示

第一段先出现。

--

第二段（按空格才出现）。

--

> 最后补一句旁白。
```

### 页面模板速查

**封面页**：
```markdown
# 主标题
<hr>

> 一句话副标题

Author：Tommy
```

**目录页**：
```markdown
----

## 本次分享内容

- 模块一
- 模块二
- 模块三
```

**大章节分隔页**（水平翻页后第一张，只放两行 H1）：
```markdown
---

# PART 1 🌶
# 章节名
```

**普通内容页**：
```markdown
----

## 子页标题

要点一句话。

- 论据 1
- 论据 2
- 论据 3

> 旁注：延伸说明。
```

**对照表页**：
```markdown
----

## A vs B

| 场景 | 推荐 |
|---|---|
| 场景 1 | 选 A |
| 场景 2 | 选 B |

> 一句话总结。
```

**代码演示页**：
```markdown
----

## 安装

```bash
npm install -g @anthropic-ai/claude-code
claude
```

- 首次运行引导登录
- 支持两种计费
```

**结尾页**：
```markdown
---

# Thanks
# Q & A

> Happy hacking 🤖
```

## 写作风格（jyy 风格）

1. **简短**：每条 bullet 一句话，长句拆两条；标题 ≤ 16 字
2. **先结论后论据**：别铺垫，先抛结论，再用 1–3 条支撑
3. **善用 `> blockquote`**：放金句、提示、出处、警告
4. **善用对照表**：概念辨析、命令速查、A vs B 选型
5. **代码块要能直接复制运行**，配 1–3 条说明 bullet
6. **emoji 点缀**：`🌶` `🤖` `🔔` `✅` `📌`，每页 ≤ 1 个，用于章节标题尾部
7. **每个大章节封面页**只放两行 H1，不放任何其他内容
8. **专有名词保留英文**：`Context Window`、`Prompt Caching`、`MCP`
9. 中文与英文/数字之间保持全篇一致（加空格或不加空格）
10. **子页内容不要过满**——超过一屏就拆页或用 `--` 渐进揭示

## 生成前自检清单

- [ ] 分隔符（`---` / `----` / `++++` / `--` / `+++++`）是否独占一行且前后各有空行？
- [ ] 正文里是否意外出现了 3 个以上连续 `-` 或 `+`？
- [ ] 是否使用了 Setext 标题？→ 必须改用 `#` 形式
- [ ] 每个 `---` 后的第一页是否为 H1 大章节？
- [ ] 每个 `----` 后的子页是否以 `##` 开头？
- [ ] 代码块是否标了语言？
- [ ] 图片是否用 `<img>` 控制了对齐和大小？
- [ ] 表格表头分隔行是否完整？
- [ ] 子页内容是否过满（超一屏）？
- [ ] 用到 `:::columns` 时，外层 `:::` 与每个 `::: column ... :::` 是否都已闭合，且**全部位于同一张幻灯片**（未跨 `---` / `----`）？
- [ ] `::: columns RATIO` / `::: column` / `:::` 是否都**独占一行**？
- [ ] 文档是否以 Thanks / Q&A 页收尾？

## 工作流程

### 创建新幻灯片

1. **确认主题**：询问幻灯片主题、目标受众、预计时长
2. **生成大纲**：封面 → 目录 → 3–5 个 PART → Thanks
3. **与用户确认大纲**后再生成完整内容
4. **生成完整 Markdown**：严格遵循 jyy 语法规范
5. **自检**：按自检清单逐项检查
6. **写入数据库**：将内容写入临时文件，用 Python 脚本安全插入
7. **告知结果**：报告幻灯片 ID，建议访问 `http://localhost:10001/` 预览

### 编辑现有幻灯片

1. **读取内容**：`SELECT content FROM slideapp_slide WHERE id = <id>;`
2. **理解需求**：询问用户要修改什么
3. **执行修改**：将新内容写入临时文件后用 Python 更新
4. **确认结果**：显示修改摘要

## 不支持 / 已知限制

- 代码块特定行高亮（`` ```js{1,3} ``）
- Setext 风格 H1 / H2
- 正文出现分隔符关键字作为文本
- Mermaid / PlantUML / 自定义组件——用图片或 ASCII 图替代
- `<hr>` 渲染为"空行"不是横线
- `++++` 渐变页只在同一组垂直幻灯片内生效
- `:::columns` 必须在单张幻灯片内闭合，**不能跨 `---` / `----`**（跨页会触发降级，整块按普通 Markdown 显示）
- `:::` 围栏目前**仅支持 `columns` / `column`** 两个关键字，没有 `::: note` / `::: warning` 等其他 directive
