> 本项目基于 [xieyumc/jyySlideWeb](https://github.com/xieyumc/jyySlideWeb) 修改而来，原作者保留所有权利。本 fork 修复了若干 bug 并添加了新功能。

# feature🚀
可以尝试访问在线[demo](http://slide.yuyu.pub/public/)，直接查看效果👀

![realtime-converter.gif](staticfiles/img/realtime-converter.gif)
> 实时转换：左边输入markdown，右边可以实时看到生成的效果

<br><br>


![realtime-preview.gif](staticfiles/img/realtime-preview.gif)
>幻灯片自动切换到正在编辑位置：右边幻灯片预览会和左边编辑位置实时对应，方便查看效果


![auto-save.png](staticfiles/img/auto-save.png)
> 自动保存：编辑幻灯片时每分钟都会自动保存一次，并且在关闭窗口，返回主页时都会自动保存

<br><br>


![auto-title.jpg](staticfiles/img/auto-title.jpg)
> 自动读取标题：幻灯片的标题会自动从文章中读取，由第一个#标题决定

<br><br>


![auto-upload-img.gif](staticfiles/img/auto-upload-img.gif)
> 快捷插入图片：可以直接拖拽或者ctrl+v粘贴图片到编辑器中，图片会自动上传到服务器，生成的链接会自动转换成markdown格式，插入到编辑器中

<br><br>


![codemirror-editor.gif](assets/codemirror-editor.gif)
> CodeMirror 6 源码模式编辑器：采用高亮显示的 Markdown 源码视图代替普通文本输入框，提供更专业、流畅的代码编辑体验，对标题、粗体、链接、代码块、列表和分割线等进行视觉增强，同时保持 Markdown 语法可见，易于编辑。

<br><br>


![img.png](staticfiles/img/public-mode.png)
> 公开分享幻灯片：幻灯片默认需要密码才能访问，也可以设置成公开的来分享，在公开模式下幻灯片是只读的

<br><br>


![category-lanes.png](assets/category-lanes.png)
> 幻灯片分类与拖拽排序：支持将幻灯片卡片分门别类整理（如 Inbox 和自定义分类），支持通过拖拽在不同分类栏之间移动卡片或在栏内调整显示顺序。

<br><br>


## 扩展 Markdown 方言：`:::` 块级指令 + 内联格式

在原有 jyy 语法（`---` / `----` / `++++` / `--`）基础上，新增了一组 `::: <keyword> ... :::` 块级指令，覆盖技术分享 / 学术汇报常见排版需求：

| 指令 | 用途 |
|---|---|
| `:::columns 40/60` | 单页内左右 / 多列布局，CSS Grid `fr` 自动归一化比例（`1/2`、`30/30/40` 都行） |
| `:::note` `:::tip` `:::warning` `:::danger` `:::success` | 五种配色提示框，支持自定义标题与内嵌 Markdown |
| `:::incremental` | 列表逐条揭示（替代连绵 `--` fragment） |
| `:::timeline` | 时间线（`- DATE: EVENT` 格式，三栏对齐 + 圆点 + halo） |
| `:::notes` | 演讲者备注（听众看不到） |

支持任意嵌套（提示框里套分栏、分栏里套提示框都行），代码栅栏内的 `:::` 字面量原样保留，未知关键字降级为普通文本不报错。

同时启用了一批 Markdown 扩展：`==高亮==`、`H~2~O` 下标、`E=mc^2^` 上标、`:rocket:` emoji 短代码、`- [x]` 任务列表、`[^1]` 脚注、定义列表。

完整语法手册见 [SLIDE_SYNTAX.md](SLIDE_SYNTAX.md)；新建幻灯片时的默认模板里也带有所有方言的范例。

<br><br>


## 用 AI 写幻灯片：jyy-slides Claude Code Skill

仓库内置了一个 [Claude Code](https://docs.claude.com/en/docs/claude-code) skill —— [`.claude/skills/jyy-slides`](.claude/skills/jyy-slides)，让 LLM 直接按 jyy 方言写稿并落库。

- **自动遵循语法**：skill 以 [SLIDE_SYNTAX.md](SLIDE_SYNTAX.md) 为唯一权威，内置分隔符禁区与生成前自检清单，避免最常见的解析翻车。
- **安全读写数据库**：附带 `scripts/slide_db.py`，对 `slideapp_slide` 表做 list / get / create / update / delete / publish，从文件或 stdin 读 content，规避引号转义并正确填充 `html_cache` / `content_hash`。

```bash
SD=.claude/skills/jyy-slides/scripts/slide_db.py
python3 $SD list                                                  # 列出全部幻灯片
python3 $SD create --title "标题" --category demo --file slide.md  # 从文件建一张
python3 $SD update <id> --file slide.md                           # 覆盖内容
python3 $SD publish <id>                                          # 解锁公开
```

在仓库目录里用 Claude Code 说「帮我做一份关于 X 的幻灯片」即可触发。

<br><br>


# 快速安装
> 本项目可以在任何平台运行，针对Windows平台还有编译好的exe文件，而其他平台推荐使用docker安装

## Windows直接运行编译好的exe

在[release](https://github.com/xieyumc/jyySlideWeb/releases)网页中，下载`jyy_slide_web.zip`，下载后解压压缩包（请完整解压，不要只解压exe）打开`jyy_slide_web.exe`即可运行
> 使用这个方式部署，实时转换时效率很低，转换很慢，我正在尝试解决这个问题，如果你有解决方案，欢迎PR
>
项目会运行在本地10001端口，接下来请参考下一节的[快速上手](#快速上手)进行操作

- 文章数据会存储在`_internal`文件夹中的`db.sqlite3`文件中
- 上传图片的图片在`_internal`文件夹中的`media`文件夹中 
- 若要升级软件后需要迁移数据，只需要复制这两个文件夹即可


## 使用docker安装

在仓库根目录下载：

- [docker-compose.yml](docker-compose.yml)
- [db.sqlite3](db.sqlite3)

然后在本地创建一个`media`文件夹，这个文件夹是存放上传图片用的

此时，你的目录结构应该是这样的：

```
├── docker-compose.yml
├── db.sqlite3
└── media
    └── xxx.img
```
然后，你需要在[docker-compose.yml](docker-compose.yml)文件中，修改CSRF_TRUSTED_ORIGINS
```
environment:
  - CSRF_TRUSTED_ORIGINS=https://localhost,https://yourdomain.com  # 定义CSRF信任域
```
这个环境变量是用来定义CSRF信任域的，如果你的域名是`yourdomain.com`，那么你需要把`https://yourdomain.com`改成你的域名（如果你不使用https，也可以不设置）


然后运行：

```bash
docker-compose up
```

项目会运行在本地10001端口，并且借助watchtower，会自动更新容器

接下来请参考下一节的[快速上手](#快速上手)进行操作

## 从源码安装

- 下载源码

- 切换到项目根目录

- `pip install -r requirements.txt`

- `daphne -p 10001 jyy_slide_web.asgi:application`

项目会运行在本地10001端口，接下来请参考下一节的[快速上手](#快速上手)进行操作


# 快速上手

## 访问主页和修改密码
安装好项目后，访问`http://localhost:10001/` 即可访问主页

默认账号是`admin`，密码是`admin@django`

若需要修改密码，请访问`http://localhost:10001/admin/` 然后点击右上角的`Change password`

## 编写幻灯片
访问`http://localhost:10001/` ，点击`新建幻灯片`

![index.png](assets/category-lanes.png)

可以看到我已经写好了两张教程幻灯片，基础语法可以直接配合幻灯片内容进行学习

## 分享幻灯片
每张幻灯片创建时默认都是上锁的（左上角的锁）

![slide-lock.png](staticfiles/img/slide-lock.png)

如果需要分享幻灯片，可以点击左上角锁的按钮，这个幻灯片就会变成公开幻灯片

然后访问`http://localhost:10001/public/` 即可看到所有公开的幻灯片，这个界面不需要密码也可以访问

在这个公开模式下，幻灯片是只读的，并且没有编辑框，会直接进入全屏展示


![img.png](staticfiles/img/public-mode.png)

# 配置nginx

如果需要配置nginx，由于本项目使用了websocket，需要一些特殊的设置，可以参考下面的配置

## http配置
```nginx
server {
    listen 80;
    server_name yourdomain.com;  # 填写你的域名

    location / {
        proxy_pass http://127.0.0.1:10001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Referer $http_referer;
        proxy_set_header Origin $http_origin;

        # WebSocket 特别配置
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    # 为 /static 路径的静态资源设置缓存策略
    location /static/ {

        proxy_pass http://127.0.0.1:10001;  # 代理到后端服务器
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Referer $http_referer;
        proxy_set_header Origin $http_origin;
        
        # 设置浏览器缓存头，缓存30天
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";

        # 允许跨域（如果需要）
        add_header Access-Control-Allow-Origin *;

        # 禁用日志（可选，减少日志量）
        access_log off;
        }
        
    }
```

## https和http/3配置
```nginx
server {
        listen 443 ssl;
        listen 443 quic;
        listen [::]:443 quic;
        http2 on;

        server_name yourdomain.com;  # 填写你的域名

        ssl_certificate /etc/nginx/certs/       # 你的SSL证书
        ssl_certificate_key /etc/nginx/certs/   # 你的SSL证书
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        location / {
            proxy_pass http://127.0.0.1:10001;
            
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Referer $http_referer;
            proxy_set_header Origin $http_origin;

            # WebSocket 特别配置
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            add_header Alt-Svc 'h3=":443"; ma=86400';


        }

        # 为 /static 路径的静态资源设置缓存策略
        location /static/ {
            proxy_pass http://127.0.0.1:10001;  # 代理到后端服务器
            
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Referer $http_referer;
            proxy_set_header Origin $http_origin;

            # 设置浏览器缓存头，缓存30天
            expires 30d;
            add_header Cache-Control "public, max-age=2592000";
            
            # 允许跨域（如果需要）
             add_header Access-Control-Allow-Origin *;

            # 禁用日志（可选，减少日志量）
            access_log off;
            add_header Alt-Svc 'h3=":443"; ma=86400';


        }
    }
```
# 感谢🙏

本项目的灵感来源为南京大学的[jyy老师](https://jyywiki.cn)

本项目基于[jyyslide-md](https://github.com/zweix123/jyyslide-md)开发，感谢大佬已经把转换逻辑完善了，本人只是做了一些微小的工作
