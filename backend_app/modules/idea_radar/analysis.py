import re

from backend_app.modules.benchmark.analysis import pick_analysis_source_text, split_title_parts


def parse_metric_number(value):
    text = re.sub(r"\s+", "", str(value or "")).replace(",", "")
    if not text:
        return 0
    match = re.search(r"([\d.]+)", text)
    if not match:
        return 0
    number = float(match.group(1))
    if "万" in text or "w" in text.lower():
        number *= 10000
    return int(number)


def classify_idea_theme(text):
    checks = [
        (["变现", "赚钱", "收入", "交付", "获客", "会员费", "分账"], "AI 变现闭环"),
        (["Skill", "智能体", "Agent", "工作流", "自审", "预测", "蒸馏"], "AI 生产系统"),
        (["开源", "Github", "GitHub", "项目", "CLI", "工具"], "开源工具机会"),
        (["第二大脑", "知识库", "聊天记录", "备份", "数字资产"], "数字资产沉淀"),
        (["入门", "小白", "教程", "学习", "电脑", "配置"], "普通人入门路径"),
        (["职业", "工程师", "GEO", "优化", "部署"], "AI 新职业地图"),
    ]
    for keywords, label in checks:
        if any(keyword.lower() in text.lower() for keyword in keywords):
            return label
    return "AI 机会识别"


def pick_evidence_type(text, like_count):
    types = []
    if parse_metric_number(like_count) >= 10000:
        types.append("高赞验证")
    if any(word in text for word in ["开源", "公开", "收入公开"]):
        types.append("公开证据")
    if any(word in text for word in ["全链路", "拆解", "教程", "指南"]):
        types.append("方法拆解")
    if any(word in text for word in ["我", "自用", "实测", "体验"]):
        types.append("亲身实验")
    return types or ["标题信号"]


def build_migration_angles(theme, text):
    if theme == "AI 变现闭环":
        return [
            "把 AI 热点翻译成普通人能执行的赚钱链路",
            "从工具介绍升级成开发、获客、交付的闭环拆解",
            "用自己的发布和复盘数据证明内容系统能产生反馈",
        ]
    if theme == "AI 生产系统":
        return [
            "把单个工具改写成一套可复用 Skill 资产",
            "用对标研究、观点提炼、发布复盘组成个人内容流水线",
            "展示一个真实任务如何被 AI 工作流接管",
        ]
    if theme == "开源工具机会":
        return [
            "把开源项目从技术新闻改写成普通人的机会窗口",
            "用项目增长速度、使用场景和替代对象讲清趋势",
            "输出一条从发现项目到内容选题的研究路径",
        ]
    if theme == "数字资产沉淀":
        return [
            "把聊天记录、选题、复盘沉淀成未来可调用资产",
            "证明数据不是看板，而是下一条内容的原料",
            "从资料收藏升级成第二大脑的运行机制",
        ]
    if theme == "普通人入门路径":
        return [
            "把入门问题拆成最低成本的第一步",
            "反对先买设备、先报课，强调先跑通一个真实任务",
            "用对标账号样本生成一条新手路线图",
        ]
    return [
        "把抽象趋势改写成普通人的具体行动",
        "从对标账号中提炼可迁移观点，而不是复制标题",
        "把热点变成自己的长期栏目和方法论资产",
    ]


def generate_idea_radar(video, target_direction=None):
    target = target_direction or "AI 生产系统研究员"
    source_text = pick_analysis_source_text(video)
    theme = classify_idea_theme(source_text)
    account = video.get("account_name") or "对标账号"
    like_count = video.get("like_count") or "0"
    evidence_types = pick_evidence_type(source_text, like_count)
    migration_angles = build_migration_angles(theme, source_text)
    hook = split_title_parts(source_text)[0] if split_title_parts(source_text) else source_text[:48]

    audience_anxieties = [
        "收藏了很多 AI 工具，但不知道怎么变成自己的产出",
        "知道热点很热，却不知道普通人能抓住什么机会",
        "会做单点尝试，但缺少从选题、制作、发布到复盘的闭环",
    ]
    if theme == "AI 变现闭环":
        audience_anxieties.insert(0, "想用 AI 赚钱，但不知道从开发、获客到交付怎么串起来")
    elif theme == "AI 生产系统":
        audience_anxieties.insert(0, "想让 AI 真正接管工作流，而不是只停留在工具尝鲜")
    elif theme == "数字资产沉淀":
        audience_anxieties.insert(0, "每天产生很多信息，却没有沉淀成可复用资产")

    asset_label = {
        "AI 变现闭环": "变现闭环",
        "AI 生产系统": "Skill 资产库",
        "开源工具机会": "机会雷达",
        "数字资产沉淀": "第二大脑资产",
        "普通人入门路径": "入门路径",
        "AI 新职业地图": "新职业地图",
        "AI 机会识别": "机会翻译系统",
    }.get(theme, "观点迁移能力")

    contrarian = {
        "AI 变现闭环": "AI 变现的关键不是会多少工具，而是有没有一条从问题到交付的闭环。",
        "AI 生产系统": "真正值钱的不是 AI 工具清单，而是你沉淀下来的 Skill 资产库。",
        "开源工具机会": "开源项目不是技术圈新闻，而是普通人提前发现需求变化的雷达。",
        "数字资产沉淀": "数据不是用来看过去的，而是用来生产下一条内容的。",
        "普通人入门路径": "AI 入门不要先买设备或报课，先跑通一个真实任务。",
    }.get(theme, "爆款不是热点本身，而是把热点翻译成普通人的机会。")

    titles = [
        f"我拆了{account}一条高赞作品，发现爆的不是话题，是{asset_label}",
        f"做 AI 账号没流量，不是工具不够多，是你没有自己的{asset_label}",
        f"别再追 AI 热点了，把热点变成你的{asset_label}才值钱",
        f"为什么这条能拿到{like_count}赞？因为它讲中了普通人的机会焦虑",
        f"普通人做 AI，最该沉淀的不是教程，而是一套可复用流程",
    ]

    opening_script = (
        f"我刚拆了一条对标作品，来自{account}，点赞大约是{like_count}。\n"
        f"表面上它讲的是：{hook}。\n"
        f"但真正让人停下来的，不是这个话题本身，而是它背后的机会翻译：{contrarian}\n"
        f"这给我的启发是，如果我的账号定位是{target}，我就不能只搬运工具，"
        "而要把对标、观点、证据和行动路径串成一条内容生产系统。"
    )
    personalized_script = (
        f"最近我拆了一条来自{account}的高赞作品，点赞大约是{like_count}。\n"
        f"它表面讲的是：{hook}。\n\n"
        f"但如果站在我这个「{target}」的身份来看，我真正想提醒你的不是这个热点本身，"
        f"而是它背后的一个变化：{contrarian}\n\n"
        "很多人做内容，会停在追热点、搬工具、改标题这一步。可真正能长期跑出来的账号，"
        "一定是在做一件事：把外部变化翻译成自己受众能执行的路径。\n\n"
        f"所以这条内容我会这样迁移：第一，先讲清楚这个变化服务谁；第二，给出一个最小交付物，"
        f"比如{migration_angles[0]}；第三，用一次真实发布或一个小样本去验证，而不是直接 All in。\n\n"
        "如果你也在做 AI 或自媒体，不要只收藏爆款。你要问的是：这条内容里的结构、痛点和证据，"
        "能不能变成我自己的选题、脚本和交付物。能迁移，才真的值得对标。"
    )

    return {
        "radar_type": "metadata",
        "target_direction": target,
        "source": {
            "id": video.get("id"),
            "account_name": account,
            "title": video.get("title"),
            "video_url": video.get("video_url"),
            "like_count": like_count,
            "like_score": parse_metric_number(like_count),
            "cover_url": video.get("cover_url"),
        },
        "viral_theme": theme,
        "audience_anxieties": audience_anxieties[:4],
        "contrarian_viewpoint": contrarian,
        "evidence_types": evidence_types,
        "migration_angles": migration_angles,
        "recommended_titles": titles,
        "opening_script": opening_script,
        "personalized_script": personalized_script,
        "formula": "爆款 = 人群焦虑 × 反常识观点 × 可验证证据 × 可迁移行动",
    }
