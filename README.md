<div align="center">

# nonebot-plugin-autoytnoti

_✨ NoneBot2 YouTube 视频更新通知插件 ✨_

<a href="https://github.com/liuqiaochi/nonebot_plugin_autoYTNoti/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/liuqiaochi/nonebot_plugin_autoYTNoti" alt="license">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">
<img src="https://img.shields.io/badge/nonebot-2.2.0+-red.svg" alt="nonebot">

</div>

## 📖 介绍

监听 YouTube 频道更新，当关注的频道发布新视频时，第一时间推送封面和视频链接给指定 QQ 用户。

支持区分视频类型：**普通视频**、**Shorts 短视频**、**直播**，可自由配置推送哪些类型。

## 💿 安装

从 GitHub 安装：

```bash
pip install git+https://github.com/liuqiaochi/nonebot_plugin_autoYTNoti.git
```

然后在 bot 的 `pyproject.toml` 中加载插件：

```toml
[tool.nonebot]
plugins = ["nonebot_plugin_autoYTNoti"]
```

## 🔧 前置依赖（必装）

> ⚠️ **使用 `YT解析` / `YT下载` 指令前，必须确保以下两个组件已安装，否则指令无法正常工作。**

### 1. yt-dlp（Python 包）

`YT解析` / `YT下载` 依赖 `yt-dlp` 解析与下载 YouTube 内容：

```bash
pip install yt-dlp
```

- 若已通过 `pip install git+https://...` 安装本插件，`yt-dlp` 通常会作为依赖自动安装；
- **若指令仍提示未安装**，请手动执行上面的命令；
- 未安装时，`YT解析` / `YT下载` 会直接提示：`请先安装 yt-dlp：pip install yt-dlp`。

### 2. ffmpeg（系统二进制，最高画质合并必需）

视频默认格式为 `bestvideo+bestaudio/best`，即分别下载**最高画质视频流**与**最高音质音频流**，必须由 `ffmpeg` 合并输出为 mp4。

> ❗ **缺少 ffmpeg 将无法生成完整视频文件**（仅能下载到分离的音视频流）。

各系统安装方式：

- **Debian / Ubuntu**
  ```bash
  sudo apt-get update && sudo apt-get install -y ffmpeg
  ```
- **CentOS / RHEL**
  ```bash
  sudo yum install -y ffmpeg
  # 若默认源无 ffmpeg，需先启用 RPM Fusion 源
  ```
- **macOS（Homebrew）**
  ```bash
  brew install ffmpeg
  ```
- **Windows**
  从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载并加入系统 `PATH`，或在 `.env` 中通过 `YT_DL_FFMPEG` 指定绝对路径。

安装后验证：

```bash
ffmpeg -version
```

若 `ffmpeg` 不在系统 `PATH` 中，请通过 `YT_DL_FFMPEG=/path/to/ffmpeg` 配置其绝对路径（见下方配置项）。

## ⚙️ 配置

在 `.env` 文件中添加以下配置项：

| 配置项 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `YT_API_KEY` | **是** | `""` | YouTube Data API v3 密钥 |
| `YT_POLL_INTERVAL` | 否 | `300` | 轮询间隔（秒），默认 5 分钟 |
| `YT_DATA_PATH` | 否 | `data/yt_noti/data.json` | 数据文件路径 |
| `YT_PROXY` | 否 | `""` | HTTP 代理地址（国内服务器必填） |
| `YT_DL_DIR` | 否 | `data/yt_downloads` | yt-dlp 下载目录（相对于 bot 根目录） |
| `YT_DL_FORMAT` | 否 | `bestvideo+bestaudio/best` | yt-dlp 视频格式选择器（ffmpeg 合并为 mp4） |
| `YT_DL_FFMPEG` | 否 | `""` | ffmpeg 可执行文件绝对路径，留空则使用系统 PATH 中的 ffmpeg |
| `YT_DL_PLAYER_CLIENTS` | 否 | `tv,tv_downgraded,web_embedded,mweb` | 免 cookie 使用的 YouTube 播放器客户端轮换列表（逗号分隔，按优先级）。YouTube 策略变化时改此项即可，详见下方「排障」 |
| `YT_DL_COOKIES` | 否 | `""` | YouTube cookies 文件（cookies.txt）【可选】。默认免 cookie（轮换客户端，≤1080p）；配置后可切回 web 客户端获取最高画质 |
| `YT_DL_COOKIES_BROWSER` | 否 | `""` | 从本机已登录浏览器直读 cookies（如 chrome/firefox/safari）【可选】，效果同上 |

### 获取 YouTube API Key

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建项目并启用 **YouTube Data API v3**
3. 创建 API 密钥，填入 `YT_API_KEY`

### 配置示例

```env
SUPERUSERS=["123456789"]
YT_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
YT_POLL_INTERVAL=300
YT_PROXY=http://127.0.0.1:7890
```

> ⚠️ 国内服务器必须配置 `YT_PROXY`，否则无法访问 YouTube API 和图片 CDN。支持 `http://` 和 `socks5://` 格式。

## 🎉 使用

> ⚠️ **所有指令仅超级用户可用，指令不区分大小写（YT/yt/Yt 均可）**

### 频道监听管理

| 指令 | 说明 | 示例 |
|------|------|------|
| `YT监听添加 <handle>` | 添加监听的 YouTube 频道 | `YT监听添加 StarSavior_EN` |
| `YT监听删除 <handle>` | 删除监听的 YouTube 频道 | `YT监听删除 StarSavior_EN` |
| `YT监听查看` | 以图片展示当前监听列表 | |

### 推送用户管理

| 指令 | 说明 | 示例 |
|------|------|------|
| `YT推送添加 <QQ号/@人>` | 添加推送目标用户 | `YT推送添加 280035768` 或 `YT推送添加 @某人` |
| `YT推送删除 <QQ号/@人>` | 删除推送目标用户 | `YT推送删除 @某人` |

### 推送类型配置

| 指令 | 说明 | 示例 |
|------|------|------|
| `YT配置 <类型...>` | 配置推送类型（空格分隔） | `YT配置 视频 短视频 直播` |

可选类型：`视频`、`短视频`、`直播`，默认仅推送 `视频`。

### 查看与工具

| 指令 | 说明 |
|------|------|
| `YT列表` | 查看当前全部配置（合并转发） |
| `YT测试 [handle]` | 测试推送有效性，获取频道最新视频发送给推送用户 |
| `YT解析 <链接>` | 解析 YouTube 链接，返回标题/频道/时长/播放量/发布日期与封面图（不下载） |
| `YT下载 <链接>` | 使用 yt-dlp 下载视频（ffmpeg 合并为 mp4）与最优封面图；以两条直发消息返回：① 封面图+元信息 ② 视频（避免转发内视频显示「已过期」） |

> 以上两条指令支持**直接发送链接**，也支持**回复 / 引用**一条含链接的消息来触发（无需在指令后手动贴链接）。

| `YT帮助` | 以图片展示帮助信息 |

## 🔧 工作原理

1. 通过 YouTube Data API 的 `forHandle` 参数将频道 handle 解析为 `channel_id`
2. 使用 YouTube RSS Feed 轮询最新视频（不消耗 API 配额）
3. 对新发现的视频调用 `videos.list` 获取详情，判断视频类型
4. Shorts 识别：通过频道的 Shorts 专属播放列表（`UUSH` 前缀）判断
5. 直播识别：通过 `snippet.liveBroadcastContent` 字段判断
6. 封面图通过代理下载后以 base64 格式发送，无需协议端访问外网
7. 将符合配置类型的新视频封面和链接推送给目标用户

### 按需解析与下载（yt-dlp）

- `YT解析 <链接>`：调用 yt-dlp 解析任意 YouTube 链接（watch / youtu.be / shorts 等），返回标题、频道、时长、播放量、发布日期及**最优封面图**，**不下载文件**。
- `YT下载 <链接>`：调用 yt-dlp 将视频与封面图下载到 `YT_DL_DIR` 目录。
  - **视频**：默认 `bestvideo+bestaudio/best`，由 ffmpeg 合并最佳视频流与最佳音频流为 mp4。默认轮换 tv 系客户端，**画质上限约 1080p**（免 cookie，开箱即用）。
  - **封面图**：优先取 YouTube `maxresdefault`（最高清），缺失时回退 `hqdefault`。
  - 以**两条直发消息**返回：① 封面图 + 元信息 ② 视频（不放入转发节点，避免 go-cqhttp 转发内视频显示「已过期」）。视频直发失败时会提示本地保存路径。
  - **自动清理**：视频成功发送后，本地的视频文件与封面文件会自动删除，避免长期占用磁盘；若发送失败则保留文件以便从保存目录找回。
- 支持**直接发送链接**，也支持**回复 / 引用**一条含链接的消息触发指令。
- 视频格式由 `YT_DL_FORMAT` 控制，合并依赖 `ffmpeg`（需位于 PATH，或用 `YT_DL_FFMPEG` 指定绝对路径）；下载/解析/封面均复用 `YT_PROXY` 代理。
- **默认免 cookie**：轮换使用 `tv` / `tv_downgraded` / `web_embedded` / `mweb` 等播放器客户端（由 `YT_DL_PLAYER_CLIENTS` 配置），绕过 `Sign in to confirm you're not a bot` 检测，无需任何登录态即可下载（画质上限约 1080p）。前置依赖 `yt-dlp` 与 `ffmpeg` 的安装方式，详见上方「🔧 前置依赖（必装）」小节。

#### 内置自愈重试

`YT解析` / `YT下载` 失败时会自动重试，无需人工清缓存：

1. 先用 `YT_DL_PLAYER_CLIENTS` 的完整客户端列表尝试一次
2. 失败后**禁用 yt-dlp 缓存**（等价于 `yt-dlp --rm-cache-dir`，但不删磁盘文件），再按客户端**逐个**重试
3. 全部失败才返回错误（返回最后一个错误信息）

重试过程会写入 bot 日志（含每次使用的客户端），便于定位是哪个客户端被封。

#### 排障：出现「Sign in to confirm you're not a bot」或「The page needs to be reloaded」

YouTube 会持续调整风控，且**重点封禁机房/数据中心 IP**。若此类错误复现，按以下顺序排查：

> 两个错误的区别：前者是**未通过 bot 检测**（客户端选择/登录态问题）；后者是**通过了检测但播放器返回空格式**（多为 yt-dlp 版本过旧或缓存过期，参见 yt-dlp issue #16212——2026.03.03 强制的 `player_js_version` 被 YouTube 拒绝，已于 2026.03.17 修复）。**两者最常见的原因都是 yt-dlp 版本过旧。**

按以下顺序排查：

1. **升级 yt-dlp（最常见原因）**——YouTube 改版后旧版必然失效：
   ```bash
   pip install -U yt-dlp
   yt-dlp --version
   ```
2. **清理 yt-dlp 缓存**——风控挑战的求解结果会过期，导致原本可用的请求开始失败：
   ```bash
   yt-dlp --rm-cache-dir
   ```
3. **轮换播放器客户端**——把 `YT_DL_PLAYER_CLIENTS` 换成其他组合，重启 bot 重试：
   ```env
   # 依次尝试：优先 tv 系 → 嵌入式/移动 web → android_vr
   YT_DL_PLAYER_CLIENTS=tv_downgraded,tv,web_embedded,mweb,android_vr
   ```
   可用值：`tv` / `tv_downgraded` / `tv_simply` / `web` / `web_safari` / `web_embedded` / `web_music` / `web_creator` / `mweb` / `android` / `android_vr` / `ios` / `visionos`
   （具体以安装的 yt-dlp 版本为准；`web` 与 `visionos` 是默认客户端，最易触发检测，不要放在前面。）

   > ⚠️ 若填了无效名称，yt-dlp 会静默跳过并回退默认 `web` 客户端（本插件日志默认静默），表现就是「明明改了配置却仍报 bot 错误」。请严格按上述可用值填写。
4. **使用 PO Token 服务（机房 IP 的根本解法）**——若服务器 IP 已被 YouTube 标记，单纯换客户端无效。可部署 `bgutil-ytdlp-pot-provider`（动态生成 Proof-of-Origin 令牌，无需账号/cookie）：
   ```bash
   pip install bgutil-ytdlp-pot-provider
   ```
   其服务端默认监听 `127.0.0.1:4416`，启动后设置环境变量 `YT_DLP_POT_PROVIDER_URL=http://127.0.0.1:4416` 再重启 bot。
5. **兜底：配置 cookies**——见下一小节。cookies 有效期有限，需定期重新导出，故优先级最低。

#### 可选增强：使用 cookies 获取最高画质（4K/HDR）

默认 `tv` 客户端的画质上限约 1080p。如需 4K/HDR 等更高规格，可提供已登录 YouTube 账号的 cookies，将自动切回 `web` 客户端：

- **方式一（推荐，服务器通用）**：在本地已登录 YouTube 的浏览器中用扩展（如「Get cookies.txt」/「cookie-editor」）导出 `cookies.txt`，上传到服务器，配置 `YT_DL_COOKIES=/path/cookies.txt`。
- **方式二（需服务器装有浏览器）**：配置 `YT_DL_COOKIES_BROWSER=chrome`（可选 `chrome` / `chromium` / `firefox` / `safari` / `edge` 等），由 yt-dlp 直接从本机已登录浏览器读取 cookies。
- 两者二选一（优先 cookies 文件）；解析与下载均会复用该登录态。cookies 过期后需重新导出。

## 📝 更新日志

### v0.1.5

- **修复免 cookie 失效（关键 bug）**：`extractor_args` 的 `player_client` 之前误用逗号分隔字符串，而 yt-dlp 的 Python API 不会像 CLI 那样按逗号拆分，导致值被逐字符拆成 `['w','e','b','_',...]`，所有客户端名无效被跳过，静默回退默认 `web` 客户端 → 仍报 `Sign in to confirm you're not a bot`。现已改为列表注入
- 新增 `YT_DL_PLAYER_CLIENTS` 配置项（逗号分隔，默认 `tv,tv_downgraded,web_embedded,mweb`），客户端轮换可在 `.env` 调整，YouTube 策略变化无需改代码
- 新增 _player_clients() 并补充回归自测：校验注入为 list、经 yt-dlp 自身解析后客户端名完整有效、并复现旧写法的失败路径
- **新增内置自愈重试**：解析/下载失败后自动禁用 yt-dlp 缓存（`cachedir=False`，等价 `--rm-cache-dir` 但不删磁盘文件）并按客户端逐个重试，全部失败才返回最后错误；重试过程写入 bot 日志。免 cookie 模式按客户端轮换重试，cookie 模式仅无缓存重试一次以保持最高画质
- README 排障小节扩充：新增「The page needs to be reloaded」错误的定位（多为 yt-dlp 版本过旧，参考 issue #16212）与两个错误的区别说明

### v0.1.4

- **默认免 cookie 下载**：YouTube 改用 `tv/web_embedded` 电视客户端，天然绕过 `Sign in to confirm you're not a bot` 检测，开箱即用（画质上限约 1080p）
- `YT_DL_COOKIES` / `YT_DL_COOKIES_BROWSER` 降为**可选增强**：仅在需要 4K/HDR 最高画质时配置，自动切回 `web` 客户端并注入登录态
- README 同步更新 bot 检测说明与 cookies 导出指引

### v0.1.3

- 下载默认最高画质：`bestvideo+bestaudio/best`，由 ffmpeg 合并最高画质视频流与最高音质音频流为 mp4
- 封面图改为取 YouTube 最优（`maxresdefault`，缺失回退 `hqdefault`）
- 新增 `YT_DL_FFMPEG` 配置项，可指定 ffmpeg 绝对路径
- `YT解析` / `YT下载` 兼容「回复 / 引用」含链接的消息触发，无需手动贴链接
- `YT下载` 结果以两条直发消息返回：① 封面图+元信息 ② 视频（不放入转发，避免显示「已过期」），发送失败时提示本地路径
- `YT下载` 视频发送成功后自动删除本地视频与封面文件（发送失败则保留）

### v0.1.2

- 新增 `YT解析 <链接>`：基于 yt-dlp 解析 YouTube 链接，返回元信息与封面图（不下载）
- 新增 `YT下载 <链接>`：基于 yt-dlp 下载视频与封面图到本地并回传
- 新增配置项 `YT_DL_DIR`（下载目录）与 `YT_DL_FORMAT`（视频格式选择器）
- 解析/下载复用 `YT_PROXY` 代理；新增 `yt-dlp` pip 依赖

### v0.1.1

- 指令不区分大小写（YT/yt/Yt 均可）
- 推送添加/删除支持 @用户 自动获取 QQ 号
- `YT监听查看` 统一指令格式
- 新增 `YT测试` 指令验证推送有效性
- `YT列表` 改为合并转发消息
- 图片渲染美化（卡片式设计），去除 emoji 避免字体兼容问题
- 封面图通过代理下载转 base64 发送，解决国内服务器图片超时
- 新增 `YT_PROXY` 配置项支持 HTTP 代理

### v0.1.0

- 初始版本
- 支持频道监听管理
- 支持推送用户管理
- 支持视频类型过滤（视频/Shorts/直播）
- 支持图片形式查看监听列表和帮助

## 📄 许可证

[MIT License](LICENSE)
