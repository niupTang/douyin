"""Command-line client for the local Sunbird MCP HTTP service."""

import argparse
import json
import os
import platform
import socket
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


def request_json(base_url, path, method="GET", payload=None, token=None, instance_token=None):
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if instance_token:
        headers["X-SAU-Instance-Token"] = instance_token
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=1800) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = str(exc)
        raise SystemExit(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise SystemExit(f"无法连接后端 {base_url}：{exc.reason}") from exc


def config_path():
    root = Path(os.environ.get("APPDATA") or Path.home()) / "Sunbird MCP"
    root.mkdir(parents=True, exist_ok=True)
    return root / "config.json"


def load_config():
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config):
    config_path().write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def login(args):
    config = load_config()
    device_id = config.get("device_id") or f"dev_{uuid.uuid4().hex}"
    response = request_json(
        args.cloud_url,
        "/api/desktop/license/activate",
        "POST",
        {
            "code": args.code,
            "deviceId": device_id,
            "deviceName": socket.gethostname(),
            "platform": platform.system().lower(),
            "appId": "sunbird-mcp-cli",
            "appVersion": "0.1.0",
        },
    )
    if response.get("code") not in (0, 200):
        raise SystemExit(response.get("message") or response.get("msg") or "桌面许可证激活失败")
    data = response.get("data") or {}
    config.update({
        "device_id": device_id,
        "refresh_token": data["refreshToken"],
        "license": data["license"],
    })

    # The local backend signs the short-lived Bearer token after verifying the
    # cloud-issued license envelope. SAU_INSTANCE_TOKEN must match the token
    # used when the standalone backend was started.
    instance_token = os.environ.get("SAU_INSTANCE_TOKEN")
    if instance_token:
        installed_response = request_json(
            args.url,
            "/runtime/license/install",
            "POST",
            {"license": data["license"], "deviceId": device_id},
            token=None,
            instance_token=instance_token,
        )
        config["token"] = (installed_response.get("data") or {}).get("token")
    save_config(config)
    print(json.dumps({"ok": True, "device_id": device_id, "config": str(config_path())}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Sunbird 本地 MCP CLI")
    parser.add_argument("--url", default="http://127.0.0.1:5409", help="后端地址")
    parser.add_argument("--token", default=None, help="许可证登录令牌，也可使用 SAU_TOKEN 环境变量")
    parser.add_argument("--cloud-url", default=os.environ.get("SAU_LICENSE_API_BASE", "https://yichushiwu.club/watermark-api"), help="桌面许可证云端地址")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="列出 MCP 工具")
    login_parser = subparsers.add_parser("login", help="使用桌面许可证登录")
    login_parser.add_argument("--code", required=True, help="桌面程序卡密")
    invoke = subparsers.add_parser("invoke", help="调用 MCP 工具")
    invoke.add_argument("name", help="工具名称")
    invoke.add_argument("--args", default="{}", help="JSON 参数对象")
    invoke.add_argument("--args-file", help="从 UTF-8 JSON 文件读取参数")

    args = parser.parse_args()
    if args.command == "login":
        login(args)
        return
    saved_token = load_config().get("token")
    auth_token = args.token or os.environ.get("SAU_TOKEN") or saved_token
    if not auth_token:
        raise SystemExit("未找到访问令牌。请先启动并激活 Sunbird 桌面程序，或设置 SAU_TOKEN。")
    if args.command == "list":
        result = request_json(args.url, "/mcp/tools", token=auth_token)
    else:
        if args.args_file:
            with open(args.args_file, "r", encoding="utf-8") as handle:
                arguments = json.load(handle)
        else:
            try:
                arguments = json.loads(args.args)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"--args 不是有效 JSON：{exc}") from exc
        if not isinstance(arguments, dict):
            raise SystemExit("--args 必须是 JSON 对象")
        result = request_json(
            args.url,
            "/mcp/invoke",
            "POST",
            {"name": args.name, "arguments": arguments},
            token=auth_token,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
