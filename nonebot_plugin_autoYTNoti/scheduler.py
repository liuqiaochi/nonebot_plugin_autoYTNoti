"""定时轮询与推送逻辑"""

from nonebot import get_bot, logger, require

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

from nonebot.adapters.onebot.v11 import Bot, MessageSegment

from . import plugin_config
from .models import load_data, save_data
from .youtube import fetch_latest_video_ids, get_video_details, VideoInfo, download_image_b64


async def _send_notification(bot: Bot, user_id: str, video: VideoInfo) -> None:
    """向指定用户发送视频通知"""
    type_names = {"video": "视频", "short": "短视频", "live": "直播"}
    type_label = type_names.get(video.video_type, "视频")

    # 通过代理下载封面图转base64，避免协议端直接访问YouTube CDN
    img_b64 = await download_image_b64(video.thumbnail_url)

    msg = MessageSegment.text(f"[YT新{type_label}更新]\n")
    msg += MessageSegment.text(f"{video.title}\n")
    if img_b64:
        msg += MessageSegment.image(img_b64)
    msg += MessageSegment.text(f"\n{video.url}")

    try:
        await bot.send_private_msg(user_id=int(user_id), message=msg)
    except Exception as e:
        logger.error(f"推送消息给用户 {user_id} 失败: {e}")


@scheduler.scheduled_job(
    "interval",
    seconds=plugin_config.yt_poll_interval,
    id="yt_noti_poll",
    misfire_grace_time=60,
)
async def poll_youtube_updates():
    """定时轮询YouTube频道更新"""
    try:
        bot: Bot = get_bot()  # type: ignore
    except ValueError:
        logger.debug("YouTube通知: 没有可用的Bot连接")
        return

    data = load_data()

    if not data.channels or not data.push_users:
        return

    has_update = False

    for handle, channel in data.channels.items():
        if not channel.channel_id:
            continue

        try:
            # 获取最新视频ID列表
            latest_ids = await fetch_latest_video_ids(channel.channel_id)
            if not latest_ids:
                continue

            # 找出新视频
            known_ids = set(channel.last_video_ids)
            new_ids = [vid for vid in latest_ids if vid not in known_ids]

            if not new_ids:
                continue

            # 获取新视频详情（传入channel_id用于判断Shorts）
            videos = await get_video_details(new_ids, channel.channel_id)

            # 按配置的类型过滤
            filtered_videos = [
                v for v in videos if v.video_type in data.push_types
            ]

            # 推送给所有目标用户
            for video in filtered_videos:
                for user_id in data.push_users:
                    await _send_notification(bot, user_id, video)

            # 更新已知视频ID（保留最近15条防止遗漏）
            channel.last_video_ids = latest_ids[:15]
            has_update = True

        except Exception as e:
            logger.error(f"轮询频道 {handle} 时出错: {e}")

    if has_update:
        save_data(data)
