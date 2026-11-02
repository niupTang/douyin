import asyncio
import re
from types import SimpleNamespace

from myUtils.douyin_benchmark import normalize_douyin_user_url, scrape_douyin_benchmark

from . import repository as benchmark_repository
from .analysis import (
    build_douyin_analysis_prompt,
    generate_douyin_video_analysis_fallback,
    get_codex_analysis_schema,
    normalize_codex_video_analysis,
)


def create_benchmark_operations(get_db_path, idea_radar_job_registry, run_structured):

    def get_douyin_benchmark_video_urls(account_id):
        return benchmark_repository.list_video_urls(get_db_path(), account_id)


    def upsert_douyin_benchmark(homepage_url):
        return benchmark_repository.upsert_account(
            get_db_path(), homepage_url, normalize_douyin_user_url
        )


    def delete_douyin_benchmark(account_id):
        pending = benchmark_repository.delete_account_cascade(get_db_path(), account_id)
        if not pending:
            return None
        account = pending["account"]
        active_video_ids = idea_radar_job_registry.cancel_many(pending["video_ids"])
        cancelled_job_count = len(active_video_ids)
        deleted = pending["deleted"]

        return {
            "id": account_id,
            "nickname": account["nickname"],
            "homepage_url": account["homepage_url"],
            "deleted_videos": deleted["videos"],
            "deleted_analyses": deleted["analysis"],
            "deleted_transcripts": deleted["transcripts"],
            "cancelled_jobs": cancelled_job_count,
        }


    def save_douyin_benchmark_sync(account_id, data):
        return benchmark_repository.save_sync(get_db_path(), account_id, data)


    def save_douyin_benchmark_error(account_id, error_message):
        benchmark_repository.save_error(get_db_path(), account_id, error_message)


    def sync_one_douyin_benchmark(homepage_url, cookie_file, max_videos=20):
        homepage_url = normalize_douyin_user_url(homepage_url)
        if not homepage_url:
            raise ValueError("无效的抖音用户主页链接")
        account_id = upsert_douyin_benchmark(homepage_url)
        existing_urls = get_douyin_benchmark_video_urls(account_id)
        sync_data = asyncio.run(scrape_douyin_benchmark(
            homepage_url,
            cookie_file=cookie_file,
            max_videos=max_videos,
            existing_video_urls=existing_urls
        ))
        stats = save_douyin_benchmark_sync(account_id, sync_data)
        return {"id": account_id, "sync": stats, "account": sync_data}


    def parse_keywords_payload(value):
        if isinstance(value, list):
            keywords = value
        else:
            keywords = re.split(r"[,，\n\r]+", str(value or ""))
        return [item.strip() for item in keywords if item and item.strip()]


    def generate_douyin_video_analysis_by_codex(video):
        prompt = build_douyin_analysis_prompt(video)
        agent_data = run_structured(
            "benchmarkAnalysis", prompt, get_codex_analysis_schema()
        )
        return normalize_codex_video_analysis(video, agent_data)


    def generate_douyin_video_analysis(video):
        try:
            return generate_douyin_video_analysis_by_codex(video)
        except Exception as e:
            analysis = generate_douyin_video_analysis_fallback(video)
            analysis["analysis_type"] = "metadata_fallback"
            raw_analysis = analysis.get("raw_analysis") or {}
            raw_analysis["codex_error"] = str(e)
            analysis["raw_analysis"] = raw_analysis
            return analysis


    def save_douyin_video_analysis(video_id, analysis):
        return benchmark_repository.save_analysis(get_db_path(), video_id, analysis)

    return SimpleNamespace(
        list_video_urls=get_douyin_benchmark_video_urls,
        upsert_account=upsert_douyin_benchmark,
        delete_account=delete_douyin_benchmark,
        save_sync=save_douyin_benchmark_sync,
        save_error=save_douyin_benchmark_error,
        sync_account=sync_one_douyin_benchmark,
        parse_keywords=parse_keywords_payload,
        analyze_by_agent=generate_douyin_video_analysis_by_codex,
        analyze_video=generate_douyin_video_analysis,
        save_analysis=save_douyin_video_analysis,
    )
