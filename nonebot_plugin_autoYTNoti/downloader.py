"""基于 yt-dlp 的 YouTube 链接解析与下载

提供能力：
- parse_youtube(url):      解析链接，返回清洗后的视频元信息（不下载）
- download_youtube(url):   下载视频与封面图到本地目录，返回路径信息
- thumbnail_b64_best(id):  获取视频最优封面图（maxres）的 base64，用于即时展示

特性：
- 默认免 cookie：轮换 YouTube 播放器客户端（默认 tv/tv_downgraded/web_embedded/mweb），
  绕过 "Sign in to confirm you're not a bot" 检测，画质上限约 1080p。
  客户端列表由 YT_DL_PLAYER_CLIENTS 配置，YouTube 策略变化时改配置即可。
- 可选增强：在 .env 配置 YT_DL_COOKIES / YT_DL_COOKIES_BROWSER 后，自动切回 web
  客户端并注入登录态，可获取 4K/HDR 等最高画质
- 视频使用 ffmpeg 合并最佳视频流 + 最佳音频流（mp4）
- 封面图优先取 YouTube maxresdefault（最高清），失败时回退 hqdefault
- 解析/下载/封面均复用 config 中的 YT_PROXY 代理配置

依赖：yt-dlp、ffmpeg（用于音视频合并，需位于 PATH 或通过 YT_DL_FFMPEG 指定）
"""

import asyncio
import base64
import functools
import re
from pathlib import Path
from typing import Dict, Optional

import httpx
from nonebot import logger

from . import plugin_config

# yt-dlp 可用性缓存：None=未检测, True/False=已检测
_YT_DLP_AVAILABLE: Optional[bool] = None

# 封面图常见扩展名
_THUMB_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# 用于从文本中提取 URL 的正则（仅匹配 ASCII 安全字符，避免吞入中文/标点）
_URL_RE = re.compile(r"https?://[A-Za-z0-9_./?=&%#:+\-]+")


def _require_yt_dlp():
    """返回已导入的 yt_dlp 模块，未安装时抛出友好异常"""
    global _YT_DLP_AVAILABLE
    if _YT_DLP_AVAILABLE is False:
        raise RuntimeError("未安装 yt-dlp，请先执行: pip install yt-dlp")
    try:
        import yt_dlp  # type: ignore
        _YT_DLP_AVAILABLE = True
        return yt_dlp
    except ImportError:
        _YT_DLP_AVAILABLE = False
        raise RuntimeError("未安装 yt-dlp，请先执行: pip install yt-dlp")


def _is_youtube_url(url: str) -> bool:
    """粗略判断是否为 YouTube 链接（watch / youtu.be / shorts / channel 等）"""
    return bool(re.search(r"(?:youtube\.com|youtu\.be)", url, re.IGNORECASE))


def _find_url(text: str) -> str:
    """从文本中提取第一个 http(s) 链接"""
    if not text:
        return ""
    m = _URL_RE.search(text)
    return m.group(0) if m else ""


def _http_kwargs() -> dict:
    """构造 httpx 客户端参数（含代理）"""
    kwargs: dict = {"timeout": 60, "follow_redirects": True}
    if plugin_config.yt_proxy:
        kwargs["proxy"] = plugin_config.yt_proxy
    return kwargs


def _ydl_opts(extra: Optional[Dict] = None) -> Dict:
    """构造 yt-dlp 通用选项，注入代理与合并配置"""
    opts: Dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,  # 默认只处理单个视频，避免误下载整张播放列表
        "nocheckcertificate": True,
        "proxy": plugin_config.yt_proxy or None,
        "socket_timeout": 60,
        "retries": 3,
        # 最高画质：分别选取最佳视频流与最佳音频流，合并为 mp4
        "merge_output_format": "mp4",
    }
    # 若指定了 ffmpeg 路径则启用（用于音视频合并）
    if plugin_config.yt_dl_ffmpeg:
        opts["ffmpeg_location"] = plugin_config.yt_dl_ffmpeg

    # 客户端策略：
    # - 未配置 cookie：使用 tv/web_embedded 电视客户端，免登录即可绕过 bot 检测，
    #   画质上限约 1080p（与 FeiTools 的 server 方案一致）
    # - 已配置 cookie：切回默认 web 客户端并注入登录态，可获取 4K/HDR 等最高画质
    _ck_file = plugin_config.yt_dl_cookies
    _ck_browser = plugin_config.yt_dl_cookies_browser
    if _ck_file or _ck_browser:
        # 配置了 cookie：用 web 客户端拿最高画质，注入登录态
        if _ck_file:
            opts["cookiefile"] = _ck_file
        else:
            # cookiesfrombrowser 接受 (browser, profile_key, profile_name, cookie_file) 元组
            opts["cookiesfrombrowser"] = (_ck_browser,)
    else:
        # 默认免 cookie：轮换使用电视/嵌入式/移动 web 客户端，绕过
        # "Sign in to confirm you're not a bot" 检测（画质上限约 1080p）
        clients = _player_clients()
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}

    if extra:
        opts.update(extra)
    return opts


def _player_clients() -> list:
    """
    将配置项 yt_dl_player_clients（逗号分隔字符串）解析为 yt-dlp 所需的列表。

    重要：yt-dlp 的 Python API 中 extractor_args 的值必须是 list。
    若传入 "tv,web_embedded" 这样的逗号分隔字符串，其内部扁平化逻辑会把字符串
    逐字符拆成 ['t','v',',',...]（与 CLI 的 --extractor-args 行为不同），
    导致所有客户端名无效而被跳过，最终回退默认 web 客户端并触发 bot 检测。
    """
    raw = getattr(plugin_config, "yt_dl_player_clients", "") or ""
    return [c.strip() for c in raw.split(",") if c.strip()]


async def _extract_with_retry(yt_dlp, url: str, extra: Dict, download: bool) -> Dict:
    """
    带自愈能力的 yt-dlp 提取。

    尝试顺序：
      ① 常规尝试一次（使用 YT_DL_PLAYER_CLIENTS 配置的完整客户端列表 + 启用缓存）
      ② 若失败，禁用 yt-dlp 缓存（cachedir=False）后重试：
         - 免 cookie 模式：按客户端逐个重试（仅指定单个客户端）
         - cookie 模式：仅禁用缓存重试一次（保持默认客户端 + 登录态）

    背景：YouTube 的风控具有间歇性，常见报错如
    "The page needs to be reloaded." / "Sign in to confirm you're not a bot"，
    常由缓存中的 visitor data、PO Token 或播放器 JS 过期引起（yt-dlp 官方
    排障建议即 `yt-dlp --rm-cache-dir`）。这里用 cachedir=False 达成同样效果
    且无需删除磁盘文件，配合换客户端可显著提高成功率，免去人工介入。
    """
    loop = asyncio.get_running_loop()

    def _attempt(**override):
        _extra = dict(extra)
        _extra.update(override)
        with yt_dlp.YoutubeDL(_ydl_opts(_extra)) as ydl:
            return ydl.extract_info(url, download=download)

    # 免 cookie 模式才做客户端轮换；cookie 模式下保持默认客户端以拿到最高画质
    use_cookies = bool(
        getattr(plugin_config, "yt_dl_cookies", "")
        or getattr(plugin_config, "yt_dl_cookies_browser", "")
    )
    clients = [] if use_cookies else _player_clients()

    if clients:
        retries = [
            {"cachedir": False, "extractor_args": {"youtube": {"player_client": [c]}}}
            for c in clients
        ]
    else:
        retries = [{"cachedir": False}]

    last_err: Optional[Exception] = None
    try:
        return await loop.run_in_executor(None, _attempt)
    except Exception as e:
        last_err = e
        logger.warning(f"yt-dlp 首次尝试失败 [{url}]: {e}")

    for i, override in enumerate(retries, 1):
        label = override.get("extractor_args", {}).get("youtube", {}).get("player_client")
        label = label[0] if label else "默认客户端"
        try:
            logger.info(f"yt-dlp 重试 {i}/{len(retries)}（客户端 {label}，禁用缓存）: {url}")
            return await loop.run_in_executor(None, functools.partial(_attempt, **override))
        except Exception as e:
            last_err = e
            logger.warning(f"yt-dlp 重试 {i}（客户端 {label}）失败: {e}")

    raise last_err


def _format_duration(seconds) -> str:
    """秒数格式化为 m:ss 或 h:mm:ss"""
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        return "未知"
    if seconds <= 0:
        return "0:00"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_count(num) -> str:
    """播放量转为 万 / 亿 中文计数"""
    try:
        num = int(num or 0)
    except (TypeError, ValueError):
        return "未知"
    if num >= 100_000_000:
        return f"{num / 100_000_000:.1f}亿"
    if num >= 10_000:
        return f"{num / 10_000:.1f}万"
    return f"{num:,}"


def _format_date(raw) -> str:
    """upload_date 形如 20240131 -> 2024-01-31"""
    if not raw or len(str(raw)) != 8:
        return "未知"
    try:
        s = str(raw)
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    except Exception:
        return "未知"


def _summarize(info: Dict) -> Dict:
    """从 yt-dlp 原始 info 中提取关键字段，统一为可读字符串"""
    return {
        "id": info.get("id"),
        "title": info.get("title", "未知标题"),
        "channel": info.get("channel") or info.get("uploader") or "未知频道",
        "duration": _format_duration(info.get("duration")),
        "view_count": _format_count(info.get("view_count")),
        "upload_date": _format_date(info.get("upload_date")),
        "webpage_url": info.get("webpage_url") or info.get("url", ""),
        "thumbnail": info.get("thumbnail", ""),
        "description": (info.get("description") or "").strip(),
    }


async def _fetch_thumbnail_bytes(video_id: str) -> Optional[bytes]:
    """
    获取视频最优封面图字节：优先 maxresdefault（YouTube 最高清），
    失败回退 hqdefault。返回 None 表示均不可用。
    """
    if not video_id:
        return None
    urls = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    ]
    try:
        async with httpx.AsyncClient(**_http_kwargs()) as client:
            for u in urls:
                try:
                    resp = await client.get(u)
                    # 过滤 404 占位小图（YouTube 对缺失 maxres 会返回极小图）
                    if resp.status_code == 200 and len(resp.content) > 2000:
                        return resp.content
                except Exception:
                    continue
    except Exception:
        return None
    return None


async def thumbnail_b64_best(video_id: str) -> Optional[str]:
    """获取最优封面图的 base64:// 字符串，用于即时展示；失败返回 None"""
    data = await _fetch_thumbnail_bytes(video_id)
    if not data:
        return None
    return "base64://" + base64.b64encode(data).decode()


async def parse_youtube(url: str) -> Dict:
    """
    解析 YouTube 链接，返回清洗后的元信息字典（不下载任何文件）。

    Returns:
        {
            "id", "title", "channel", "duration", "view_count",
            "upload_date", "webpage_url", "thumbnail", "description"
        }
    """
    yt_dlp = _require_yt_dlp()
    info = await _extract_with_retry(yt_dlp, url, {"skip_download": True}, download=False)
    return _summarize(info)


async def download_youtube(
    url: str,
    output_dir: Optional[Path] = None,
    with_thumbnail: bool = True,
) -> Dict:
    """
    下载 YouTube 视频（最高画质，ffmpeg 合并为 mp4）与最优封面图到本地目录。

    Args:
        url: YouTube 链接
        output_dir: 保存目录，默认取 plugin_config.yt_dl_dir
        with_thumbnail: 是否同时下载封面图

    Returns:
        {
            "summary": {...},       # 同 parse_youtube 的清洗结果
            "video_path": str|None, # 视频文件绝对路径
            "thumb_path": str|None, # 封面图文件绝对路径（最优）
            "output_dir": str,      # 实际保存目录
        }
    """
    yt_dlp = _require_yt_dlp()

    out_dir = Path(output_dir or plugin_config.yt_dl_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    info = await _extract_with_retry(yt_dlp, url, {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "format": plugin_config.yt_dl_format,
        # 封面图由本模块自行下载最优版本（maxres），无需 yt-dlp 写入
        "writethumbnail": False,
        "continuedl": True,
    }, download=True)
    summary = _summarize(info)
    video_id = info.get("id")

    # 定位视频文件路径：优先使用 requested_downloads，其次按 id glob
    video_path: Optional[str] = None
    requested = info.get("requested_downloads") or []
    if requested:
        video_path = requested[0].get("filepath")
    if not video_path and video_id:
        for p in out_dir.glob(f"{video_id}.*"):
            if p.suffix.lower() not in _THUMB_EXTS:
                video_path = str(p)
                break

    # 下载最优封面图（maxres）
    thumb_path: Optional[str] = None
    if with_thumbnail:
        data = await _fetch_thumbnail_bytes(video_id)
        if data:
            thumb_path = str(out_dir / f"{video_id}.jpg")
            Path(thumb_path).write_bytes(data)

    return {
        "summary": summary,
        "video_path": video_path,
        "thumb_path": thumb_path,
        "output_dir": str(out_dir),
    }
