import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend_app.agent.errors import (
    AgentCancelledError,
    AgentRuntimeError,
    ModelCapabilityError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from backend_app.agent.model_router_v2 import ModelRouter
from backend_app.agent.providers import CodexCliProviderAdapter, OpenAICompatibleProviderAdapter
from backend_app.agent.strategies import StructuredExecutionStrategy, ToolLoopExecutionStrategy
from backend_app.agent.tool_registry import ToolRegistry
from backend_app.modules.agent_runs import repository as run_repository
from backend_app.modules.ai_settings import AiSettingsService


class AgentRuntime:
    def __init__(
        self,
        db_path,
        *,
        base_dir=None,
        settings_service=None,
        tool_registry=None,
        adapter_factory=None,
        max_workers=2,
        log=None,
    ):
        self.db_path = Path(db_path)
        self.base_dir = Path(base_dir or self.db_path.parent)
        self.settings_service = settings_service or AiSettingsService(self.db_path)
        self.model_router = ModelRouter(self.db_path, self.settings_service)
        self.tool_registry = tool_registry or ToolRegistry()
        self.adapter_factory = adapter_factory or self._default_adapter_factory
        self.structured_strategy = StructuredExecutionStrategy()
        self.tool_strategy = ToolLoopExecutionStrategy()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sunbird-agent")
        self.cancel_flags = {}
        self.lock = threading.Lock()
        self.log = log
        run_repository.mark_unfinished_interrupted(self.db_path)

    def _default_adapter_factory(self, route):
        if route.provider["provider_type"] == "codex_cli":
            return CodexCliProviderAdapter(
                route.provider,
                route.model_profile,
                self.base_dir,
                log=self.log,
            )
        return OpenAICompatibleProviderAdapter(
            route.provider, route.model_profile, route.api_key
        )

    @staticmethod
    def _can_fallback(exc):
        return isinstance(exc, (ProviderUnavailableError, ProviderRateLimitError))

    def _execute_with_route(self, agent_key, input_payload, *, model_profile_id=None, event=None, cancelled=None):
        self.settings_service.ensure_default_agent_profiles()
        route = self.model_router.resolve(agent_key, model_profile_id=model_profile_id)
        try:
            return self._execute_route(route, input_payload, event=event, cancelled=cancelled), route
        except Exception as exc:
            if not self._can_fallback(exc) or not route.agent_profile.get("fallback_model_profile_id"):
                raise
            if event:
                event("model_fallback", {"reason": getattr(exc, "code", type(exc).__name__)})
            fallback_route = self.model_router.resolve(agent_key, fallback=True)
            return self._execute_route(fallback_route, input_payload, event=event, cancelled=cancelled), fallback_route

    def _execute_route(self, route, input_payload, *, event=None, cancelled=None):
        adapter = self.adapter_factory(route)
        timeout = route.agent_profile.get("timeout_seconds") or route.provider.get("timeout_seconds")
        if route.agent_profile["execution_mode"] == "structured":
            prompt = str(input_payload.get("prompt") or "")
            schema = input_payload.get("schema") or {}
            return self.structured_strategy.execute(
                adapter,
                prompt,
                schema,
                timeout=timeout,
                event=event,
                cancelled=cancelled,
            )
        capabilities = route.provider.get("capabilities") or {}
        if capabilities.get("tools") is False:
            raise ModelCapabilityError("当前 Provider 未启用工具调用能力")
        return self.tool_strategy.execute(
            adapter,
            str(input_payload.get("prompt") or ""),
            self.tool_registry,
            system_prompt=str(input_payload.get("systemPrompt") or "你是 Sunbird OS 的中文自媒体运营 Agent。只使用提供的工具，不得编造数据。"),
            timeout=timeout,
            max_steps=route.agent_profile.get("max_steps") or 8,
            event=event,
            cancelled=cancelled,
        )

    def run_structured(self, agent_key, prompt, schema, *, model_profile_id=None):
        result, _route = self._execute_with_route(
            agent_key,
            {"prompt": prompt, "schema": schema},
            model_profile_id=model_profile_id,
        )
        return result

    def submit(self, agent_key, input_payload):
        run = run_repository.create_run(self.db_path, agent_key, input_payload)
        flag = threading.Event()
        with self.lock:
            self.cancel_flags[run["id"]] = flag
        self.executor.submit(self._run_background, run["id"], agent_key, input_payload, flag)
        return run

    def _run_background(self, run_id, agent_key, input_payload, flag):
        from backend_app.common.tool_gateway import ToolExecutionContext, execution_context
        context_token = execution_context.set(ToolExecutionContext(source="agent", run_id=run_id))
        def event(event_type, payload=None):
            run_repository.append_event(self.db_path, run_id, event_type, payload)

        try:
            if flag.is_set():
                raise AgentCancelledError("Agent 任务已取消")
            run_repository.update_run(self.db_path, run_id, "running")
            event("run_started", {"agentKey": agent_key})
            result, route = self._execute_with_route(
                agent_key,
                input_payload,
                event=event,
                cancelled=flag.is_set,
            )
            event("run_succeeded", {"modelProfileId": route.model_profile["id"]})
            run_repository.update_run(
                self.db_path,
                run_id,
                "succeeded",
                output=result,
                model_profile_id=route.model_profile["id"],
            )
        except AgentCancelledError as exc:
            event("run_cancelled", {})
            run_repository.update_run(
                self.db_path,
                run_id,
                "cancelled",
                error_code=exc.code,
                error_message=str(exc),
            )
        except Exception as exc:
            code = exc.code if isinstance(exc, AgentRuntimeError) else "agent_execution_failed"
            event("run_failed", {"errorCode": code})
            run_repository.update_run(
                self.db_path,
                run_id,
                "failed",
                error_code=code,
                error_message=str(exc),
            )
            if self.log:
                self.log(f"Agent run failed: run={run_id} agent={agent_key} code={code} error={exc}")
        finally:
            execution_context.reset(context_token)
            with self.lock:
                self.cancel_flags.pop(run_id, None)

    def get_run(self, run_id):
        return run_repository.get_run(self.db_path, run_id)

    def get_events(self, run_id):
        return run_repository.list_events(self.db_path, run_id)

    def cancel(self, run_id):
        with self.lock:
            flag = self.cancel_flags.get(run_id)
        if flag:
            flag.set()
        return run_repository.request_cancel(self.db_path, run_id)

    def shutdown(self, wait=True):
        self.executor.shutdown(wait=wait, cancel_futures=True)
