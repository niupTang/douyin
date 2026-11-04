import json

from backend_app.agent.errors import ProviderResponseError
from backend_app.agent.structured_runner import load_json_object


class StructuredExecutionStrategy:
    def execute(self, adapter, prompt, schema, *, timeout=None, event=None, cancelled=None):
        if hasattr(adapter, "run_structured"):
            return adapter.run_structured(prompt, schema, timeout=timeout)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是严格的结构化内容分析 Agent。只返回一个合法 JSON 对象，不要使用 Markdown。"
                    "输出必须匹配以下 JSON Schema："
                    + json.dumps(schema, ensure_ascii=False)
                ),
            },
            {"role": "user", "content": prompt},
        ]
        last_error = None
        for attempt in range(2):
            if cancelled and cancelled():
                from backend_app.agent.errors import AgentCancelledError

                raise AgentCancelledError("Agent 任务已取消")
            message = adapter.complete(messages, timeout=timeout)
            content = message.get("content") or ""
            try:
                return load_json_object(content)
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if event:
                    event("format_retry", {"attempt": attempt + 1})
                messages.extend(
                    [
                        {"role": "assistant", "content": str(content)[-6000:]},
                        {
                            "role": "user",
                            "content": "上一次输出不是合法 JSON，请修正并只返回符合 Schema 的 JSON 对象。",
                        },
                    ]
                )
        raise ProviderResponseError(f"结构化输出解析失败：{last_error}")
