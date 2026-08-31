"""插件配置"""

from pydantic import BaseModel


class Config(BaseModel):
    """YouTube通知插件配置"""

    # YouTube Data API v3 密钥
    yt_api_key: str = ""

    # 轮询间隔（秒），默认5分钟
    yt_poll_interval: int = 300

    # 数据文件路径（相对于bot根目录）
    yt_data_path: str = "data/yt_noti/data.json"

    # HTTP代理地址（用于访问YouTube/Google API）
    # 例如: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080
    yt_proxy: str = ""

    # 监听时间段（24小时制），只在该区间内轮询和推送
    # 默认 8:00 ~ 23:00
    yt_active_start: int = 8
    yt_active_end: int = 23

    # yt-dlp 下载目录（相对于bot根目录）
    yt_dl_dir: str = "data/yt_downloads"

    # 视频下载格式（yt-dlp format 选择器）
    # 默认最高画质：分别选取最佳视频流与最佳音频流，由 ffmpeg 合并为 mp4
    yt_dl_format: str = "bestvideo+bestaudio/best"

    # ffmpeg 可执行文件路径（用于合并最高画质视频与音频）
    # 留空则使用系统 PATH 中的 ffmpeg；若未安装可填写绝对路径，如 /usr/bin/ffmpeg
    yt_dl_ffmpeg: str = ""

    # JavaScript 运行时【必装，yt-dlp 2026 依赖它解 YouTube 的 JS 挑战题】
    # 默认只会启用 deno（node/bun/quickjs 需显式指定）。缺失时可用播放器客户端会被
    # 降级为仅 visionos，播放器返回 LOGIN_REQUIRED，最终报
    # "Sign in to confirm you're not a bot"。
    # 安装：curl -fsSL https://deno.land/install.sh | sh
    # 留空：由 yt-dlp 从 PATH 查找 deno（交互式终端可用）
    # 指定路径：systemd 等服务环境的 PATH 常不含 ~/.deno/bin，需显式给绝对路径，例如
    #   deno:/home/laofei/.deno/bin/deno
    yt_dl_js_runtime: str = ""

    # YouTube cookies 文件路径（Netscape 格式 cookies.txt），可选增强
    # 配置后注入登录态并切回默认客户端：可解锁 4K/HDR 最高画质，
    # 并彻底规避 "Sign in to confirm you're not a bot" 风控。
    # 与 yt_dl_cookies_browser 二选一，同时配置时文件优先。
    # 导出方法见 README「Cookies 登录态（可选）」小节。
    yt_dl_cookies: str = ""

    # 从本机浏览器读取 cookies（如 chrome/firefox/safari/edge），可选
    # 仅适合 bot 与浏览器同机的桌面场景；服务器请用 yt_dl_cookies 指向导出的文件。
    yt_dl_cookies_browser: str = ""

    # ── 远程下载服务（将下载卸载到 Mac 上的 app.py）──
    # 留空 = 使用本机 yt-dlp 直接下载（默认）；
    # 填写 Mac app.py 地址后，解析/下载改为调用该 HTTP 服务，
    # 本机无需安装 yt-dlp / ffmpeg / deno。
    # 例: http://10.211.55.2:5099
    yt_remote_server: str = ""

    # 与 Mac app.py 的 API_TOKEN 对应的校验令牌，留空表示不校验
    yt_remote_token: str = ""

    # 单次远程下载最长等待时间（秒），超时则报错
    yt_remote_timeout: int = 600
