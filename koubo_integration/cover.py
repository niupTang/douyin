import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 1920


def find_font():
    configured = os.environ.get("KOUBO_FONT_PATH")
    candidates = [
        configured,
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def font(size):
    font_path = find_font()
    return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()


def split_title(title, line_length=7):
    normalized = "".join(str(title).strip().splitlines())
    return textwrap.wrap(normalized, width=line_length)[:4] or ["口播封面"]


def render_cover(output_path, title, template="knowledge", author=""):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if template == "business":
        background = (9, 10, 13)
        accent = (209, 171, 81)
        foreground = (244, 240, 229)
        label = "BUSINESS VIEW"
    else:
        background = (8, 9, 11)
        accent = (250, 200, 52)
        foreground = (250, 249, 244)
        label = "KNOWLEDGE"
    image = Image.new("RGB", (WIDTH, HEIGHT), background)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        shade = int(26 * (1 - y / HEIGHT))
        draw.line((0, y, WIDTH, y), fill=tuple(min(255, value + shade) for value in background))
    draw.rounded_rectangle((72, 104, 390, 166), radius=31, fill=accent)
    draw.text((102, 119), label, font=font(27), fill=(20, 18, 12))
    draw.line((72, 224, 1008, 224), fill=accent, width=5)
    lines = split_title(title)
    title_font = font(142 if len(lines) <= 3 else 118)
    y = 520
    for index, line in enumerate(lines):
        fill = accent if index == 1 or (len(lines) == 1 and index == 0) else foreground
        bbox = draw.textbbox((0, 0), line, font=title_font, stroke_width=2)
        line_width = bbox[2] - bbox[0]
        x = max(72, (WIDTH - line_width) // 2)
        draw.text((x + 8, y + 12), line, font=title_font, fill=(0, 0, 0), stroke_width=4)
        draw.text((x, y), line, font=title_font, fill=fill, stroke_width=2, stroke_fill=fill)
        y += int(title_font.size * 1.24) if hasattr(title_font, "size") else 160
    draw.line((72, 1640, 1008, 1640), fill=(74, 76, 82), width=2)
    draw.text((72, 1685), author or "SUNBIRD CONTENT STUDIO", font=font(38), fill=foreground)
    draw.text((72, 1750), "观点 · 方法 · 可执行", font=font(28), fill=(145, 149, 158))
    image.save(output_path, "PNG", optimize=True)
    return output_path
