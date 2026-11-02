from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import main
from app.db import get_connection
from app.seed import seed_demo_data


def test_seed_populates_empty_database_with_oleg_without_entries(client, clock):
    connection = get_connection()
    try:
        seed_demo_data(connection)
        employee_count = connection.execute(
            "SELECT count(*) FROM employees"
        ).fetchone()[0]
        entries_by_name = dict(
            connection.execute(
                """
                SELECT employees.name, count(time_entries.id)
                FROM employees
                LEFT JOIN time_entries ON time_entries.employee_id = employees.id
                GROUP BY employees.id
                """
            ).fetchall()
        )
    finally:
        connection.close()

    assert employee_count == 3
    assert entries_by_name["Олег Кузнецов"] == 0
    assert 6 <= sum(entries_by_name.values()) <= 8


def test_seed_has_one_running_ivan_timer_and_recent_finished_entries(client, clock):
    connection = get_connection()
    try:
        seed_demo_data(connection)
        running = connection.execute(
            """
            SELECT employees.name, count(time_entries.id) AS running_count
            FROM employees
            JOIN time_entries ON time_entries.employee_id = employees.id
            WHERE time_entries.ended_at IS NULL
            GROUP BY employees.id
            """
        ).fetchall()
        finished_starts = [
            datetime.fromisoformat(row[0])
            for row in connection.execute(
                "SELECT started_at FROM time_entries WHERE ended_at IS NOT NULL"
            ).fetchall()
        ]
    finally:
        connection.close()

    lower_bound = clock.now() - timedelta(days=7)
    assert [(row["name"], row["running_count"]) for row in running] == [
        ("Иван Петров", 1)
    ]
    assert all(
        lower_bound <= started_at <= clock.now() for started_at in finished_starts
    )


def test_seed_is_idempotent_and_does_nothing_with_existing_employee(client, clock):
    connection = get_connection()
    try:
        seed_demo_data(connection)
        initial_counts = (
            connection.execute("SELECT count(*) FROM employees").fetchone()[0],
            connection.execute("SELECT count(*) FROM time_entries").fetchone()[0],
        )
        seed_demo_data(connection)
        repeated_counts = (
            connection.execute("SELECT count(*) FROM employees").fetchone()[0],
            connection.execute("SELECT count(*) FROM time_entries").fetchone()[0],
        )
        connection.execute("DELETE FROM time_entries")
        connection.execute("DELETE FROM employees")
        connection.execute(
            """
            INSERT INTO employees (name, name_key, created_at)
            VALUES (?, ?, ?)
            """,
            ("Existing employee", "existing employee", "2026-11-02T09:00:00+00:00"),
        )
        connection.commit()
        before = (
            connection.execute("SELECT count(*) FROM employees").fetchone()[0],
            connection.execute("SELECT count(*) FROM time_entries").fetchone()[0],
        )
        seed_demo_data(connection)
        after = (
            connection.execute("SELECT count(*) FROM employees").fetchone()[0],
            connection.execute("SELECT count(*) FROM time_entries").fetchone()[0],
        )
    finally:
        connection.close()

    assert repeated_counts == initial_counts
    assert after == before


def test_app_start_without_demo_mode_keeps_database_empty(
    db_path, monkeypatch, clock
):
    monkeypatch.delenv("DEMO_MODE", raising=False)

    with TestClient(main.app) as client:
        assert client.get("/api/employees").json() == []


def test_api_config_reports_demo_mode_from_environment(
    db_path, monkeypatch, clock
):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    with TestClient(main.app) as client:
        assert client.get("/api/config").json() == {"demo_mode": False}

    monkeypatch.setenv("DEMO_MODE", "1")
    with TestClient(main.app) as client:
        assert client.get("/api/config").json() == {"demo_mode": True}
