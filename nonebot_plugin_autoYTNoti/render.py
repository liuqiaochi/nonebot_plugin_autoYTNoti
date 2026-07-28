"""文本渲染为图片"""

import io
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

# 字体回退列表（优先使用系统中文字体）
_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    # Linux
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
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
        # 使用 Pillow 内置默认字体
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            font = ImageFont.load_default()

    _font_cache[size] = font
    return font


def text_to_image(
    text: str,
    font_size: int = 20,
    padding: int = 30,
    line_spacing: int = 8,
    bg_color: str = "#FFFFFF",
    text_color: str = "#333333",
    title: Optional[str] = None,
    title_size: int = 26,
    title_color: str = "#1a1a1a",
) -> bytes:
    """
    将文本渲染为 PNG 图片字节。

    Args:
        text: 要渲染的文本内容
        font_size: 正文字号
        padding: 边距
        line_spacing: 行间距
        bg_color: 背景色
        text_color: 文字颜色
        title: 标题（可选，会加粗居中显示）
        title_size: 标题字号
        title_color: 标题颜色

    Returns:
        PNG 图片的 bytes
    """
    font = _get_font(font_size)
    title_font = _get_font(title_size) if title else None

    lines = text.split("\n")

    # 计算每行宽度和总高度
    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    max_width = 0
    line_heights: List[int] = []

    # 标题部分
    title_height = 0
    if title and title_font:
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = bbox[2] - bbox[0]
        title_height = bbox[3] - bbox[1] + line_spacing * 2
        max_width = max(max_width, title_width)

    # 正文部分
    for line in lines:
        if not line:
            line_heights.append(font_size // 2)
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_width = max(max_width, w)
        line_heights.append(h + line_spacing)

    # 最终图片尺寸
    img_width = max_width + padding * 2
    img_height = sum(line_heights) + title_height + padding * 2

    # 绘制
    img = Image.new("RGB", (img_width, img_height), bg_color)
    draw = ImageDraw.Draw(img)

    y = padding

    # 绘制标题
    if title and title_font:
        bbox = draw.textbbox((0, 0), title, font=title_font)
        tw = bbox[2] - bbox[0]
        tx = (img_width - tw) // 2
        draw.text((tx, y), title, fill=title_color, font=title_font)
        y += title_height

    # 绘制正文
    for i, line in enumerate(lines):
        if not line:
            y += line_heights[i]
            continue
        draw.text((padding, y), line, fill=text_color, font=font)
        y += line_heights[i]

    # 输出为 bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
