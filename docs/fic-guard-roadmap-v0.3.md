# Roadmap v0.3: 持续监控与历史记录

> 写给 Claude Code 看的开发计划。动手之前请完整读完，特别是"硬约束"和"不要动的部分"。

## 0. 背景

v0.2 完成了"开包即用"的目标：双击打开浏览器，所有功能在网页上操作。

v0.3 的目标是：**从"用一次的工具"变成"一直在帮你的工具"**。

但不靠后台常驻，不靠自启动，不靠系统通知——完全靠用户主动打开时的"上次检查是 X 天前，现在检查一下吗？"这个引导。

设计原则：**用户永远在控制，工具永远透明。**

## 1. 硬约束（不许违反）

沿用 v0.2 的所有约束，额外补充：

1. **不实现开机自启。** 不写注册表，不写 launchd plist，不写任何让程序在用户不知情的情况下运行的代码。
2. **不实现系统后台常驻。** 不用 pystray，不用系统托盘，不用任何后台 daemon。
3. **不实现系统推送通知。** 不用 plyer，不用 win10toast，不用任何系统级通知 API。所有"提醒"只在用户主动打开工具时显示。
4. **SQLite 只写在 `.fic-guard/` 目录下。** 不写到系统目录、不写到用户 home 目录根部、不写到任何用户没有明确选择的地方。
5. **不收集任何使用数据。** 数据库里只存用户自己的作品信息和检查历史，不存任何可以上传或分析的遥测数据。

## 2. 不要动的部分

- 零宽水印编码常量（ZW_ZERO / ZW_ONE / ZW_DELIM）
- Fingerprint / Proof dataclass 的字段名
- 现有 CLI 命令名（fingerprint / timestamp / monitor / safe-publish / web）
- Web UI 现有路由路径（/fingerprint / /timestamp / /watermark / /safe-publish / /monitor）
- search_engines.json 的格式（刚重构完，不要改）

## 3. 新增模块：`src/fic_guard/library/`

这是 v0.3 的核心新模块，负责管理用户的作品库和检查历史。

### 3.1 数据库结构

文件路径：`.fic-guard/library.db`（SQLite）

```sql
-- 作品表
CREATE TABLE IF NOT EXISTS works (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id     TEXT NOT NULL UNIQUE,   -- 用户起的名字
    title       TEXT NOT NULL,          -- 显示用的标题
    char_count  INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    fingerprint_json TEXT NOT NULL,     -- 完整的指纹 JSON（序列化存储）
    created_at  TEXT NOT NULL,          -- ISO 8601
    last_checked_at TEXT                -- 上次检查时间，NULL 表示从未检查
);

-- 检查历史表
CREATE TABLE IF NOT EXISTS check_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id     TEXT NOT NULL,
    checked_at  TEXT NOT NULL,          -- ISO 8601
    findings_json TEXT NOT NULL         -- 本次检查发现的 URL 列表（JSON）
);

-- 发现记录表（每个 URL 一条记录）
CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id     TEXT NOT NULL,
    url         TEXT NOT NULL,
    sentence    TEXT NOT NULL,          -- 是哪条签名句触发的
    first_seen  TEXT NOT NULL,          -- 第一次发现时间
    status      TEXT NOT NULL DEFAULT 'new',  -- new / confirmed / ignored
    UNIQUE(work_id, url)                -- 同一个 URL 不重复记录
);
```

### 3.2 模块接口

`src/fic_guard/library/__init__.py` 需要提供：

```python
def get_db_path(base_dir: str | Path) -> Path:
    """返回 .fic-guard/library.db 的路径"""

def init_db(db_path: Path) -> None:
    """建表（如果不存在）"""

def add_work(db_path: Path, title: str, text: str, work_id: str) -> dict:
    """从文本生成指纹并存入数据库，返回 work 记录"""

def list_works(db_path: Path) -> list[dict]:
    """返回所有作品列表，包含 last_checked_at 和未确认发现数"""

def delete_work(db_path: Path, work_id: str) -> None:
    """删除作品及其所有历史记录"""

def run_check(db_path: Path, work_id: str) -> dict:
    """对一部作品跑一次监控，把新 URL 存入 findings 表，返回新发现数量"""

def list_findings(db_path: Path, work_id: str, status: str | None = None) -> list[dict]:
    """返回发现记录，可按 status 过滤"""

def update_finding_status(db_path: Path, finding_id: int, status: str) -> None:
    """更新发现记录的状态（new / confirmed / ignored）"""

def get_summary(db_path: Path) -> dict:
    """返回全局摘要：作品总数、未确认发现总数、最早的未检查作品"""
```

## 4. Web UI 改动

### 4.1 首页改造（最重要）

首页 `/` 从静态功能列表变成**动态仪表盘**：

```
fic-guard — 创作者自保工具箱

[如果有未确认发现]
⚠️  有 3 部作品发现了新的搜索结果，建议查看。  [查看详情]

[作品库摘要]
已监控 5 部作品   上次全量检查：2 天前   [现在检查全部]

[作品列表]
《XXX》        上次检查：3天前    新发现：2    [检查] [查看]
《YYY》        上次检查：1天前    新发现：0    [检查] [查看]
《ZZZ》        从未检查           —           [检查] [查看]

[底部]
[+ 添加新作品]    [发布自检]    [时间戳存证]    [零宽水印]
```

**关键交互**：
- "现在检查全部"：对所有作品依次跑 `run_check()`，进度实时更新（用 SSE 或轮询）
- "检查"按钮：对单部作品跑一次检查
- "查看"按钮：跳到该作品的发现详情页

### 4.2 新增路由

- `GET /library` → 作品库首页（即改造后的首页，或者重定向）
- `GET /library/add` → 添加作品表单（填标题 + 粘贴文本）
- `POST /library/add` → 处理添加，生成指纹存入 DB
- `GET /library/<work_id>` → 单部作品详情（发现列表）
- `POST /library/<work_id>/check` → 触发检查
- `POST /library/<work_id>/delete` → 删除作品
- `POST /library/findings/<id>/status` → 更新发现状态
- `GET /library/check-all` → 触发全量检查（SSE 流式响应进度）

### 4.3 现有路由保留

`/fingerprint` / `/timestamp` / `/watermark` / `/safe-publish` / `/monitor` 全部保留，不改。
在首页底部保留入口。

## 5. `.fic-guard/` 目录说明

v0.3 之后 `.fic-guard/` 目录结构：

```
.fic-guard/
├── library.db              ← 新增，作品库和历史记录
├── <work_id>.fingerprint.json   ← 现有，手动生成的指纹
└── <work_id>.proof.json         ← 现有，时间戳存证
```

Web UI 的 library 功能使用 `library.db`，现有的独立指纹文件不受影响。

`.fic-guard/` 目录的默认位置：**用户当前工作目录下**（和 v0.2 一致）。

但有一个问题：双击 exe 启动时，工作目录是 exe 所在目录，不是用户期望的位置。
需要在 `create_app()` 里加一个逻辑：如果是 frozen 状态，把 `.fic-guard/` 放在用户 home 目录下（`Path.home() / ".fic-guard"`）。
如果是开发模式，维持现有行为（当前目录下）。

## 6. 检查进度的实时反馈

"检查全部"可能需要几十秒（每部作品要查几条签名句）。需要给用户实时进度反馈。

推荐用 **Server-Sent Events（SSE）**：
- Flask 支持流式响应，不需要额外依赖
- 前端用 `EventSource` API，纯 HTML + 少量 JS
- 进度格式：`data: {"work_id": "xxx", "status": "checking", "progress": 2, "total": 5}\n\n`

如果觉得 SSE 复杂，可以退而求其次：前端每 2 秒轮询一个 `/library/check-status` 端点，后端用内存变量存进度。后者实现简单但体验稍差。

**先用轮询实现，SSE 留到 v0.4。**

## 7. 任务清单

按顺序做，每个 PR 一个任务：

- [ ] **P0**：实现 `src/fic_guard/library/__init__.py`，包含所有接口函数，补充对应测试
- [ ] **P1**：实现新增路由（`/library/*`），对应 HTML 模板
- [ ] **P2**：改造首页为动态仪表盘
- [ ] **P3**：实现全量检查的进度轮询
- [ ] **P4**：处理 frozen 状态下 `.fic-guard/` 目录位置问题
- [ ] **P5**：更新 `build.py`，确认 `library.db` 相关依赖都被打包（sqlite3 是标准库，应该没问题）
- [ ] **P6**：更新 README，加入"作品库"功能说明

## 8. 不做的事

- 系统托盘、开机自启、后台 daemon（见硬约束）
- 推送通知
- 云同步
- 多用户
- 移动端
- 爬取任何第三方站点（monitor 只生成搜索 URL，用户手动打开）

## 9. 验收标准

v0.3 完成时，用户能做到：

1. 打开工具，在首页看到"我有几部作品在监控，上次检查是什么时候"
2. 添加一部新作品（粘贴文本，填标题）
3. 点"检查"，等几秒，看到搜索链接列表
4. 如果有新 URL，首页会有提醒
5. 点进去把某个 URL 标记为"已确认"或"忽略"
6. 下次打开工具，首页显示正确的状态
