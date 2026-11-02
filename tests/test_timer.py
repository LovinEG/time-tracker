import sqlite3

import pytest

from app.db import get_connection
from tests.conftest import create_employee, start, stop


def test_timer_duration_matches_fake_clock(client, clock):
    employee = create_employee(client, "Иван Петров")

    started = start(client, employee["id"], "Подготовить отчёт")
    clock.advance(90)
    stopped = stop(client, employee["id"])
    entries = client.get("/api/entries").json()

    assert started["started_at"] == "2026-11-02T09:00:00Z"
    assert stopped["ended_at"] == "2026-11-02T09:01:30Z"
    assert entries[0]["duration_seconds"] == 90
    assert entries[0]["is_running"] is False


def test_repeated_start_conflicts_and_leaves_one_running_entry(client, clock):
    employee = create_employee(client, "Иван Петров")
    start(client, employee["id"], "Первая задача")

    response = client.post(
        f"/api/employees/{employee['id']}/timer/start",
        json={"description": "Вторая задача"},
    )
    connection = get_connection()
    try:
        count = connection.execute(
            "SELECT count(*) FROM time_entries WHERE employee_id = ? AND ended_at IS NULL",
            (employee["id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert response.status_code == 409
    assert response.json()["detail"] == "Timer is already running"
    assert count == 1


def test_timer_can_restart_after_stopping(client, clock):
    employee = create_employee(client, "Иван Петров")
    first = start(client, employee["id"], "Первая задача")
    stop(client, employee["id"])

    second = start(client, employee["id"], "Вторая задача")
    entries = client.get("/api/entries").json()

    assert second["id"] != first["id"]
    assert len(entries) == 2
    assert sum(entry["is_running"] for entry in entries) == 1


def test_stop_without_running_timer_and_stop_twice_conflict(client, clock):
    employee = create_employee(client, "Иван Петров")

    no_timer = client.post(f"/api/employees/{employee['id']}/timer/stop")
    start(client, employee["id"], "Задача")
    stop(client, employee["id"])
    second_stop = client.post(f"/api/employees/{employee['id']}/timer/stop")

    assert no_timer.status_code == 409
    assert no_timer.json()["detail"] == "No running timer"
    assert second_stop.status_code == 409
    assert second_stop.json()["detail"] == "No running timer"


def test_unknown_employee_and_empty_description_are_rejected(client, clock):
    unknown_start = client.post(
        "/api/employees/999/timer/start", json={"description": "Задача"}
    )
    unknown_stop = client.post("/api/employees/999/timer/stop")
    employee = create_employee(client, "Иван Петров")
    empty_description = client.post(
        f"/api/employees/{employee['id']}/timer/start",
        json={"description": "   "},
    )

    assert unknown_start.status_code == 404
    assert unknown_stop.status_code == 404
    assert empty_description.status_code == 422
    assert empty_description.json()["detail"] == "Description must not be empty"


def test_two_employees_can_run_timers_independently(client, clock):
    ivan = create_employee(client, "Иван Петров")
    anna = create_employee(client, "Анна Смирнова")

    start(client, ivan["id"], "Задача Ивана")
    start(client, anna["id"], "Задача Анны")

    entries = client.get("/api/entries").json()
    assert len(entries) == 2
    assert all(entry["is_running"] for entry in entries)


def test_partial_unique_index_rejects_second_running_entry(client, clock):
    employee = create_employee(client, "Иван Петров")
    start(client, employee["id"], "Первая задача")
    connection = get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO time_entries
                    (employee_id, description, started_at, ended_at)
                VALUES (?, ?, ?, NULL)
                """,
                (employee["id"], "Вторая задача", "2026-11-02T09:00:00+00:00"),
            )
    finally:
        connection.close()
