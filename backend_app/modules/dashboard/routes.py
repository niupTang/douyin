from flask import Blueprint, jsonify

from .service import get_dashboard_stats as dashboard_stats_service


def create_dashboard_blueprint(get_db_path, ensure_publish_records_table):
    blueprint = Blueprint("dashboard", __name__)

    @blueprint.route('/dashboard/stats', methods=['GET'])
    def get_dashboard_stats():
        try:
            ensure_publish_records_table()
            data = dashboard_stats_service(get_db_path())
            return jsonify(
                {
                    "code": 200,
                    "msg": "success",
                    "data": data,
                }
            ), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500

    return blueprint
