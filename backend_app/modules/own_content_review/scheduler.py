import threading
import time
from datetime import datetime


class WeeklyExportScheduler:
    def __init__(self, run_export, interval_seconds=60):
        self.run_export = run_export
        self.interval_seconds = interval_seconds
        self._started = False
        self._lock = threading.Lock()
        self._last_trigger_date = None

    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
        threading.Thread(target=self._loop, name="douyin-weekly-export", daemon=True).start()

    def _loop(self):
        while True:
            try:
                now = datetime.now()
                # Monday 03:00 local time; one run per calendar week.
                due = now.weekday() == 0 and now.hour == 3
                today = now.strftime("%Y-%m-%d")
                if due and self._last_trigger_date != today:
                    self.run_export()
                    self._last_trigger_date = today
                    time.sleep(3600)
            except Exception:
                time.sleep(self.interval_seconds)
            time.sleep(self.interval_seconds)
