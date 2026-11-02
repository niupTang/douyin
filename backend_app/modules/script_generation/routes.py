from flask import Blueprint, jsonify, request


def create_script_generation_blueprint(generate_identity_script):
    blueprint = Blueprint("script_generation", __name__)

    @blueprint.route('/script-generation/identity', methods=['POST'])
    def create_identity_script():
        try:
            payload = request.get_json(silent=True) or {}
            identity_profile = payload.get("identityProfile") or payload.get("identity_profile") or {}
            radar_result = payload.get("radarResult") or payload.get("radar_result") or {}
            benchmark_analysis = payload.get("benchmarkAnalysis") or payload.get("benchmark_analysis") or {}
            if not isinstance(identity_profile, dict) or not identity_profile:
                return jsonify({"code": 400, "msg": "请提供创作者身份资料", "data": None}), 400
            if not isinstance(radar_result, dict) or not radar_result:
                return jsonify({"code": 400, "msg": "请提供观点雷达结果", "data": None}), 400
            script = generate_identity_script(identity_profile, radar_result, benchmark_analysis)
            return jsonify({"code": 200, "msg": "success", "data": script}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500

    return blueprint
