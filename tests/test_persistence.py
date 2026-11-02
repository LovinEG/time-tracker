from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import create_employee, start, stop


def test_employee_and_finished_entry_survive_new_client(db_path, clock):
    with TestClient(app) as first_client:
        employee = create_employee(first_client, "Иван Петров")
        start(first_client, employee["id"], "Сохранённая задача")
        clock.advance(60)
        stop(first_client, employee["id"])

    with TestClient(app) as second_client:
        employees = second_client.get("/api/employees").json()
        entries = second_client.get("/api/entries").json()

    assert employees[0]["name"] == "Иван Петров"
    assert entries[0]["description"] == "Сохранённая задача"
    assert entries[0]["duration_seconds"] == 60
