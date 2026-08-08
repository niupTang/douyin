import json
import sqlite3


def _scalar(cursor, sql, params=()):
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return row[0] if row else 0


def get_dashboard_stats(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        account_total = _scalar(cursor, "SELECT COUNT(*) FROM user_info")
        account_normal = _scalar(cursor, "SELECT COUNT(*) FROM user_info WHERE status = 1")
        account_abnormal = account_total - account_normal

        total_views = _scalar(
            cursor,
            "SELECT COALESCE(SUM(views), 0) FROM publish_records WHERE status = 'success'",
        )
        total_likes = _scalar(
            cursor,
            "SELECT COALESCE(SUM(likes), 0) FROM publish_records WHERE status = 'success'",
        )
        publish_success_count = _scalar(
            cursor,
            "SELECT COUNT(*) FROM publish_records WHERE status = 'success'",
        )

        cursor.execute("SELECT type, COUNT(*) AS count FROM user_info GROUP BY type")
        platform_counts = {str(row["type"]): row["count"] for row in cursor.fetchall()}
        active_platform_total = sum(1 for count in platform_counts.values() if count > 0)

        task_total = _scalar(cursor, "SELECT COUNT(*) FROM publish_records")
        publish_success = _scalar(cursor, "SELECT COUNT(*) FROM publish_records WHERE status = 'success'")
        publish_failed = _scalar(cursor, "SELECT COUNT(*) FROM publish_records WHERE status = 'failed'")
        task_in_progress = _scalar(
            cursor,
            "SELECT COUNT(*) FROM publish_records WHERE status NOT IN ('success', 'failed')",
        )

        cursor.execute("SELECT file_path FROM file_records")
        material_files = {row["file_path"] for row in cursor.fetchall() if row["file_path"]}
        cursor.execute("SELECT file_list FROM publish_records WHERE status = 'success'")
        published_files = set()
        for row in cursor.fetchall():
            try:
                published_files.update(json.loads(row["file_list"] or "[]"))
            except Exception:
                continue
        content_total = len(material_files | published_files)
        published_content = len(published_files)
        draft_content = len(material_files - published_files)

        platform_names = {
            1: "小红书",
            2: "视频号",
            3: "抖音",
            4: "快手",
        }
        status_names = {
            "success": "已完成",
            "failed": "已失败",
            "pending": "待执行",
            "running": "进行中",
        }
        recent_tasks = []
        cursor.execute("SELECT filePath, userName FROM user_info")
        account_names = {row["filePath"]: row["userName"] for row in cursor.fetchall()}

        cursor.execute("""
        SELECT id, platform_type, title, status, created_at, account_list
        FROM publish_records
        ORDER BY id DESC
        LIMIT 5
        """)
        for row in cursor.fetchall():
            try:
                accounts = json.loads(row["account_list"] or "[]")
            except Exception:
                accounts = []
            account_label = "、".join(account_names.get(account, account) for account in accounts)
            recent_tasks.append({
                "id": row["id"],
                "title": row["title"] or "未命名发布任务",
                "platform": platform_names.get(row["platform_type"], "未知"),
                "account": account_label if account_label else "-",
                "createTime": row["created_at"],
                "status": status_names.get(row["status"], row["status"]),
            })

    return {
        "accountStats": {
            "total": account_total,
            "normal": account_normal,
            "abnormal": account_abnormal,
        },
        "platformStats": {
            "total": active_platform_total,
            "kuaishou": platform_counts.get("4", 0),
            "douyin": platform_counts.get("3", 0),
            "channels": platform_counts.get("2", 0),
            "xiaohongshu": platform_counts.get("1", 0),
        },
        "taskStats": {
            "total": task_total,
            "completed": publish_success,
            "inProgress": task_in_progress,
            "failed": publish_failed,
        },
        "contentStats": {
            "total": content_total,
            "published": published_content,
            "draft": draft_content,
        },
        "trafficStats": {
            "total_views": total_views,
            "total_likes": total_likes,
            "publish_count": publish_success_count,
        },
        "recentTasks": recent_tasks,
    }
