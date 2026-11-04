"""Shared execution boundary for business tools used by Agents and MCP."""
import json
import time
import uuid
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from backend_app.modules.runtime_logs.service import redact_text


@dataclass(frozen=True)
class ToolExecutionContext:
    source: str = "internal"
    run_id: str | None = None
    actor_id: str | None = None


execution_context = ContextVar("tool_execution_context", default=ToolExecutionContext())


class ToolExecutionError(ValueError):
    def __init__(self, code, message, status=400, invocation_id=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.invocation_id = invocation_id


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    parameters: dict
    handler: object
    side_effect: bool = False
    effect_type: str = "read"
    entitlement: str | None = None

    def openai_schema(self):
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": deepcopy(self.parameters),
        }}


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


class ToolExecutionGateway:
    def __init__(self, *, authorize=None, audit=None):
        self._tools = {}
        self._validators = {}
        self.authorize = authorize
        self.audit = audit

    def register(self, name, description, parameters, handler, *, side_effect=False,
                 effect_type=None, entitlement=None):
        if name in self._tools:
            raise ValueError(f"工具已存在：{name}")
        schema = deepcopy(parameters)
        schema.setdefault("additionalProperties", False)
        Draft202012Validator.check_schema(schema)
        self._tools[name] = RegisteredTool(
            name, description, schema, handler, side_effect,
            effect_type or ("write" if side_effect else "read"), entitlement,
        )
        self._validators[name] = Draft202012Validator(schema)

    def get(self, name):
        return self._tools.get(name)

    def _emit(self, event, payload):
        if self.audit:
            try:
                self.audit(event, payload)
            except Exception:
                pass  # Diagnostics must not turn a completed write into failure.

    def execute(self, name, raw_arguments, *, context=None, allowed_tools=None):
        context = context or execution_context.get()
        invocation_id = uuid.uuid4().hex
        started = time.monotonic()
        metadata = {"invocation_id": invocation_id, "tool": name,
                    "source": context.source, "run_id": context.run_id,
                    "actor_id": context.actor_id}
        self._emit("tool_started", metadata)
        try:
            if allowed_tools is not None and name not in allowed_tools:
                raise ToolExecutionError("TOOL_NOT_FOUND", f"调用方不可用的工具：{name}", 404)
            tool = self.get(name)
            if tool is None:
                raise ToolExecutionError("TOOL_NOT_FOUND", f"未注册工具：{name}", 404)
            arguments = raw_arguments
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments, parse_constant=_reject_constant)
                except (ValueError, RecursionError) as exc:
                    raise ToolExecutionError("TOOL_ARGUMENTS_INVALID", "工具参数不是合法 JSON") from exc
            if arguments is None:
                arguments = {}
            if not isinstance(arguments, dict):
                raise ToolExecutionError("TOOL_ARGUMENTS_INVALID", "工具参数必须是对象")
            try:
                json.dumps(arguments, allow_nan=False)
            except (TypeError, ValueError, RecursionError) as exc:
                raise ToolExecutionError("TOOL_ARGUMENTS_INVALID", "工具参数必须是有效 JSON 数据") from exc
            error = next(self._validators[name].iter_errors(arguments), None)
            if error:
                field = ".".join(str(part) for part in error.absolute_path) or "$"
                raise ToolExecutionError("TOOL_ARGUMENTS_INVALID", f"参数校验失败：{field}（{error.validator}）")
            if self.authorize:
                self.authorize(tool, context)
            result = tool.handler(**deepcopy(arguments))
        except ToolExecutionError as exc:
            exc.invocation_id = invocation_id
            self._emit("tool_failed", {**metadata, "error_code": exc.code,
                                       "duration_ms": round((time.monotonic() - started) * 1000)})
            raise
        except Exception as exc:
            if isinstance(exc, NotImplementedError):
                code, status = "TOOL_NOT_IMPLEMENTED", 501
            elif isinstance(exc, ValueError):
                code, status = "TOOL_BUSINESS_INVALID", 400
            else:
                code, status = "TOOL_EXECUTION_FAILED", 500
            self._emit("tool_failed", {**metadata, "error_code": code,
                                       "duration_ms": round((time.monotonic() - started) * 1000)})
            raise ToolExecutionError(code, redact_text(exc), status, invocation_id) from exc
        self._emit("tool_succeeded", {**metadata,
                                     "duration_ms": round((time.monotonic() - started) * 1000)})
        return result
