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

> ⚠️ **使用 `YT解析` / `YT下载` 指令前，必须确保以下三个组件已安装，否则指令无法正常工作。**
>
> ❗ **其中 `deno` 最容易被忽略**：yt-dlp 2026 依赖 JavaScript 运行时解 YouTube 的挑战题，缺失时会退化为
> `Sign in to confirm you're not a bot` 错误，且表现得很像"IP 被封"。若遇到该报错，**先查 deno**。

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

### 3. deno（JavaScript 运行时，绕过 bot 检测必需）

yt-dlp 2026 需要 **JavaScript 运行时**来执行 YouTube 播放器 JS、解开其反爬挑战题。**默认只启用 `deno`**（node / bun / quickjs 需显式指定）。

缺少 JS 运行时时，yt-dlp 可用播放器客户端会被降级为仅 `visionos`，播放器返回 `LOGIN_REQUIRED`，最终报错：

```
ERROR: [youtube] xxxxx: Sign in to confirm you're not a bot.
```

**安装 deno：**

```bash
curl -fsSL https://deno.land/install.sh | sh
# 安装到 ~/.deno/bin，按提示将其加入 PATH（或重开终端）
```

安装后验证：

```bash
deno --version
# 并确认 yt-dlp 能识别到（应显示 JS runtimes: deno-x.x.x 而非 none）
yt-dlp -v --simulate "https://www.youtube.com/watch?v=xxxxxxxxxxx" 2>&1 | grep "JS runtimes"
```

> ⚠️ **以 systemd / 后台服务方式运行 bot 时**，服务环境的 `PATH` 通常不含 `~/.deno/bin`，yt-dlp 仍会找不到 deno。
> 此时请在 `.env` 显式指定绝对路径：
> ```env
> YT_DL_JS_RUNTIME=deno:/home/laofei/.deno/bin/deno
> ```

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
| `YT_DL_JS_RUNTIME` | 否 | `""` | JS 运行时，格式 `deno` 或 `deno:/绝对路径/deno`。留空则由 yt-dlp 从 PATH 查找 deno；**systemd 服务环境建议显式指定绝对路径** |
| `YT_DL_COOKIES` | 否 | `""` | YouTube cookies 文件路径（Netscape 格式 cookies.txt）。配置后注入登录态，规避 `Sign in to confirm you're not a bot` 风控并解锁 4K/HDR，见下方「Cookies 登录态」 |
| `YT_DL_COOKIES_BROWSER` | 否 | `""` | 从本机浏览器读取 cookies（`chrome`/`firefox`/`safari`/`edge`）。仅适合桌面同机运行；与 `YT_DL_COOKIES` 二选一，两者都配置时文件优先 |
| `BILI_DL_COOKIES` | 否 | `""` | Bilibili cookies 文件（Netscape 格式 cookies.txt）路径，**仅本机模式生效**。用于解锁 Bilibili 1080P+ 高画质（未登录态仅 480p）。远程模式由 Mac 端 `app.py` 的 `cookies.txt` 控制，此处忽略 |

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

### Cookies 登录态（可选，彻底规避 bot 风控）

默认的 tv 客户端免登录方案**无账号也能用，但 YouTube 的 bot 风控按出口 IP 概率性触发**（尤其走共享/机房代理 IP 时），表现为 `Sign in to confirm you're not a bot` 时好时坏。若你遇到该报错，配置 cookies 即可彻底解决，同时解锁 4K/HDR 最高画质：

```env
YT_DL_COOKIES=/path/to/cookies.txt
# 或（bot 与浏览器同机的桌面场景）：
YT_DL_COOKIES_BROWSER=chrome
```

导出 cookies.txt（Netscape 格式）：

1. 在浏览器登录 YouTube（**建议用小号**，账号有被风控封禁的极小概率，且 cookies 会随登录设备变化失效，需定期重新导出）
2. 安装浏览器扩展 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)（Chrome/Edge）或 [cookies.txt](https://addons.mozilla.org/firefox/addon/cookies-txt/)（Firefox）
3. 打开 youtube.com，用扩展导出，保存为 `cookies.txt` 放到服务器可读路径

配置后插件自动切回 yt-dlp 默认客户端（tv 客户端不携带登录态），无需其他改动。

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
| `YT下载 <链接>` | 使用 yt-dlp 下载视频（ffmpeg 合并为 mp4）与最优封面图，以两条直发消息返回：① 封面图+元信息 ② 视频 |
| `BILI解析 <链接>` | 解析 Bilibili 链接（BV/av 号、b23.tv 短链），返回标题/UP主/时长/播放量/封面图（不下载）。另有简写别名 `bv解析`/`bv下载`（`bv`/`Bv`/`BV` 均可） |
| `BILI下载 <链接>` | 使用 yt-dlp 下载 Bilibili 视频与封面图，以两条直发消息返回：① 封面图+元信息 ② 视频。另有简写别名 `bv解析`/`bv下载` |

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
  - **视频**：默认 `bestvideo+bestaudio/best`，由 ffmpeg 合并最佳视频流与最佳音频流为 mp4。默认走 tv 客户端，**画质上限约 1080p**（免 cookie，开箱即用）。
  - **封面图**：优先取 YouTube `maxresdefault`（最高清），缺失时回退 `hqdefault`。
  - 结果以**两条直发消息**返回：① 封面图 + 元信息 ② 视频。视频**不放入合并转发节点**——转发内的视频会被 QQ 显示为「已过期」（本地文件本身正常）。视频发送失败时提示本地保存路径。
- `BILI解析 <链接>` / `BILI下载 <链接>`：解析 / 下载 **Bilibili** 链接（BV 号、av 号、b23.tv 短链），返回字段与消息格式同 YouTube。B 站需要浏览器 UA + Referer，本机模式自动附加；**1080P+ 高画质需配置 `BILI_DL_COOKIES`**（未登录态仅 480p）。
- 支持**直接发送链接**，也支持**回复 / 引用**一条含链接的消息触发指令。
- 视频格式由 `YT_DL_FORMAT` 控制，合并依赖 `ffmpeg`（需位于 PATH，或用 `YT_DL_FFMPEG` 指定绝对路径）；下载/解析/封面均复用 `YT_PROXY` 代理。
- **默认免 cookie**：YouTube 使用 `tv` 电视客户端（与 FeiTools 同源方案），免登录下载（画质上限约 1080p）。前置依赖 `yt-dlp`、`ffmpeg` 与 `deno` 的安装方式，详见上方「🔧 前置依赖（必装）」小节。
- **远程模式**：若配置了 `YT_REMOTE_SERVER`，解析 / 下载改为调用 Mac 端 `app.py`（已内置 Bilibili 支持），本机无需安装 `yt-dlp` / `ffmpeg` / `deno`。

#### Bilibili Cookie 配置（解锁 1080P+ 高画质）

未配置 Cookie 时，Bilibili 处于未登录态，**最高仅 480p**。配置登录态后可解锁 1080P+。Cookie 的生效位置取决于运行模式：

- **远程模式**（已配 `YT_REMOTE_SERVER`，即你当前的模式）：Cookie 由 **Mac 端 `app.py`** 读取 `feiTools/server/cookies.txt`（Netscape 格式）生效，与 bot 侧配置无关。
- **本机模式**（未配远程服务器）：在 `.env` 配置 `BILI_DL_COOKIES=/绝对路径/bilibili_cookies.txt`（Netscape 格式）。

**获取方式（任选其一）：**

1. **浏览器扩展导出（最通用）**：PC 浏览器登录 bilibili.com → 安装扩展 *Get cookies.txt LOCALLY* → 在 bilibili 页面导出 **Netscape 格式** → 保存为 `feiTools/server/cookies.txt`（远程模式）或 `BILI_DL_COOKIES` 指向的文件（本机模式）→ 重启 `app.py`（远程模式）。
2. **仅取 3 个关键值（最省事，app.py 自带生成接口）**：浏览器 F12 → Application → Cookies → `bilibili.com` 复制 `SESSDATA`（必填）、`bili_jct`、`DedeUserID`，POST 给 app.py 自动生成（远程模式）：
   ```bash
   curl -X POST http://<app.py地址>/api/cookies \
     -H "Content-Type: application/json" \
     -d '{"sessdata":"...","bili_jct":"...","dedeuserid":"..."}'
   ```

**验证**：`app.py` 启动日志出现 `✅ 检测到 cookies.txt，Bilibili 1080P+ 高画质已解锁`；或 `GET /api/cookies` 返回 `bilibili_cookies: true`。

> ⚠️ `SESSDATA` 等同账号登录凭证，请勿泄露；该文件已被 `.gitignore` 忽略（`feiTools/server/cookies.txt`），不会误提交进仓库。Cookie 会随登录过期，失效后重新导出一次即可。

#### 排障：出现「Sign in to confirm you're not a bot」

YouTube 风控持续调整，且**重点封禁机房/数据中心 IP**。按以下顺序排查：

**0. 先确认 JS 运行时（deno）已安装 —— 最易被忽略，症状与本错误完全一致**

```bash
yt-dlp -v --simulate "https://www.youtube.com/watch?v=xxxxxxxxxxx" 2>&1 | grep "JS runtimes"
```

- 输出 `JS runtimes: none` → **根因就是它**。装 deno（见「🔧 前置依赖（必装）」第 3 节）；
  若 bot 以 systemd 运行，还需配 `YT_DL_JS_RUNTIME=deno:/home/<user>/.deno/bin/deno`。

  原理：缺 JS 运行时时，yt-dlp 可用客户端被降级为仅 `visionos`，播放器返回 `LOGIN_REQUIRED`，
  最终报出本错误——**与"IP 被封"的表现完全相同，但解法完全不同**。
- 输出 `JS runtimes: deno-x.x.x` → 运行时正常，继续下一步。

**1. 升级 yt-dlp** —— YouTube 改版后旧版必然失效：

```bash
pip install -U yt-dlp
yt-dlp --version
```

**2. 清理 yt-dlp 缓存** —— 风控挑战的求解结果会过期：

```bash
yt-dlp --rm-cache-dir
```

**3. 轮换播放器客户端** —— 代码默认仅使用 `tv` 电视客户端（免登录）。若 YouTube 风控策略变化，可临时用命令行验证其他客户端是否可用（可用值：`tv` / `tv_downgraded` / `tv_simply` / `web_embedded` / `mweb` / `web` 等，以安装的 yt-dlp 版本为准；`web` 最易触发检测）：

```bash
yt-dlp -v --extractor-args "youtube:player_client=web_embedded" --skip-download "视频链接"
```

**4. 使用 PO Token 服务（机房 IP 的根本解法）** —— 若服务器 IP 已被标记，换客户端无效。
`bgutil-ytdlp-pot-provider` 动态生成 Proof-of-Origin 令牌，无需账号/cookie：

```bash
pip install bgutil-ytdlp-pot-provider
# 服务端默认监听 127.0.0.1:4416，启动后设置环境变量再重启 bot
export YT_DLP_POT_PROVIDER_URL=http://127.0.0.1:4416
```

## 📝 更新日志

### v0.1.7

- **恢复 cookies 可选增强**：新增 `YT_DL_COOKIES`（Netscape 格式 cookies.txt 路径）与 `YT_DL_COOKIES_BROWSER`（从本机浏览器读取）配置项。tv 免登录客户端受 YouTube 按 IP 概率性 bot 风控影响（`Sign in to confirm you're not a bot` 时好时坏），配置 cookies 后注入登录态、切回默认客户端，彻底规避风控并解锁 4K/HDR 画质。不配置则保持 v0.1.6 的 tv 免登录行为，完全向后兼容

### v0.1.6

- **修复 tv 客户端从未真正生效的 bug**：Python API 的 `extractor_args.player_client` 此前传的是逗号字符串，被 yt-dlp 逐字符拆开判定全部无效，**静默回退默认客户端（visionos/web）**，这是 bot 持续报 bot 检测错误的直接原因。现改为列表并锁定为 `["tv"]`（与 FeiTools 同源方案）
- **移除 cookies 相关配置**（`YT_DL_COOKIES` / `YT_DL_COOKIES_BROWSER`）及全部 cookie 注入逻辑，统一走 tv 免登录客户端
- 新增每天 0 点定时清理 `YT_DL_DIR` 中的历史封面与视频文件
- `YT下载` 完成消息不再显示保存目录

### v0.1.5

- **修复 bot 检测的真实根因：缺少 JS 运行时（deno）**。yt-dlp 2026 依赖 JS 运行时解 YouTube 播放器挑战题，默认只启用 deno。缺失时可用客户端被降级为仅 `visionos`，播放器返回 `LOGIN_REQUIRED`，最终报 `Sign in to confirm you're not a bot`——**与"IP 被封"表现完全相同但解法完全不同**。此前多轮改动均未触及此点
- 新增 `YT_DL_JS_RUNTIME` 配置项（格式 `deno` 或 `deno:/绝对路径/deno`）。留空则沿用 yt-dlp 默认（从 PATH 查找 deno）；**systemd 等服务环境 PATH 不含 `~/.deno/bin`，需显式指定绝对路径**
- README：deno 提升为「🔧 前置依赖（必装）」第 3 项（与 yt-dlp、ffmpeg 并列）；排障小节重建，并将「先查 deno」置于第 0 步
- `YT下载` 结果改为**两条直发消息**：① 封面图 + 元信息 ② 视频，不再使用合并转发（转发内的视频会被 QQ 显示为「已过期」）。仅改动消息发送方式，不涉及下载逻辑

### v0.1.4

- **默认免 cookie 下载**：YouTube 改用 `tv/web_embedded` 电视客户端，天然绕过 `Sign in to confirm you're not a bot` 检测，开箱即用（画质上限约 1080p）
- `YT_DL_COOKIES` / `YT_DL_COOKIES_BROWSER` 降为**可选增强**：仅在需要 4K/HDR 最高画质时配置，自动切回 `web` 客户端并注入登录态
- README 同步更新 bot 检测说明与 cookies 导出指引

### v0.1.3

- 下载默认最高画质：`bestvideo+bestaudio/best`，由 ffmpeg 合并最高画质视频流与最高音质音频流为 mp4
- 封面图改为取 YouTube 最优（`maxresdefault`，缺失回退 `hqdefault`）
- 新增 `YT_DL_FFMPEG` 配置项，可指定 ffmpeg 绝对路径
- `YT解析` / `YT下载` 兼容「回复 / 引用」含链接的消息触发，无需手动贴链接
- `YT下载` 结果以合并转发形式返回（封面图 + 视频），发送失败时自动回退逐条发送

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
