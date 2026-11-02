"""SQLite-compatible API; databases with encryption metadata use SQLCipher keys."""
from sqlcipher3.dbapi2 import *  # noqa: F403
from backend_app.common.database_encryption import open_database

connect = open_database
