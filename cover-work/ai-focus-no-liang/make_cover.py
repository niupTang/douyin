from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent
SRC = BASE / "frame-045.png"
OUT = BASE / "ai-focus-data-no-liang.png"
W, H = 1080, 1920


def f(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(name, size=size)


bold = r"C:\Windows\Fonts\msyhbd.ttc"
regular = r"C:\Windows\Fonts\msyh.ttc"

src = Image.open(SRC).convert("RGB")
scale = max(W / src.width, H / src.height)
resized = src.resize((int(src.width * scale), int(src.height * scale)), Image.Resampling.LANCZOS)
x = max(0, (resized.width - W) // 2)
y = max(0, int((resized.height - H) * 0.38))
bg = resized.crop((x, y, x + W, y + H))
bg = ImageEnhance.Contrast(bg).enhance(1.06)
bg = ImageEnhance.Color(bg).enhance(1.04)
bg = bg.filter(ImageFilter.GaussianBlur(4)).convert("RGBA")

shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shade)
sd.rectangle((0, 0, W, H), fill=(0, 0, 0, 128))
sd.rectangle((0, 0, W, 760), fill=(0, 0, 0, 92))
sd.rectangle((0, 1320, W, H), fill=(0, 0, 0, 138))
canvas = Image.alpha_composite(bg, shade)
draw = ImageDraw.Draw(canvas)


def text_center(text: str, y: int, font, fill, stroke=8, stroke_fill=(0, 0, 0)):
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    x = (W - (box[2] - box[0])) // 2
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def tag(text: str, x: int, y: int):
    font = f(regular, 34)
    box = draw.textbbox((0, 0), text, font=font)
    draw.rounded_rectangle((x, y, x + box[2] + 44, y + box[3] + 28), radius=18, fill=(0, 0, 0, 170), outline=(255, 218, 71, 220), width=2)
    draw.text((x + 22, y + 10), text, font=font, fill=(255, 230, 95))


tag("AI内容复盘", 58, 64)
text_center("工具越多", 210, f(bold, 138), (255, 255, 255), stroke=9)
text_center("越要克制", 370, f(bold, 152), (255, 218, 58), stroke=9)
text_center("别每天追新工具", 590, f(bold, 62), (255, 255, 255), stroke=5)

draw.rounded_rectangle((78, 1320, W - 78, 1510), radius=32, fill=(0, 0, 0, 188), outline=(255, 218, 58, 230), width=3)
text_center("先聚焦一件事", 1350, f(bold, 86), (199, 117, 255), stroke=6)
text_center("把数据沉淀下来", 1580, f(bold, 60), (255, 255, 255), stroke=5)

canvas.convert("RGB").save(OUT, quality=95)
print(OUT)
