from datetime import datetime, timedelta
from types import SimpleNamespace

from backend_app.modules.accounts import repository as account_repository
from backend_app.modules.browser_settings import service as browser_settings_service

from . import repository as own_content_repository
from .accounts import list_douyin_data_accounts, resolve_douyin_data_account
from .analysis import build_own_video_analysis_prompt, own_video_analysis_schema
from .exporter import export_creator_content
from .importer import clean_import_value, own_douyin_source_key, parse_own_douyin_import
from .scheduler import WeeklyExportScheduler
from .service import parse_analysis


def create_own_content_operations(get_db_path, get_agent_runtime, base_dir, log):
    own_content_export_scheduler = None

    def save_own_douyin_import(rows, account):
        account_name = clean_import_value(account.get("userName")) or f"抖音账号 {account['id']}"
        return own_content_repository.save_import(
            get_db_path(),
            rows,
            account["id"],
            account_name,
            own_douyin_source_key,
        )


    def run_own_douyin_creator_export(account, run_id=None):
        run_id = run_id or own_content_repository.create_export_run(
            get_db_path(), account["id"], account.get("userName")
        )
        try:
            export_path = export_creator_content(
                account["cookie_path"],
                download_dir=browser_settings_service.require_download_directory(get_db_path()),
            )
            with open(export_path, "rb") as file:
                file_storage = type("ExportFile", (), {
                    "filename": export_path.name,
                    "read": file.read,
                })()
                parsed = parse_own_douyin_import(file_storage)
            result = save_own_douyin_import(parsed["rows"], account)
            own_content_repository.finish_export_run(
                get_db_path(), run_id, "success", str(export_path), result["total"]
            )
            log(f"Douyin creator export imported for account {account['id']}: {result}")
            return {"run_id": run_id, "user_info_id": account["id"], "file_path": str(export_path), **result}
        except Exception as exc:
            if "登录态已失效" in str(exc):
                account_repository.mark_account_invalid(get_db_path(), account["id"])
            own_content_repository.finish_export_run(
                get_db_path(), run_id, "failed", error_message=str(exc)
            )
            log(f"Douyin creator export failed for account {account['id']}: {exc}")
            raise


    def run_scheduled_own_content_exports():
        today = datetime.now().strftime("%Y-%m-%d")
        for row in list_douyin_data_accounts(get_db_path()):
            if int(row.get("status") or 0) != 1:
                continue
            latest = own_content_repository.get_latest_export_run(get_db_path(), row["id"])
            if latest and str(latest.get("started_at") or "")[:10] == today:
                continue
            try:
                account = resolve_douyin_data_account(get_db_path(), row["id"], base_dir)
                run_own_douyin_creator_export(account)
            except Exception as exc:
                log(f"Scheduled Douyin creator export skipped for account {row['id']}: {exc}")


    def start_own_content_export_scheduler():
        nonlocal own_content_export_scheduler
        if own_content_export_scheduler is None:
            own_content_export_scheduler = WeeklyExportScheduler(run_scheduled_own_content_exports)
        own_content_export_scheduler.start()


    def list_own_douyin_videos(user_info_id, limit=100):
        videos = own_content_repository.list_videos(get_db_path(), user_info_id, limit)
        for video in videos:
            video["analysis"] = parse_analysis(video)
        return videos


    def list_all_own_douyin_videos(limit=100):
        videos = own_content_repository.list_all_videos(get_db_path(), limit)
        for video in videos:
            video["analysis"] = parse_analysis(video)
        return videos


    def own_video_analysis_is_freshly_running(video, max_age=timedelta(minutes=5)):
        if video.get("analysis_status") != "running":
            return False
        value = video.get("analysis_updated_at")
        if not value:
            return False
        try:
            updated_at = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return False
        return datetime.utcnow() - updated_at <= max_age


    def run_own_video_analysis(video_id, force=False):
        video = own_content_repository.get_video(get_db_path(), video_id)
        if not video:
            raise ValueError("作品不存在")
        if own_video_analysis_is_freshly_running(video) and not force:
            return video
        if video.get("analysis_json") and not force:
            video["analysis"] = parse_analysis(video)
            return video
        own_content_repository.set_analysis_status(get_db_path(), video_id, "running")
        try:
            peers = own_content_repository.list_analysis_peers(get_db_path(), video["account_id"])
            result = get_agent_runtime().run_structured(
                "ownContentReview",
                build_own_video_analysis_prompt(video, peers),
                own_video_analysis_schema(),
            )
            own_content_repository.set_analysis_status(get_db_path(), video_id, "success", result)
            video["analysis_status"] = "success"
            video["analysis"] = result
            return video
        except Exception as exc:
            own_content_repository.set_analysis_status(get_db_path(), video_id, "failed", error=str(exc))
            raise

    return SimpleNamespace(
        save_import=save_own_douyin_import,
        export_account=run_own_douyin_creator_export,
        run_scheduled_exports=run_scheduled_own_content_exports,
        start_scheduler=start_own_content_export_scheduler,
        list_videos=list_own_douyin_videos,
        list_all_videos=list_all_own_douyin_videos,
        analysis_is_running=own_video_analysis_is_freshly_running,
        analyze_video=run_own_video_analysis,
    )
