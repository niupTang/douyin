import json

from backend_app.agent.errors import AgentCancelledError, ProviderResponseError


class ToolLoopExecutionStrategy:
    def execute(
        self,
        adapter,
        prompt,
        tool_registry,
        *,
        system_prompt,
        timeout=None,
        max_steps=8,
        event=None,
        cancelled=None,
    ):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        tools = tool_registry.schemas()
        for step in range(1, max_steps + 1):
            if cancelled and cancelled():
                raise AgentCancelledError("Agent 任务已取消")
            if event:
                event("model_call", {"step": step})
            message = adapter.complete(messages, tools=tools, timeout=timeout)
            tool_calls = message.get("tool_calls") or []
            content = message.get("content") or ""
            if not tool_calls:
                if not content:
                    raise ProviderResponseError("Tool Agent 没有返回文本或工具调用")
                return {"content": content, "steps": step}
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                function = call.get("function") or {}
                name = function.get("name") or ""
                if event:
                    event("tool_call", {"step": step, "tool": name})
                try:
                    result = tool_registry.execute(name, function.get("arguments") or "{}")
                    serialized = json.dumps(result, ensure_ascii=False, default=str)
                    if event:
                        event("tool_result", {"step": step, "tool": name, "ok": True})
                except Exception as exc:
                    serialized = json.dumps({
                        "error": str(exc), "error_code": getattr(exc, "code", "TOOL_EXECUTION_FAILED"),
                        "invocation_id": getattr(exc, "invocation_id", None),
                    }, ensure_ascii=False)
                    if event:
                        event("tool_result", {"step": step, "tool": name, "ok": False})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or f"tool-{step}",
                        "name": name,
                        "content": serialized,
                    }
                )
        raise ProviderResponseError(f"Tool Agent 达到最大步骤数 {max_steps}，未生成最终结果")
