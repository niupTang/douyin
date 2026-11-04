import json
import uuid

from backend_app.common.database import connect


def ensure_tables(db_path):
    with connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chat_conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL
                    REFERENCES chat_conversations(id),
                role TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'succeeded',
                run_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
                ON chat_messages(conversation_id, created_at);
        """)


def conversations(db_path):
    with connect(db_path) as conn:
        return [dict(row) for row in conn.execute(
            'SELECT * FROM chat_conversations ORDER BY updated_at DESC, rowid DESC LIMIT 100'
        )]


def create_conversation(db_path):
    item = {'id': uuid.uuid4().hex, 'title': '新对话'}
    with connect(db_path) as conn:
        conn.execute('INSERT INTO chat_conversations(id,title) VALUES (?,?)',
                     (item['id'], item['title']))
    return item


def messages(db_path, conversation_id):
    with connect(db_path) as conn:
        if not conn.execute('SELECT 1 FROM chat_conversations WHERE id=?', (conversation_id,)).fetchone():
            raise LookupError('对话不存在')
        rows = conn.execute(
            'SELECT * FROM chat_messages WHERE conversation_id=? ORDER BY rowid',
            (conversation_id,),
        ).fetchall()
    return [{**dict(row), 'payload': json.loads(row['payload_json'])} for row in rows]


def add_message(db_path, conversation_id, role, content='', *, kind='text',
                status='succeeded', payload=None, message_id=None):
    message_id = message_id or uuid.uuid4().hex
    with connect(db_path) as conn:
        conn.execute('''INSERT INTO chat_messages
            (id, conversation_id, role, kind, content, status, payload_json)
            VALUES (?,?,?,?,?,?,?)''',
            (message_id, conversation_id, role, kind, content, status,
             json.dumps(payload or {}, ensure_ascii=False)))
        conn.execute('UPDATE chat_conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?', (conversation_id,))
        if role == 'user' and kind == 'text':
            conn.execute("UPDATE chat_conversations SET title=? WHERE id=? AND title='新对话'",
                         (content[:40], conversation_id))
    return message_id


def update_message(db_path, message_id, *, status, content, run_id=None):
    with connect(db_path) as conn:
        conn.execute('''UPDATE chat_messages SET status=?, content=?,
            run_id=COALESCE(?,run_id) WHERE id=?''', (status, content, run_id, message_id))
