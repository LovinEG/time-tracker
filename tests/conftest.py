from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import main, repository
from app.db import get_connection


class FakeClock:
    def __init__(self):
        self.current = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("TIME_TRACKER_DB", str(path))
    return path


@pytest.fixture
def clock(monkeypatch):
    fake_clock = FakeClock()
    monkeypatch.setattr(main, "utc_now", fake_clock.now)
    monkeypatch.setattr(repository, "utc_now", fake_clock.now)
    return fake_clock


@pytest.fixture
def client(db_path):
    with TestClient(main.app) as test_client:
        yield test_client


def create_employee(client: TestClient, name: str) -> dict:
    response = client.post("/api/employees", json={"name": name})
    assert response.status_code == 201
    return response.json()


def start(client: TestClient, employee_id: int, description: str) -> dict:
    response = client.post(
        f"/api/employees/{employee_id}/timer/start",
        json={"description": description},
    )
    assert response.status_code == 201
    return response.json()


def stop(client: TestClient, employee_id: int) -> dict:
    response = client.post(f"/api/employees/{employee_id}/timer/stop")
    assert response.status_code == 200
    return response.json()


def insert_entry(
    employee_id: int,
    started_at: str,
    ended_at: str | None,
    description: str = "Fixture entry",
) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO time_entries (employee_id, description, started_at, ended_at)
            VALUES (?, ?, ?, ?)
            """,
            (employee_id, description, started_at, ended_at),
        )
        connection.commit()
    finally:
        connection.close()
