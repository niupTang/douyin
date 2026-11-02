import sqlite3
from queue import Queue

from backend_app.common.database import ensure_core_tables
from backend_app.modules.accounts import repository
from backend_app.modules.accounts.login_service import sse_stream


def test_account_schema_and_list_support_stable_platform_identity(tmp_path):
    db_path = tmp_path / "accounts.db"
    ensure_core_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(user_info)").fetchall()
        }
        assert {
            "platform_user_id",
            "display_name",
            "remark_name",
            "last_validated_at",
            "last_error_code",
            "created_at",
            "updated_at",
        }.issubset(columns)
        conn.execute(
            """
            INSERT INTO user_info
                (type, filePath, userName, status, platform_user_id,
                 display_name, remark_name)
            VALUES (3, 'douyin.json', '旧名称', 1, 'douyin-42', '真实昵称', '工作号')
            """
        )

    assert repository.list_accounts(db_path) == [
        {
            "id": 1,
            "type": 3,
            "filePath": "douyin.json",
            "userName": "旧名称",
            "status": 1,
            "follower_count": 0,
            "platform_user_id": "douyin-42",
            "display_name": "真实昵称",
            "remark_name": "工作号",
            "name": "工作号",
            "last_validated_at": None,
            "last_error_code": None,
            "created_at": repository.list_accounts(db_path)[0]["created_at"],
            "updated_at": repository.list_accounts(db_path)[0]["updated_at"],
        }
    ]


def test_platform_identity_is_unique_per_platform(tmp_path):
    db_path = tmp_path / "accounts.db"
    ensure_core_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO user_info (type, filePath, userName, platform_user_id) VALUES (3, 'a.json', 'A', 'same')"
        )
        try:
            conn.execute(
                "INSERT INTO user_info (type, filePath, userName, platform_user_id) VALUES (3, 'b.json', 'B', 'same')"
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("duplicate platform identity should be rejected")


def test_account_binding_login_is_public_without_token(monkeypatch):
    import sau_backend

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args

        def start(self):
            self.args[2].put("500")

    monkeypatch.setattr(sau_backend.threading, "Thread", ImmediateThread)

    response = sau_backend.app.test_client().get(
        "/login?type=3&id=test&loginSessionId=session-1"
    )

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"


def test_sse_stream_always_cleans_up_login_session():
    queue = Queue()
    queue.put("200")
    cleaned = []

    assert list(sse_stream(queue, on_close=lambda: cleaned.append(True))) == [
        "data: 200\n\n"
    ]
    assert cleaned == [True]


def test_douyin_binding_is_idempotent_and_relogin_rejects_other_identity(tmp_path):
    db_path = tmp_path / "accounts.db"
    ensure_core_tables(db_path)

    first = repository.bind_douyin_account(
        db_path,
        cookie_filename="first.json",
        platform_user_id="douyin-42",
        display_name="真实昵称",
        remark_name="工作号",
    )
    repeated = repository.bind_douyin_account(
        db_path,
        cookie_filename="second.json",
        platform_user_id="douyin-42",
        display_name="新昵称",
        remark_name="新备注",
    )

    assert repeated["account"]["id"] == first["account"]["id"]
    assert repeated["replaced_cookie"] == "first.json"
    assert len(repository.list_accounts(db_path)) == 1

    try:
        repository.bind_douyin_account(
            db_path,
            cookie_filename="wrong.json",
            platform_user_id="douyin-99",
            display_name="其他账号",
            remark_name="工作号",
            existing_account_id=first["account"]["id"],
        )
    except repository.AccountIdentityMismatch:
        pass
    else:
        raise AssertionError("relogin with another identity should be rejected")

    account = repository.list_accounts(db_path)[0]
    assert account["filePath"] == "second.json"
    assert account["platform_user_id"] == "douyin-42"
