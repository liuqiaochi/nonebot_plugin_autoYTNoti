"""数据模型与持久化"""

import json
from pathlib import Path
from typing import Dict, List, Set

from pydantic import BaseModel, Field

from . import plugin_config


class ChannelData(BaseModel):
    """单个频道的监听数据"""

    handle: str
    channel_id: str = ""
    last_video_ids: List[str] = Field(default_factory=list)


class PluginData(BaseModel):
    """插件全局持久化数据"""

    # 监听的频道列表 {handle: ChannelData}
    channels: Dict[str, ChannelData] = Field(default_factory=dict)

    # 推送目标QQ用户ID列表
    push_users: List[str] = Field(default_factory=list)

    # 推送的视频类型: video(视频), short(短视频), live(直播)
    push_types: List[str] = Field(default_factory=lambda: ["video"])


def _get_data_path() -> Path:
    """获取数据文件路径"""
    path = Path(plugin_config.yt_data_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_data() -> PluginData:
    """从文件加载数据"""
    path = _get_data_path()
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return PluginData.model_validate(raw)
    return PluginData()


def save_data(data: PluginData) -> None:
    """保存数据到文件"""
    path = _get_data_path()
    path.write_text(
        data.model_dump_json(indent=2),
        encoding="utf-8",
    )
