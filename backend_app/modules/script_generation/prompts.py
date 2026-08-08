import json


def build_identity_script_prompt(identity_profile, radar_result, benchmark_analysis=None):
    payload = {
        "identity_profile": identity_profile or {},
        "radar_result": radar_result or {},
        "benchmark_analysis": benchmark_analysis or {},
    }
    return f"""
你是中文短视频口播编剧，任务是把对标拆解和观点雷达结果改写成一条“属于创作者本人”的口播文案。

要求：
1. 不得照搬原视频标题、原文案或原作者经历。
2. 必须贴合 identity_profile 中的身份、经验边界、表达风格、受众和商业目标。
3. 文案适合 60-90 秒口播，语言自然、有停顿感，适合提词器直接使用。
4. 结构包含：前三秒钩子、身份切入、核心观点、证据或小案例、可执行步骤、结尾引导。
5. 同时给出标题、封面短句、标签、拍摄提示。
6. 输出严格匹配 JSON Schema，不要输出 Markdown。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()
