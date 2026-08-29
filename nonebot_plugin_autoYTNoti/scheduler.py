"""定时轮询与推送逻辑"""

import asyncio
from datetime import datetime
from pathlib import Path

from nonebot import get_bot, logger, require

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

from nonebot.adapters.onebot.v11 import Bot, MessageSegment

from . import plugin_config
from .models import load_data, save_data
from .youtube import fetch_latest_video_ids, get_video_details, VideoInfo, download_image_b64


def _is_active_time() -> bool:
    """判断当前是否在监听活跃时间段内"""
    now_hour = datetime.now().hour
    start = plugin_config.yt_active_start
    end = plugin_config.yt_active_end

    if start <= end:
        # 正常区间，如 8~23
        return start <= now_hour < end
    else:
        # 跨午夜区间，如 22~6 表示 22:00 到次日 06:00
        return now_hour >= start or now_hour < end


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
    # 检查是否在活跃时间段内
    if not _is_active_time():
        logger.debug(
            f"YouTube通知: 当前不在监听时段 "
            f"({plugin_config.yt_active_start}:00~{plugin_config.yt_active_end}:00)，跳过"
        )
        return

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
            # 获取最新视频ID列表（取15条以防频繁发布遗漏）
            latest_ids = await fetch_latest_video_ids(channel.channel_id, limit=15)
            if not latest_ids:
                logger.debug(f"频道 {handle}: RSS返回为空")
                continue

            # 首次轮询：记录当前视频但不推送（避免添加频道时疯狂推送历史视频）
            if not channel.last_video_ids:
                logger.info(f"频道 {handle}: 首次轮询，记录当前 {len(latest_ids)} 个视频ID")
                channel.last_video_ids = latest_ids[:15]
                has_update = True
                continue

            # 找出新视频（不在已知列表中的）
            known_ids = set(channel.last_video_ids)
            new_ids = [vid for vid in latest_ids if vid not in known_ids]

            if not new_ids:
                logger.debug(f"频道 {handle}: 没有新视频")
                continue

            logger.info(f"频道 {handle}: 发现 {len(new_ids)} 个新视频: {new_ids}")

            # 获取新视频详情（传入channel_id用于判断Shorts）
            videos = await get_video_details(new_ids, channel.channel_id)

            # 按配置的类型过滤
            filtered_videos = [
                v for v in videos if v.video_type in data.push_types
            ]

            logger.info(
                f"频道 {handle}: {len(videos)} 个视频详情, "
                f"类型过滤后剩 {len(filtered_videos)} 个 "
                f"(配置类型: {data.push_types})"
            )

            # 推送给所有目标用户
            for video in filtered_videos:
                for user_id in data.push_users:
                    await _send_notification(bot, user_id, video)

            # 更新已知视频ID（合并新旧，保留最近15条）
            merged_ids = list(dict.fromkeys(latest_ids + channel.last_video_ids))[:15]
            channel.last_video_ids = merged_ids
            has_update = True

        except Exception as e:
            logger.error(f"轮询频道 {handle} 时出错: {e}")

    if has_update:
        save_data(data)


@scheduler.scheduled_job(
    "cron",
    hour=0,
    minute=0,
    id="yt_dl_dir_cleanup",
    misfire_grace_time=300,
)
async def cleanup_yt_downloads():
    """每天0点清理下载目录中的历史封面和视频文件"""
    dl_dir = Path(plugin_config.yt_dl_dir).resolve()
    if not dl_dir.is_dir():
        return

    def _cleanup() -> int:
        removed = 0
        for f in dl_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                    removed += 1
                except OSError as e:
                    logger.warning(f"清理下载目录失败 {f}: {e}")
        return removed

    try:
        removed = await asyncio.to_thread(_cleanup)
    except Exception as e:
        logger.error(f"清理下载目录 {dl_dir} 失败: {e}")
        return

    if removed:
        logger.info(f"YouTube下载目录已清理: 删除 {removed} 个文件 ({dl_dir})")
