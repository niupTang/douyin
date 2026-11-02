from flask import Blueprint, jsonify, request

from .service import get_status as get_idea_radar_status_payload


def create_idea_radar_blueprint(
    list_idea_radar_videos, load_idea_radar_video,
    start_idea_radar_pipeline, get_idea_radar_transcript,
):
    blueprint = Blueprint("idea_radar", __name__)

    @blueprint.route('/idea-radar/douyin/videos', methods=['GET'])
    def get_idea_radar_videos():
        try:
            limit = request.args.get("limit", 80)
            videos = list_idea_radar_videos(limit)
            return jsonify({"code": 200, "msg": "success", "data": videos}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/idea-radar/douyin/videos/<int:video_id>/analyze', methods=['POST'])
    def analyze_idea_radar_video(video_id):
        try:
            payload = request.get_json(silent=True) or {}
            target_direction = payload.get("targetDirection") or payload.get("target_direction")
            target_direction = target_direction or "AI 生产系统研究员"
            if not load_idea_radar_video(video_id):
                return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
            task = start_idea_radar_pipeline(
                video_id,
                target_direction,
                force=bool(payload.get("force")),
                force_transcription=bool(payload.get("forceTranscription") or payload.get("force_transcription")),
            )
            return jsonify({"code": 200, "msg": "success", "data": task}), 200
        except ValueError as e:
            return jsonify({"code": 400, "msg": str(e), "data": None}), 400
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/idea-radar/douyin/videos/<int:video_id>/status', methods=['GET'])
    def get_idea_radar_video_status(video_id):
        try:
            if not load_idea_radar_video(video_id):
                return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
            task = get_idea_radar_status_payload(video_id, get_idea_radar_transcript)
            return jsonify({"code": 200, "msg": "success", "data": task}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500

    return blueprint
