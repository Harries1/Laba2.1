from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


# =========================
# Model
# =========================

@dataclass(frozen=True)
class Task:
    name: str
    hardness: str  # "жёсткое" / "твёрдое" / "мягкое"
    C: int         # Время выполнения, мс
    D: int         # Относительный дедлайн, мс
    T: int         # Период, мс


# =========================
# Helpers (normalization)
# =========================

def _norm(s: str) -> str:
    return s.strip().lower().replace("ё", "е")


def _is_hard(task: Task) -> bool:
    return _norm(task.hardness) == "жесткое"


# =========================
# Calculation functions
# =========================

def slack(task: Task) -> int:
    """L = D - C"""
    return task.D - task.C


def is_feasible(task: Task) -> bool:
    """Проверка запаса времени: L >= 0"""
    return slack(task) >= 0


def deadline_type(task: Task) -> str:
    """Классификация по соотношению D и T"""
    if task.D == task.T:
        return "неявный (D=T)"
    if task.D < task.T:
        return "ограниченный (D<T)"
    return "произвольный (D>T)"


def classify_system(tasks: Iterable[Task]) -> str:
    """Класс системы реального времени"""
    tasks_list = list(tasks)

    if any(_is_hard(t) for t in tasks_list):
        return "жёсткого реального времени"

    return "мягкого реального времени"


def critical_task(tasks: Iterable[Task]) -> Task | None:
    """Критическая задача с минимальным запасом среди жёстких задач"""
    hard_tasks = [t for t in tasks if _is_hard(t)]

    if not hard_tasks:
        return None

    return min(hard_tasks, key=slack)


def required_reaction_time(tasks: Iterable[Task]) -> int:
    """Требуемое время реакции"""
    tasks_list = list(tasks)

    if not tasks_list:
        raise ValueError("Список задач пуст.")

    hard_tasks = [t for t in tasks_list if _is_hard(t)]
    base = hard_tasks if hard_tasks else tasks_list

    return min(t.D for t in base)


def utilization(tasks: Iterable[Task]) -> float:
    """Коэффициент загрузки U = sum(Ci / Ti)"""
    total = 0.0

    for t in tasks:
        if t.T <= 0:
            raise ValueError(
                f"Некорректный период T у задачи '{t.name}': {t.T}"
            )

        total += t.C / t.T

    return total


def classify_architecture(n_cpu: int, has_network: bool) -> str:
    """Классификация архитектуры системы"""
    if has_network:
        return "распределённая"

    if n_cpu <= 1:
        return "однопроцессорная"

    return "многопроцессорная"


# =========================
# JSON input
# =========================

def load_variant_json(
    path: Path,
) -> tuple[list[Task], int, bool]:
    """
    Формат JSON:

    {
        "system": {
            "n_cpu": 1,
            "has_network": false
        },
        "tasks": [
            {
                "name": "Задача 1",
                "hardness": "жёсткое",
                "C": 2,
                "D": 5,
                "T": 10
            }
        ]
    }
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Файл не найден: {path}\n"
            "Проверь название файла и путь к папке."
        )

    try:
        data: dict[str, Any] = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Ошибка в формате JSON: {e}"
        ) from e

    system = data.get("system", {})

    n_cpu = int(system.get("n_cpu", 1))
    has_network = bool(system.get("has_network", False))

    raw_tasks = data.get("tasks", [])

    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError(
            "Поле 'tasks' отсутствует или не содержит задач."
        )

    tasks: list[Task] = []

    for i, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"Задача #{i} должна быть JSON-объектом."
            )

        try:
            task = Task(
                name=str(item["name"]),
                hardness=str(item["hardness"]),
                C=int(item["C"]),
                D=int(item["D"]),
                T=int(item["T"]),
            )
        except KeyError as e:
            raise ValueError(
                f"В задаче #{i} отсутствует поле: {e}"
            ) from e
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Некорректные данные в задаче #{i}."
            ) from e

        if task.C < 0 or task.D < 0 or task.T <= 0:
            raise ValueError(
                f"Некорректные значения у задачи '{task.name}': "
                f"C={task.C}, D={task.D}, T={task.T}"
            )

        tasks.append(task)

    return tasks, n_cpu, has_network


# =========================
# Output table
# =========================

def print_table(tasks: list[Task]) -> None:
    headers = [
        "Задача",
        "Класс",
        "C",
        "D",
        "T",
        "L",
        "Выполнимо",
        "Тип дедлайна",
    ]

    rows: list[list[str]] = []

    for t in tasks:
        L = slack(t)

        rows.append([
            t.name,
            t.hardness,
            str(t.C),
            str(t.D),
            str(t.T),
            str(L),
            "да" if is_feasible(t) else "нет",
            deadline_type(t),
        ])

    cols = list(zip(headers, *rows))
    widths = [
        max(len(str(value)) for value in col)
        for col in cols
    ]

    def fmt_row(values: list[str]) -> str:
        return " | ".join(
            value.ljust(width)
            for value, width in zip(values, widths)
        )

    separator = "-+-".join("-" * width for width in widths)

    print("\nРезультаты расчёта:\n")
    print(fmt_row(headers))
    print(separator)

    for row in rows:
        print(fmt_row(row))


# =========================
# Conclusion
# =========================

def print_conclusion(
    tasks: list[Task],
    n_cpu: int,
    has_network: bool,
) -> None:

    sys_class = classify_system(tasks)
    arch = classify_architecture(n_cpu, has_network)
    crit = critical_task(tasks)
    r_req = required_reaction_time(tasks)
    u = utilization(tasks)

    all_slack_ok = all(is_feasible(t) for t in tasks)
    u_ok = u <= 1.0

    print("\nЗаключение:")
    print(f"- Класс системы: {sys_class}")

    print(
        f"- Архитектура: {arch} "
        f"(CPU={n_cpu}, "
        f"сеть={'да' if has_network else 'нет'})"
    )

    if crit is not None:
        print(
            f"- Критическая задача: {crit.name} "
            f"(L={slack(crit)} мс)"
        )
    else:
        print(
            "- Критическая задача отсутствует "
            "(жёсткие задачи не заданы)"
        )

    print(
        f"- Требуемое время реакции "
        f"R_треб = {r_req} мс"
    )

    print(
        f"- Коэффициент загрузки U = {u:.4f}; "
        f"условие U <= 1: "
        f"{'выполнено' if u_ok else 'НЕ выполнено'}"
    )

    print(
        f"- Проверка дедлайнов (L >= 0): "
        f"{'все выполнимы' if all_slack_ok else 'есть невыполнимые'}"
    )


# =========================
# Main
# =========================

def main() -> None:
    # Путь к JSON-файлу с исходными данными
    input_file = Path(
        r"D:\ACS-TP-Python-main\Repo\Data\variant.json"
    )

    try:
        tasks, n_cpu, has_network = load_variant_json(input_file)

        print_table(tasks)
        print_conclusion(tasks, n_cpu, has_network)

    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"\nОшибка: {e}")

    except Exception as e:
        print(f"\nНепредвиденная ошибка: {e}")


if __name__ == "__main__":
    main()
