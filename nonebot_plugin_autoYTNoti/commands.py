"""指令处理"""

from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    Message,
)
from nonebot.exception import FinishedException
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from .models import ChannelData, load_data, save_data
from .render import text_to_image_b64
from .youtube import resolve_channel_id, fetch_latest_video_ids, get_video_details, download_image_b64
from .downloader import (
    parse_youtube,
    download_youtube,
    thumbnail_b64_best,
    _is_youtube_url,
    _require_yt_dlp,
    _find_url,
)


# ========== 工具函数 ==========


def _cmd(name: str, **kwargs):
    """注册指令，自动添加大小写变体aliases"""
    aliases = set()
    suffix = name[2:]  # 去掉 "YT" 前缀
    for prefix in ("yt", "Yt", "yT"):
        aliases.add(f"{prefix}{suffix}")
    return on_command(name, aliases=aliases, **kwargs)


def _extract_youtube_url(event, args: Message) -> str:
    """
    从指令参数或被引用/回复的消息中提取 YouTube 链接。
    支持直接发送链接，也支持「回复 / 引用」一条含链接的消息触发。
    """
    # 1) 优先从指令参数文本中取
    url = _find_url(args.extract_plain_text())
    if url:
        return url

    # 2) 从被引用 / 回复的消息中取
    reply = getattr(event, "reply", None)
    if reply is not None:
        # 情况A：reply 本身就是 Message 对象
        if hasattr(reply, "extract_plain_text"):
            url = _find_url(reply.extract_plain_text())
            if url:
                return url
        # 情况B：reply.message 是 Message 对象
        msg = getattr(reply, "message", None)
        if msg is not None and hasattr(msg, "extract_plain_text"):
            url = _find_url(msg.extract_plain_text())
            if url:
                return url
    return ""


# ========== 指令注册 ==========

yt_watch_add = _cmd("YT监听添加", permission=SUPERUSER, priority=5, block=True)
yt_watch_del = _cmd("YT监听删除", permission=SUPERUSER, priority=5, block=True)
yt_watch_list = _cmd("YT监听查看", permission=SUPERUSER, priority=5, block=True)

yt_push_add = _cmd("YT推送添加", permission=SUPERUSER, priority=5, block=True)
yt_push_del = _cmd("YT推送删除", permission=SUPERUSER, priority=5, block=True)

yt_config = _cmd("YT配置", permission=SUPERUSER, priority=5, block=True)
yt_list = _cmd("YT列表", permission=SUPERUSER, priority=5, block=True)
yt_test = _cmd("YT测试", permission=SUPERUSER, priority=5, block=True)
yt_help = _cmd("YT帮助", permission=SUPERUSER, priority=5, block=True)

yt_parse = _cmd("YT解析", permission=SUPERUSER, priority=5, block=True)
yt_dl = _cmd("YT下载", permission=SUPERUSER, priority=5, block=True)


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

    clean_handle = handle.lstrip("@")

    data = load_data()
    if clean_handle in data.channels:
        await yt_watch_add.finish(f"频道 {clean_handle} 已在监听列表中")

    await yt_watch_add.send(f"正在解析频道 {clean_handle} ...")

    channel_id = await resolve_channel_id(clean_handle)
    if not channel_id:
        await yt_watch_add.finish(
            f"无法解析频道 {clean_handle}，请确认handle正确且API Key已配置"
        )

    # 添加时获取当前视频列表作为基线，避免首次轮询推送历史视频
    current_ids = await fetch_latest_video_ids(channel_id, limit=15)

    data.channels[clean_handle] = ChannelData(
        handle=clean_handle,
        channel_id=channel_id,
        last_video_ids=current_ids,
    )
    save_data(data)
    await yt_watch_add.finish(
        f"已添加监听频道: {clean_handle}\n频道ID: {channel_id}\n已记录当前 {len(current_ids)} 个视频作为基线"
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


# ---------- 推送添加（支持@用户或手动输入QQ号） ----------


@yt_push_add.handle()
async def handle_push_add(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    # 优先从消息中提取 @用户 的QQ号
    user_id = ""
    for seg in args:
        if seg.type == "at":
            user_id = str(seg.data.get("qq", ""))
            break

    # 如果没有@，则尝试从纯文本获取
    if not user_id:
        user_id = args.extract_plain_text().strip()

    if not user_id:
        await yt_push_add.finish(
            "请提供QQ号或@用户\n"
            "示例: YT推送添加 280035768\n"
            "示例: YT推送添加 @某人"
        )

    if not user_id.isdigit():
        await yt_push_add.finish("无法识别QQ号，请直接输入数字或@用户")

    data = load_data()
    if user_id in data.push_users:
        await yt_push_add.finish(f"用户 {user_id} 已在推送列表中")

    data.push_users.append(user_id)
    save_data(data)
    await yt_push_add.finish(f"已添加推送用户: {user_id}")


# ---------- 推送删除（支持@用户或手动输入QQ号） ----------


@yt_push_del.handle()
async def handle_push_del(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    user_id = ""
    for seg in args:
        if seg.type == "at":
            user_id = str(seg.data.get("qq", ""))
            break

    if not user_id:
        user_id = args.extract_plain_text().strip()

    if not user_id:
        await yt_push_del.finish("请提供QQ号或@用户")

    if not user_id.isdigit():
        await yt_push_del.finish("无法识别QQ号，请直接输入数字或@用户")

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


# ---------- 监听查看（图片） ----------


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


# ---------- 测试推送 ----------


@yt_test.handle()
async def handle_test(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    data = load_data()

    if not data.channels:
        await yt_test.finish("当前没有监听任何频道，请先添加监听")

    if not data.push_users:
        await yt_test.finish("当前没有推送用户，请先添加推送用户")

    # 可以指定频道handle测试，否则取第一个
    target_handle = args.extract_plain_text().strip().lstrip("@")
    if target_handle and target_handle in data.channels:
        channel = data.channels[target_handle]
    else:
        target_handle = next(iter(data.channels))
        channel = data.channels[target_handle]

    if not channel.channel_id:
        await yt_test.finish(f"频道 {target_handle} 的channel_id为空，请删除后重新添加")

    await yt_test.send(f"正在获取频道 @{target_handle} 的最新视频...")

    try:
        video_ids = await fetch_latest_video_ids(channel.channel_id, limit=1)
        if not video_ids:
            await yt_test.finish("未能获取到视频，请检查网络和代理配置")

        videos = await get_video_details(video_ids, channel.channel_id)
        if not videos:
            await yt_test.finish("未能获取视频详情，请检查API Key配置")

        video = videos[0]
        type_names = {"video": "视频", "short": "短视频", "live": "直播"}
        type_label = type_names.get(video.video_type, "视频")

        # 通过代理下载封面图转base64
        img_b64 = await download_image_b64(video.thumbnail_url)

        msg = MessageSegment.text(f"[测试推送] YouTube{type_label}\n")
        msg += MessageSegment.text(f"{video.title}\n")
        if img_b64:
            msg += MessageSegment.image(img_b64)
        msg += MessageSegment.text(f"\n{video.url}")

        # 推送给所有目标用户
        success_count = 0
        fail_count = 0
        for user_id in data.push_users:
            try:
                await bot.send_private_msg(user_id=int(user_id), message=msg)
                success_count += 1
            except Exception as e:
                logger.error(f"测试推送给 {user_id} 失败: {e}")
                fail_count += 1

        result = f"测试完成: 成功 {success_count} 人"
        if fail_count:
            result += f"，失败 {fail_count} 人"
        await yt_test.finish(result)

    except FinishedException:
        raise
    except Exception as e:
        await yt_test.finish(f"测试失败: {e}")


# ---------- 帮助（图片） ----------

HELP_TEXT = """\
[监听管理]
  YT监听添加 <handle>  添加监听频道
  YT监听删除 <handle>  删除监听频道
  YT监听查看           查看监听列表(图片)

[推送管理]
  YT推送添加 <QQ/@人>  添加推送用户
  YT推送删除 <QQ/@人>  删除推送用户

[配置]
  YT配置 <类型...>     设置推送类型
    可选: 视频 / 短视频 / 直播
    示例: YT配置 视频 短视频

[查看]
  YT列表               查看全部配置(转发)
  YT测试 [handle]      测试推送第一个视频
  YT帮助               显示本帮助(图片)

[按需解析/下载]
  YT解析 <链接>        解析链接,返回标题/频道/时长/播放量/封面
  YT下载 <链接>        下载视频与封面图(两条消息直发:封面+视频)
    链接支持直接发送,也可回复/引用含链接的消息
    走tv客户端免cookie(画质上限约1080p)

* 指令不区分大小写 (YT/yt/Yt 均可)
* 推送添加/删除支持直接@用户
* 所有指令仅超级用户可用"""


@yt_help.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    img_b64 = text_to_image_b64(
        HELP_TEXT,
        title="YT通知插件 - 帮助",
        font_size=17,
    )
    await yt_help.finish(MessageSegment.image(img_b64))


# ---------- 链接解析（仅元信息，不下载） ----------


@yt_parse.handle()
async def handle_parse(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    url = _extract_youtube_url(event, args)
    if not url:
        await yt_parse.finish(
            "未找到YouTube链接。可直接发送链接，或回复/引用一条含链接的消息。\n"
            "示例：YT解析 https://www.youtube.com/watch?v=xxxxxxxxxxx"
        )

    if not _is_youtube_url(url):
        await yt_parse.finish("链接似乎不是YouTube链接，请检查后重试")

    try:
        _require_yt_dlp()
    except RuntimeError as e:
        await yt_parse.finish(str(e))

    await yt_parse.send("正在解析链接...")

    try:
        summary = await parse_youtube(url)
    except Exception as e:
        await yt_parse.finish(f"解析失败: {e}")

    text = (
        f"[YouTube 解析]\n"
        f"标题: {summary['title']}\n"
        f"频道: {summary['channel']}\n"
        f"时长: {summary['duration']}\n"
        f"播放量: {summary['view_count']}\n"
        f"发布: {summary['upload_date']}\n"
        f"链接: {summary['webpage_url']}"
    )
    msg = MessageSegment.text(text)

    # 优先使用最优封面图（maxres），失败回退到 API 缩略图
    if summary.get("id"):
        img_b64 = await thumbnail_b64_best(summary["id"])
        if not img_b64 and summary.get("thumbnail"):
            img_b64 = await download_image_b64(summary["thumbnail"])
        if img_b64:
            msg += MessageSegment.image(img_b64)

    await yt_parse.finish(msg)


# ---------- 链接下载（视频 + 封面图） ----------


@yt_dl.handle()
async def handle_dl(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    url = _extract_youtube_url(event, args)
    if not url:
        await yt_dl.finish(
            "未找到YouTube链接。可直接发送链接，或回复/引用一条含链接的消息。\n"
            "示例：YT下载 https://www.youtube.com/watch?v=xxxxxxxxxxx"
        )

    if not _is_youtube_url(url):
        await yt_dl.finish("链接似乎不是YouTube链接，请检查后重试")

    try:
        _require_yt_dlp()
    except RuntimeError as e:
        await yt_dl.finish(str(e))

    await yt_dl.send("正在解析并下载（最高画质，视频+音频合并；封面取最优），请稍候...")

    try:
        result = await download_youtube(url)
    except Exception as e:
        await yt_dl.finish(f"下载失败: {e}")

    summary = result["summary"]
    video_path = result.get("video_path")
    thumb_path = result.get("thumb_path")
    output_dir = result.get("output_dir")

    # 以两条直发消息返回（不使用合并转发）：① 封面图 + 元信息 ② 视频
    info_text = (
        f"[YouTube 下载完成]\n"
        f"标题: {summary['title']}\n"
        f"频道: {summary['channel']}\n"
        f"时长: {summary['duration']}"
    )
    cover_node = MessageSegment.text(info_text)
    if thumb_path:
        cover_node += MessageSegment.image(thumb_path)
    await yt_dl.send(cover_node)

    # 视频单独直发：放进合并转发节点会被 QQ 显示为「已过期」
    if video_path:
        try:
            await yt_dl.send(MessageSegment.video(video_path))
        except Exception as ve:
            logger.error(f"发送视频文件失败 {video_path}: {ve}")
            await yt_dl.send(
                f"视频文件已保存到本地: {video_path}\n"
                f"（通过QQ发送失败：{ve}）"
            )
    else:
        await yt_dl.send(f"视频文件未生成，保存目录: {output_dir}")
