from backend_app.common.tool_gateway import ToolExecutionError, ToolExecutionGateway


def create_application_gateway(license_registry, log_service):
    def authorize(tool, context):
        if not tool.entitlement:
            return
        allowed, status = license_registry.require(tool.entitlement)
        if not allowed:
            raise ToolExecutionError(
                status.get("reasonCode") or "TOOL_PERMISSION_DENIED",
                status.get("message") or "没有执行此工具的权限", 403,
            )

    def audit(event, metadata):
        log_service.log(
            level="WARNING" if event == "tool_failed" else "INFO",
            module="tool_gateway", event=event,
            message=f"{event}: {metadata['tool']}", context=metadata,
        )

    return ToolExecutionGateway(authorize=authorize, audit=audit)
