import json
import sqlite3

import pytest

from backend_app.modules.account_diagnosis import repository, stats


# ---------------------------------------------------------------- stats 纯函数

def test_parse_count():
    assert stats.parse_count("1.2万") == 12000
    assert stats.parse_count("86,000") == 86000
    assert stats.parse_count("3.5w") == 35000
    assert stats.parse_count(86000) == 86000
    assert stats.parse_count("") == 0
    assert stats.parse_count(None) == 0


def test_benchmark_classification_thresholds():
    videos = [
        {"id": 1, "title": "爆款", "like_count": "100000"},
        {"id": 2, "title": "半爆", "like_count": "30000"},
        {"id": 3, "title": "正常", "like_count": "10000"},
        {"id": 4, "title": "低", "like_count": "4000"},
        {"id": 5, "title": "正常2", "like_count": "12000"},
    ]
    account = {"id": 1, "nickname": "x", "followers_count": "1000000"}
    facts = stats.build_benchmark_facts(account, videos)

    assert facts["engagement"]["like_median"] == 12000
    by_title = {row["title"]: row for row in facts["videos"]}
    assert by_title["爆款"]["classification"] == "爆款"
    assert by_title["半爆"]["classification"] == "表现突出（半爆）"
    assert by_title["正常"]["classification"] == "粉丝基数正常发挥"
    assert by_title["低"]["classification"] == "低于自身基线"
    # 点赞率 = 点赞/粉丝
    assert by_title["爆款"]["like_rate"] == 0.1


def test_benchmark_no_followers_still_computes_deviation():
    videos = [
        {"id": 1, "title": "a", "like_count": "1000"},
        {"id": 2, "title": "b", "like_count": "100"},
    ]
    facts = stats.build_benchmark_facts({"followers_count": None}, videos)
    assert facts["engagement"]["like_median"] == 550
    assert facts["videos"][0]["like_rate"] is None  # 无粉丝数时点赞率算不出


def test_own_facts_signals():
    videos = [
        {"id": 1, "title": "高", "play_count": 10000, "two_sec_bounce_rate": 0.2,
         "completion_rate": 0.5, "like_count": 100},
        {"id": 2, "title": "低", "play_count": 100, "two_sec_bounce_rate": 0.6,
         "completion_rate": 0.1, "like_count": 1},
    ]
    facts = stats.build_own_facts(videos, [], account={"userName": "me", "follower_count": "1000"})
    assert facts["own_videos"]["signals"]["play_median"] == 5050.0
    assert facts["own_videos"]["signals"]["has_two_sec"] is True
    assert facts["own_videos"]["signals"]["low_play_count"] == 1
    assert facts["own_videos"]["top_by_play"][0]["title"] == "高"


# ---------------------------------------------------------------- repository 迁移与绑定

@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE user_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT, type INTEGER NOT NULL,
        filePath TEXT NOT NULL, userName TEXT NOT NULL,
        status INTEGER DEFAULT 0, follower_count INTEGER DEFAULT 0
    )''')
    cursor.execute('''
    CREATE TABLE douyin_own_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        source TEXT NOT NULL DEFAULT 'manual_import',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''
    CREATE TABLE publish_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, platform_type INTEGER NOT NULL,
        title TEXT, account_list TEXT, status TEXT NOT NULL,
        views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0, video_url TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''
    CREATE TABLE douyin_benchmark_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, homepage_url TEXT NOT NULL UNIQUE,
        nickname TEXT, followers_count TEXT, last_sync_at DATETIME
    )''')
    cursor.execute('''
    CREATE TABLE douyin_benchmark_videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL,
        video_url TEXT NOT NULL, title TEXT, like_count TEXT,
        comment_count TEXT, share_count TEXT, collect_count TEXT
    )''')
    conn.commit()
    conn.close()
    return path


def test_ensure_tables_adds_columns_and_report_table(db):
    repository.ensure_tables(db)
    conn = sqlite3.connect(db)
    own_cols = {r[1] for r in conn.execute("PRAGMA table_info(douyin_own_accounts)")}
    pub_cols = {r[1] for r in conn.execute("PRAGMA table_info(publish_records)")}
    assert "user_info_id" in own_cols
    assert "user_info_id" in pub_cols
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "diagnosis_reports" in tables
    conn.close()


def test_bind_and_facts_payload(db):
    repository.ensure_tables(db)
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_info (type, filePath, userName, status, follower_count) VALUES (3, 'c1.json', '我的抖音', 1, 5000)")
    user_info_id = cursor.lastrowid
    cursor.execute("INSERT INTO douyin_own_accounts (name) VALUES ('太阳鸟')")
    own_account_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO publish_records (platform_type, title, account_list, status, views) VALUES (3, 't', ?, 'success', 100)",
        (json.dumps(["c1.json"]),),
    )
    conn.commit()
    conn.close()

    repository.bind_own_account(db, own_account_id, user_info_id)
    assert repository.get_bound_own_account(db, user_info_id)["id"] == own_account_id

    # 回填发布记录的 user_info_id
    repository.backfill_publish_user_info(db)
    records = repository.list_publish_records_for_user(db, user_info_id)
    assert len(records) == 1
    assert records[0]["user_info_id"] == user_info_id


def test_backfill_publish_by_filepath(db):
    repository.ensure_tables(db)
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_info (type, filePath, userName, status, follower_count) VALUES (3, 'd.json', '抖音号', 1, 0)")
    user_info_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO publish_records (platform_type, title, account_list, status) VALUES (3, 'x', ?, 'success')",
        (json.dumps(["d.json"]),),
    )
    conn.commit()
    conn.close()
    updated = repository.backfill_publish_user_info(db)
    assert updated == 1
    records = repository.list_publish_records_for_user(db, user_info_id)
    assert len(records) == 1


def test_create_and_get_report(db):
    repository.ensure_tables(db)
    report_id = repository.create_report(db, "benchmark", 1, "success", facts={"a": 1}, report={"summary": "ok"})
    report = repository.get_report(db, report_id)
    assert report["target_type"] == "benchmark"
    assert report["report"]["summary"] == "ok"
    assert report["facts"]["a"] == 1
