import argparse
import base64
import hashlib
import hmac
import json
import os
import ssl
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import websocket


def assemble_auth_url(host_url, api_key, api_secret):
    parsed = urlparse(host_url)
    date = format_date_time(time.time())
    signature_origin = "\n".join(
        [
            f"host: {parsed.netloc}",
            f"date: {date}",
            f"GET {parsed.path} HTTP/1.1",
        ]
    )
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode(
        {
            "host": parsed.netloc,
            "date": date,
            "authorization": authorization,
        }
    )
    return f"{host_url}?{query}"


def split_text(text, max_chars=650):
    paragraphs = [line.strip() for line in text.replace("\r\n", "\n").split("\n") if line.strip()]
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= max_chars:
            current = f"{current}\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


def synthesize_chunk(text, app_id, api_key, api_secret, host_url, voice):
    ws_url = assemble_auth_url(host_url, api_key, api_secret)
    result = bytearray()
    error = None

    def on_open(ws):
        payload = {
            "common": {"app_id": app_id},
            "business": {
                "aue": "lame",
                "auf": "audio/L16;rate=16000",
                "vcn": voice,
                "speed": 50,
                "volume": 80,
                "pitch": 50,
                "tte": "UTF8",
            },
            "data": {
                "status": 2,
                "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            },
        }
        ws.send(json.dumps(payload, ensure_ascii=False))

    def on_message(ws, message):
        nonlocal error
        data = json.loads(message)
        code = data.get("code", 0)
        if code != 0:
            error = RuntimeError(f"讯飞 TTS 失败: code={code}, message={data.get('message')}")
            ws.close()
            return
        audio = data.get("data", {}).get("audio")
        if audio:
            result.extend(base64.b64decode(audio))
        if data.get("data", {}).get("status") == 2:
            ws.close()

    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    if error:
        raise error
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description="Generate narration with iFlytek/XFYun TTS.")
    parser.add_argument("--text", required=True, help="UTF-8 text file.")
    parser.add_argument("--out", required=True, help="Output MP3 path.")
    parser.add_argument("--voice", default="x4_lingbosong", help="XFYun voice name, default x4_lingbosong.")
    parser.add_argument("--host-url", default="wss://tts-api.xfyun.cn/v2/tts")
    args = parser.parse_args()

    app_id = os.environ.get("XFYUN_APPID")
    api_key = os.environ.get("XFYUN_API_KEY")
    api_secret = os.environ.get("XFYUN_API_SECRET")
    missing = [name for name, value in {
        "XFYUN_APPID": app_id,
        "XFYUN_API_KEY": api_key,
        "XFYUN_API_SECRET": api_secret,
    }.items() if not value]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

    text = Path(args.text).read_text(encoding="utf-8").strip()
    chunks = split_text(text)
    audio = bytearray()
    for index, chunk in enumerate(chunks, start=1):
        print(f"Synthesizing chunk {index}/{len(chunks)}...")
        audio.extend(synthesize_chunk(chunk, app_id, api_key, api_secret, args.host_url, args.voice))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(audio)
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
