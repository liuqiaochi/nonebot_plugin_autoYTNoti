"""NoneBot2 YouTube 视频更新通知插件"""

from nonebot import get_plugin_config, require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="YouTube视频更新通知",
    description="监听YouTube频道更新，第一时间推送新视频给指定QQ用户",
    usage=(
        "YT监听添加 <handle> - 添加监听的YouTube频道\n"
        "YT监听删除 <handle> - 删除监听的YouTube频道\n"
        "YT推送添加 <qq号> - 添加推送目标用户\n"
        "YT推送删除 <qq号> - 删除推送目标用户\n"
        "YT配置 <类型...> - 配置推送类型(视频/短视频/直播，空格分隔)\n"
        "YT查看监听 - 查看监听频道列表(图片)\n"
        "YT列表 - 查看当前全部配置\n"
        "YT帮助 - 显示帮助信息(图片)"
    ),
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

plugin_config = get_plugin_config(Config)

from . import commands  # noqa: E402, F401
from . import scheduler  # noqa: E402, F401
