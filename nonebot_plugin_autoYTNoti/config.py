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

    # YouTube 播放器客户端轮换列表【免 cookie 的关键配置】
    # 未配置 cookies 时使用这些客户端绕过 "Sign in to confirm you're not a bot" 检测。
    # 逗号分隔，按优先级排列；yt-dlp 会依次尝试并合并各客户端可用格式。
    # 可用值（yt-dlp 版本相关）：tv / tv_downgraded / tv_simply / web / web_safari /
    #   web_embedded / web_music / web_creator / mweb / android / android_vr / ios / visionos
    # 注意：web 与 visionos 为默认客户端，最易触发 bot 检测，一般不要放在前面。
    # YouTube 策略变化时，改此项即可，无需改代码；改完建议同时升级 yt-dlp。
    yt_dl_player_clients: str = "tv,tv_downgraded,web_embedded,mweb"

    # YouTube 登录态 cookies【可选增强，非必需】
    # 默认（不配置）已通过 tv/web_embedded 电视客户端免登录绕过 bot 检测（画质上限约 1080p）
    # 仅在需要 4K/HDR 等最高画质时，才配置以下其一以切回 web 客户端：
    # 方式一：cookies 文件路径（由浏览器扩展导出 cookies.txt），如 /path/cookies.txt
    yt_dl_cookies: str = ""
    # 方式二：从本机已登录的浏览器直接读取 cookies（需服务器装有该浏览器且已登录 YouTube）
    # 可选值：chrome / chromium / firefox / safari / edge / opera 等
    yt_dl_cookies_browser: str = ""
