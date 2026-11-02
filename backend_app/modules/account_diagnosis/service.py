from backend_app.agent.structured_runner import call_hermes_structured

from . import repository, stats
from .prompts import build_benchmark_report_prompt, build_own_report_prompt
from .schemas import benchmark_report_schema, own_report_schema


def build_own_facts_payload(db_path, user_info_id):
    account = repository.get_user_info_account(db_path, user_info_id)
    own_account = repository.get_bound_own_account(db_path, user_info_id)
    own_videos = repository.list_own_videos_for_user(db_path, user_info_id)
    publish_records = repository.list_publish_records_for_user(db_path, user_info_id)
    facts = stats.build_own_facts(own_videos, publish_records, account=account)
    facts["_meta"] = {
        "user_info_id": user_info_id,
        "bound_own_account_id": own_account.get("id") if own_account else None,
        "bound_own_account_name": own_account.get("name") if own_account else None,
        "own_videos_count": len(own_videos),
        "publish_records_count": len(publish_records),
    }
    return facts


def build_benchmark_facts_payload(db_path, account_id):
    account = repository.get_benchmark_account(db_path, account_id)
    if not account:
        raise ValueError("对标账号不存在")
    videos = repository.list_benchmark_videos(db_path, account_id)
    return stats.build_benchmark_facts(account, videos)


def run_diagnosis_task(db_path, settings, target_type, target_id, report_id, progress_cb):
    """在后台线程中执行诊断，逐阶段回传进度，并把结果写回报告行。"""
    try:
        progress_cb(30, "正在汇总账号数据…")
        if target_type == "own":
            facts = build_own_facts_payload(db_path, target_id)
            if facts["_meta"]["own_videos_count"] == 0 and facts["_meta"]["publish_records_count"] == 0:
                raise ValueError("该账号下没有自有作品或发布记录，无法诊断")
            schema = own_report_schema
            prompt_fn = build_own_report_prompt
        else:
            facts = build_benchmark_facts_payload(db_path, target_id)
            if not facts.get("videos"):
                raise ValueError("该对标账号下没有作品数据，无法诊断")
            schema = benchmark_report_schema
            prompt_fn = build_benchmark_report_prompt

        progress_cb(60, "正在计算指标…")
        progress_cb(90, "正在调用模型生成报告…")
        report = call_hermes_structured(
            prompt_fn(facts), schema(), settings=settings, task_name="viralAnalysis"
        )
        repository.update_report_progress(
            db_path, report_id, status="success", progress=100,
            message="诊断完成", facts=facts, report=report,
        )
    except Exception as exc:
        repository.update_report_progress(db_path, report_id, status="failed", error=str(exc))
