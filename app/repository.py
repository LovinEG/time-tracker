import sqlite3
from datetime import date, datetime, time, timedelta, timezone

from app.time_utils import to_iso, utc_now


def create_employee(
    connection: sqlite3.Connection, name: str, name_key: str, created_at: datetime
) -> sqlite3.Row:
    """Insert an employee and return the stored row."""
    cursor = connection.execute(
        "INSERT INTO employees (name, name_key, created_at) VALUES (?, ?, ?)",
        (name, name_key, to_iso(created_at)),
    )
    connection.commit()
    return get_employee(connection, cursor.lastrowid)


def get_employee(
    connection: sqlite3.Connection, employee_id: int
) -> sqlite3.Row | None:
    """Return an employee by ID."""
    return connection.execute(
        "SELECT id, name, created_at FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()


def employee_name_exists(connection: sqlite3.Connection, name_key: str) -> bool:
    """Check for a case-insensitive employee name match."""
    return (
        connection.execute(
            "SELECT 1 FROM employees WHERE name_key = ?",
            (name_key,),
        ).fetchone()
        is not None
    )


def list_employees(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return employees with any running timer, ordered by name."""
    return connection.execute(
        """
        SELECT e.id, e.name, e.created_at,
               t.id AS running_id, t.description AS running_description,
               t.started_at AS running_started_at
        FROM employees AS e
        LEFT JOIN time_entries AS t
          ON t.employee_id = e.id AND t.ended_at IS NULL
        ORDER BY e.name_key, e.name
        """
    ).fetchall()


def get_running_entry(
    connection: sqlite3.Connection, employee_id: int
) -> sqlite3.Row | None:
    """Return an employee's running timer, if any."""
    return connection.execute(
        """
        SELECT id, employee_id, description, started_at, ended_at
        FROM time_entries
        WHERE employee_id = ? AND ended_at IS NULL
        """,
        (employee_id,),
    ).fetchone()


def start_timer(
    connection: sqlite3.Connection,
    employee_id: int,
    description: str,
    started_at: datetime,
) -> sqlite3.Row:
    """Insert a running timer and return it."""
    cursor = connection.execute(
        """
        INSERT INTO time_entries (employee_id, description, started_at)
        VALUES (?, ?, ?)
        """,
        (employee_id, description, to_iso(started_at)),
    )
    connection.commit()
    return connection.execute(
        """
        SELECT id, employee_id, description, started_at, ended_at
        FROM time_entries WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()


def stop_timer(
    connection: sqlite3.Connection, employee_id: int, ended_at: datetime
) -> sqlite3.Row | None:
    """Stop the running timer and return the updated row."""
    running = get_running_entry(connection, employee_id)
    if running is None:
        return None
    connection.execute(
        "UPDATE time_entries SET ended_at = ? WHERE id = ?",
        (to_iso(ended_at), running["id"]),
    )
    connection.commit()
    return connection.execute(
        """
        SELECT id, employee_id, description, started_at, ended_at
        FROM time_entries WHERE id = ?
        """,
        (running["id"],),
    ).fetchone()


def _period_bounds(
    date_from: date | None, date_to: date | None, tz_offset: int = 0
) -> tuple[str | None, str | None]:
    """Convert local dates to UTC bounds; tz_offset follows JavaScript's sign."""
    local_timezone = timezone(timedelta(minutes=-tz_offset))
    lower = (
        to_iso(datetime.combine(date_from, time.min, local_timezone))
        if date_from is not None
        else None
    )
    upper = (
        to_iso(datetime.combine(date_to + timedelta(days=1), time.min, local_timezone))
        if date_to is not None
        else None
    )
    return lower, upper


def _entry_duration(started_at: str, ended_at: str | None, now: datetime) -> int:
    """Return an entry duration in whole seconds."""
    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(ended_at) if ended_at else now
    return int((end - start).total_seconds())


def list_entries(
    connection: sqlite3.Connection,
    employee_id: int | None,
    date_from: date | None,
    date_to: date | None,
    tz_offset: int = 0,
) -> list[dict[str, object]]:
    """Return matching entries with durations and running state."""
    lower, upper = _period_bounds(date_from, date_to, tz_offset)
    clauses: list[str] = []
    parameters: list[object] = []
    if employee_id is not None:
        clauses.append("t.employee_id = ?")
        parameters.append(employee_id)
    if lower is not None:
        clauses.append("t.started_at >= ?")
        parameters.append(lower)
    if upper is not None:
        clauses.append("t.started_at < ?")
        parameters.append(upper)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""
        SELECT t.id, t.employee_id, e.name AS employee_name,
               t.description, t.started_at, t.ended_at
        FROM time_entries AS t
        JOIN employees AS e ON e.id = t.employee_id
        {where}
        ORDER BY t.started_at DESC
        """,
        parameters,
    ).fetchall()
    now = utc_now()
    return [
        {
            **dict(row),
            "duration_seconds": _entry_duration(row["started_at"], row["ended_at"], now),
            "is_running": row["ended_at"] is None,
        }
        for row in rows
    ]


def build_report(
    connection: sqlite3.Connection, date_from: date, date_to: date, tz_offset: int = 0
) -> dict[str, object]:
    """Aggregate entries in an inclusive UTC date period for every employee."""
    lower, upper = _period_bounds(date_from, date_to, tz_offset)
    rows = connection.execute(
        """
        SELECT e.id AS employee_id, e.name AS employee_name,
               t.started_at, t.ended_at
        FROM employees AS e
        LEFT JOIN time_entries AS t
          ON t.employee_id = e.id AND t.started_at >= ? AND t.started_at < ?
        ORDER BY e.name_key, e.name
        """,
        (lower, upper),
    ).fetchall()
    now = utc_now()
    employees: list[dict[str, object]] = []
    for row in rows:
        if employees and employees[-1]["employee_id"] == row["employee_id"]:
            employee = employees[-1]
        else:
            employee = {
                "employee_id": row["employee_id"],
                "employee_name": row["employee_name"],
                "total_seconds": 0,
                "entries_count": 0,
            }
            employees.append(employee)
        if row["started_at"] is not None:
            employee["total_seconds"] += _entry_duration(
                row["started_at"], row["ended_at"], now
            )
            employee["entries_count"] += 1
    return {
        "date_from": date_from,
        "date_to": date_to,
        "total_seconds": sum(employee["total_seconds"] for employee in employees),
        "employees": employees,
    }
