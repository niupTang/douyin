import os
import secrets
import json
import sys
import threading
from pathlib import Path
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import Flask, request, render_template, send_from_directory
from backend_app.agent.gateway_client import (
    get_hermes_settings as agent_get_hermes_settings,
    hermes_request as agent_hermes_request,
    public_hermes_settings as agent_public_hermes_settings,
)
from backend_app.agent.model_registry import get_agent_models as agent_get_agent_models, normalize_agent_model as agent_normalize_agent_model
from backend_app.modules.benchmark import repository as benchmark_repository
from backend_app.modules.benchmark.routes import create_benchmark_blueprint
from backend_app.modules.benchmark.operations import create_benchmark_operations
from backend_app.modules.benchmark.search import run_content_search_task
from backend_app.modules.benchmark.analysis import is_douyin_analysis_stale, parse_douyin_video_analysis
from backend_app.modules.idea_radar.jobs import IdeaRadarJobRegistry
from backend_app.modules.idea_radar.service import start_pipeline_task
from backend_app.modules.idea_radar.pipeline import run_pipeline as run_idea_radar_pipeline_core
from backend_app.modules.idea_radar.analysis import parse_metric_number
from backend_app.modules.idea_radar.operations import create_idea_radar_operations
from backend_app.modules.idea_radar.progress import update_progress as update_idea_radar_progress_core
from backend_app.modules.idea_radar.routes import create_idea_radar_blueprint
from backend_app.modules.browser_settings.routes import create_browser_settings_blueprint
from backend_app.modules.browser_settings import service as browser_settings_service
from backend_app.modules.script_generation.routes import create_script_generation_blueprint
from backend_app.modules.script_generation.service import generate_identity_script as generate_identity_script_core
from backend_app.modules.own_content_review import repository as own_content_repository
from backend_app.modules.own_content_review.routes import create_own_content_blueprint
from backend_app.modules.own_content_review.operations import create_own_content_operations
from backend_app.modules.ai_publish import repository as publish_repository
from backend_app.modules.ai_publish.routes import create_publish_blueprint
from backend_app.modules.ai_publish.operations import create_publish_operation
from backend_app.modules.accounts import repository as account_repository
from backend_app.modules.accounts.routes import create_accounts_blueprint
from backend_app.modules.dashboard.routes import create_dashboard_blueprint
from backend_app.modules.materials.routes import create_materials_blueprint
from backend_app.modules.runtime_logs import RuntimeLogService
from backend_app.modules.settings.routes import create_legacy_ai_settings_blueprint
from backend_app.agent.structured_runner import call_hermes_structured as legacy_generate
from backend_app.common.database import ensure_core_tables as ensure_base_tables
from backend_app.licensing.service import license_registry
from backend_app.licensing.routes import create_license_blueprint
from conf import BASE_DIR
from backend_app.modules.account_diagnosis import repository as account_diagnosis_repository
from backend_app.modules.account_diagnosis.routes import create_account_diagnosis_blueprint
from backend_app.modules.mcp_server.routes import create_mcp_blueprint
from backend_app.modules.mcp_server.handlers import create_mcp_handlers
from backend_app.modules.benchmark.discovery import create_candidate_discovery
from backend_app.modules.runtime.routes import create_runtime_blueprint
from backend_app.modules.auth.routes import create_auth_blueprint
from backend_app.modules.auth.security import configure_auth_policy


idea_radar_job_registry = IdeaRadarJobRegistry()
runtime_log_service = RuntimeLogService(BASE_DIR)
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SAU_SECRET_KEY") or secrets.token_hex(32)
AUTH_TOKEN_MAX_AGE = int(os.environ.get("SAU_AUTH_TOKEN_MAX_AGE", str(7 * 24 * 60 * 60)))
token_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="sau-local-auth")

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")
    except (BadSignature, SignatureExpired):
        pass

#允许所有来源跨域访问
CORS(app)

# 限制上传文件大小为160MB
app.config['MAX_CONTENT_LENGTH'] = 160 * 1024 * 1024


auth_policy = configure_auth_policy(
    app, token_serializer, AUTH_TOKEN_MAX_AGE, license_registry
)
auth_required = auth_policy.auth_required
valid_instance_token = auth_policy.valid_instance_token


def get_db_path():
    return Path(BASE_DIR / "db" / "database.db")


def get_settings_path():
    return Path(BASE_DIR / "settings.json")





def load_runtime_settings():
    settings_path = get_settings_path()
    if not settings_path.exists():
        return {}
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_runtime_settings(settings):
    settings_path = get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = settings_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_path.replace(settings_path)


def get_hermes_settings(settings=None):
    return agent_get_hermes_settings(settings or load_runtime_settings())


def get_agent_models(settings=None):
    return agent_get_agent_models(settings or load_runtime_settings())


def public_hermes_settings(settings=None):
    return agent_public_hermes_settings(settings or load_runtime_settings())


def hermes_request(path, method="GET", payload=None, timeout=None, settings=None):
    return agent_hermes_request(path, method=method, payload=payload, timeout=timeout, settings=settings or load_runtime_settings())


def normalize_agent_model(payload, existing_id=None):
    return agent_normalize_agent_model(payload, existing_id)


def ensure_core_tables():
    ensure_base_tables(get_db_path())
    ensure_publish_records_table()
    ensure_douyin_benchmark_tables()
    ensure_douyin_own_tables()


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(arg) for arg in args)
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"), **kwargs)


def backend_log(message):
    runtime_log_service.log(message=message)








def run_structured(task_name, prompt, schema):
    return legacy_generate(prompt, schema, settings=load_runtime_settings(),
                           task_name=task_name, log=backend_log)


@app.after_request
def log_failed_response(response):
    if response.status_code >= 400:
        runtime_log_service.log(
            level="ERROR" if response.status_code >= 500 else "WARNING",
            module="http",
            event="response_failed",
            message=f"{request.method} {request.path} returned {response.status_code}",
            context={"method": request.method, "path": request.path, "status": response.status_code},
        )
    return response

def ensure_publish_records_table():
    publish_repository.ensure_tables(get_db_path())


def ensure_douyin_benchmark_tables():
    benchmark_repository.ensure_tables(get_db_path())


def ensure_douyin_own_tables():
    own_content_repository.ensure_tables(get_db_path())


def latest_douyin_cookie_file():
    return account_repository.latest_douyin_cookie_file(get_db_path())


own_content_operations = create_own_content_operations(
    get_db_path, run_structured, BASE_DIR, backend_log
)
save_own_douyin_import = own_content_operations.save_import
run_own_douyin_creator_export = own_content_operations.export_account
run_scheduled_own_content_exports = own_content_operations.run_scheduled_exports
start_own_content_export_scheduler = own_content_operations.start_scheduler
list_own_douyin_videos = own_content_operations.list_videos
list_all_own_douyin_videos = own_content_operations.list_all_videos
own_video_analysis_is_freshly_running = own_content_operations.analysis_is_running
run_own_video_analysis = own_content_operations.analyze_video


benchmark_operations = create_benchmark_operations(
    get_db_path, idea_radar_job_registry, run_structured
)
get_douyin_benchmark_video_urls = benchmark_operations.list_video_urls
upsert_douyin_benchmark = benchmark_operations.upsert_account
delete_douyin_benchmark = benchmark_operations.delete_account
save_douyin_benchmark_sync = benchmark_operations.save_sync
save_douyin_benchmark_error = benchmark_operations.save_error
sync_one_douyin_benchmark = benchmark_operations.sync_account
parse_keywords_payload = benchmark_operations.parse_keywords
generate_douyin_video_analysis_by_codex = benchmark_operations.analyze_by_agent
generate_douyin_video_analysis = benchmark_operations.analyze_video
save_douyin_video_analysis = benchmark_operations.save_analysis


idea_radar_operations = create_idea_radar_operations(
    get_db_path, run_structured, load_runtime_settings,
    BASE_DIR, latest_douyin_cookie_file, backend_log,
)
parse_idea_radar_transcript = idea_radar_operations.parse_idea_radar_transcript
get_idea_radar_transcript = idea_radar_operations.get_idea_radar_transcript
update_idea_radar_transcript = idea_radar_operations.update_idea_radar_transcript
write_netscape_cookie_file = idea_radar_operations.write_netscape_cookie_file
download_douyin_video_with_ytdlp = idea_radar_operations.download_douyin_video_with_ytdlp
download_douyin_video_with_playwright = idea_radar_operations.download_douyin_video_with_playwright
download_douyin_video = idea_radar_operations.download_douyin_video
transcribe_idea_radar_media = idea_radar_operations.transcribe_idea_radar_media
clean_transcript_text = idea_radar_operations.clean_transcript_text
list_idea_radar_videos = idea_radar_operations.list_idea_radar_videos
get_transcript_radar_schema = idea_radar_operations.get_transcript_radar_schema
build_transcript_radar_prompt = idea_radar_operations.build_transcript_radar_prompt
get_task_agent_model = idea_radar_operations.get_task_agent_model
call_hermes_structured = idea_radar_operations.call_hermes_structured
run_codex_structured = idea_radar_operations.run_codex_structured
load_idea_radar_video = idea_radar_operations.load_idea_radar_video


def update_idea_radar_progress(video_id, stage, percent, message, status="processing", **values):
    return update_idea_radar_progress_core(
        video_id, stage, percent, message, status,
        registry=idea_radar_job_registry,
        get_transcript=get_idea_radar_transcript,
        update_transcript=update_idea_radar_transcript,
        **values,
    )


def generate_identity_script(identity_profile, radar_result, benchmark_analysis=None):
    return generate_identity_script_core(
        run_structured, identity_profile, radar_result, benchmark_analysis,
    )


def run_idea_radar_pipeline(video_id, target_direction, force_transcription=False):
    return run_idea_radar_pipeline_core(
        video_id,
        target_direction,
        force_transcription=force_transcription,
        load_video=load_idea_radar_video,
        get_transcript=get_idea_radar_transcript,
        update_progress=update_idea_radar_progress,
        download_video=download_douyin_video,
        transcribe_media=transcribe_idea_radar_media,
        clean_transcript=clean_transcript_text,
        build_prompt=build_transcript_radar_prompt,
        schema_factory=get_transcript_radar_schema,
        run_structured=run_codex_structured,
        get_agent_model=get_task_agent_model,
        parse_metric_number=parse_metric_number,
        registry=idea_radar_job_registry,
        get_download_root=lambda: browser_settings_service.require_download_directory(get_db_path()),
    )


def start_idea_radar_pipeline(video_id, target_direction, force=False, force_transcription=False):
    current = get_idea_radar_transcript(video_id)
    if force_transcription or not (current or {}).get("cleaned_transcript"):
        browser_settings_service.require_download_directory(get_db_path())
    started = start_pipeline_task(
        video_id,
        target_direction,
        current=current,
        registry=idea_radar_job_registry,
        update_transcript=update_idea_radar_transcript,
        pipeline_fn=run_idea_radar_pipeline,
        force=force,
        force_transcription=force_transcription,
    )
    return started or get_idea_radar_transcript(video_id)


publish_video_payload = create_publish_operation(get_db_path)

ensure_core_tables()
account_diagnosis_repository.ensure_tables(get_db_path())

# 获取当前目录（假设 index.html 和 assets 在这里）
current_dir = os.path.dirname(os.path.abspath(__file__))

# 处理所有静态资源请求（未来打包用）
@app.route('/assets/<filename>')
def custom_static(filename):
    return send_from_directory(os.path.join(current_dir, 'assets'), filename)

# 处理 favicon.ico 静态资源（未来打包用）
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'favicon.ico')

# （未来打包用）
@app.route('/')
def hello_world():  # put application's code here
    return render_template('index.html')


def run_douyin_content_search_task(task_id, keyword, target_count, cookie_file):
    return run_content_search_task(
        get_db_path(), task_id, keyword, target_count, cookie_file
    )


candidate_discovery = create_candidate_discovery(get_db_path)
mcp_tool_handlers = create_mcp_handlers(
    get_db_path, latest_douyin_cookie_file, sync_one_douyin_benchmark,
    generate_douyin_video_analysis, save_douyin_video_analysis,
    load_idea_radar_video, start_idea_radar_pipeline, generate_identity_script,
    list_all_own_douyin_videos, publish_video_payload,
)
app.register_blueprint(create_browser_settings_blueprint(get_db_path))
app.register_blueprint(create_account_diagnosis_blueprint(
    get_db_path, load_runtime_settings, run_structured, backend_log
))
app.register_blueprint(create_own_content_blueprint(
    get_db_path, BASE_DIR, save_own_douyin_import,
    list_own_douyin_videos, list_all_own_douyin_videos,
    own_video_analysis_is_freshly_running, run_own_video_analysis,
    run_own_douyin_creator_export, backend_log,
))
app.register_blueprint(create_benchmark_blueprint(
    get_db_path, latest_douyin_cookie_file, sync_one_douyin_benchmark,
    save_douyin_benchmark_error, upsert_douyin_benchmark,
    parse_keywords_payload, run_douyin_content_search_task,
    delete_douyin_benchmark, get_douyin_benchmark_video_urls,
    save_douyin_benchmark_sync, is_douyin_analysis_stale,
    generate_douyin_video_analysis, save_douyin_video_analysis,
    parse_douyin_video_analysis,
    candidate_discovery=candidate_discovery,
))
app.register_blueprint(create_idea_radar_blueprint(
    list_idea_radar_videos, load_idea_radar_video,
    start_idea_radar_pipeline, get_idea_radar_transcript,
))
app.register_blueprint(create_script_generation_blueprint(generate_identity_script))
app.register_blueprint(create_materials_blueprint(get_db_path, BASE_DIR))
app.register_blueprint(create_accounts_blueprint(get_db_path, backend_log))
app.register_blueprint(create_publish_blueprint(get_db_path, publish_video_payload))
app.register_blueprint(create_dashboard_blueprint(get_db_path, ensure_publish_records_table))
app.register_blueprint(create_mcp_blueprint(mcp_tool_handlers))
app.register_blueprint(create_license_blueprint(
    valid_instance_token, license_registry, token_serializer
))
app.register_blueprint(create_runtime_blueprint(BASE_DIR))
app.register_blueprint(create_auth_blueprint(auth_required))
app.register_blueprint(create_legacy_ai_settings_blueprint(
    load_runtime_settings, save_runtime_settings, get_hermes_settings,
    public_hermes_settings, hermes_request, get_agent_models,
    normalize_agent_model, call_hermes_structured, backend_log,
))

if __name__ == '__main__':
    ensure_core_tables()
    start_own_content_export_scheduler()
    app.run(host='127.0.0.1', port=int(os.environ.get("SAU_BACKEND_PORT", "5409")))
