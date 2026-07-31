"""YouTube API 交互逻辑"""

import base64
import re
from typing import List, Optional, Set, Tuple

import httpx
from nonebot import logger

from . import plugin_config

# YouTube RSS Feed URL
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# YouTube Data API v3 端点
API_BASE = "https://www.googleapis.com/youtube/v3"


def _get_client_kwargs() -> dict:
    """获取 httpx 客户端公共参数（含代理配置）"""
    kwargs: dict = {"timeout": 30}
    if plugin_config.yt_proxy:
        kwargs["proxy"] = plugin_config.yt_proxy
    return kwargs


async def resolve_channel_id(handle: str) -> Optional[str]:
    """
    通过 handle（如 StarSavior_EN）解析出 channel_id。
    使用 YouTube Data API v3 channels.list 的 forHandle 参数。
    """
    # 确保 handle 带 @ 前缀
    if not handle.startswith("@"):
        handle = f"@{handle}"

    url = f"{API_BASE}/channels"
    params = {
        "part": "id",
        "forHandle": handle,
        "key": plugin_config.yt_api_key,
    }

    async with httpx.AsyncClient(**_get_client_kwargs()) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None
        return items[0]["id"]


async def fetch_latest_video_ids(channel_id: str, limit: int = 15) -> List[str]:
    """
    获取频道最近的视频 ID 列表。
    优先通过 RSS Feed（不消耗配额），失败则回退到 API playlistItems。
    """
    # 方案1: RSS Feed
    video_ids = await _fetch_via_rss(channel_id, limit)
    if video_ids:
        return video_ids

    # 方案2: 回退到 YouTube Data API（消耗配额）
    logger.info(f"RSS获取失败，回退到API方式获取频道 {channel_id} 的视频列表")
    video_ids = await _fetch_via_api(channel_id, limit)
    return video_ids


async def _fetch_via_rss(channel_id: str, limit: int) -> List[str]:
    """通过 RSS Feed 获取视频ID列表"""
    url = RSS_URL.format(channel_id=channel_id)

    try:
        async with httpx.AsyncClient(**_get_client_kwargs()) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"RSS请求失败: {url} -> 状态码 {resp.status_code}")
                return []
    except Exception as e:
        logger.warning(f"RSS请求异常: {url} -> {e}")
        return []

    # 从 XML 中提取 video ID
    video_ids = re.findall(r"<yt:videoId>([^<]+)</yt:videoId>", resp.text)
    logger.debug(f"RSS获取到 {len(video_ids)} 个视频ID (channel: {channel_id})")
    return video_ids[:limit]


async def _fetch_via_api(channel_id: str, limit: int) -> List[str]:
    """
    通过 YouTube Data API playlistItems 获取频道上传播放列表。
    频道上传播放列表 ID 为将 channel_id 的 "UC" 前缀替换为 "UU"。
    """
    if not channel_id.startswith("UC"):
        return []

    uploads_playlist_id = "UU" + channel_id[2:]

    url = f"{API_BASE}/playlistItems"
    params = {
        "part": "contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": min(limit, 50),
        "key": plugin_config.yt_api_key,
    }

    try:
        async with httpx.AsyncClient(**_get_client_kwargs()) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"API playlistItems 请求失败: 状态码 {resp.status_code}")
                return []
            data = resp.json()
    except Exception as e:
        logger.warning(f"API playlistItems 请求异常: {e}")
        return []

    video_ids = [
        item["contentDetails"]["videoId"]
        for item in data.get("items", [])
        if "contentDetails" in item
    ]
    logger.debug(f"API获取到 {len(video_ids)} 个视频ID (channel: {channel_id})")
    return video_ids


class VideoInfo:
    """视频信息"""

    def __init__(
        self,
        video_id: str,
        title: str,
        thumbnail_url: str,
        video_type: str,  # "video", "short", "live"
    ):
        self.video_id = video_id
        self.title = title
        self.thumbnail_url = thumbnail_url
        self.video_type = video_type

    @property
    def url(self) -> str:
        if self.video_type == "short":
            return f"https://www.youtube.com/shorts/{self.video_id}"
        return f"https://www.youtube.com/watch?v={self.video_id}"


async def _fetch_shorts_ids(channel_id: str) -> Set[str]:
    """
    获取频道的 Shorts 播放列表中的视频ID集合。
    YouTube 频道的 Shorts 播放列表 ID 为将 channel_id 的 "UC" 前缀替换为 "UUSH"。
    """
    # UC... -> UUSH...
    if not channel_id.startswith("UC"):
        return set()

    shorts_playlist_id = "UUSH" + channel_id[2:]

    url = f"{API_BASE}/playlistItems"
    params = {
        "part": "contentDetails",
        "playlistId": shorts_playlist_id,
        "maxResults": 15,
        "key": plugin_config.yt_api_key,
    }

    try:
        async with httpx.AsyncClient(**_get_client_kwargs()) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return set()
            data = resp.json()
    except Exception as e:
        logger.debug(f"获取Shorts播放列表失败: {e}")
        return set()

    return {
        item["contentDetails"]["videoId"]
        for item in data.get("items", [])
        if "contentDetails" in item
    }


async def get_video_details(
    video_ids: List[str], channel_id: str = ""
) -> List[VideoInfo]:
    """
    通过 YouTube Data API v3 获取视频详情，判断视频类型。
    - 直播: snippet.liveBroadcastContent == "live" 或 "upcoming"
    - Shorts: 视频ID出现在该频道的Shorts播放列表 (UUSH) 中
    - 普通视频: 其他
    """
    if not video_ids:
        return []

    # 获取该频道的 Shorts 视频 ID 集合
    shorts_ids: Set[str] = set()
    if channel_id:
        shorts_ids = await _fetch_shorts_ids(channel_id)

    url = f"{API_BASE}/videos"
    params = {
        "part": "snippet,contentDetails,liveStreamingDetails",
        "id": ",".join(video_ids),
        "key": plugin_config.yt_api_key,
    }

    async with httpx.AsyncClient(**_get_client_kwargs()) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()

    results = []
    for item in data.get("items", []):
        video_id = item["id"]
        snippet = item.get("snippet", {})

        title = snippet.get("title", "")
        # 优先使用高清封面
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url", "")
        )

        # 判断视频类型
        live_content = snippet.get("liveBroadcastContent", "none")

        if live_content in ("live", "upcoming"):
            video_type = "live"
        elif video_id in shorts_ids:
            video_type = "short"
        else:
            video_type = "video"

        results.append(
            VideoInfo(
                video_id=video_id,
                title=title,
                thumbnail_url=thumbnail_url,
                video_type=video_type,
            )
        )

    return results


async def download_image_b64(url: str) -> Optional[str]:
    """
    通过代理下载图片并转为 base64://xxx 格式。
    用于解决国内服务器无法访问 YouTube 图片 CDN 的问题。
    返回 None 表示下载失败。
    """
    if not url:
        return None
    try:
        async with httpx.AsyncClient(**_get_client_kwargs()) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            b64 = base64.b64encode(resp.content).decode()
            return f"base64://{b64}"
    except Exception as e:
        logger.debug(f"下载图片失败 {url}: {e}")
        return None
