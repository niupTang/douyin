import asyncio
import threading
import traceback

from flask import Blueprint, jsonify, request

from myUtils.douyin_benchmark import (
    discover_douyin_benchmark_accounts,
    normalize_douyin_user_url,
    open_douyin_login_browser,
    scrape_douyin_benchmark,
)
from . import repository as benchmark_repository
from myUtils.douyin_session import open_preview, save_session, validate_preview_url
from .discovery import CandidateDiscovery


def create_benchmark_blueprint(
    get_db_path, latest_douyin_cookie_file, sync_one_douyin_benchmark,
    save_douyin_benchmark_error, upsert_douyin_benchmark,
    parse_keywords_payload, run_douyin_content_search_task,
    delete_douyin_benchmark, get_douyin_benchmark_video_urls,
    save_douyin_benchmark_sync, is_douyin_analysis_stale,
    generate_douyin_video_analysis, save_douyin_video_analysis,
    parse_douyin_video_analysis, *, candidate_discovery=None,
):
    blueprint = Blueprint("benchmark", __name__)
    discovery = candidate_discovery if candidate_discovery is not None else CandidateDiscovery(
        get_db_path, discover_douyin_benchmark_accounts, scrape_douyin_benchmark)
    blueprint.candidate_discovery = discovery

    @blueprint.route('/benchmark/douyin/auto-discover', methods=['POST'])
    @blueprint.route('/benchmark/douyin/discovery-tasks', methods=['POST'])
    def start_candidate_discovery():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"code": 400, "msg": "请提供搜索参数", "data": None}), 400
        try:
            keywords = list(dict.fromkeys(parse_keywords_payload(payload.get('keywords') or payload.get('keyword'))))
            if not keywords or len(keywords) > 20:
                raise ValueError('请填写 1 到 20 个对标关键词')
            limit = int(payload.get('limit', 5))
            max_videos = int(payload.get('maxVideos', payload.get('max_videos', 10)))
            if not 1 <= limit <= 20 or not 1 <= max_videos <= 30:
                raise ValueError('候选账号数须为 1 到 20，每号作品数须为 1 到 30')
            task = discovery.start(keywords, limit, max_videos, latest_douyin_cookie_file())
            return jsonify({"code": 202, "msg": "正在搜索候选账号，确认前不会入库", "data": task}), 202
        except (ValueError, TypeError) as exc:
            return jsonify({"code": 400, "msg": str(exc), "data": None}), 400

    @blueprint.route('/benchmark/douyin/discovery-tasks/<task_id>', methods=['GET'])
    def get_candidate_discovery(task_id):
        task = discovery.get(task_id)
        if not task:
            return jsonify({"code": 404, "msg": "搜索任务不存在", "data": None}), 404
        return jsonify({"code": 200, "msg": "success", "data": task})

    @blueprint.route('/benchmark/douyin/discovery-tasks/<task_id>/candidates/<candidate_id>/import', methods=['POST'])
    def import_discovered_candidate(task_id, candidate_id):
        try:
            result = discovery.import_candidate(task_id, candidate_id)
            return jsonify({"code": 200, "msg": "已加入对标库", "data": result})
        except LookupError as exc:
            return jsonify({"code": 404, "msg": str(exc), "data": None}), 404
        except ValueError as exc:
            return jsonify({"code": 400, "msg": str(exc), "data": None}), 400

    @blueprint.route('/benchmark/douyin/preview', methods=['POST'])
    def preview_douyin_video():
        try:
            url = validate_preview_url((request.get_json(silent=True) or {}).get("url"))
        except ValueError as exc:
            return jsonify({"code": 400, "msg": str(exc), "data": None}), 400
        try:
            result = asyncio.run(open_preview(url, latest_douyin_cookie_file()))
            return jsonify({"code": 200, "msg": "已在共享会话中打开", "data": result})
        except Exception as exc:
            return jsonify({"code": 500, "msg": f"打开预览失败：{exc}", "data": None}), 500

    @blueprint.route('/benchmark/douyin/session/save', methods=['POST'])
    def save_douyin_browser_session():
        try:
            result = asyncio.run(save_session(latest_douyin_cookie_file()))
            return jsonify({"code": 200, "msg": "会话已保存", "data": result})
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    @blueprint.route('/benchmark/douyin/accounts', methods=['POST'])
    def add_douyin_benchmark_account():
        data = request.get_json() or {}
        homepage_url = data.get("url") or data.get("link") or data.get("homepageUrl") or data.get("homepage_url")
        try:
            cookie_file = latest_douyin_cookie_file()
            result = sync_one_douyin_benchmark(homepage_url, cookie_file, max_videos=20)
            return jsonify({"code": 200, "msg": "success", "data": {"id": result["id"], "sync": result["sync"], "input_type": result.get("input_type", "profile")}}), 200
        except ValueError as e:
            return jsonify({"code": 400, "msg": str(e), "data": None}), 400
        except Exception as e:
            try:
                if normalize_douyin_user_url(homepage_url):
                    save_douyin_benchmark_error(upsert_douyin_benchmark(homepage_url), str(e))
            except Exception:
                pass
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/benchmark/douyin/content-search', methods=['POST'])
    def create_douyin_content_search():
        payload = request.get_json() or {}
        keyword = str(payload.get('keyword') or '').strip()
        if not keyword:
            return jsonify({"code": 400, "msg": "请填写内容关键词", "data": None}), 400
        target_count = max(10, min(int(payload.get('targetCount') or payload.get('target_count') or 50), 100))
        task_id = benchmark_repository.create_search_task(get_db_path(), keyword, target_count)
        thread = threading.Thread(target=run_douyin_content_search_task, args=(task_id, keyword, target_count, latest_douyin_cookie_file()), daemon=True)
        thread.start()
        return jsonify({"code": 200, "msg": "success", "data": {"task_id": task_id, "status": "pending"}}), 200


    @blueprint.route('/benchmark/douyin/login', methods=['POST'])
    def open_douyin_login():
        """打开可见、持久化的抖音浏览器窗口供用户扫码或处理验证。"""
        cookie_file = latest_douyin_cookie_file()
        def runner():
            try:
                asyncio.run(open_douyin_login_browser(cookie_file=cookie_file))
            except Exception:
                traceback.print_exc()
        threading.Thread(target=runner, daemon=True).start()
        return jsonify({"code": 200, "msg": "已打开抖音验证窗口", "data": {"status": "opened"}}), 200


    @blueprint.route('/benchmark/douyin/content-search/<int:task_id>', methods=['GET'])
    def get_douyin_content_search_task(task_id):
        task = benchmark_repository.get_search_task(get_db_path(), task_id)
        if not task:
            return jsonify({"code": 404, "msg": "搜索任务不存在", "data": None}), 404
        return jsonify({"code": 200, "msg": "success", "data": task}), 200


    @blueprint.route('/benchmark/douyin/content-search/<int:task_id>/results', methods=['GET'])
    def get_douyin_content_search_results(task_id):
        if not benchmark_repository.get_search_task(get_db_path(), task_id):
            return jsonify({"code": 404, "msg": "搜索任务不存在", "data": None}), 404
        return jsonify({"code": 200, "msg": "success", "data": benchmark_repository.list_search_results(get_db_path(), task_id)}), 200


    @blueprint.route('/benchmark/douyin/videos', methods=['GET'])
    def get_all_douyin_benchmark_videos():
        return jsonify({"code": 200, "msg": "success", "data": benchmark_repository.list_all_videos(
            get_db_path(), request.args.get('keyword'), request.args.get('source_type'), request.args.get('limit', 200)
        )}), 200


    @blueprint.route('/benchmark/douyin/accounts', methods=['GET'])
    def get_douyin_benchmark_accounts():
        try:
            accounts = benchmark_repository.list_accounts(get_db_path())
            return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/benchmark/douyin/accounts/<int:account_id>', methods=['DELETE'])
    def delete_douyin_benchmark_account(account_id):
        try:
            result = delete_douyin_benchmark(account_id)
            if not result:
                return jsonify({"code": 404, "msg": "对标账号不存在", "data": None}), 404
            return jsonify({
                "code": 200,
                "msg": "删除成功",
                "data": result,
            }), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/benchmark/douyin/accounts/<int:account_id>/sync', methods=['POST'])
    def sync_douyin_benchmark_account(account_id):
        try:
            cookie_file = latest_douyin_cookie_file()
            homepage_url = benchmark_repository.get_account_homepage(get_db_path(), account_id)
            if not homepage_url:
                return jsonify({"code": 404, "msg": "对标账号不存在", "data": None}), 404
            existing_urls = get_douyin_benchmark_video_urls(account_id)
            sync_data = asyncio.run(scrape_douyin_benchmark(
                homepage_url,
                cookie_file=cookie_file,
                max_videos=20,
                existing_video_urls=existing_urls
            ))
            stats = save_douyin_benchmark_sync(account_id, sync_data)
            return jsonify({"code": 200, "msg": "success", "data": {"id": account_id, "sync": stats}}), 200
        except Exception as e:
            save_douyin_benchmark_error(account_id, str(e))
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/benchmark/douyin/accounts/<int:account_id>/videos', methods=['GET'])
    def get_douyin_benchmark_videos(account_id):
        try:
            videos = benchmark_repository.list_videos(get_db_path(), account_id)
            return jsonify({"code": 200, "msg": "success", "data": videos}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/benchmark/douyin/videos/<int:video_id>/analysis', methods=['GET'])
    def get_douyin_benchmark_video_analysis(video_id):
        try:
            video = benchmark_repository.get_video(get_db_path(), video_id)
            if not video:
                return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
            row = benchmark_repository.get_analysis(get_db_path(), video_id)
            if is_douyin_analysis_stale(row, video):
                analysis = generate_douyin_video_analysis(video)
                save_douyin_video_analysis(video_id, analysis)
                row = benchmark_repository.get_analysis(get_db_path(), video_id)
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": {
                    "video": video,
                    "analysis": parse_douyin_video_analysis(row)
                }
            }), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/benchmark/douyin/videos/<int:video_id>/analysis', methods=['POST'])
    def create_douyin_benchmark_video_analysis(video_id):
        try:
            force = bool((request.get_json(silent=True) or {}).get("force"))
            video = benchmark_repository.get_video(get_db_path(), video_id)
            if not video:
                return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
            existing = benchmark_repository.get_analysis(get_db_path(), video_id)
            if existing and not force and not is_douyin_analysis_stale(existing, video):
                return jsonify({
                    "code": 200,
                    "msg": "success",
                    "data": parse_douyin_video_analysis(existing)
                }), 200

            analysis = generate_douyin_video_analysis(video)
            save_douyin_video_analysis(video_id, analysis)
            row = benchmark_repository.get_analysis(get_db_path(), video_id)
            return jsonify({"code": 200, "msg": "success", "data": parse_douyin_video_analysis(row)}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/benchmark/douyin/videos/<int:video_id>/pi-analysis', methods=['POST'])
    def save_pi_douyin_benchmark_video_analysis(video_id):
        video = benchmark_repository.get_video(get_db_path(), video_id)
        if not video:
            return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
        payload = request.get_json(silent=True) or {}
        required_text = ["summary", "hook", "core_viewpoint"]
        required_lists = ["pain_points", "viral_points", "reusable_points", "script_suggestions"]
        if any(not str(payload.get(key) or "").strip() for key in required_text):
            return jsonify({"code": 400, "msg": "PI Agent分析缺少必要文本字段", "data": None}), 400
        if any(not isinstance(payload.get(key), list) for key in required_lists):
            return jsonify({"code": 400, "msg": "PI Agent分析数组字段格式错误", "data": None}), 400
        analysis = {**payload, "analysis_type": "pi_agent"}
        benchmark_repository.save_analysis(get_db_path(), video_id, analysis)
        return jsonify({"code": 200, "msg": "PI Agent分析已保存", "data": parse_douyin_video_analysis(
            benchmark_repository.get_analysis(get_db_path(), video_id)
        )}), 200

    return blueprint
