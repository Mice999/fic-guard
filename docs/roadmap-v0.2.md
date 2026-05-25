# Roadmap v0.2: 降低使用门槛

> 这份文档是写给 Claude Code 看的（也写给未来回到这个项目的人看）。
> 目标：让非技术创作者也能用上 fic-guard。
>
> **如果你是 Claude Code，请在动手之前先完整读完这份文档，特别是"硬约束"和"现有架构不要动的部分"两节。**

## 0. 上下文：这个项目是什么

`fic-guard` 是给 fiction 创作者的自保工具。当前 v0.1.0 已经实现了 fingerprint、timestamp、monitor、safe-publish 四个核心命令，全部是 Python CLI。详见 [README](../README.md) 和 [threat-model](threat-model.md)。

v0.2 的核心痛点：**安装门槛太高**。目标用户是同人写手，其中相当一部分没装过 Python、没用过命令行。当前的"装 Python → 开终端 → pip install → 跑命令"流程，会在第 1 步就劝退一大半人。

## 1. 硬约束（不许违反，不许"优化"掉）

这些是项目的设计立场，不是技术细节：

1. **绝不爬取任何第三方站点的数据。** 不实现"自动监控某站点是否搬运了作品"的爬虫，不实现绕过任何站点反爬措施的代码。`monitor` 只生成搜索 URL，最多调用搜索引擎的公开 HTML 接口。
2. **绝不实现"公示墙"/"举报"功能。** 不收集、不展示、不传输任何关于第三方用户、群组、站点的指控性信息。理由见 [why-not-a-callout-site.md](why-not-a-callout-site.md)。
3. **本地优先。所有用户数据不上传任何服务器。** 即使是"匿名遥测"也不要加。新功能涉及网络的，必须 opt-in（明确的 `--network` 类似开关）。
4. **不引入用户身份。** 不要加登录、不要加云同步、不要加"用户账号"概念。
5. **不引入需要服务端的功能。** v0.2 范围内全部是本地工具。私密预警网络的事情留到 v0.3+ 单独立项。
6. **不在代码里硬编码任何具体平台名 / 用户名 / 群号 / 域名作为"已知爬虫"。** 哪怕作为示例也不行。

## 2. 现有架构不要动的部分

如果你想动以下东西，先停下来，去开一个 issue 讨论，不要直接改：

- `src/fic_guard/fingerprint/__init__.py` 的零宽水印编码（ZW_ZERO/ZW_ONE/ZW_DELIM）——一旦改了，老的水印就解不出来了，会让早期用户白做了
- `Fingerprint` 和 `Proof` dataclass 的字段名——已经写到 JSON 里了，要保持向后兼容
- `safe_publish` 的题目内容和打分逻辑——这是和用户体验直接相关的，改之前先在 issue 里讨论措辞
- CLI 命令名（`fingerprint make`、`timestamp make` 等）——已经写在 README 里教用户用了，不要重命名

可以动 / 应该动 的部分：内部实现细节、错误处理、性能优化、添加新命令、添加新模块。

## 3. v0.2 任务清单

按优先级从高到低排。**做完一项就提一个 PR**，不要把所有东西攒一起。

### P0: 单文件可执行（让 Windows 用户能双击运行）

**目标**：创作者下载一个 `fic-guard.exe`（或 macOS 上的 `.app`、Linux 上的 ELF），双击就能用，不需要装 Python。

**实现路径**：

1. 用 [PyInstaller](https://pyinstaller.org) 打包。Nuitka 也可以但更复杂，先用 PyInstaller。
2. 在 `.github/workflows/` 里加 `release.yml`，当推送 tag（如 `v0.2.0`）时自动在 ubuntu / windows / macos 三个 runner 上 build，把产物上传到 GitHub Release。
3. 不要在仓库里 commit 任何 build 产物。
4. 在 README 里加"下载预编译版"小节，链到 GitHub Release 页。

**验收标准**：

- `git tag v0.2.0-test && git push --tags` 触发 release workflow，三个平台都产出可执行文件
- 在一台没装 Python 的机器上，下载 `fic-guard.exe`，能跑通 `fic-guard guide`、`fic-guard fingerprint make examples\sample.txt --work-id demo`
- 文件大小 < 30MB

**陷阱预警**：

- PyInstaller 打包 `rich` 库时偶尔丢资源文件，需要 `--collect-all rich`。`click` 通常没问题。
- Windows 上的 console 编码默认是 GBK，对中文输出可能出乱码。可能需要在 `cli.py` 入口处加 `sys.stdout.reconfigure(encoding='utf-8')`（Python 3.7+）。
- macOS 上的 binary 默认没签名，用户双击会被 Gatekeeper 拦。这一步**不要花钱去搞 Apple 开发者签名**——在 README 里说明用户怎么 `chmod +x` 并在 Gatekeeper 里放行就够了。

### P1: 本地 Web UI（让不爱命令行的人也能用）

**目标**：创作者跑一条命令 `fic-guard web`，自动打开浏览器，所有功能用页面操作。

**实现路径**：

1. 新建 `src/fic_guard/web/` 模块。技术选型：**Flask + 服务端渲染的简单 HTML（Jinja2 模板）**。不要用 React/Vue，会让单文件可执行那条路变得复杂。
2. 默认绑定 `127.0.0.1`（**绝对不要绑 0.0.0.0**——这是本地工具，不应该被局域网其他人访问）。
3. 端口随机选一个可用的（用 socket 抢一个空闲端口），避免和别的程序冲突。
4. 启动时 `webbrowser.open()` 自动打开。
5. 关闭浏览器或按 Ctrl+C 时优雅退出。
6. 页面功能（先做这几个，每个对应一个路由）：
   - `/` —— 首页，简介 + 4 个功能入口
   - `/fingerprint` —— 上传或粘贴文本 → 生成指纹 → 下载 JSON
   - `/timestamp` —— 同上，生成存证
   - `/watermark` —— 输入文本 + payload → 嵌入水印 → 下载结果
   - `/safe-publish` —— 把交互式清单做成单页表单，提交后给出评级和建议
   - `/monitor` —— 上传指纹 JSON → 显示搜索 URL 列表（带"全部打开"按钮）

**验收标准**：

- `fic-guard web` 启动后浏览器自动打开
- 所有 5 个功能在浏览器里能完成完整流程
- 跑 PyInstaller 打包后，单文件可执行版本里 `fic-guard.exe web` 也能用
- 任何上传的文件只在内存里处理，不写入临时目录之外的地方；离开页面后内存释放

**安全要求（这一节必看）**：

- **CSRF**：表单提交必须带 CSRF token。即使是本地服务，也要防恶意网站通过用户浏览器对 `127.0.0.1` 发请求。用 `flask-wtf` 或自己实现 token。
- **Host 头校验**：拒绝非 `127.0.0.1`/`localhost` 的 Host 头，防 DNS rebinding 攻击。
- **不接受任意路径写入**：用户"下载"产物应通过 `send_file` 内存流，不要落地到用户指定的路径。
- **不暴露文件系统**：不要做"浏览本地文件夹"这种功能。文件交互只通过 `<input type="file">` 上传和 `Content-Disposition: attachment` 下载。

**陷阱预警**：

- 如果用 PyInstaller 打包，Flask 的模板文件需要 `--add-data` 显式带上。建议把模板放进 `src/fic_guard/web/templates/`，并用 `importlib.resources` 读取，对打包友好。
- 不要用 `app.run(debug=True)` —— 那会启用 Werkzeug debugger，是一个远程代码执行口子。用 `waitress` 作为 WSGI server 更稳。

### P2: 非技术用户安装指南

**目标**：一份带截图的、对零编程经验用户友好的安装文档。

**实现路径**：

1. 新建 `docs/install-for-writers.md`
2. 内容：
   - "如果你只想要一个能直接用的程序" → 引导到 GitHub Release 下载预编译版（依赖 P0 完成）
   - "如果上面那条路不行" → Python 安装步骤，每一步配截图（Windows / macOS 分开写）
   - 装好之后第一次怎么用：跑 `fic-guard web` 打开浏览器（依赖 P1 完成）
   - 常见报错和对应解决方案（"找不到 fic-guard 命令"、"pip 报错"、"中文乱码"等）
3. 截图放在 `docs/images/install/`，用通用一点的系统语言（中文界面 + 英文系统都给一份更友好）

**验收标准**：

- 找一个不写代码的朋友按这份文档操作一遍，能装上能跑通
- 文档里不出现任何只有程序员才看得懂的术语而不解释

**注意**：写这份文档时**不要嘲讽**任何"不会用命令行"的用户。同人圈很多人是文字工作者、艺术从业者，不写代码不代表笨——他们只是没必要学这些。

### P3: 长篇分章节批量处理

**目标**：当前 `fingerprint make` 一次只处理一个文件。长篇可能几十章，应该支持目录级输入。

**实现路径**：

1. `fingerprint make` 接受目录作为输入：自动遍历 `.txt` / `.md` 文件，每个文件生成一个独立的指纹，`work-id` 自动用文件名（可选 `--prefix` 前缀）
2. `timestamp make` 同上
3. 新加 `fic-guard batch report <fingerprint-dir>` 命令：聚合多个指纹生成一个 HTML 报告，方便创作者打印归档作为证据材料

**验收标准**：

- 对一个含 50 个 `.txt` 文件的目录跑 `fic-guard fingerprint make ./book --prefix mybook` 能正确生成 50 个指纹文件
- 顺序确定（按文件名排序），不会因为操作系统不同而产生不同结果
- 大文件（单个 1MB+ 文本）不会让程序明显卡顿

### P4（不做，仅记录）: 以下事情不要在 v0.2 里做

- 任何形式的"自动跨站搜索结果分析"（属于爬虫范畴）
- 任何形式的账号系统、云同步
- 移动端 App
- 浏览器扩展（除非你愿意承担非常严肃的安全审查；浏览器扩展能读取所有页面内容，威胁模型完全变了）
- 集成 LLM 来"判断是不是抄袭"（成本高、误判高、给用户错误的安全感）

## 4. Claude Code 的工作姿势建议

(给操作 Claude Code 的人看)

1. 把这份文档作为 Claude Code 会话的初始上下文。建议第一句话就说："请先读 `docs/roadmap-v0.2.md`，然后我们从 P0 开始。"
2. 一次只让它做一个 P 级任务，做完一个 PR，本地跑一遍测试，没问题再开始下一个。
3. 每次 PR 提交前，让 Claude Code 自己跑：
   ```
   pytest tests/ -v
   fic-guard guide  # 烟囱测试
   ```
4. 如果 Claude Code 想加新依赖，先问问自己：这个依赖会不会让 PyInstaller 打包变难？常见的会增加体积或带来打包问题的库：torch、transformers、playwright、selenium。能不加就不加。
5. 如果 Claude Code 提出的方案违反了"硬约束"一节，**不要让它继续**——这是项目立场问题，不是技术问题。可以问它："你这个方案是不是违反了 roadmap 里的第 X 条约束？"通常它会承认并换方案。

## 5. 测试覆盖目标

v0.2 完成时，以下应该都有测试覆盖：

- [x] fingerprint 的核心逻辑（v0.1 已有）
- [x] timestamp 的核心逻辑（v0.1 已有）
- [x] safe_publish 的打分逻辑（v0.1 已有）
- [ ] web 路由：每个路由的 happy path + 一个错误路径
- [ ] web 安全：CSRF token 校验、Host 头校验、超大文件拒绝
- [ ] batch：目录输入、文件名排序确定性

## 6. 发布节奏

- P0 完成 → tag `v0.2.0-alpha.1`，发预编译版
- P1 完成 → tag `v0.2.0-alpha.2`
- P2、P3 完成 → tag `v0.2.0`，正式版

每次 tag 之前更新 `CHANGELOG.md`（这个文件 v0.1 还没有，第一个 PR 顺手建一下）。
