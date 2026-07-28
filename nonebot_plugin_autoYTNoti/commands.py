"""指令处理"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.permission import SUPERUSER

from .models import ChannelData, load_data, save_data
from .render import text_to_image_b64
from .youtube import resolve_channel_id

# ========== 监听管理 ==========

yt_watch_add = on_command("YT监听添加", permission=SUPERUSER, priority=5, block=True)
yt_watch_del = on_command("YT监听删除", permission=SUPERUSER, priority=5, block=True)

# ========== 推送用户管理 ==========

yt_push_add = on_command("YT推送添加", permission=SUPERUSER, priority=5, block=True)
yt_push_del = on_command("YT推送删除", permission=SUPERUSER, priority=5, block=True)

# ========== 配置管理 ==========

yt_config = on_command("YT配置", permission=SUPERUSER, priority=5, block=True)
yt_list = on_command("YT列表", permission=SUPERUSER, priority=5, block=True)

# ========== 查看与帮助 ==========

yt_watch_list = on_command("YT查看监听", permission=SUPERUSER, priority=5, block=True)
yt_help = on_command("YT帮助", permission=SUPERUSER, priority=5, block=True)


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


# ---------- 列表查看 ----------

@yt_list.handle()
async def handle_list(bot: Bot, event: MessageEvent):
    data = load_data()

    lines = ["===== YouTube通知配置 ====="]

    # 监听频道
    lines.append("\n📺 监听频道:")
    if data.channels:
        for handle, ch in data.channels.items():
            lines.append(f"  - {handle} ({ch.channel_id})")
    else:
        lines.append("  (无)")

    # 推送用户
    lines.append("\n👤 推送用户:")
    if data.push_users:
        for uid in data.push_users:
            lines.append(f"  - {uid}")
    else:
        lines.append("  (无)")

    # 推送类型
    lines.append("\n📋 推送类型:")
    type_display = " ".join(TYPE_NAMES.get(t, t) for t in data.push_types)
    lines.append(f"  {type_display}")

    await yt_list.finish("\n".join(lines))


# ---------- 查看监听（图片） ----------

@yt_watch_list.handle()
async def handle_watch_list(bot: Bot, event: MessageEvent):
    data = load_data()

    lines = []
    if data.channels:
        lines.append(f"共监听 {len(data.channels)} 个频道:")
        lines.append("")
        for i, (handle, ch) in enumerate(data.channels.items(), 1):
            lines.append(f"  {i}. @{handle}")
            lines.append(f"     ID: {ch.channel_id}")
            lines.append("")
    else:
        lines.append("当前没有监听任何频道")

    img_b64 = text_to_image_b64(
        "\n".join(lines),
        title="📺 YouTube 监听列表",
    )
    await yt_watch_list.finish(MessageSegment.image(img_b64))


# ---------- 帮助（图片） ----------

HELP_TEXT = """\
YT监听添加 <handle>
  添加监听的YouTube频道
  示例: YT监听添加 StarSavior_EN

YT监听删除 <handle>
  删除监听的YouTube频道

YT推送添加 <QQ号>
  添加推送目标用户
  示例: YT推送添加 280035768

YT推送删除 <QQ号>
  删除推送目标用户

YT配置 <类型...>
  配置推送视频类型（空格分隔）
  可选: 视频 短视频 直播
  默认: 视频
  示例: YT配置 视频 短视频

YT查看监听
  查看当前监听的频道列表（图片）

YT列表
  查看当前全部配置（文本）

YT帮助
  显示本帮助信息（图片）

注: 所有指令仅超级用户可用"""


@yt_help.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    img_b64 = text_to_image_b64(
        HELP_TEXT,
        title="📖 YT通知插件帮助",
        font_size=18,
    )
    await yt_help.finish(MessageSegment.image(img_b64))
