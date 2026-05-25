# fic-guard

> 给同人 / 原创作者的自保工具箱：文本指纹、零宽水印、时间戳存证、跨站搜索、发布前自检。
> 完全本地运行，不上传任何数据，不替你联系任何平台。

## 这是什么

如果你是一名 fiction 写作者——无论是同人还是原创——你的作品可能在你不知情的情况下被搬运到其他站点、整理进资源群、或被打包贩卖。`fic-guard` 不能阻止这些事情发生（任何能被读者看到的内容，原则上都可以被复制），但它能帮你做四件具体的事：

1. **指纹**：从你的作品中挑出几条最具识别度的句子，未来你可以用这些句子去搜索引擎/可疑站点反查，确认是不是同一份内容。
2. **水印**：在文本里嵌入肉眼看不到的零宽字符标签，比如给每个发布平台嵌一个不同的标签，这样万一在第三方看到内容，能追溯泄露源头。
3. **时间戳存证**：给作品生成一份 SHA-256 哈希存证文件。配合 [OpenTimestamps](https://opentimestamps.org)，可以把"我在 X 时间已经持有这份内容"锚定到比特币区块链上，免费、无需账号，作为未来维权的证据基础。
4. **发布前自检**：一个本地交互式清单，帮你过一遍可见性设置、身份关联、备份情况等容易踩坑的点，给出具体建议。

## 这不是什么

- **不是反爬虫工具。** 我们不爬任何站点，也不试图破坏任何爬虫。
- **不是举报平台。**不指名道姓任何人或团体。如果你看到的爬取行为构成侵权，请走平台投诉或法律渠道。
- **不替你做决定。** 是否发布、发布到哪里、用什么身份发布，都是你的选择。这个工具只在你做决定前提供信息。

为什么这样设计：见 [`docs/why-not-a-callout-site.md`](docs/why-not-a-callout-site.md)。

## 下载预编译版（推荐给不想装 Python 的用户）

前往本仓库的 **[Releases 页面](https://github.com/Mice999/fic-guard/releases)**，下载对应你系统的文件，双击即可使用，无需安装 Python：

| 系统 | 文件名 |
|------|--------|
| Windows 64位 | `fic-guard-windows-x64.exe` |
| macOS Apple Silicon | `fic-guard-macos-arm64` |
| macOS Intel | `fic-guard-macos-x86_64` |
| Linux 64位 | `fic-guard-linux-x64` |

**注意事项**：
- 预编译版不附带 `examples/sample.txt`，直接用你自己的 `.txt` 文件即可，例如：`fic-guard fingerprint make 我的小说.txt --work-id ch1`
- **macOS**：下载后先在终端执行 `chmod +x fic-guard-macos-*`。第一次打开可能被 Gatekeeper 拦截，有两种方式放行：① 在"系统设置 → 隐私与安全性"里点"仍要打开"；② 或者右键点击文件 → 选择"打开" → 在弹窗里点"打开"（macOS 15+ 推荐用这种方式）。
- **Windows**：可能出现 SmartScreen 提示，点"更多信息 → 仍要运行"即可。

---

## 从源码安装

需要 Python 3.9+。

```bash
pip install -e .
```

或者将来发到 PyPI 之后：

```bash
pip install fic-guard
```

## 快速上手

```bash
# 1. 给你的作品生成指纹（包含若干"签名句"和 SHA-256）
fic-guard fingerprint make ./mywork.txt --work-id mywork-ch1

# 2. 生成时间戳存证
fic-guard timestamp make ./mywork.txt --work-id mywork-ch1

# 3.（可选）发布到不同平台时，各嵌入一个不同的隐形标签
fic-guard fingerprint watermark ./mywork.txt --payload site-A --output mywork.site-A.txt
fic-guard fingerprint watermark ./mywork.txt --payload site-B --output mywork.site-B.txt

# 4. 一段时间后，用指纹查询作品有没有出现在别处
fic-guard monitor .fic-guard/mywork-ch1.fingerprint.json

# 5. 发布前过一遍自检清单
fic-guard safe-publish
```

所有产物默认放在 `.fic-guard/` 目录下。建议把这个目录纳入你自己的备份策略（私人备份，**不要上传到公开仓库**）。

## 各命令详解

### `fingerprint make`

从作品中挑出若干"签名句"。挑选标准是：长度适中、词组独特、不易被同义替换的句子。它们会保存进一个 JSON 文件，未来用于搜索。

```bash
fic-guard fingerprint make work.txt --work-id ch1 --count 5 --seed 42
```

- `--count`：生成多少条签名句（默认 5）。
- `--seed`：可选的固定种子，便于复现同样的指纹。

### `fingerprint watermark` / `extract` / `strip`

在文本里嵌入 / 提取 / 移除零宽字符水印。

```bash
# 嵌入
fic-guard fingerprint watermark work.txt --payload "site-A" --output work.site-A.txt
# 提取（在任何疑似来自你作品的文本上跑）
fic-guard fingerprint extract suspicious.txt
# 移除（如果你想发布纯净版）
fic-guard fingerprint strip work.site-A.txt --output work.clean.txt
```

**重要限制**：零宽水印能被知道它的人轻易移除（甚至 `fic-guard fingerprint strip` 自己就能干这事）。它的作用是抓懒爬虫，不是抓有备而来的对手。把它当成"低成本的第一道筛子"，配合签名句指纹和时间戳一起用。

### `timestamp make` / `verify`

生成 / 验证 SHA-256 存证。

```bash
fic-guard timestamp make work.txt --work-id ch1
# 三个月后，验证文件没有被改动
fic-guard timestamp verify .fic-guard/ch1.proof.json work.txt
```

**让存证更有说服力的两种方式**（任选其一或都做）：

- 在公开账号（微博、Mastodon 等）发一条只包含 SHA-256 的内容，让平台时间戳给你背书。
- 安装 `opentimestamps-client`，跑 `ots stamp .fic-guard/ch1.proof.json`，把哈希锚定到比特币链上。

### `monitor`

把指纹里的签名句变成搜索 URL。默认离线模式，只生成 URL 让你手动打开（最稳）。加 `--network` 会尝试调用 DuckDuckGo HTML 端点做一次轻量查询。

```bash
fic-guard monitor .fic-guard/ch1.fingerprint.json            # 离线，生成 URL 列表
fic-guard monitor .fic-guard/ch1.fingerprint.json --network  # 顺便联网试一下
```

报告文件保存在 `.fic-guard/<work-id>.monitor.json`。

### `safe-publish`

一个本地交互式清单，问你几个关于可见性、身份关联、备份的问题，给出风险评级和建议。完全离线，答案不保存到任何地方（除非你自己重定向到文件）。

```bash
fic-guard safe-publish
```

## 进阶阅读

- [`docs/threat-model.md`](docs/threat-model.md) — 我们假设的对手是谁，能做什么、不能做什么
- [`docs/why-not-a-callout-site.md`](docs/why-not-a-callout-site.md) — 为什么不做"爬虫公示墙"
- [`docs/patterns/`](docs/patterns/) — 已知的爬取手法和应对模式（不指名道姓）
- [`docs/incident-response.md`](docs/incident-response.md) — 如果发现作品被搬运了，先做什么

## 项目状态

Alpha。功能可用，但 API 可能在 1.0 之前调整。下一阶段开发计划见 [`docs/roadmap-v0.2.md`](docs/roadmap-v0.2.md)（v0.2 的目标是让非技术创作者也能用上：单文件可执行 + 本地 Web UI）。

欢迎 issue 和 PR，但**请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 里关于「我们不接受什么」的部分**——这个仓库不是举报平台，issue 区不接受指名道姓任何用户/团体/群组的内容。

## License

MIT。详见 [LICENSE](LICENSE)。
