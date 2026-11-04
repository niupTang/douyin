from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


BASE = Path(__file__).resolve().parent
SRC = BASE / "portrait2.png"
OUT = BASE / "douyin-cover-1080x1920.png"
W, H = 1080, 1920


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


font_bold = r"C:\Windows\Fonts\msyhbd.ttc"
font_regular = r"C:\Windows\Fonts\msyh.ttc"

img = Image.open(SRC).convert("RGB")

# Cover crop with a slight upward bias so the face remains visible and platform UI stays clear.
scale = max(W / img.width, H / img.height)
resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
x = max(0, (resized.width - W) // 2)
y = max(0, int((resized.height - H) * 0.36))
bg = resized.crop((x, y, x + W, y + H))

bg = ImageEnhance.Contrast(bg).enhance(1.08)
bg = ImageEnhance.Color(bg).enhance(1.12)

blur = bg.filter(ImageFilter.GaussianBlur(10))
canvas = Image.blend(blur, bg, 0.68).convert("RGBA")
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(overlay)
od.rectangle((0, 0, W, H), fill=(0, 0, 0, 82))
od.rectangle((0, 0, W, 650), fill=(0, 0, 0, 72))
od.rectangle((0, 1460, W, H), fill=(0, 0, 0, 120))
canvas = Image.alpha_composite(canvas, overlay)

draw = ImageDraw.Draw(canvas)


def centered_text(text: str, y: int, fnt, fill, stroke_width: int = 7, stroke_fill=(0, 0, 0)):
    bbox = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def label(text: str, xy, fnt):
    x0, y0 = xy
    bbox = draw.textbbox((0, 0), text, font=fnt, stroke_width=2)
    pad_x, pad_y = 22, 12
    draw.rounded_rectangle(
        (x0, y0, x0 + bbox[2] + pad_x * 2, y0 + bbox[3] + pad_y * 2),
        radius=18,
        fill=(0, 0, 0, 150),
        outline=(255, 220, 83, 180),
        width=2,
    )
    draw.text((x0 + pad_x, y0 + pad_y - 4), text, font=fnt, fill=(255, 230, 83), stroke_width=2, stroke_fill=(0, 0, 0))


label("AI自媒体复盘", (54, 62), font(font_regular, 34))
centered_text("AI工具", 190, font(font_bold, 160), (255, 255, 255), stroke_width=9)
centered_text("别贪多", 350, font(font_bold, 170), (255, 220, 68), stroke_width=9)
centered_text("普通人要学会克制", 590, font(font_bold, 56), (255, 255, 255), stroke_width=5)

draw.rounded_rectangle((78, 1375, W - 78, 1548), radius=34, fill=(0, 0, 0, 170), outline=(255, 220, 68, 210), width=3)
centered_text("聚焦一件事", 1390, font(font_bold, 104), (196, 112, 255), stroke_width=7)
centered_text("数据才会变成资产", 1582, font(font_bold, 58), (255, 255, 255), stroke_width=5)

canvas.convert("RGB").save(OUT, quality=95)
print(OUT)
