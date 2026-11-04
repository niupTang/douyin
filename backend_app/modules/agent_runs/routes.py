from flask import Blueprint, jsonify, request


def create_agent_runs_blueprint(runtime_factory):
    blueprint = Blueprint("agent_runs", __name__)

    @blueprint.route("/api/agents/<agent_key>/runs", methods=["POST"])
    def create_agent_run(agent_key):
        payload = request.get_json(silent=True) or {}
        if not str(payload.get("prompt") or "").strip():
            return jsonify({"code": 400, "message": "Agent Prompt 不能为空", "data": None}), 400
        try:
            run = runtime_factory().submit(agent_key, payload)
            return jsonify({"code": 202, "message": "Agent 任务已创建", "data": run}), 202
        except (ValueError, RuntimeError) as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/api/agent-runs/<run_id>", methods=["GET"])
    def get_agent_run(run_id):
        run = runtime_factory().get_run(run_id)
        if not run:
            return jsonify({"code": 404, "message": "Agent 任务不存在", "data": None}), 404
        return jsonify({"code": 200, "data": run})

    @blueprint.route("/api/agent-runs/<run_id>/events", methods=["GET"])
    def get_agent_run_events(run_id):
        runtime = runtime_factory()
        if not runtime.get_run(run_id):
            return jsonify({"code": 404, "message": "Agent 任务不存在", "data": None}), 404
        return jsonify({"code": 200, "data": runtime.get_events(run_id)})

    @blueprint.route("/api/agent-runs/<run_id>/cancel", methods=["POST"])
    def cancel_agent_run(run_id):
        run = runtime_factory().cancel(run_id)
        if not run:
            return jsonify({"code": 404, "message": "Agent 任务不存在", "data": None}), 404
        return jsonify({"code": 200, "message": "Agent 任务已取消", "data": run})

    return blueprint
