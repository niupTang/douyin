from .tools import create_tool_handlers
from backend_app.modules.benchmark import repository as benchmark_repository
from backend_app.modules.benchmark.analysis import (
    is_douyin_analysis_stale,
    parse_douyin_video_analysis,
)
from backend_app.modules.own_content_review.service import review_published_content as review_published_content_core



def create_mcp_handlers(
    get_db_path, latest_douyin_cookie_file, sync_one_douyin_benchmark,
    generate_douyin_video_analysis, save_douyin_video_analysis,
    load_idea_radar_video, start_idea_radar_pipeline, generate_identity_script,
    list_all_own_douyin_videos, publish_video_payload,
):

    def collect_douyin_account(homepage_url, max_videos=20):
        cookie_file = latest_douyin_cookie_file()
        return sync_one_douyin_benchmark(homepage_url, cookie_file, max_videos=max_videos)


    def list_benchmark_videos(account_id, page=1, page_size=20):
        videos = benchmark_repository.list_videos(get_db_path(), account_id)
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 100))
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": videos[start:end],
            "page": page,
            "page_size": page_size,
            "total": len(videos),
        }


    def analyze_benchmark_video(video_id, force=False):
        video = benchmark_repository.get_video(get_db_path(), video_id)
        if not video:
            raise ValueError("作品不存在")
        existing = benchmark_repository.get_analysis(get_db_path(), video_id)
        if existing and not force and not is_douyin_analysis_stale(existing, video):
            return parse_douyin_video_analysis(existing)
        analysis = generate_douyin_video_analysis(video)
        save_douyin_video_analysis(video_id, analysis)
        return parse_douyin_video_analysis(benchmark_repository.get_analysis(get_db_path(), video_id))


    def run_idea_radar(video_id, target_direction="AI 生产系统研究员", force=False, force_transcription=False):
        if not load_idea_radar_video(video_id):
            raise ValueError("作品不存在")
        return start_idea_radar_pipeline(
            video_id,
            target_direction,
            force=force,
            force_transcription=force_transcription,
        )


    def generate_my_script(identity_profile, radar_result, benchmark_analysis=None):
        return generate_identity_script(identity_profile, radar_result, benchmark_analysis or {})


    def review_published_content(work_id=None, limit=50):
        videos = list_all_own_douyin_videos(limit)
        if work_id is not None:
            videos = [video for video in videos if str(video.get("id")) == str(work_id)]
        return review_published_content_core(videos)


    def publish_video(**kwargs):
        return publish_video_payload(kwargs)


    services = {
        "collect_douyin_account": collect_douyin_account,
        "list_benchmark_videos": list_benchmark_videos,
        "analyze_benchmark_video": analyze_benchmark_video,
        "run_idea_radar": run_idea_radar,
        "generate_my_script": generate_my_script,
        "review_published_content": review_published_content,
        "publish_video": publish_video,
    }

    return lambda: create_tool_handlers(services)
