from flask import Blueprint, jsonify, request

from . import repository as publish_repository


def create_publish_blueprint(get_db_path, publish_video_payload):
    blueprint = Blueprint("ai_publish", __name__)

    @blueprint.route('/getPublishRecords', methods=['GET'])
    def get_publish_records():
        try:
            records = publish_repository.list_records(get_db_path())
            return jsonify({"code": 200, "msg": "success", "data": records}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/publish/updateStats', methods=['POST'])
    def update_publish_stats():
        """手动更新某条发布记录的流量数据"""
        try:
            data = request.get_json()
            record_id = data.get('id')
            if not record_id:
                return jsonify({"code": 400, "msg": "缺少记录ID"}), 400

            fields = publish_repository.update_stats(get_db_path(), record_id, data)
            if not fields:
                return jsonify({"code": 400, "msg": "没有需要更新的字段"}), 400
            return jsonify({"code": 200, "msg": "更新成功", "data": fields}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/publish/batchUpdateStats', methods=['POST'])
    def batch_update_publish_stats():
        """批量更新多条记录的流量数据（来自前端批量操作或爬取结果）"""
        try:
            data = request.get_json()
            records = data.get('records', [])
            if not records:
                return jsonify({"code": 400, "msg": "没有记录"}), 400

            updated = publish_repository.batch_update_stats(get_db_path(), records)
            return jsonify({"code": 200, "msg": f"更新成功 {updated} 条记录", "data": {"updated": updated}}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/postVideo', methods=['POST'])
    def postVideo():
        data = request.get_json() or {}
        print("File List:", data.get('fileList', []))
        print("Account List:", data.get('accountList', []))
        try:
            publish_video_payload(data)
        except Exception as e:
            return jsonify(
                {
                    "code": 500,
                    "msg": str(e),
                    "data": None
                }), 500
        # 返回响应给客户端
        return jsonify(
            {
                "code": 200,
                "msg": None,
                "data": None
            }), 200


    @blueprint.route('/postVideoBatch', methods=['POST'])
    def postVideoBatch():
        data_list = request.get_json()

        if not isinstance(data_list, list):
            return jsonify({"error": "Expected a JSON array"}), 400
        for data in data_list:
            print("File List:", data.get('fileList', []))
            print("Account List:", data.get('accountList', []))
            try:
                publish_video_payload(data or {})
            except Exception as e:
                return jsonify({"code": 500, "msg": str(e), "data": None}), 500
        # 返回响应给客户端
        return jsonify(
            {
                "code": 200,
                "msg": None,
                "data": None
            }), 200

    return blueprint
