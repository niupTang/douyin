import threading
import uuid
from queue import Queue

from flask import Blueprint, Response, jsonify, request

from myUtils.login import (
    get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen,
)
from . import repository as account_repository
from .login_service import run_login_task, sse_stream as account_login_sse_stream


def create_accounts_blueprint(get_db_path, log):
    blueprint = Blueprint("accounts", __name__)
    active_queues = {}
    active_queues_lock = threading.Lock()

    @blueprint.route("/getValidAccounts", methods=['GET'])
    def getValidAccounts():
        rows_list = account_repository.list_accounts(get_db_path())
        return jsonify(
                        {
                            "code": 200,
                            "msg": None,
                            "data": rows_list
                        }),200


    @blueprint.route('/account/updateFollower', methods=['POST'])
    def update_account_follower():
        """更新账号粉丝数"""
        try:
            data = request.get_json()
            account_id = data.get('id')
            follower_count = data.get('follower_count')
            if not account_id or follower_count is None:
                return jsonify({"code": 400, "msg": "缺少账号ID或粉丝数"}), 400

            account_repository.update_follower_count(get_db_path(), account_id, follower_count)

            return jsonify({"code": 200, "msg": "更新成功"}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/account/followers', methods=['GET'])
    def get_account_followers():
        """获取所有账号的粉丝数"""
        try:
            accounts = account_repository.list_followers(get_db_path())
            return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/deleteAccount', methods=['GET'])
    def delete_account():
        account_id = int(request.args.get('id'))

        try:
            record = account_repository.delete_account(get_db_path(), account_id)
            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "account not found",
                    "data": None
                }), 404

            return jsonify({
                "code": 200,
                "msg": "account deleted successfully",
                "data": None
            }), 200

        except Exception as e:
            return jsonify({
                "code": 500,
                "msg": str("delete failed!"),
                "data": None
            }), 500


    @blueprint.route('/login')
    def login():
        # 1 小红书 2 视频号 3 抖音 4 快手
        type = request.args.get('type')
        # 账号名
        id = request.args.get('id')
        user_info_id = request.args.get('userInfoId')
        login_session_id = request.args.get('loginSessionId') or uuid.uuid4().hex

        if str(type) not in {"1", "2", "3", "4"}:
            return jsonify({"code": 400, "message": "不支持的平台类型", "data": None}), 400
        if not id:
            return jsonify({"code": 400, "message": "缺少账号备注", "data": None}), 400

        # 模拟一个用于异步通信的队列
        status_queue = Queue()
        with active_queues_lock:
            if login_session_id in active_queues:
                return jsonify({"code": 409, "message": "登录会话已存在", "data": None}), 409
            active_queues[login_session_id] = status_queue

        def on_close():
            with active_queues_lock:
                if active_queues.get(login_session_id) is status_queue:
                    active_queues.pop(login_session_id, None)
            log(f"account login session cleaned: {login_session_id}")
        # 启动异步任务线程
        thread = threading.Thread(
            target=run_async_function,
            args=(type, id, status_queue, user_info_id),
            daemon=True,
        )
        thread.start()
        response = Response(
            sse_stream(status_queue, on_close=on_close),
            mimetype='text/event-stream',
        )
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Accel-Buffering'] = 'no'  # 关键：禁用 Nginx 缓冲
        response.headers['Content-Type'] = 'text/event-stream'
        response.headers['Connection'] = 'keep-alive'
        return response


    @blueprint.route('/updateUserinfo', methods=['POST'])
    def updateUserinfo():
        # 获取JSON数据
        data = request.get_json()

        # 从JSON数据中提取 type 和 userName
        user_id = data.get('id')
        type = data.get('type')
        userName = data.get('userName')
        try:
            account_repository.update_account_info(get_db_path(), user_id, type, userName)

            return jsonify({
                "code": 200,
                "msg": "account update successfully",
                "data": None
            }), 200

        except Exception as e:
            return jsonify({
                "code": 500,
                "msg": str("update failed!"),
                "data": None
            }), 500


    def run_async_function(type, id, status_queue, user_info_id=None):
        douyin_login = (
            lambda account_name, queue: douyin_cookie_gen(
                account_name, queue, existing_account_id=user_info_id
            )
        )
        return run_login_task(
            type,
            id,
            status_queue,
            login_handlers={
                "1": xiaohongshu_cookie_gen,
                "2": get_tencent_cookie,
                "3": douyin_login,
                "4": get_ks_cookie,
            },
            log=log,
        )


    def sse_stream(status_queue, on_close=None):
        return account_login_sse_stream(
            status_queue,
            log=log,
            on_close=on_close,
        )

    return blueprint
