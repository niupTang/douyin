import json
import statistics


def own_video_analysis_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "traffic_diagnosis", "low_traffic_reason", "two_second_diagnosis", "evidence", "actions", "opening_rewrites", "confidence"],
        "properties": {
            "summary": {"type": "string"},
            "traffic_diagnosis": {"type": "string"},
            "low_traffic_reason": {"type": "string"},
            "two_second_diagnosis": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "actions": {"type": "array", "items": {"type": "string"}},
            "opening_rewrites": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string"},
        },
    }


def _number(item, key):
    try:
        value = item.get(key)
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _median(videos, key):
    values = [value for value in (_number(item, key) for item in videos) if value is not None]
    return round(statistics.median(values), 4) if values else None


def build_own_video_analysis_prompt(video, peers):
    metric_keys = (
        "play_count", "completion_rate", "five_sec_completion_rate", "cover_click_rate",
        "two_sec_bounce_rate", "avg_play_duration", "like_count", "share_count",
        "comment_count", "collect_count", "profile_visit_count", "follower_delta",
    )
    metrics = {key: video.get(key) for key in metric_keys}
    payload = {
        "video": {
            "title": video.get("title"),
            "published_at": video.get("published_at"),
            "content_format": video.get("content_format"),
            "transcript": video.get("transcript"),
            "metrics": metrics,
        },
        "account_sample_medians": {key: _median(peers, key) for key in metric_keys},
        "sample_size": len(peers),
    }
    return f"""
你是太阳鸟 IP 的短视频数据复盘分析师。请分析一条已发布抖音作品为什么有流量、为什么没有流量，以及前两秒跳出率高的可能原因。

## 诊断框架
1. 先把本作品和账号样本中位数比较，不要只看绝对播放量。样本不足或指标为空时明确写“无法判断”。
2. 将问题拆成四层：曝光/分发、前 2 秒停留、5 秒到完播留存、互动与转化。
3. 播放低不等于内容差：可能是曝光不足、标题/封面点击弱、前 2 秒承诺不清，必须区分证据和推断。
4. 2 秒跳出高时，重点检查开头是否先铺垫、身份介绍、抽象表达、结果不清、观众不知道与自己有什么关系，或标题/首句承诺不一致。
5. 只依据输入数据、标题、文案和样本中位数分析。没有首帧、逐字字幕、评论、流量来源或留存曲线时，不能编造画面和观众反馈。
6. 所有数组输出 3 到 5 条，必须具体。输出合法 JSON，不要 Markdown。

## 字段要求
- summary：一句话给出这条作品当前最主要的流量结论。
- traffic_diagnosis：判断属于“曝光不足”“开头留不住”“内容留存弱”“互动转化弱”或“表现相对较好”，并说明依据。
- low_traffic_reason：即使作品播放不低，也要说明如果它没有继续放量，最可能卡在哪一层；证据不足则写待验证。
- two_second_diagnosis：解释 2 秒跳出率高或低的原因；没有该指标时写无法判断，并给出需要补采的数据。
- evidence：列出指标对比和由此得到的事实/合理推断，每条标注“事实”或“推断”。
- actions：给出下一条视频可执行的选题、标题、封面、节奏或互动改法，按优先级排序。
- opening_rewrites：给出 3 个不同的前 2 秒开头版本，不能照抄原文。
- confidence：高/中/低，并说明缺少哪些数据。

输入数据：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()
