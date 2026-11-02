"""Keep browser contexts on one event loop across HTTP requests and worker threads."""
import asyncio
import atexit
import functools
import threading
from contextlib import asynccontextmanager
from dataclasses import replace


class BrowserWorker:
    def __init__(self):
        self._lock = threading.Lock()
        self.loop = None

    def submit(self, coroutine):
        with self._lock:
            if self.loop is None:
                self.loop = asyncio.new_event_loop()
                threading.Thread(target=self.loop.run_forever, daemon=True,
                                 name="shared-browser").start()
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    async def run(self, coroutine):
        if asyncio.get_running_loop() is self.loop:
            return await coroutine
        return await asyncio.wrap_future(self.submit(coroutine))


worker = BrowserWorker()


def on_browser_worker(function):
    @functools.wraps(function)
    async def wrapped(*args, **kwargs):
        return await worker.run(function(*args, **kwargs))
    return wrapped


class SharedContexts:
    def __init__(self):
        self.entries = {}
        self.locks = {}

    async def get(self, engine, spec):
        key = spec.shared_key
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self.entries.get(key)
            if entry and not entry[2]["closed"]:
                return entry[1]
            if entry:
                await entry[0].__aexit__(None, None, None)
                self.entries.pop(key, None)
            # Retain the session owner; individual tasks only own their own page.
            owner = engine.session(replace(spec, shared_key=None))
            context, _ = await owner.__aenter__()
            state = {"closed": False}
            context.on("close", lambda *_: state.update(closed=True))
            self.entries[key] = (owner, context, state)
            return context

    @asynccontextmanager
    async def session(self, engine, spec):
        if asyncio.get_running_loop() is not worker.loop:
            raise RuntimeError("Shared browser operations must run on the browser worker")
        context = await self.get(engine, spec)
        page = await context.new_page()
        try:
            yield context, page
        finally:
            if not page.is_closed():
                await page.close()

    async def close(self):
        entries, self.entries = list(self.entries.values()), {}
        for owner, _, _ in entries:
            try:
                await owner.__aexit__(None, None, None)
            except Exception:
                pass
        self.locks.clear()


shared_contexts = SharedContexts()


def shutdown():
    if worker.loop is not None and worker.loop.is_running():
        try:
            worker.submit(shared_contexts.close()).result(timeout=5)
        except Exception:
            pass
        worker.loop.call_soon_threadsafe(worker.loop.stop)


atexit.register(shutdown)
