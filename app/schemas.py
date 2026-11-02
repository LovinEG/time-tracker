from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class EmployeeCreate(BaseModel):
    name: str = Field(max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        """Trim employee names and reject blank input."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Name must not be empty")
        return value


class TimerStart(BaseModel):
    description: str = Field(max_length=500)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        """Trim timer descriptions and reject blank input."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Description must not be empty")
        return value


class RunningEntryResponse(BaseModel):
    id: int
    description: str
    started_at: datetime


class EmployeeResponse(BaseModel):
    id: int
    name: str
    created_at: datetime


class EmployeeWithTimerResponse(EmployeeResponse):
    running_entry: RunningEntryResponse | None


class TimerEntryResponse(BaseModel):
    id: int
    employee_id: int
    description: str
    started_at: datetime
    ended_at: datetime | None


class EntryResponse(TimerEntryResponse):
    employee_name: str
    duration_seconds: int
    is_running: bool


class EmployeeReport(BaseModel):
    employee_id: int
    employee_name: str
    total_seconds: int
    entries_count: int


class ReportResponse(BaseModel):
    date_from: date
    date_to: date
    total_seconds: int
    employees: list[EmployeeReport]
