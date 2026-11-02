from flask import Blueprint, jsonify, request

from .tools import describe_tools as describe_mcp_tools


def create_mcp_blueprint(mcp_tool_handlers):
    blueprint = Blueprint("mcp_server", __name__)

    @blueprint.route('/mcp/tools', methods=['GET'])
    def list_mcp_tools():
        describe = getattr(mcp_tool_handlers, "describe_tools", describe_mcp_tools)
        return jsonify({"code": 200, "msg": "success", "data": describe()}), 200


    @blueprint.route('/mcp/invoke', methods=['POST'])
    def invoke_mcp_tool():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"code": 400, "msg": "请求必须是 JSON 对象", "data": None}), 400
        tool_name = str(payload.get("name") or "").strip()
        arguments = payload.get("arguments", {})
        if not tool_name:
            return jsonify({"code": 400, "msg": "请提供 MCP 工具名称", "data": None}), 400
        if not isinstance(arguments, dict):
            return jsonify({"code": 400, "msg": "MCP 工具参数必须是对象", "data": None}), 400
        handlers = mcp_tool_handlers()
        handler = handlers.get(tool_name)
        if not handler:
            return jsonify({"code": 404, "msg": "MCP 工具不存在", "data": None}), 404
        try:
            return jsonify({"code": 200, "msg": "success", "data": handler(arguments)}), 200
        except NotImplementedError as exc:
            return jsonify({"code": 501, "msg": str(exc), "data": None}), 501
        except KeyError as exc:
            return jsonify({"code": 400, "msg": f"缺少参数：{exc}", "data": None}), 400
        except Exception as exc:
            return jsonify({"code": 500, "msg": str(exc), "data": None}), 500

    return blueprint
