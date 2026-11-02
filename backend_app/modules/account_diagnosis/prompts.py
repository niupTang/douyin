import json


def build_own_report_prompt(facts):
    return f"""
你是一名短视频账号流量复盘分析师。下面是某抖音账号的「诊断事实卡」（已由后端确定性计算好，含播放、完播、2 秒跳出等指标的中位数、均值和低播放作品清单）。

你的任务：基于事实卡，回答「这个账号为什么播放量低」，并给出可执行建议。

## 硬性规则
1. 只用事实卡里的数字下结论，不要编造首帧画面、评论、流量来源、留存曲线等没有的数据。
2. 数据不足（如缺少 2 秒跳出率、完播率）时，明确写「无法判断 / 待补采」，不要臆断。
3. 把问题拆成四层：曝光/分发、前 2 秒停留、5 秒到完播留存、互动与转化。每层给出 judgment（明显问题 / 疑似问题 / 数据不足 / 无明显问题）和 reason。
4. 播放低不等于内容差，要区分「曝光不足」与「内容留不住」。
5. key_metrics 输出 3 到 5 条，引用事实卡里的具体数值。
6. low_performing_videos 列出低播放作品的标题 + 一句话判断，最多 10 条。
7. improvement_actions 输出 3 到 5 条，按优先级排序，具体到标题/封面/前 2 秒/节奏。
8. confidence 说明判断置信度（高/中/低）以及缺什么数据。
9. 只输出合法 JSON 对象，不要 Markdown 或多余解释。

诊断事实卡：
{json.dumps(facts, ensure_ascii=False, indent=2)}
""".strip()


def build_benchmark_report_prompt(facts):
    return f"""
你是一名短视频对标账号分析师。下面是某对标账号的「诊断事实卡」，其中每条视频已由后端确定性算好 like_rate（点赞/粉丝）和 deviation_x（该视频点赞 ÷ 账号点赞中位数），并给了初步分类标签。

你的任务：回答「这个账号的数据为什么高——是真爆了，还是靠粉丝基数」，并对每条视频给出结论。

## 判定口径（后端已算好 deviation_x，你要解释，不要自己重新算数）
- deviation_x >= 5：爆款（显著脱离粉丝基数）
- deviation_x 在 2~5：表现突出（半爆）
- deviation_x 在 0.5~2：粉丝基数正常发挥
- deviation_x < 0.5：低于自身基线

## 硬性规则
1. 用 like_rate 和 deviation_x 区分「绝对数字高」与「相对粉丝规模是否异常」，这是核心。
2. 只依据事实卡，不编造播放量、完播率、评论内容等没有的数据。
3. viral_conclusion 用一句话回答：这个号整体是「内容驱动型爆款」还是「粉丝基数型」，并给出依据。
4. per_video_classification 对每条视频给出 classification（复用上面的口径词）+ reason（引用具体数值），最多 20 条。
5. key_metrics 输出 3 到 5 条，引用粉丝数、点赞中位数/均值/最高、最高 deviation_x 等。
6. takeaways 输出 3 到 5 条，说明哪些机制可以借鉴、哪些依赖粉丝基数不能照搬。
7. confidence 说明判断置信度（高/中/低）以及缺什么数据（例如缺少播放量时如何影响结论）。
8. 只输出合法 JSON 对象，不要 Markdown 或多余解释。

诊断事实卡：
{json.dumps(facts, ensure_ascii=False, indent=2)}
""".strip()
