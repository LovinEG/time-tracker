from contextlib import asynccontextmanager
import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import repository
from app.db import get_connection, init_db
from app.schemas import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeWithTimerResponse,
    EntryResponse,
    ReportResponse,
    TimerEntryResponse,
    TimerStart,
)
from app.time_utils import utc_now


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database before serving requests."""
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


def get_db() -> Iterator[sqlite3.Connection]:
    """Yield a database connection for one request."""
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    """Return validation errors using the API's detail object shape."""
    errors = exc.errors()
    detail = errors[0]["msg"] if errors else "Invalid request"
    if detail.startswith("Value error, "):
        detail = detail.removeprefix("Value error, ")
    return JSONResponse(status_code=422, content={"detail": detail})


def validate_period(date_from: date, date_to: date) -> None:
    """Reject reversed inclusive date ranges."""
    if date_from > date_to:
        raise HTTPException(
            status_code=422, detail="date_from must be on or before date_to"
        )


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report that the API is available."""
    return {"status": "ok"}


@app.post("/api/employees", response_model=EmployeeResponse, status_code=201)
def create_employee(
    request: EmployeeCreate, connection: sqlite3.Connection = Depends(get_db)
):
    """Create an employee."""
    name_key = request.name.casefold()
    if repository.employee_name_exists(connection, name_key):
        raise HTTPException(status_code=409, detail="Employee already exists")
    try:
        return dict(
            repository.create_employee(
                connection, request.name, name_key, utc_now()
            )
        )
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        if exc.sqlite_errorname != "SQLITE_CONSTRAINT_UNIQUE":
            raise
        raise HTTPException(status_code=409, detail="Employee already exists")


@app.get("/api/employees", response_model=list[EmployeeWithTimerResponse])
def list_employees(connection: sqlite3.Connection = Depends(get_db)):
    """List employees with their running timer, if any."""
    result = []
    for row in repository.list_employees(connection):
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "running_entry": (
                    {
                        "id": row["running_id"],
                        "description": row["running_description"],
                        "started_at": row["running_started_at"],
                    }
                    if row["running_id"] is not None
                    else None
                ),
            }
        )
    return result


@app.post(
    "/api/employees/{employee_id}/timer/start",
    response_model=TimerEntryResponse,
    status_code=201,
)
def start_timer(
    employee_id: int,
    request: TimerStart,
    connection: sqlite3.Connection = Depends(get_db),
):
    """Start an employee's timer."""
    if repository.get_employee(connection, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if repository.get_running_entry(connection, employee_id) is not None:
        raise HTTPException(status_code=409, detail="Timer is already running")
    try:
        return dict(
            repository.start_timer(
                connection, employee_id, request.description, utc_now()
            )
        )
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        if exc.sqlite_errorname != "SQLITE_CONSTRAINT_UNIQUE":
            raise
        raise HTTPException(status_code=409, detail="Timer is already running")


@app.post(
    "/api/employees/{employee_id}/timer/stop",
    response_model=TimerEntryResponse,
)
def stop_timer(
    employee_id: int, connection: sqlite3.Connection = Depends(get_db)
):
    """Stop an employee's running timer."""
    if repository.get_employee(connection, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    entry = repository.stop_timer(connection, employee_id, utc_now())
    if entry is None:
        raise HTTPException(status_code=409, detail="No running timer")
    return dict(entry)


@app.get("/api/entries", response_model=list[EntryResponse])
def list_entries(
    employee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    tz_offset: int = Query(default=0, ge=-840, le=840),
    connection: sqlite3.Connection = Depends(get_db),
):
    """List timer entries with optional employee and UTC date filters."""
    if date_from is not None and date_to is not None:
        validate_period(date_from, date_to)
    return repository.list_entries(
        connection, employee_id, date_from, date_to, tz_offset
    )


@app.get("/api/report", response_model=ReportResponse)
def report(
    date_from: date,
    date_to: date,
    tz_offset: int = Query(default=0, ge=-840, le=840),
    connection: sqlite3.Connection = Depends(get_db),
):
    """Summarize entry durations for every employee in a UTC date range."""
    validate_period(date_from, date_to)
    return repository.build_report(connection, date_from, date_to, tz_offset)


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True),
    name="static",
)
