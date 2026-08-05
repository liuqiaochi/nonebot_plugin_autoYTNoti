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
