"""文本渲染为图片（美化版）"""

import base64
import io
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# 字体回退列表（优先使用系统中文字体）
_FONT_CANDIDATES = [
    # Linux (服务器常见)
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

_font_cache: dict = {}


def _get_font(size: int = 20) -> ImageFont.FreeTypeFont:
    """获取字体，带缓存"""
    if size in _font_cache:
        return _font_cache[size]

    font = None
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue

    if font is None:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            font = ImageFont.load_default()

    _font_cache[size] = font
    return font


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int, int, int],
    radius: int,
    fill: str,
) -> None:
    """绘制圆角矩形"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def text_to_image(
    text: str,
    font_size: int = 18,
    padding: int = 36,
    line_spacing: int = 10,
    bg_color: str = "#F5F7FA",
    text_color: str = "#2C3E50",
    title: Optional[str] = None,
    title_size: int = 22,
    title_color: str = "#FFFFFF",
    title_bg_color: str = "#4A90D9",
    card_bg: str = "#FFFFFF",
    card_radius: int = 12,
    min_width: int = 420,
) -> bytes:
    """
    将文本渲染为美化的卡片式 PNG 图片。

    Args:
        text: 要渲染的文本内容（不要用emoji，用中文标记代替）
        font_size: 正文字号
        padding: 内边距
        line_spacing: 行间距
        bg_color: 整体背景色
        text_color: 正文颜色
        title: 标题文字
        title_size: 标题字号
        title_color: 标题文字颜色
        title_bg_color: 标题栏背景色
        card_bg: 卡片背景色
        card_radius: 卡片圆角
        min_width: 最小宽度

    Returns:
        PNG 图片的 bytes
    """
    font = _get_font(font_size)
    title_font = _get_font(title_size) if title else None

    lines = text.split("\n")

    # 计算内容尺寸
    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    content_width = 0
    line_heights: List[int] = []

    for line in lines:
        if not line:
            line_heights.append(font_size // 2 + 4)
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        content_width = max(content_width, w)
        line_heights.append(h + line_spacing)

    # 标题栏高度
    title_bar_height = 0
    if title and title_font:
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_bar_height = (bbox[3] - bbox[1]) + padding

    # 图片尺寸
    card_content_width = max(content_width + padding * 2, min_width)
    card_content_height = sum(line_heights) + padding * 2
    card_total_height = card_content_height + title_bar_height

    outer_padding = 20
    img_width = card_content_width + outer_padding * 2
    img_height = card_total_height + outer_padding * 2

    # 绘制
    img = Image.new("RGB", (img_width, img_height), bg_color)
    draw = ImageDraw.Draw(img)

    # 卡片背景（圆角）
    card_x1 = outer_padding
    card_y1 = outer_padding
    card_x2 = img_width - outer_padding
    card_y2 = img_height - outer_padding
    _draw_rounded_rect(draw, (card_x1, card_y1, card_x2, card_y2), card_radius, card_bg)

    # 标题栏
    y_cursor = card_y1
    if title and title_font:
        # 标题栏背景（只有顶部圆角）
        title_bar_rect = (card_x1, card_y1, card_x2, card_y1 + title_bar_height)
        _draw_rounded_rect(draw, title_bar_rect, card_radius, title_bg_color)
        # 底部补回直角（覆盖标题栏下方圆角）
        overlap_rect = (card_x1, card_y1 + title_bar_height - card_radius, card_x2, card_y1 + title_bar_height)
        draw.rectangle(overlap_rect, fill=title_bg_color)

        # 绘制标题文字（居中）
        bbox = draw.textbbox((0, 0), title, font=title_font)
        tw = bbox[2] - bbox[0]
        tx = (img_width - tw) // 2
        ty = card_y1 + (title_bar_height - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), title, fill=title_color, font=title_font)
        y_cursor = card_y1 + title_bar_height + padding
    else:
        y_cursor = card_y1 + padding

    # 绘制正文
    text_x = card_x1 + padding
    for i, line in enumerate(lines):
        if not line:
            y_cursor += line_heights[i]
            continue
        draw.text((text_x, y_cursor), line, fill=text_color, font=font)
        y_cursor += line_heights[i]

    # 底部装饰线
    footer_y = card_y2 - 4
    draw.line(
        [(card_x1 + padding, footer_y), (card_x2 - padding, footer_y)],
        fill="#E0E6ED",
        width=1,
    )

    # 输出
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def text_to_image_b64(text: str, **kwargs) -> str:
    """
    将文本渲染为图片并返回 base64 URI 字符串。
    兼容各类 OneBot 协议端。

    Returns:
        "base64://xxxxx" 格式的字符串
    """
    img_bytes = text_to_image(text, **kwargs)
    b64 = base64.b64encode(img_bytes).decode()
    return f"base64://{b64}"
