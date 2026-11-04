from moviepy import *
from PIL import Image, ImageDraw, ImageFont
import numpy as np

AUDIO_PATH = r"E:\social-auto-upload\videos\tencent-rongcuolv-tts.mp3"
OUTPUT_PATH = r"E:\social-auto-upload\videos\tencent-rongcuolv-video.mp4"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
W, H = 1080, 1920
FPS = 24

# Total proportion from segments table (last segment's ep)
TOTAL_PROPORTION = 1.38

def create_bg():
    img = Image.new('RGB', (W, H), (10, 14, 28))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(15 * (1 - y / H))
        draw.rectangle([(0, y), (W, y)], fill=(10+v, 14+v, 28+v))
    draw.rectangle([(108, 345), (972, 347)], fill=(37, 99, 235))
    draw.rectangle([(108, 1600), (972, 1601)], fill=(37, 99, 235, 40))
    return img

bg_img = create_bg()

segments = [
    (["你说腾讯在AI赛道落后了半年？", "对，没错。"], 0.0, 0.04, False),
    (["但你看现在——微信那个AI功能，", "日活已经反超了。"], 0.04, 0.08, False),
    (["从无人问津到跟世界一流平齐，", "用了多久？半年。就半年。"], 0.08, 0.13, False),
    (["这就是大厂的容错率。"], 0.13, 0.17, True),
    (["落后半年算什么？用户基数在那儿、", "生态位在那儿、现金流在那儿。"], 0.17, 0.23, False),
    (["走错路？掉头就行。试错成本", "对我们来说是倾家荡产，", "对他们来说是季度财报里的一行脚注。"], 0.23, 0.29, False),
    (["但这不是让我最震撼的。"], 0.29, 0.32, False),
    (["最震撼的是——腾讯这次", "弯道超车的打法变了。"], 0.32, 0.37, True),
    (["以前腾讯的优势是产品体验。", "这次呢？是work binding——工作流绑定。"], 0.37, 0.42, False),
    (["不需要你多装一个App，", "不需要你换工具。"], 0.42, 0.45, False),
    (["你的沟通、文件、审批、支付，", "全在微信里。AI直接嵌进去，", "你根本不需要用AI，", "你只是在做你每天做的事。"], 0.45, 0.52, False),
    (["这叫什么？", "这叫把能力绑进生态里。"], 0.52, 0.56, True),
    (["字节的豆包、阿里的通义千问，", "全是你过来用我的逻辑。"], 0.56, 0.60, False),
    (["腾讯不一样——", "你不需要过来，我就在你手边。"], 0.60, 0.64, False),
    (["这不只是产品策略的差异。", "这是两种世界观。"], 0.64, 0.67, False),
    (["大厂之间拼的是生态位——", "谁绑得更深、更自然、更难替代。"], 0.67, 0.71, False),
    (["那我们普通人呢？"], 0.71, 0.74, False),
    (["我们跟大厂最大的差距", "不是钱、不是技术——", "是容错率。"], 0.74, 0.80, True),
    (["大厂犯个错，花半年追回来。", "你失业一次呢？"], 0.80, 0.84, False),
    (["房贷谁还？孩子学费谁交？", "社保断了一个月，补起来都是麻烦。"], 0.84, 0.88, False),
    (["我们普通人最大的敌人", "不是能力不足，", "是没有试错空间。"], 0.88, 0.92, True),
    (["所以你能怎么办？"], 0.92, 0.94, False),
    (["答案是：像腾讯一样，", "做自己的work binding。"], 0.94, 0.97, True),
    (["不是去学AI工具的快捷键——", "那个东西下个月就更新了。"], 0.97, 1.00, False),
    (["不是去追大厂的免费额度——", "那个东西明年就收费了。"], 1.00, 1.03, False),
    (["你要做的是：", "把你的能力，绑进你自己的系统里。"], 1.03, 1.06, True),
    (["一个内容选题，AI辅助写成框架，", "TTS生成配音，自动化剪辑，多平台分发。"], 1.06, 1.10, False),
    (["这套流程跑通了，", "你不是在用AI，", "你是在经营一个系统。"], 1.10, 1.14, True),
    (["这个系统就是你的生态位。", "这个系统就是你的容错率。"], 1.14, 1.18, True),
    (["腾讯的容错率来自12亿用户。"], 1.18, 1.21, False),
    (["你的容错率来自：一个能自动产出", "的内容系统，两个能变现的平台，", "三个月的应急现金。"], 1.21, 1.27, False),
    (["前者你控制不了。", "后者，你现在就能开始建。"], 1.27, 1.31, False),
    (["别等到被裁了那天，", "才想起来给自己搭一艘船。"], 1.31, 1.38, True),
]

def make_textframe(lines, highlight=False):
    img = bg_img.copy()
    draw = ImageDraw.Draw(img)
    n = len(lines)
    if n == 1: ms = 72
    elif n == 2: ms = 64
    elif n <= 3: ms = 56
    else: ms = 48
    try:
        bf = ImageFont.truetype(FONT_BOLD, ms)
        rf = ImageFont.truetype(FONT_REG, int(ms * 0.82))
    except:
        bf = rf = ImageFont.load_default()
    lh_list, tot = [], 0
    for i, line in enumerate(lines):
        f = bf if i == 0 else rf
        b = draw.textbbox((0, 0), line, font=f)
        lh = b[3] - b[1] + 12
        lh_list.append((lh, f))
        tot += lh
    y = (H - tot) // 2 - 60
    for i, line in enumerate(lines):
        lh, f = lh_list[i]
        c = (248, 250, 252) if i == 0 else (203, 213, 225)
        b = draw.textbbox((0, 0), line, font=f)
        x = (W - (b[2] - b[0])) // 2
        if highlight and i == 0:
            draw.rectangle([(x-25, y-8), (x+(b[2]-b[0])+25, y+lh+8)], fill=(37, 99, 235, 25))
        draw.text((x, y), line, font=f, fill=c)
        y += lh
    return img

# === Load audio FIRST to get actual duration ===
print("Loading audio...")
audio = AudioFileClip(AUDIO_PATH)
total_dur = audio.duration
print(f"Audio duration: {total_dur:.1f}s")
scale = total_dur / TOTAL_PROPORTION

# Create segment clips with proper timing
print("Generating segment backgrounds...")
seg_clips = []
for i, (lines, sp, ep, hl) in enumerate(segments):
    img = make_textframe(lines, highlight=hl)
    p = f"/tmp/tc_seg_{i}.png"
    img.save(p)
    dur = (ep - sp) * scale
    c = ImageClip(p).with_duration(dur)
    seg_clips.append(c)
    print(f"  seg {i}: {dur:.2f}s ({'★' if hl else '  '}) {lines[0][:20]}...")

print("Compositing...")
final = concatenate_videoclips(seg_clips, method="compose")
if abs(final.duration - total_dur) > 0.1:
    final = final.with_duration(total_dur)

final = final.with_audio(audio)
final = final.resized((W, H))

print(f"Video duration: {final.duration:.1f}s")
print(f"Rendering to {OUTPUT_PATH}...")
final.write_videofile(OUTPUT_PATH, codec='libx264', audio_codec='aac',
                      fps=FPS, preset='medium', bitrate='5000k', threads=4,
                      logger='bar')
print(f"DONE!")
