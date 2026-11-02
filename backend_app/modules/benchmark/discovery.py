"""Persist candidate previews separately; only confirmed candidates enter the library."""
import asyncio
import json
from backend_app.common import sqlite as sqlite3
import threading
import uuid
from contextlib import contextmanager

from myUtils.douyin_benchmark import (
    normalize_douyin_user_url, discover_douyin_benchmark_accounts, scrape_douyin_benchmark,
)
from . import repository


@contextmanager
def connect(db_path):
    connection = sqlite3.connect(db_path, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def create_candidate_discovery(get_db_path):
    return CandidateDiscovery(get_db_path, discover_douyin_benchmark_accounts, scrape_douyin_benchmark)


class CandidateDiscovery:
    def __init__(self, get_db_path, discover, inspect_account):
        self.get_db_path = get_db_path
        self.discover = discover
        self.inspect_account = inspect_account
        self.lock = threading.Lock()
        self.initialized = False
        self.slots = threading.BoundedSemaphore(2)

    def initialize(self):
        with self.lock:
            if self.initialized:
                return
            repository.ensure_tables(self.get_db_path())
            with connect(self.get_db_path()) as conn:
                conn.executescript('''
                    CREATE TABLE IF NOT EXISTS benchmark_discovery_tasks (
                        id TEXT PRIMARY KEY, keywords_json TEXT NOT NULL,
                        status TEXT NOT NULL, error TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS benchmark_discovery_candidates (
                        id TEXT PRIMARY KEY, task_id TEXT NOT NULL, rank INTEGER NOT NULL,
                        homepage_url TEXT NOT NULL, candidate_json TEXT NOT NULL,
                        profile_json TEXT, status TEXT NOT NULL, error TEXT,
                        account_id INTEGER, UNIQUE(task_id, homepage_url)
                    );
                ''')
                conn.execute("UPDATE benchmark_discovery_tasks SET status='interrupted', error='服务已重启，请重新搜索' WHERE status IN ('queued','running')")
                conn.execute("UPDATE benchmark_discovery_candidates SET status='failed', error='服务已重启，请重新搜索' WHERE status='pending'")
            self.initialized = True

    def start(self, keywords, limit, max_videos, cookie_file):
        self.initialize()
        if not self.slots.acquire(blocking=False):
            raise ValueError("已有两个找对标任务正在执行，请稍后重试")
        task_id = uuid.uuid4().hex
        try:
            with connect(self.get_db_path()) as conn:
                conn.execute("INSERT INTO benchmark_discovery_tasks(id,keywords_json,status) VALUES (?,?,'queued')",
                             (task_id, json.dumps(keywords, ensure_ascii=False)))
            threading.Thread(target=self._run, args=(task_id, keywords, limit, max_videos, cookie_file),
                             daemon=True, name="benchmark-discovery").start()
        except BaseException:
            self.slots.release()
            raise
        return self.get(task_id)

    def _run(self, task_id, keywords, limit, max_videos, cookie_file):
        try:
            self._update_task(task_id, 'running')
            candidates = asyncio.run(self.discover(keywords, cookie_file=cookie_file, limit=limit))
            if not candidates:
                raise ValueError('未找到候选账号，请检查关键词或先完成抖音登录与验证')
            queued = []
            seen = set()
            for candidate in candidates[:limit]:
                url = normalize_douyin_user_url(candidate.get('homepage_url'))
                if not url or url in seen:
                    continue
                seen.add(url)
                candidate_id = uuid.uuid4().hex
                with connect(self.get_db_path()) as conn:
                    conn.execute('''INSERT INTO benchmark_discovery_candidates
                        (id,task_id,rank,homepage_url,candidate_json,status) VALUES (?,?,?,?,?,'pending')''',
                        (candidate_id, task_id, len(queued), url, json.dumps(candidate, ensure_ascii=False)))
                queued.append((candidate_id, url))
            for candidate_id, url in queued:
                try:
                    profile = asyncio.run(self.inspect_account(url, cookie_file=cookie_file, max_videos=max_videos))
                    if not profile.get('videos'):
                        raise ValueError('未读取到作品，可能需要登录或验证；请查看主页后重新搜索')
                    with connect(self.get_db_path()) as conn:
                        conn.execute("UPDATE benchmark_discovery_candidates SET profile_json=?,status='ready' WHERE id=?",
                                     (json.dumps(profile, ensure_ascii=False), candidate_id))
                except Exception as exc:
                    with connect(self.get_db_path()) as conn:
                        conn.execute("UPDATE benchmark_discovery_candidates SET status='failed',error=? WHERE id=?",
                                     (str(exc), candidate_id))
            self._update_task(task_id, 'completed')
        except Exception as exc:
            self._update_task(task_id, 'failed', str(exc))
        finally:
            self.slots.release()

    def _update_task(self, task_id, status, error=None):
        with connect(self.get_db_path()) as conn:
            conn.execute('''UPDATE benchmark_discovery_tasks SET status=?,error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                         (status, error, task_id))

    def get(self, task_id):
        self.initialize()
        with connect(self.get_db_path()) as conn:
            row = conn.execute('SELECT * FROM benchmark_discovery_tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result['keywords'] = json.loads(result.pop('keywords_json'))
            candidates = conn.execute('SELECT * FROM benchmark_discovery_candidates WHERE task_id=? ORDER BY rank', (task_id,)).fetchall()
            result['candidates'] = []
            for row in candidates:
                item = dict(row)
                candidate = json.loads(item.pop('candidate_json'))
                profile = json.loads(item.pop('profile_json') or '{}')
                item.update({key: profile.get(key) or candidate.get(key) or ''
                             for key in ('nickname', 'avatar', 'bio', 'followers_count', 'video_count', 'source_keyword')})
                item['videos'] = profile.get('videos') or []
                item['already_in_library'] = conn.execute('SELECT 1 FROM douyin_benchmark_accounts WHERE homepage_url=?',
                                                         (item['homepage_url'],)).fetchone() is not None
                result['candidates'].append(item)
            result['summary'] = {
                'found': len(candidates),
                'ready': sum(c['status'] in ('ready', 'imported') for c in result['candidates']),
                'failed': sum(c['status'] == 'failed' for c in result['candidates']),
                'imported': sum(c['status'] == 'imported' for c in result['candidates']),
            }
            return result

    def import_candidate(self, task_id, candidate_id):
        self.initialize()
        # One transaction commits the account, works and candidate status together.
        with connect(self.get_db_path()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM benchmark_discovery_candidates WHERE id=? AND task_id=?',
                               (candidate_id, task_id)).fetchone()
            if row is None:
                raise LookupError('候选账号不存在')
            if row['status'] == 'imported' and conn.execute(
                    'SELECT 1 FROM douyin_benchmark_accounts WHERE id=?', (row['account_id'],)).fetchone():
                return {'id': row['account_id'], 'alreadyImported': True}
            if row['status'] not in ('ready', 'imported'):
                raise ValueError('候选账号作品尚未读取成功，不能入库')
            profile = json.loads(row['profile_json'])
            account_id = repository.upsert_account(self.get_db_path(), row['homepage_url'], normalize_douyin_user_url, connection=conn)
            stats = repository.save_sync(self.get_db_path(), account_id, profile, connection=conn)
            conn.execute("UPDATE benchmark_discovery_candidates SET status='imported',account_id=? WHERE id=?",
                         (account_id, candidate_id))
        return {'id': account_id, 'sync': stats, 'alreadyImported': False}
