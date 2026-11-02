const errorMessages = {
  "Employee already exists": "Сотрудник с таким именем уже есть",
  "Timer is already running": "Таймер уже запущен",
  "No running timer": "Таймер не запущен",
  "Employee not found": "Сотрудник не найден",
  "date_from must be on or before date_to":
    "Дата «С» должна быть не позже даты «По»",
  "Description must not be empty": "Введите описание задачи",
  "Name must not be empty": "Введите имя сотрудника",
};

const errorArea = document.querySelector("#error-area");
const employeeForm = document.querySelector("#employee-form");
const employeeInput = document.querySelector("#employee-name");
const employeesList = document.querySelector("#employees-list");
const reportForm = document.querySelector("#report-form");
const dateFromInput = document.querySelector("#date-from");
const dateToInput = document.querySelector("#date-to");
const employeeFilter = document.querySelector("#employee-filter");
const summaryBody = document.querySelector("#summary-body");
const entriesBody = document.querySelector("#entries-body");
const entriesEmpty = document.querySelector("#entries-empty");
const entriesTableWrap = document.querySelector("#entries-table-wrap");
const demoBanner = document.querySelector("#demo-banner");

reportForm.noValidate = true;

class ApiError extends Error {
  constructor(detail) {
    super(detail);
    this.detail = detail;
  }
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError("Сервер недоступен");
  }

  let data;
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    throw new ApiError(data.detail || "Ошибка сервера");
  }
  clearError();
  return data;
}

function showError(error) {
  const detail = error instanceof ApiError ? error.detail : "Сервер недоступен";
  errorArea.textContent = errorMessages[detail] || detail;
  errorArea.hidden = false;
}

function clearError() {
  errorArea.textContent = "";
  errorArea.hidden = true;
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return [hours, minutes, remainder]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

function makeElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function dateInputValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function setDefaultPeriod(demoMode) {
  const today = new Date();
  const start = new Date(today);
  if (demoMode) {
    start.setDate(today.getDate() - 6);
  } else {
    const daysSinceMonday = (today.getDay() + 6) % 7;
    start.setDate(today.getDate() - daysSinceMonday);
  }
  dateFromInput.value = dateInputValue(start);
  dateToInput.value = dateInputValue(today);
}

function updateTimerClocks() {
  const now = Date.now();
  document.querySelectorAll(".timer-clock[data-started-at]").forEach((clock) => {
    const startedAt = new Date(clock.dataset.startedAt).getTime();
    clock.textContent = formatDuration(Math.floor((now - startedAt) / 1000));
  });
}

function renderEmployees(employees, skipDescriptionForId = null) {
  const selectedEmployee = employeeFilter.value;
  const descriptions = new Map();
  employeesList.querySelectorAll(".employee-card").forEach((card) => {
    const input = card.querySelector(".timer-start-form input");
    if (input && card.dataset.employeeId !== String(skipDescriptionForId)) {
      descriptions.set(card.dataset.employeeId, input.value);
    }
  });
  employeesList.replaceChildren();

  for (const employee of employees) {
    const card = makeElement("article", "employee-card");
    card.dataset.employeeId = String(employee.id);
    const name = makeElement("p", "employee-name", employee.name);
    card.append(name);

    const controls = makeElement("div", "timer-controls");
    if (employee.running_entry) {
      const task = makeElement(
        "span",
        "running-task",
        employee.running_entry.description,
      );
      const clock = makeElement("span", "timer-clock");
      clock.dataset.startedAt = employee.running_entry.started_at;
      const stopButton = makeElement("button", "stop-button", "Стоп");
      stopButton.type = "button";
      stopButton.addEventListener("click", () =>
        stopTimer(employee.id, stopButton),
      );
      controls.append(task, clock, stopButton);
    } else {
      const form = makeElement("form", "timer-start-form");
      const description = document.createElement("input");
      description.type = "text";
      description.maxLength = 500;
      description.placeholder = "Описание задачи";
      description.setAttribute("aria-label", `Описание задачи: ${employee.name}`);
      description.required = true;
      description.value = descriptions.get(String(employee.id)) || "";
      const startButton = makeElement("button", "", "Старт");
      startButton.type = "submit";
      form.append(description, startButton);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        startTimer(employee.id, description.value, startButton);
      });
      controls.append(form);
    }

    card.append(controls);
    employeesList.append(card);
  }
  renderEmployeeFilter(employees, selectedEmployee);
  updateTimerClocks();
}

function renderEmployeeFilter(employees, selectedEmployee) {
  employeeFilter.replaceChildren();
  const allOption = makeElement("option", "", "Все сотрудники");
  allOption.value = "";
  employeeFilter.append(allOption);

  for (const employee of employees) {
    const option = makeElement("option", "", employee.name);
    option.value = String(employee.id);
    employeeFilter.append(option);
  }
  employeeFilter.value = selectedEmployee;
}

async function loadEmployees(skipDescriptionForId = null) {
  const employees = await api("/api/employees");
  renderEmployees(employees, skipDescriptionForId);
  return employees;
}

async function loadReport() {
  const dateFrom = dateFromInput.value;
  const dateTo = dateToInput.value;
  if (!dateFrom || !dateTo) {
    throw new ApiError("Выберите период");
  }
  const tzOffset = new Date().getTimezoneOffset();
  const query = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
    tz_offset: String(tzOffset),
  });
  const [report, entries] = await Promise.all([
    api(`/api/report?${query}`),
    api(`/api/entries?${query}`),
  ]);
  renderSummary(report);
  renderEntries(entries);
}

function renderSummary(report) {
  const selectedId = employeeFilter.value;
  const employees = selectedId
    ? report.employees.filter(
        (employee) => String(employee.employee_id) === selectedId,
      )
    : report.employees;
  summaryBody.replaceChildren();
  let totalSeconds = 0;
  let totalEntries = 0;

  for (const employee of employees) {
    totalSeconds += employee.total_seconds;
    totalEntries += employee.entries_count;
    const row = document.createElement("tr");
    row.append(
      makeElement("td", "", employee.employee_name),
      makeElement("td", "", String(employee.entries_count)),
      makeElement("td", "", formatDuration(employee.total_seconds)),
    );
    summaryBody.append(row);
  }

  const totalRow = makeElement("tr", "total-row");
  totalRow.append(
    makeElement("td", "", "Итого"),
    makeElement("td", "", String(totalEntries)),
    makeElement("td", "", formatDuration(totalSeconds)),
  );
  summaryBody.append(totalRow);
}

function localDateTime(value) {
  return new Date(value).toLocaleString("ru-RU");
}

function renderEntries(entries) {
  const selectedId = employeeFilter.value;
  const visibleEntries = selectedId
    ? entries.filter((entry) => String(entry.employee_id) === selectedId)
    : entries;
  entriesBody.replaceChildren();
  entriesEmpty.hidden = visibleEntries.length !== 0;
  entriesTableWrap.hidden = visibleEntries.length === 0;

  for (const entry of visibleEntries) {
    const row = document.createElement("tr");
    row.append(
      makeElement("td", "", entry.employee_name),
      makeElement("td", "", entry.description),
      makeElement("td", "", localDateTime(entry.started_at)),
      makeElement("td", "", entry.is_running ? "идёт" : localDateTime(entry.ended_at)),
      makeElement("td", "", formatDuration(entry.duration_seconds)),
    );
    entriesBody.append(row);
  }
}

async function startTimer(employeeId, description, button) {
  button.disabled = true;
  try {
    await api(`/api/employees/${employeeId}/timer/start`, {
      method: "POST",
      body: JSON.stringify({ description }),
    });
    await Promise.all([loadEmployees(employeeId), loadReport()]);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
}

async function stopTimer(employeeId, button) {
  button.disabled = true;
  try {
    await api(`/api/employees/${employeeId}/timer/stop`, { method: "POST" });
    await Promise.all([loadEmployees(), loadReport()]);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
}

employeeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = employeeForm.querySelector("button");
  button.disabled = true;
  try {
    await api("/api/employees", {
      method: "POST",
      body: JSON.stringify({ name: employeeInput.value }),
    });
    employeeInput.value = "";
    await loadEmployees();
    await loadReport();
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
});

reportForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await loadReport();
  } catch (error) {
    showError(error);
  }
});

employeeFilter.addEventListener("change", async () => {
  try {
    await loadReport();
  } catch (error) {
    showError(error);
  }
});

async function initialize() {
  let demoMode = false;
  try {
    const config = await api("/api/config");
    demoMode = config.demo_mode;
    demoBanner.hidden = !demoMode;
  } catch (error) {
    showError(error);
  }
  setDefaultPeriod(demoMode);
  try {
    await loadEmployees();
    await loadReport();
  } catch (error) {
    showError(error);
  }
  window.setInterval(updateTimerClocks, 1000);
}

initialize();
