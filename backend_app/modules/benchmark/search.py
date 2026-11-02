import asyncio

from myUtils.douyin_benchmark import search_douyin_content

from . import repository


def run_content_search_task(db_path, task_id, keyword, target_count, cookie_file):
    try:
        repository.update_search_task(db_path, task_id, status="running", started_at="CURRENT_TIMESTAMP")
        results = asyncio.run(search_douyin_content(
            [keyword], cookie_file=cookie_file, target_count=target_count
        ))
        repository.save_search_results(db_path, task_id, keyword, results)
        repository.update_search_task(
            db_path, task_id, status="success",
            collected_count=len(results), finished_at="CURRENT_TIMESTAMP",
        )
    except Exception as exc:
        repository.update_search_task(
            db_path, task_id, status="failed",
            error_message=str(exc), finished_at="CURRENT_TIMESTAMP",
        )
