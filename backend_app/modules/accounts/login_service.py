import asyncio
import time


def run_login_task(platform_type, account_id, status_queue, *, login_handlers, log=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        if log:
            log(f"account login started type={platform_type} id={account_id}")
        handler = login_handlers.get(str(platform_type))
        if not handler:
            raise ValueError(f"Unsupported login type: {platform_type}")
        loop.run_until_complete(handler(account_id, status_queue))
        if log:
            log(f"account login finished type={platform_type} id={account_id}")
    except Exception as exc:
        if log:
            log(f"account login failed type={platform_type} id={account_id}: {repr(exc)}")
        status_queue.put(f"ERROR:{exc}")
        status_queue.put("500")
    finally:
        loop.close()


def sse_stream(status_queue, *, timeout_seconds=240, idle_sleep=0.1, log=None):
    started_at = time.time()
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
            if msg in ("200", "500") or str(msg).startswith("ERROR:"):
                break
        elif time.time() - started_at > timeout_seconds:
            if log:
                log("SSE account login timeout")
            yield "data: 500\n\n"
            break
        else:
            time.sleep(idle_sleep)
