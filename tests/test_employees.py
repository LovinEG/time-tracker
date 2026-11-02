import pytest

from tests.conftest import create_employee, start


def test_create_employee_trims_name(client, clock):
    response = client.post("/api/employees", json={"name": "  Иван Петров  "})

    assert response.status_code == 201
    assert response.json()["name"] == "Иван Петров"
    assert response.json()["created_at"] == "2026-11-02T09:00:00Z"


@pytest.mark.parametrize("name", ["", "   "])
def test_create_employee_rejects_empty_name(client, name, clock):
    response = client.post("/api/employees", json={"name": name})

    assert response.status_code == 422
    assert response.json()["detail"] == "Name must not be empty"


def test_employee_names_are_unique_case_insensitively_for_cyrillic(client, clock):
    create_employee(client, "Иван Петров")

    response = client.post("/api/employees", json={"name": "иван петров"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Employee already exists"


def test_employee_list_is_ordered_and_includes_running_entry(client, clock):
    ivan = create_employee(client, "Иван Петров")
    anna = create_employee(client, "Анна Смирнова")
    running = start(client, ivan["id"], "Разработка")

    response = client.get("/api/employees")

    assert response.status_code == 200
    employees = response.json()
    assert [employee["name"] for employee in employees] == [
        "Анна Смирнова",
        "Иван Петров",
    ]
    assert employees[0]["id"] == anna["id"]
    assert employees[0]["running_entry"] is None
    assert employees[1]["running_entry"] == {
        "id": running["id"],
        "description": "Разработка",
        "started_at": "2026-11-02T09:00:00Z",
    }
