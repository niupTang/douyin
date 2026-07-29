import json
import time


def register_realtime(app, store):
    try:
        from flask import request
        from flask_sock import Sock
    except ImportError:
        return False

    sock = Sock(app)

    @sock.route("/api/koubo/mobile/stream")
    def mobile_stream(websocket):
        device = store.authenticate(request.args.get("token", ""), "mobile")
        if not device:
            websocket.close(1008, "invalid device token")
            return
        last_signature = None
        try:
            while True:
                projects = store.list_projects()
                project = projects[0] if projects else None
                signature = (
                    (project["id"], project["script_version"], project["updated_at"])
                    if project
                    else None
                )
                if signature != last_signature:
                    websocket.send(
                        json.dumps({"type": "project", "project": project}, ensure_ascii=False)
                    )
                    last_signature = signature
                time.sleep(1)
        except Exception:
            return

    return True
