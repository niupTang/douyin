import threading

from flask import Blueprint, jsonify, request

from . import repository, service


def create_account_diagnosis_blueprint(
    get_db_path, load_runtime_settings, get_agent_runtime, log
):
    blueprint = Blueprint("account_diagnosis", __name__)

    @blueprint.route('/account-diagnosis/accounts', methods=['GET'])
    def get_diagnosis_accounts():
        try:
            accounts = repository.list_douyin_user_info_accounts(get_db_path())
            return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    @blueprint.route('/own/accounts', methods=['GET'])
    def get_own_accounts():
        try:
            accounts = repository.list_own_accounts(get_db_path())
            return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    @blueprint.route('/own/accounts/<int:own_account_id>/bind', methods=['POST'])
    def bind_own_account(own_account_id):
        try:
            payload = request.get_json(silent=True) or {}
            user_info_id = payload.get("userInfoId") or payload.get("user_info_id")
            if not user_info_id:
                return jsonify({"code": 400, "msg": "缺少目标账号", "data": None}), 400
            user_info_id = int(user_info_id)
            target = repository.get_user_info_account(get_db_path(), user_info_id)
            if not target:
                return jsonify({"code": 404, "msg": "账号管理中的账号不存在", "data": None}), 404
            if int(target.get("type") or 0) != 3:
                return jsonify({"code": 400, "msg": "只能绑定抖音账号（type=3）", "data": None}), 400
            if not repository.get_own_account(get_db_path(), own_account_id):
                return jsonify({"code": 404, "msg": "自有账号不存在", "data": None}), 404
            repository.bind_own_account(get_db_path(), own_account_id, user_info_id)
            return jsonify({
                "code": 200,
                "msg": "绑定成功",
                "data": {"ownAccountId": own_account_id, "userInfoId": user_info_id},
            }), 200
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    @blueprint.route('/account-diagnosis/facts/<target_type>/<int:target_id>', methods=['GET'])
    def get_account_diagnosis_facts(target_type, target_id):
        try:
            if target_type == "own":
                facts = service.build_own_facts_payload(get_db_path(), target_id)
            elif target_type == "benchmark":
                facts = service.build_benchmark_facts_payload(get_db_path(), target_id)
            else:
                return jsonify({"code": 400, "msg": "target_type 只能是 own 或 benchmark", "data": None}), 400
            return jsonify({"code": 200, "msg": "success", "data": facts}), 200
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    @blueprint.route('/account-diagnosis/<target_type>/<int:target_id>', methods=['POST'])
    def run_account_diagnosis(target_type, target_id):
        if target_type not in ("own", "benchmark"):
            return jsonify({"code": 400, "msg": "target_type 只能是 own 或 benchmark", "data": None}), 400
        settings = load_runtime_settings()
        report_id = repository.create_report(
            get_db_path(), target_type, target_id, "running", progress=5, message="任务已创建"
        )

        def progress_cb(percent, message):
            repository.update_report_progress(
                get_db_path(), report_id, progress=percent, message=message
            )

        def runner():
            try:
                service.run_diagnosis_task(
                    get_db_path(), settings, target_type, target_id, report_id, progress_cb,
                    runtime=get_agent_runtime(),
                )
            except Exception as exc:
                log(f"Account diagnosis failed for {target_type}/{target_id}: {exc}")

        threading.Thread(
            target=runner, name=f"account-diagnosis-{target_type}-{target_id}", daemon=True
        ).start()
        return jsonify({"code": 200, "msg": "诊断已开始", "data": {"reportId": report_id, "status": "running"}}), 200

    @blueprint.route('/account-diagnosis/reports', methods=['GET'])
    def list_account_diagnosis_reports():
        try:
            target_type = request.args.get("targetType")
            reports = repository.list_reports(get_db_path(), target_type=target_type)
            return jsonify({"code": 200, "msg": "success", "data": reports}), 200
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    @blueprint.route('/account-diagnosis/reports/<int:report_id>', methods=['GET'])
    def get_account_diagnosis_report(report_id):
        try:
            report = repository.get_report(get_db_path(), report_id)
            if not report:
                return jsonify({"code": 404, "msg": "报告不存在", "data": None}), 404
            return jsonify({"code": 200, "msg": "success", "data": report}), 200
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    return blueprint
