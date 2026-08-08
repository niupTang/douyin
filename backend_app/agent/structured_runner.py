import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .gateway_client import get_hermes_settings, hermes_request
from .model_registry import get_task_agent_model


def load_json_object(text):
    if not text:
        raise ValueError("empty response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


def resolve_executable(command, label, settings_path=None):
    if not command:
        raise RuntimeError(f"{label} 未配置")
    command = os.path.expandvars(os.path.expanduser(str(command).strip().strip('"')))
    if not command:
        raise RuntimeError(f"{label} 未配置")
    if any(sep in command for sep in (os.sep, "/", "\\")):
        path = Path(command)
        if not path.exists():
            suffix = f"。请在 {settings_path} 中配置正确路径。" if settings_path else "。"
            raise RuntimeError(f"{label} 不存在：{command}{suffix}")
        return str(path)
    found = shutil.which(command)
    if not found:
        suffix = f"，或在 {settings_path} 中配置路径" if settings_path else ""
        raise RuntimeError(f"找不到 {label}：{command}。请安装它{suffix}。")
    return found


def run_codex_cli_structured(prompt, schema, *, base_dir, codex_cmd, codex_model, timeout=180, log=None):
    resolved_cmd = resolve_executable(codex_cmd, "Codex CLI", Path(base_dir) / "settings.json")
    if log:
        log(f"codex structured path: {resolved_cmd} (configured={codex_cmd})")
    with tempfile.TemporaryDirectory(prefix="agent-codex-") as tmp_dir:
        schema_path = Path(tmp_dir) / "schema.json"
        output_path = Path(tmp_dir) / "result.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
        command = [
            resolved_cmd, "exec", "--model", codex_model,
            "--sandbox", "read-only", "--ephemeral", "--ignore-rules", "--cd", str(base_dir),
            "--output-schema", str(schema_path), "--output-last-message", str(output_path), "-",
        ]
        completed = subprocess.run(
            command, input=prompt, cwd=str(base_dir), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "Codex 分析失败")[-2000:])
        output_text = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        return load_json_object(output_text)


def call_hermes_structured(prompt, schema, *, settings, model_config=None, task_name="viralAnalysis", timeout=None, log=None):
    model_config = model_config or get_task_agent_model(task_name, settings=settings)
    model_options = {}
    if model_config.get("reasoningEffort"):
        model_options["reasoning_effort"] = model_config["reasoningEffort"]
    if model_config.get("serviceTier"):
        model_options["service_tier"] = model_config["serviceTier"]
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
    payload = {
        "model": model_config.get("model"),
        "stream": False,
        "messages": messages,
    }
    if model_config.get("provider") != "gateway-default":
        payload["provider"] = model_config.get("provider")
    if model_options:
        payload["model_options"] = model_options
    if log:
        log(f"hermes structured model: provider={model_config.get('provider')} model={model_config.get('model')}")
    last_error = None
    for _ in range(2):
        content = ""
        try:
            response = hermes_request(
                "/v1/chat/completions", method="POST", payload=payload,
                timeout=timeout or get_hermes_settings(settings)["timeout"], settings=settings,
            )
            choices = response.get("choices") if isinstance(response, dict) else None
            content = choices[0].get("message", {}).get("content") if choices else ""
            if not content:
                raise RuntimeError("Hermes Gateway 未返回分析内容")
            return load_json_object(content)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            messages.extend([
                {"role": "assistant", "content": str(content)[-6000:]},
                {"role": "user", "content": "上一次输出不是合法 JSON，请修正并只返回符合 Schema 的 JSON 对象。"},
            ])
        except Exception as exc:
            last_error = exc
            break
    raise RuntimeError(f"Hermes 结构化分析失败：{last_error}")
