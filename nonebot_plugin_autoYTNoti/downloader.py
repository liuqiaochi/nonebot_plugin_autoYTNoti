"""基于 yt-dlp 的 YouTube 链接解析与下载

提供能力：
- parse_youtube(url):      解析链接，返回清洗后的视频元信息（不下载）
- download_youtube(url):   下载视频与封面图到本地目录，返回路径信息
- thumbnail_b64_best(id):  获取视频最优封面图（maxres）的 base64，用于即时展示

特性：
- 默认免 cookie：YouTube 使用 tv 电视客户端（与 FeiTools 同源方案），免登录，
  画质上限约 1080p；配置 cookies（YT_DL_COOKIES / YT_DL_COOKIES_BROWSER）后
  自动注入登录态并切回默认客户端，可解锁 4K/HDR 并规避 bot 风控
- 视频使用 ffmpeg 合并最佳视频流 + 最佳音频流（mp4）
- 封面图优先取 YouTube maxresdefault（最高清），失败时回退 hqdefault
- 解析/下载/封面均复用 config 中的 YT_PROXY 代理配置

依赖：yt-dlp、ffmpeg（用于音视频合并，需位于 PATH 或通过 YT_DL_FFMPEG 指定）
"""

import asyncio
import base64
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


def _is_bilibili_url(url: str) -> bool:
    """粗略判断是否为 Bilibili 链接（bilibili.com / b23.tv / bilibili.tv）"""
    return bool(re.search(r"(?:bilibili\.com|b23\.tv|bilibili\.tv)", url, re.IGNORECASE))


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

    # JS 运行时：yt-dlp 2026 需要 JS 运行时（默认仅 deno）来解 YouTube 的 JS 挑战题。
    # 缺失时可用客户端会被降级为 _DEFAULT_JSLESS_CLIENTS（仅 visionos），
    # 播放器返回 LOGIN_REQUIRED，最终表现为 "Sign in to confirm you're not a bot"。
    # 留空则沿用 yt-dlp 默认（deno，从 PATH 查找）。
    js_runtime = getattr(plugin_config, "yt_dl_js_runtime", "") or ""
    if js_runtime.strip():
        name, _, path = js_runtime.partition(":")
        name, path = name.strip().lower(), path.strip()
        if name:
            opts["js_runtimes"] = {name: {"path": path} if path else {}}

    # 客户端策略（免 cookie 模式）：仅使用 tv 电视客户端（免登录，与 FeiTools 同源方案）。
    # 注意：Python API 的 extractor_args 必须传 list，传逗号字符串会被
    # yt-dlp 逐字符拆开导致全部无效，进而静默回退默认 web 客户端触发 bot 检测。
    # 配置 cookies 后则不强制 tv 客户端：tv 客户端不携带登录态，
    # 有登录态时切回默认客户端可解锁 4K/HDR 并规避 bot 风控。
    cookies_file = (getattr(plugin_config, "yt_dl_cookies", "") or "").strip()
    cookies_browser = (getattr(plugin_config, "yt_dl_cookies_browser", "") or "").strip()
    if cookies_file:
        opts["cookiefile"] = cookies_file
    if cookies_browser:
        # Python API 要求 tuple：(browser, profile, keyring, container)
        opts["cookiesfrombrowser"] = (cookies_browser,)
    if not (cookies_file or cookies_browser):
        opts["extractor_args"] = {"youtube": {"player_client": ["tv"]}}

    if extra:
        opts.update(extra)
    return opts


def _bili_ydl_opts(extra: Optional[Dict] = None) -> Dict:
    """
    Bilibili 专用 yt-dlp 选项（本机模式）。
    关键：B 站需要浏览器 UA + Referer，否则返回 412 Precondition Failed。
    画质策略与 YouTube 一致（强制 avc1+AAC 合并为 mp4，保证全平台可播放）。
    可选 cookies（bili_dl_cookies）用于解锁 1080P+。
    """
    opts: Dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "proxy": plugin_config.yt_proxy or None,
        "socket_timeout": 60,
        "retries": 3,
        "merge_output_format": "mp4",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "referer": "https://www.bilibili.com",
        "http_headers": {"Referer": "https://www.bilibili.com"},
    }
    if plugin_config.yt_dl_ffmpeg:
        opts["ffmpeg_location"] = plugin_config.yt_dl_ffmpeg
    cookies = (getattr(plugin_config, "bili_dl_cookies", "") or "").strip()
    if cookies:
        opts["cookiefile"] = cookies
    if extra:
        opts.update(extra)
    return opts


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
    # 远程模式：解析交给 Mac 的 app.py，本机无需 yt-dlp
    if plugin_config.yt_remote_server:
        return await remote_parse_youtube(url)

    yt_dlp = _require_yt_dlp()

    def _run():
        opts = _ydl_opts({"skip_download": True})
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = await asyncio.get_running_loop().run_in_executor(None, _run)
    return _summarize(info)


async def download_youtube(
    url: str,
    output_dir: Optional[Path] = None,
    with_thumbnail: bool = True,
    mode: str = "best",
) -> Dict:
    """
    下载 YouTube 视频（最高画质，ffmpeg 合并为 mp4）与最优封面图到本地目录。

    Args:
        url: YouTube 链接
        output_dir: 保存目录，默认取 plugin_config.yt_dl_dir
        with_thumbnail: 是否同时下载封面图
        mode: 下载画质模式（仅远程模式生效），见 app.py 的 mode 取值

    Returns:
        {
            "summary": {...},       # 同 parse_youtube 的清洗结果
            "video_path": str|None, # 视频文件绝对路径
            "thumb_path": str|None, # 封面图文件绝对路径（最优）
            "output_dir": str,      # 实际保存目录
        }
    """
    # 远程模式：下载交给 Mac 的 app.py，本机只负责拉回成品文件并发消息
    if plugin_config.yt_remote_server:
        return await remote_download_youtube(
            url, output_dir=output_dir, with_thumbnail=with_thumbnail, mode=mode
        )

    yt_dlp = _require_yt_dlp()

    out_dir = Path(output_dir or plugin_config.yt_dl_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    def _run():
        opts = _ydl_opts({
            "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
            "format": plugin_config.yt_dl_format,
            # 封面图由本模块自行下载最优版本（maxres），无需 yt-dlp 写入
            "writethumbnail": False,
            "continuedl": True,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = await asyncio.get_running_loop().run_in_executor(None, _run)
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


# ========== Bilibili 解析 / 下载 ==========
#
# 远程模式（yt_remote_server）下与 YouTube 共用 app.py 的 /api/info、/api/download，
# 这些接口按 URL 自动识别平台，因此对 Bilibili 同样适用。
# 封面处理差异：app.py 的任务状态不回传 B 站封面，故封面统一由解析返回的
# summary["thumbnail"] 字段拉取（见下方各函数）。


async def parse_bilibili(url: str) -> Dict:
    """
    解析 Bilibili 链接，返回清洗后的元信息字典（不下载任何文件）。
    字段同 parse_youtube：id/title/channel/duration/view_count/upload_date/webpage_url/thumbnail/description
    """
    if plugin_config.yt_remote_server:
        # 远程接口平台无关，直接复用（函数名虽含 youtube，逻辑通用）
        return await remote_parse_youtube(url)

    yt_dlp = _require_yt_dlp()

    def _run():
        opts = _bili_ydl_opts({"skip_download": True})
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = await asyncio.get_running_loop().run_in_executor(None, _run)
    return _summarize(info)


async def download_bilibili(
    url: str,
    output_dir: Optional[Path] = None,
    with_thumbnail: bool = True,
    mode: str = "best",
) -> Dict:
    """
    下载 Bilibili 视频（最高画质，ffmpeg 合并为 mp4）与封面图到本地目录。
    返回结构同 download_youtube。
    """
    if plugin_config.yt_remote_server:
        # 封面不在远程任务回传中，先让远程接口拉视频（不拉封面），再单独取解析返回的封面
        result = await remote_download_youtube(
            url, output_dir=output_dir, with_thumbnail=False, mode=mode
        )
        if with_thumbnail:
            tb_url = (result.get("summary") or {}).get("thumbnail")
            if tb_url:
                server = plugin_config.yt_remote_server.rstrip("/")
                token = plugin_config.yt_remote_token
                # B 站封面是绝对 URL（https://i0.hdslb.com/...），直接拉取；
                # 若为相对路径（理论上不会）才拼远程服务地址
                src = tb_url if tb_url.startswith(("http://", "https://")) else f"{server}{tb_url}"
                tb = await _remote_bytes(src, token)
                if tb:
                    out_dir = Path(result.get("output_dir") or plugin_config.yt_dl_dir).resolve()
                    out_dir.mkdir(parents=True, exist_ok=True)
                    bili_id = (result.get("summary") or {}).get("id") or "cover"
                    thumb_path = str(out_dir / f"{bili_id}.jpg")
                    Path(thumb_path).write_bytes(tb)
                    result["thumb_path"] = thumb_path
        return result

    yt_dlp = _require_yt_dlp()

    out_dir = Path(output_dir or plugin_config.yt_dl_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    def _run():
        opts = _bili_ydl_opts({
            "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
            "format": plugin_config.yt_dl_format,
            "writethumbnail": False,
            "continuedl": True,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = await asyncio.get_running_loop().run_in_executor(None, _run)
    summary = _summarize(info)
    bili_id = info.get("id")

    video_path: Optional[str] = None
    requested = info.get("requested_downloads") or []
    if requested:
        video_path = requested[0].get("filepath")
    if not video_path and bili_id:
        for p in out_dir.glob(f"{bili_id}.*"):
            if p.suffix.lower() not in _THUMB_EXTS:
                video_path = str(p)
                break

    # 封面：优先用解析返回的 thumbnail 字段
    thumb_path: Optional[str] = None
    if with_thumbnail:
        tb_url = summary.get("thumbnail")
        if tb_url:
            try:
                async with httpx.AsyncClient(**_http_kwargs()) as client:
                    r = await client.get(tb_url)
                    if r.status_code == 200 and r.content:
                        thumb_path = str(out_dir / f"{bili_id or 'cover'}.jpg")
                        Path(thumb_path).write_bytes(r.content)
            except Exception as e:
                logger.debug(f"下载 Bilibili 封面失败 {tb_url}: {e}")

    return {
        "summary": summary,
        "video_path": video_path,
        "thumb_path": thumb_path,
        "output_dir": str(out_dir),
    }


# ========== 远程模式：下载/解析全部卸载到 Mac 的 app.py ==========
#
# 数据流（pull 模型）：
#   1. bot(本机) POST /api/download {url, mode}  -> 拿到 task_id
#   2. bot 轮询 GET /api/task/<id> 直到 status=done / error（或超时）
#   3. 完成后从 /downloads/<file> 拉回视频字节、从 thumbnail_url 拉回封面字节
#   4. bot 把它们存到本机 yt_dl_dir，再像本机模式一样发消息
# app.py 侧需开启 API_TOKEN 鉴权（可选），并在任务里返回 download_url / thumbnail_url。


async def _remote_request(method: str, url: str, *, token: str = "", json_body=None, timeout: float = 60):
    """带鉴权头的远程请求；失败抛 RuntimeError。"""
    headers = {"X-Api-Token": token} if token else {}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.request(method, url, json=json_body, headers=headers)
    return resp


async def _remote_bytes(url: str, token: str = "") -> Optional[bytes]:
    """下载二进制（视频/封面）并返回字节；失败返回 None。"""
    headers = {"X-Api-Token": token} if token else {}
    try:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.content
    except Exception:
        return None
    return None


async def remote_parse_youtube(url: str) -> Dict:
    """调用 Mac app.py /api/info 解析元信息。"""
    server = plugin_config.yt_remote_server.rstrip("/")
    token = plugin_config.yt_remote_token
    resp = await _remote_request(
        "POST", f"{server}/api/info", token=token, json_body={"url": url}, timeout=60
    )
    if resp.status_code != 200:
        raise RuntimeError(f"远程解析失败: HTTP {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"远程解析失败: {data['error']}")
    return {
        "id": data.get("id"),
        "title": data.get("title", "未知标题"),
        "channel": data.get("uploader", "未知频道"),
        "duration": _format_duration(data.get("duration")),
        "view_count": _format_count(data.get("view_count")),
        "upload_date": _format_date(data.get("upload_date")),
        "webpage_url": data.get("webpage_url") or url,
        "thumbnail": data.get("thumbnail", ""),
        "description": (data.get("description") or "")[:300],
    }


async def remote_download_youtube(
    url: str,
    output_dir: Optional[Path] = None,
    with_thumbnail: bool = True,
    mode: str = "best",
) -> Dict:
    """调用 Mac app.py 完成下载，并拉回视频与封面到本机。"""
    server = plugin_config.yt_remote_server.rstrip("/")
    token = plugin_config.yt_remote_token
    timeout = plugin_config.yt_remote_timeout

    out_dir = Path(output_dir or plugin_config.yt_dl_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 元信息（用于封面消息标题等）；失败不致命，用兜底摘要
    try:
        summary = await remote_parse_youtube(url)
    except Exception as e:
        logger.warning(f"远程解析元信息失败，使用兜底: {e}")
        summary = {
            "id": "", "title": "未知标题", "channel": "", "duration": "",
            "view_count": "", "upload_date": "", "webpage_url": url,
            "thumbnail": "", "description": "",
        }

    # 2) 提交下载任务
    resp = await _remote_request(
        "POST", f"{server}/api/download", token=token,
        json_body={"url": url, "mode": mode}, timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"远程下载提交失败: HTTP {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"远程下载提交失败: {data['error']}")
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError("远程下载提交失败: 未返回 task_id")

    # 3) 轮询任务状态
    poll_interval = 5
    elapsed = 0
    video_path: Optional[str] = None
    thumb_path: Optional[str] = None
    while elapsed < timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        try:
            r = await _remote_request("GET", f"{server}/api/task/{task_id}", token=token, timeout=30)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        t = r.json()
        status = t.get("status")
        if status == "done":
            # 拉回视频
            dl_url = t.get("download_url")
            if dl_url:
                vb = await _remote_bytes(f"{server}{dl_url}", token)
                if vb:
                    fname = t.get("filename") or f"{task_id}.mp4"
                    # 去掉可能带上的任务前缀文件名冲突，使用任务id保底
                    safe_name = fname if task_id in fname else f"{task_id}_{fname}"
                    video_path = str(out_dir / safe_name)
                    Path(video_path).write_bytes(vb)
            # 拉回封面：优先 app.py 下发的 thumbnail_url，否则回退 YouTube maxres
            if with_thumbnail:
                tb_url = t.get("thumbnail_url")
                if tb_url:
                    tb = await _remote_bytes(f"{server}{tb_url}", token)
                    if tb:
                        thumb_path = str(out_dir / f"{task_id}_thumb.jpg")
                        Path(thumb_path).write_bytes(tb)
                elif summary.get("id"):
                    tb = await _fetch_thumbnail_bytes(summary["id"])
                    if tb:
                        thumb_path = str(out_dir / f"{summary['id']}.jpg")
                        Path(thumb_path).write_bytes(tb)
            break
        elif status == "error":
            raise RuntimeError(f"远程下载失败: {t.get('error', '未知错误')}")
    else:
        raise RuntimeError(
            f"远程下载超时（>{timeout}s），任务 {task_id} 仍在服务器进行中，"
            f"稍后可去 Mac 端 /downloads 目录取文件"
        )

    return {
        "summary": summary,
        "video_path": video_path,
        "thumb_path": thumb_path,
        "output_dir": str(out_dir),
    }
