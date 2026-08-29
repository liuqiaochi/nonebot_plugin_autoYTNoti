"""插件配置"""

from pydantic import BaseModel, Field


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

    # YouTube 登录态 cookies【可选增强，非必需】
    # 默认（不配置）已通过 tv/web_embedded 电视客户端免登录绕过 bot 检测（画质上限约 1080p）
    # 仅在需要 4K/HDR 等最高画质时，才配置以下其一以切回 web 客户端：
    # 方式一：cookies 文件路径（由浏览器扩展导出 cookies.txt），如 /path/cookies.txt
    yt_dl_cookies: str = ""
    # 方式二：从本机已登录的浏览器直接读取 cookies（需服务器装有该浏览器且已登录 YouTube）
    # 可选值：chrome / chromium / firefox / safari / edge / opera 等
    yt_dl_cookies_browser: str = ""
