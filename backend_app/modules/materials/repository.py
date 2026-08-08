import sqlite3


def add_file_record(db_path, filename, filesize, file_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO file_records (filename, filesize, file_path)
        VALUES (?, ?, ?)
        """, (filename, filesize, file_path))
        conn.commit()
        return cursor.lastrowid


def list_file_records(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM file_records").fetchall()
    return [dict(row) for row in rows]


def get_file_record(db_path, file_id):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM file_records WHERE id = ?",
            (file_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_file_record(db_path, file_id):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM file_records WHERE id = ?",
            (file_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM file_records WHERE id = ?", (file_id,))
        conn.commit()
    return dict(row)
