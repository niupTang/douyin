import json


def build_transcript_radar_prompt(video, transcript, target_direction):
    payload = {
        "video_id": video.get("id"),
        "account_name": video.get("account_name"),
        "title": video.get("title"),
        "video_url": video.get("video_url"),
        "like_count": video.get("like_count"),
        "comment_count": video.get("comment_count"),
        "share_count": video.get("share_count"),
        "collect_count": video.get("collect_count"),
        "target_direction": target_direction,
        "transcript": transcript,
    }
    return f"""
你是一个严格依据视频正文工作的中文内容研究员和普通人机会分析师。

任务分三步完成：先拆解原视频为什么能传播，再把视频揭示的变化翻译成普通人的具体机会，最后生成适合 target_direction 身份使用的完整口播文案。

硬性规则：
1. 正文是主要证据，标题和互动数据只能补充，禁止编造视频画面、评论、完播率、收入或案例。
2. 先说明原作目标人群、真实处境、开头钩子、内容结构、核心观点、证据、情绪转折和传播承诺。
3. 明确哪些机制可借鉴，哪些内容依赖作者身份、经历或既有流量，不能直接复制。
4. 机会分析必须走完：变化信号 -> 下降的成本或门槛 -> 新获得能力的人群 -> 未满足需求 -> 具体交付物 -> 潜在付费者 -> 最小验证 -> 风险。
5. migration_angles 每一条必须包含“服务谁、交付什么、怎么验证”中的至少两项，禁止只写“关注趋势”“抓住机会”。
6. recommended_titles 面向普通人、运营者、小企业主或自由职业者，不默认写给测试工程师或底层技术开发者。
7. personalized_script 必须是一条 60-90 秒可直接拍摄的完整口播文案，符合 target_direction 的身份、经验边界和表达口吻。
8. personalized_script 不能照搬原视频，只能迁移结构、观点和机会；结构包含：前三秒钩子、身份切入、核心观点、证据/案例、行动建议、结尾引导。
9. 事实、原作者经验、合理推断、待验证假设必须在 evidence_types 中区分。
10. 没有充分证据时直接指出信息缺口，不要为了完整而补写。
11. 输出严格匹配 JSON Schema，不要输出 Markdown 或额外解释。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()
