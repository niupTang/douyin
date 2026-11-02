from types import SimpleNamespace

from backend_app.agent.model_registry import get_task_agent_model as agent_get_task_agent_model
from backend_app.modules.browser_settings import service as browser_settings_service
from backend_app.modules.benchmark import repository as benchmark_repository

from . import media as idea_radar_media
from . import repository as idea_radar_repository
from .analysis import parse_metric_number
from .prompts import build_transcript_radar_prompt as build_idea_radar_prompt
from .schemas import transcript_radar_schema


def create_idea_radar_operations(
    get_db_path, run_structured, load_runtime_settings,
    base_dir, latest_douyin_cookie_file, log,
):

    def parse_idea_radar_transcript(row):
        return idea_radar_repository.parse_transcript(row)


    def get_idea_radar_transcript(video_id):
        return idea_radar_repository.get_transcript(get_db_path(), video_id)


    def update_idea_radar_transcript(video_id, **values):
        idea_radar_repository.update_transcript(get_db_path(), video_id, **values)


    def write_netscape_cookie_file(storage_state_path, output_path):
        return idea_radar_media.write_netscape_cookie_file(storage_state_path, output_path)


    def download_douyin_video_with_ytdlp(video_url, output_dir, cookie_file, progress_callback=None):
        return idea_radar_media.download_with_ytdlp(
            video_url,
            output_dir,
            cookie_file,
            progress_callback=progress_callback,
            log=log,
        )


    async def download_douyin_video_with_playwright(
        video_url, output_path, storage_state_path=None, progress_callback=None
    ):
        return await idea_radar_media.download_with_playwright(
            video_url,
            output_path,
            storage_state_path=storage_state_path,
            progress_callback=progress_callback,
        )


    def download_douyin_video(video_url, work_dir, progress_callback=None):
        return idea_radar_media.download_douyin_video(
            video_url,
            work_dir,
            base_dir=base_dir,
            latest_cookie_file=latest_douyin_cookie_file,
            progress_callback=progress_callback,
            log=log,
        )


    def transcribe_idea_radar_media(media_path, progress_callback=None):
        cache_dir = browser_settings_service.require_download_directory(get_db_path()) / ".sau-cache" / "whisper"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return idea_radar_media.transcribe_media(
            media_path,
            progress_callback=progress_callback,
            log=log,
            download_root=cache_dir,
        )


    def clean_transcript_text(text):
        return idea_radar_media.clean_transcript_text(text)


    def list_idea_radar_videos(limit=80):
        return benchmark_repository.list_idea_radar_videos(
            get_db_path(), parse_metric_number, limit
        )


    def get_transcript_radar_schema():
        return transcript_radar_schema()


    def build_transcript_radar_prompt(video, transcript, target_direction):
        return build_idea_radar_prompt(video, transcript, target_direction)


    def get_task_agent_model(task_name="viralAnalysis", settings=None):
        return agent_get_task_agent_model(task_name, settings or load_runtime_settings())


    def call_hermes_structured(prompt, schema, model_config=None, timeout=None, task_name="viralAnalysis"):
        from backend_app.agent.structured_runner import call_hermes_structured as generate
        return generate(prompt, schema, settings=load_runtime_settings(),
                        model_config=model_config, timeout=timeout, task_name=task_name, log=log)


    def run_codex_structured(prompt, schema, timeout=None):
        return call_hermes_structured(prompt, schema, timeout=timeout, task_name="ideaRadar")


    def load_idea_radar_video(video_id):
        return benchmark_repository.get_video(get_db_path(), video_id, include_account=True)

    return SimpleNamespace(
        parse_idea_radar_transcript=parse_idea_radar_transcript,
        get_idea_radar_transcript=get_idea_radar_transcript,
        update_idea_radar_transcript=update_idea_radar_transcript,
        write_netscape_cookie_file=write_netscape_cookie_file,
        download_douyin_video_with_ytdlp=download_douyin_video_with_ytdlp,
        download_douyin_video_with_playwright=download_douyin_video_with_playwright,
        download_douyin_video=download_douyin_video,
        transcribe_idea_radar_media=transcribe_idea_radar_media,
        clean_transcript_text=clean_transcript_text,
        list_idea_radar_videos=list_idea_radar_videos,
        get_transcript_radar_schema=get_transcript_radar_schema,
        build_transcript_radar_prompt=build_transcript_radar_prompt,
        get_task_agent_model=get_task_agent_model,
        call_hermes_structured=call_hermes_structured,
        run_codex_structured=run_codex_structured,
        load_idea_radar_video=load_idea_radar_video,
    )
