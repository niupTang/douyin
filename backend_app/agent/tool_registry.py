"""Agent-facing tool view backed by the shared business execution gateway."""
from backend_app.common.tool_gateway import RegisteredTool, ToolExecutionGateway, ToolExecutionError


class ToolRegistry:
    def __init__(self, gateway=None):
        self.gateway = gateway or ToolExecutionGateway()
        self._names = []

    def register(self, name, description, parameters, handler, *, side_effect=False,
                 effect_type=None, entitlement=None):
        self.gateway.register(name, description, parameters, handler,
                              side_effect=side_effect, effect_type=effect_type,
                              entitlement=entitlement)
        self._names.append(name)

    def schemas(self):
        return [self.gateway.get(name).openai_schema() for name in self._names]

    def expose(self, name):
        """Expose an already-registered shared tool without duplicating its handler."""
        if self.gateway.get(name) is None:
            raise ValueError(f"工具尚未注册：{name}")
        if name not in self._names:
            self._names.append(name)

    def execute(self, name, raw_arguments):
        return self.gateway.execute(name, raw_arguments, allowed_tools=self._names)
