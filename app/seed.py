import sqlite3
from datetime import timedelta

from app import repository
from app.time_utils import utc_now


def seed_demo_data(connection: sqlite3.Connection) -> None:
    """Populate an empty database with fictional demo employees and entries."""
    employee_count = connection.execute(
        "SELECT count(*) FROM employees"
    ).fetchone()[0]
    if employee_count:
        return

    now = utc_now()
    employees = {
        name: repository.create_employee(
            connection, name, name.strip().casefold(), now
        )["id"]
        for name in ("Иван Петров", "Анна Смирнова", "Олег Кузнецов")
    }
    demo_entries = (
        ("Иван Петров", 1, 90, "Подготовка еженедельного отчёта"),
        ("Анна Смирнова", 2, 60, "Обновление карточек клиентов"),
        ("Иван Петров", 3, 120, "Проверка интеграции с платёжным сервисом"),
        ("Анна Смирнова", 4, 45, "Подготовка материалов для встречи"),
        ("Иван Петров", 5, 180, "Анализ результатов за неделю"),
        ("Анна Смирнова", 6, 75, "Обработка входящих обращений"),
    )
    for name, days_ago, duration_minutes, description in demo_entries:
        started_at = now - timedelta(days=days_ago, hours=5)
        entry = repository.start_timer(
            connection, employees[name], description, started_at
        )
        repository.stop_timer(
            connection,
            employees[name],
            started_at + timedelta(minutes=duration_minutes),
        )
