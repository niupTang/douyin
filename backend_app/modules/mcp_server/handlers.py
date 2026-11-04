"""Legacy MCP HTTP adapter over the shared business tool gateway."""
from backend_app.common.tool_gateway import ToolExecutionGateway
from backend_app.modules.tool_execution.catalog import TOOL_DEFINITIONS, TOOL_POLICY, create_tool_handlers
from backend_app.modules.tool_execution.services import create_business_services


# Preserve the existing MCP name while distinguishing account pagination from
# the Agent's keyword-based, cross-account list_benchmark_videos tool.
MCP_TOOL_NAMES = {"list_benchmark_videos": "list_account_benchmark_videos"}



def create_mcp_handlers(
    get_db_path, latest_douyin_cookie_file, sync_one_douyin_benchmark,
    generate_douyin_video_analysis, save_douyin_video_analysis,
    load_idea_radar_video, start_idea_radar_pipeline, generate_identity_script,
    list_all_own_douyin_videos, publish_video_payload, *, gateway=None, extra_tool_names=(),
):
    gateway = gateway or ToolExecutionGateway()
    services = create_business_services(
        get_db_path, latest_douyin_cookie_file, sync_one_douyin_benchmark,
        generate_douyin_video_analysis, save_douyin_video_analysis,
        load_idea_radar_video, start_idea_radar_pipeline, generate_identity_script,
        list_all_own_douyin_videos, publish_video_payload,
    )
    handlers = create_tool_handlers(services)
    for definition in TOOL_DEFINITIONS:
        name = definition["name"]
        effect, entitlement = TOOL_POLICY[name]
        gateway.register(
            MCP_TOOL_NAMES.get(name, name), definition["description"],
            definition["input_schema"],
            lambda _handler=handlers[name], **arguments: _handler(arguments),
            side_effect=effect != "read", effect_type=effect, entitlement=entitlement,
        )

    exposed_names = [*handlers, *extra_tool_names]
    for name in extra_tool_names:
        if gateway.get(name) is None:
            raise ValueError(f"工具尚未注册：{name}")

    def mcp_tool_handlers():
        return {
            name: lambda arguments, _name=name: gateway.execute(
                MCP_TOOL_NAMES.get(_name, _name), arguments,
            )
            for name in exposed_names
        }

    mcp_tool_handlers.gateway = gateway
    def describe_tools():
        return [
            {
                "name": name,
                "description": gateway.get(MCP_TOOL_NAMES.get(name, name)).description,
                "input_schema": gateway.get(MCP_TOOL_NAMES.get(name, name)).openai_schema()["function"]["parameters"],
                "effect_type": gateway.get(MCP_TOOL_NAMES.get(name, name)).effect_type,
                "entitlement": gateway.get(MCP_TOOL_NAMES.get(name, name)).entitlement,
            }
            for name in exposed_names
        ]
    mcp_tool_handlers.describe_tools = describe_tools
    return mcp_tool_handlers
