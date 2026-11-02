from tests.conftest import create_employee, insert_entry, start


def report(client, date_from, date_to, **params):
    return client.get(
        "/api/report",
        params={"date_from": date_from, "date_to": date_to, **params},
    )


def test_empty_report_returns_zero_totals(client, clock):
    response = report(client, "2026-11-02", "2026-11-02")

    assert response.status_code == 200
    assert response.json() == {
        "date_from": "2026-11-02",
        "date_to": "2026-11-02",
        "total_seconds": 0,
        "employees": [],
    }


def test_report_includes_employees_without_entries(client, clock):
    create_employee(client, "Иван Петров")
    create_employee(client, "Анна Смирнова")

    response = report(client, "2026-11-02", "2026-11-02")

    assert response.status_code == 200
    assert [employee["total_seconds"] for employee in response.json()["employees"]] == [
        0,
        0,
    ]
    assert [employee["entries_count"] for employee in response.json()["employees"]] == [
        0,
        0,
    ]


def test_report_sums_multiple_entries_per_employee_and_overall(client, clock):
    ivan = create_employee(client, "Иван Петров")
    anna = create_employee(client, "Анна Смирнова")
    insert_entry(ivan["id"], "2026-11-02T08:00:00+00:00", "2026-11-02T08:10:00+00:00")
    insert_entry(ivan["id"], "2026-11-02T08:30:00+00:00", "2026-11-02T08:50:00+00:00")
    insert_entry(anna["id"], "2026-11-02T08:00:00+00:00", "2026-11-02T08:05:00+00:00")

    response = report(client, "2026-11-02", "2026-11-02")
    employees = {row["employee_id"]: row for row in response.json()["employees"]}

    assert response.json()["total_seconds"] == 2100
    assert employees[ivan["id"]]["total_seconds"] == 1800
    assert employees[ivan["id"]]["entries_count"] == 2
    assert employees[anna["id"]]["total_seconds"] == 300


def test_date_period_excludes_outside_entries_and_includes_end_date(client, clock):
    employee = create_employee(client, "Иван Петров")
    insert_entry(employee["id"], "2026-11-01T23:59:00+00:00", "2026-11-02T00:00:00+00:00")
    insert_entry(employee["id"], "2026-11-03T23:59:00+00:00", "2026-11-03T23:59:30+00:00")
    insert_entry(employee["id"], "2026-11-04T00:00:00+00:00", "2026-11-04T00:01:00+00:00")

    response = report(client, "2026-11-02", "2026-11-03")

    assert response.status_code == 200
    assert response.json()["employees"][0]["total_seconds"] == 30
    assert response.json()["employees"][0]["entries_count"] == 1


def test_report_applies_minsk_timezone_offset(client, clock):
    employee = create_employee(client, "Иван Петров")
    insert_entry(employee["id"], "2026-11-01T22:30:00+00:00", "2026-11-01T23:30:00+00:00")

    minsk = report(client, "2026-11-02", "2026-11-02", tz_offset=-180)
    utc = report(client, "2026-11-02", "2026-11-02", tz_offset=0)

    assert minsk.json()["employees"][0]["total_seconds"] == 3600
    assert utc.json()["employees"][0]["total_seconds"] == 0


def test_running_entry_counts_duration_up_to_fake_now(client, clock):
    employee = create_employee(client, "Иван Петров")
    start(client, employee["id"], "Текущая задача")
    clock.advance(120)

    response = report(client, "2026-11-02", "2026-11-02")

    assert response.json()["total_seconds"] == 120


def test_report_rejects_reversed_dates_missing_dates_and_bad_offset(client, clock):
    reversed_dates = client.get(
        "/api/report", params={"date_from": "2026-11-03", "date_to": "2026-11-02"}
    )
    missing_dates = client.get("/api/report")
    bad_offset = report(client, "2026-11-02", "2026-11-02", tz_offset=841)

    assert reversed_dates.status_code == 422
    assert missing_dates.status_code == 422
    assert bad_offset.status_code == 422


def test_entries_filters_by_employee_and_period_and_sorts_descending(client, clock):
    ivan = create_employee(client, "Иван Петров")
    anna = create_employee(client, "Анна Смирнова")
    insert_entry(ivan["id"], "2026-11-02T08:00:00+00:00", "2026-11-02T08:01:00+00:00")
    insert_entry(ivan["id"], "2026-11-02T09:00:00+00:00", None, "Running")
    insert_entry(anna["id"], "2026-11-01T08:00:00+00:00", "2026-11-01T08:01:00+00:00")

    response = client.get(
        "/api/entries",
        params={
            "employee_id": ivan["id"],
            "date_from": "2026-11-02",
            "date_to": "2026-11-02",
        },
    )

    entries = response.json()
    assert response.status_code == 200
    assert [entry["started_at"] for entry in entries] == [
        "2026-11-02T09:00:00Z",
        "2026-11-02T08:00:00Z",
    ]
    assert entries[0]["is_running"] is True
    assert entries[0]["ended_at"] is None
