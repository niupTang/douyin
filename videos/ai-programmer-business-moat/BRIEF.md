---
workflow: general-video
flow: automation
storyboard: no
message: "AI 时代程序员真正的护城河，是把技术变成业务结果"
destination: douyin
aspect: 1080x1920
language: zh-CN
audience: "担心被 AI 替代、正在寻找转型方向的程序员"
length: audio-driven
angle: contrarian-business-opportunity
voice: local-kokoro-male
---

## Intent

制作一条中文竖屏知识口播视频。开场用“最先被 AI 淘汰的可能是只会写代码的程序员”制造冲突，随后解释 FDE、AI 落地和传统企业的信息差，最终收束到“代码越来越便宜，解决真实问题的人越来越贵”。表达直接、通俗、有判断，不做算法科普。

## Assets

- `narration.txt` — 完整口播稿，也是音频、字幕和分镜的唯一文本依据。
- `E:/social-auto-upload/tools/gbro-collage-broll` — 纸拼贴视觉语言与隐喻设计参考；动画改由本地 HyperFrames 实现。

## Customizations

- GPT 生成 9:16 editorial halftone paper-collage 静帧。
- 每个镜头从空色场逐件组装，强调 slide-in、snap、卡位和纸张阴影，不使用慢速缩放。
- 画面右侧固定预留约 35% 真人口播安全区；主要信息和拼贴主体放在左侧约 60%。
- 使用本地 Kokoro 生成试听口播音频；不调用 Gemini 或 HeyGen。
- 中文重点字幕避开人物位，每屏只保留一句核心短语。

## Notes

- 用户要求按“先音频、再拆图片动画、最后生成视频”的顺序执行。
- 不出现第三方账号 Logo、水印或虚构数据。
- 最终渲染仍需用户确认预览。
