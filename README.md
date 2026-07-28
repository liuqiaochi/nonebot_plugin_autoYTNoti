<div align="center">

# nonebot-plugin-autoytnoti

_✨ NoneBot2 YouTube 视频更新通知插件 ✨_

<a href="https://github.com/liuqiaochi/nonebot_plugin_autoYTNoti/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/liuqiaochi/nonebot_plugin_autoYTNoti" alt="license">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">
<img src="https://img.shields.io/badge/nonebot-2.2.0+-red.svg" alt="nonebot">

</div>

## 📖 介绍

监听 YouTube 频道更新，当关注的频道发布新视频时，第一时间推送封面和视频链接给指定 QQ 用户。

支持区分视频类型：**普通视频**、**Shorts 短视频**、**直播**，可自由配置推送哪些类型。

## 💿 安装

使用 nb-cli 安装（推荐）：

```bash
nb plugin install nonebot-plugin-autoytnoti
```

或使用 pip 安装：

```bash
pip install nonebot-plugin-autoytnoti
```

## ⚙️ 配置

在 `.env` 文件中添加以下配置项：

| 配置项 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `YT_API_KEY` | **是** | `""` | YouTube Data API v3 密钥 |
| `YT_POLL_INTERVAL` | 否 | `300` | 轮询间隔（秒），默认 5 分钟 |
| `YT_DATA_PATH` | 否 | `data/yt_noti/data.json` | 数据文件路径 |

### 获取 YouTube API Key

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建项目并启用 **YouTube Data API v3**
3. 创建 API 密钥，填入 `YT_API_KEY`

### 配置示例

```env
SUPERUSERS=["123456789"]
YT_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
YT_POLL_INTERVAL=300
```

## 🎉 使用

> ⚠️ **所有指令仅超级用户可用**

### 频道监听管理

| 指令 | 说明 | 示例 |
|------|------|------|
| `YT监听添加 <handle>` | 添加监听的 YouTube 频道 | `YT监听添加 StarSavior_EN` |
| `YT监听删除 <handle>` | 删除监听的 YouTube 频道 | `YT监听删除 StarSavior_EN` |

### 推送用户管理

| 指令 | 说明 | 示例 |
|------|------|------|
| `YT推送添加 <QQ号>` | 添加推送目标用户 | `YT推送添加 280035768` |
| `YT推送删除 <QQ号>` | 删除推送目标用户 | `YT推送删除 280035768` |

### 推送类型配置

| 指令 | 说明 | 示例 |
|------|------|------|
| `YT配置 <类型...>` | 配置推送类型（空格分隔） | `YT配置 视频 短视频 直播` |

可选类型：`视频`、`短视频`、`直播`，默认仅推送 `视频`。

### 查看与帮助

| 指令 | 说明 |
|------|------|
| `YT查看监听` | 以图片展示当前监听的频道列表 |
| `YT列表` | 查看当前全部配置 |
| `YT帮助` | 以图片展示帮助信息 |

## 🔧 工作原理

1. 通过 YouTube Data API 的 `forHandle` 参数将频道 handle 解析为 `channel_id`
2. 使用 YouTube RSS Feed 轮询最新视频（不消耗 API 配额）
3. 对新发现的视频调用 `videos.list` 获取详情，判断视频类型
4. Shorts 识别：通过频道的 Shorts 专属播放列表（`UUSH` 前缀）判断
5. 直播识别：通过 `snippet.liveBroadcastContent` 字段判断
6. 将符合配置类型的新视频封面和链接推送给目标用户

## 📝 更新日志

### v0.1.0

- 初始版本
- 支持频道监听管理
- 支持推送用户管理
- 支持视频类型过滤（视频/Shorts/直播）
- 支持图片形式查看监听列表和帮助

## 📄 许可证

[MIT License](LICENSE)
