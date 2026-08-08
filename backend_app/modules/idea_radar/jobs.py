import threading


class IdeaRadarJobRegistry:
    def __init__(self):
        self._active = set()
        self._cancelled = set()
        self._lock = threading.Lock()

    def cancel_many(self, video_ids):
        with self._lock:
            active_video_ids = {video_id for video_id in video_ids if video_id in self._active}
            self._cancelled.update(active_video_ids)
            return active_video_ids

    def uncancel_many(self, video_ids):
        with self._lock:
            self._cancelled.difference_update(video_ids)

    def ensure_not_cancelled(self, video_id):
        with self._lock:
            if video_id in self._cancelled:
                raise RuntimeError("观点雷达任务已取消")

    def is_cancelled(self, video_id):
        with self._lock:
            return video_id in self._cancelled

    def start(self, video_id):
        with self._lock:
            if video_id in self._active:
                return False
            self._cancelled.discard(video_id)
            self._active.add(video_id)
            return True

    def finish(self, video_id):
        with self._lock:
            self._active.discard(video_id)
            self._cancelled.discard(video_id)
