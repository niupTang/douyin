"""Offline SQLCipher migration. Stop the app before running this command."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import socket

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend_app.common.database_encryption import encrypt_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default=str(Path(__file__).resolve().parents[1] / 'db' / 'database.db'))
    args = parser.parse_args()
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(('127.0.0.1', int(os.environ.get('SAU_BACKEND_PORT', '5409')))) == 0:
            raise SystemExit('后端仍在运行，请先退出 Sunbird OS 并停止数据库使用进程后再迁移')
    password = os.environ.get('SAU_DATABASE_PASSWORD') or getpass.getpass('数据库加密密码：')
    print(json.dumps(encrypt_database(args.database, password), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
