from contextlib import closing
import os
import sqlite3
from pathlib import Path


def _db_path() -> Path:
    configured_path = os.environ.get("TIME_TRACKER_DB")
    if configured_path:
        return Path(configured_path)
    return Path(__file__).resolve().parent.parent / "data" / "time_tracker.db"


def get_connection() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with closing(get_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                description TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_time_entries_one_running_per_employee
            ON time_entries(employee_id)
            WHERE ended_at IS NULL;
            """
        )
