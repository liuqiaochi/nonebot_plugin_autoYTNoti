"""指令处理"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    Message,
)
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from .models import ChannelData, load_data, save_data
from .render import text_to_image_b64
from .youtube import resolve_channel_id


# ========== 工具函数 ==========


def _cmd(name: str, **kwargs):
    """注册指令，自动添加大小写变体aliases"""
    # 生成大小写变体：YT -> yt, Yt, yT
    aliases = set()
    # 将"YT"部分替换为各种大小写组合
    suffix = name[2:]  # 去掉 "YT" 前缀
    for prefix in ("yt", "Yt", "yT"):
        aliases.add(f"{prefix}{suffix}")
    return on_command(name, aliases=aliases, **kwargs)


# ========== 监听管理 ==========

yt_watch_add = _cmd("YT监听添加", permission=SUPERUSER, priority=5, block=True)
yt_watch_del = _cmd("YT监听删除", permission=SUPERUSER, priority=5, block=True)

# ========== 推送用户管理 ==========

yt_push_add = _cmd("YT推送添加", permission=SUPERUSER, priority=5, block=True)
yt_push_del = _cmd("YT推送删除", permission=SUPERUSER, priority=5, block=True)

# ========== 配置管理 ==========

yt_config = _cmd("YT配置", permission=SUPERUSER, priority=5, block=True)
yt_list = _cmd("YT列表", permission=SUPERUSER, priority=5, block=True)

# ========== 查看与帮助 ==========

yt_watch_list = _cmd("YT查看监听", permission=SUPERUSER, priority=5, block=True)
yt_help = _cmd("YT帮助", permission=SUPERUSER, priority=5, block=True)


# ========== 合并转发工具 ==========


async def _send_forward_msg(bot: Bot, event: MessageEvent, messages: list):
    """
    发送合并转发消息。
    messages: list of str 或 MessageSegment，每条作为转发中的一个节点。
    """
    bot_info = await bot.get_login_info()
    bot_name = bot_info.get("nickname", "YT通知")
    bot_id = str(bot_info.get("user_id", bot.self_id))

    forward_nodes = []
    for msg_content in messages:
        forward_nodes.append({
            "type": "node",
            "data": {
                "name": bot_name,
                "uin": bot_id,
                "content": str(msg_content) if isinstance(msg_content, str) else msg_content,
            },
        })

    if isinstance(event, GroupMessageEvent):
        await bot.call_api(
            "send_group_forward_msg",
            group_id=event.group_id,
            messages=forward_nodes,
        )
    else:
        await bot.call_api(
            "send_private_forward_msg",
            user_id=event.user_id,
            messages=forward_nodes,
        )


# ---------- 监听添加 ----------


@yt_watch_add.handle()
async def handle_watch_add(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    handle = args.extract_plain_text().strip()
    if not handle:
        await yt_watch_add.finish("请提供YouTube频道handle，例如：YT监听添加 StarSavior_EN")

    # 去掉可能的 @ 前缀用于存储
    clean_handle = handle.lstrip("@")

    data = load_data()
    if clean_handle in data.channels:
        await yt_watch_add.finish(f"频道 {clean_handle} 已在监听列表中")

    await yt_watch_add.send(f"正在解析频道 {clean_handle} ...")

    # 解析 channel_id
    channel_id = await resolve_channel_id(clean_handle)
    if not channel_id:
        await yt_watch_add.finish(
            f"无法解析频道 {clean_handle}，请确认handle正确且API Key已配置"
        )

    data.channels[clean_handle] = ChannelData(
        handle=clean_handle,
        channel_id=channel_id,
    )
    save_data(data)
    await yt_watch_add.finish(
        f"已添加监听频道: {clean_handle}\n频道ID: {channel_id}"
    )


# ---------- 监听删除 ----------


@yt_watch_del.handle()
async def handle_watch_del(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    handle = args.extract_plain_text().strip().lstrip("@")
    if not handle:
        await yt_watch_del.finish("请提供要删除的YouTube频道handle")

    data = load_data()
    if handle not in data.channels:
        await yt_watch_del.finish(f"频道 {handle} 不在监听列表中")

    del data.channels[handle]
    save_data(data)
    await yt_watch_del.finish(f"已删除监听频道: {handle}")


# ---------- 推送添加 ----------


@yt_push_add.handle()
async def handle_push_add(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    user_id = args.extract_plain_text().strip()
    if not user_id:
        await yt_push_add.finish("请提供QQ号，例如：YT推送添加 280035768")

    if not user_id.isdigit():
        await yt_push_add.finish("QQ号必须为纯数字")

    data = load_data()
    if user_id in data.push_users:
        await yt_push_add.finish(f"用户 {user_id} 已在推送列表中")

    data.push_users.append(user_id)
    save_data(data)
    await yt_push_add.finish(f"已添加推送用户: {user_id}")


# ---------- 推送删除 ----------


@yt_push_del.handle()
async def handle_push_del(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    user_id = args.extract_plain_text().strip()
    if not user_id:
        await yt_push_del.finish("请提供要删除的QQ号")

    data = load_data()
    if user_id not in data.push_users:
        await yt_push_del.finish(f"用户 {user_id} 不在推送列表中")

    data.push_users.remove(user_id)
    save_data(data)
    await yt_push_del.finish(f"已删除推送用户: {user_id}")


# ---------- 类型配置 ----------

VALID_TYPES = {"视频": "video", "短视频": "short", "直播": "live"}
TYPE_NAMES = {v: k for k, v in VALID_TYPES.items()}


@yt_config.handle()
async def handle_config(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    text = args.extract_plain_text().strip()
    if not text:
        await yt_config.finish(
            "请提供推送类型（空格分隔），可选：视频 短视频 直播\n"
            "例如：YT配置 视频 短视频"
        )

    types = text.split()
    invalid = [t for t in types if t not in VALID_TYPES]
    if invalid:
        await yt_config.finish(
            f"无效的类型: {', '.join(invalid)}\n可选: 视频 短视频 直播"
        )

    push_types = list(set(VALID_TYPES[t] for t in types))

    data = load_data()
    data.push_types = push_types
    save_data(data)

    type_display = " ".join(TYPE_NAMES[t] for t in push_types)
    await yt_config.finish(f"推送类型已更新为: {type_display}")


# ---------- 列表查看（合并转发） ----------


@yt_list.handle()
async def handle_list(bot: Bot, event: MessageEvent):
    data = load_data()

    messages = []

    # 第一条：监听频道
    ch_lines = ["[ 监听频道 ]"]
    if data.channels:
        for i, (handle, ch) in enumerate(data.channels.items(), 1):
            ch_lines.append(f"{i}. @{handle}")
            ch_lines.append(f"   ID: {ch.channel_id}")
    else:
        ch_lines.append("(无)")
    messages.append("\n".join(ch_lines))

    # 第二条：推送用户
    user_lines = ["[ 推送用户 ]"]
    if data.push_users:
        for i, uid in enumerate(data.push_users, 1):
            user_lines.append(f"{i}. {uid}")
    else:
        user_lines.append("(无)")
    messages.append("\n".join(user_lines))

    # 第三条：推送类型
    type_display = "、".join(TYPE_NAMES.get(t, t) for t in data.push_types)
    messages.append(f"[ 推送类型 ]\n{type_display}")

    await _send_forward_msg(bot, event, messages)


# ---------- 查看监听（图片） ----------


@yt_watch_list.handle()
async def handle_watch_list(bot: Bot, event: MessageEvent):
    data = load_data()

    lines = []
    if data.channels:
        lines.append(f"共监听 {len(data.channels)} 个频道")
        lines.append("")
        for i, (handle, ch) in enumerate(data.channels.items(), 1):
            lines.append(f"  {i}. @{handle}")
            lines.append(f"     ID: {ch.channel_id}")
            lines.append("")
    else:
        lines.append("当前没有监听任何频道")

    img_b64 = text_to_image_b64(
        "\n".join(lines),
        title="YouTube 监听列表",
    )
    await yt_watch_list.finish(MessageSegment.image(img_b64))


# ---------- 帮助（图片） ----------

HELP_TEXT = """\
[监听管理]
  YT监听添加 <handle>  添加监听频道
  YT监听删除 <handle>  删除监听频道

[推送管理]
  YT推送添加 <QQ号>    添加推送用户
  YT推送删除 <QQ号>    删除推送用户

[配置]
  YT配置 <类型...>     设置推送类型
    可选: 视频 / 短视频 / 直播
    示例: YT配置 视频 短视频

[查看]
  YT查看监听           查看监听列表(图片)
  YT列表               查看全部配置(转发)
  YT帮助               显示本帮助(图片)

* 指令不区分大小写 (YT/yt/Yt 均可)
* 所有指令仅超级用户可用"""


@yt_help.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    img_b64 = text_to_image_b64(
        HELP_TEXT,
        title="YT通知插件 - 帮助",
        font_size=17,
    )
    await yt_help.finish(MessageSegment.image(img_b64))
