from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from typing import Any


def _id(name: str) -> str:
    """Детерминированный UUID: повторный запуск создаёт тот же набор данных."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"university-demo/{name}"))


# Идентификаторы первой ветви сохранены: ими пользуются примеры запросов ЛР.
IDS = {name: _id(name) for name in (
    "university", "institute", "department", "specialty", "group", "course",
    "course_architecture", "lecture_1", "lecture_2", "lecture_3", "student_1",
)}

FIRST_NAMES = ("Александр", "Анна", "Дмитрий", "Елена", "Иван", "Мария", "Никита", "Ольга", "Павел", "София")
LAST_NAMES = ("Иванов", "Петров", "Смирнов", "Кузнецов", "Попов", "Соколов", "Васильев", "Новиков", "Фёдоров", "Морозов")

DATASET_SCALE = "large"

SCALE_PROFILES = {
    "small": {
        "universities": 1,
        "groups_per_university": 1,
        "students_per_group": 20,
        "students_count": 20,
    },
    "large": {
        "universities": 2,
        "groups_per_university": 20,
        "students_per_group": 25,
        "students_count": 1000,
    },
}
DEFAULT_STUDENTS_COUNT = SCALE_PROFILES[DATASET_SCALE]["students_count"]


def build_dataset(seed: int = 20260926, students_count: int | None = None) -> dict[str, list[dict[str, Any]]]:
    """Создаёт набор выбранного масштаба из ``DATASET_SCALE``."""
    try:
        scale = SCALE_PROFILES[DATASET_SCALE]
    except KeyError as error:
        raise ValueError("DATASET_SCALE должен быть 'small' или 'large'") from error
    if students_count is None:
        students_count = scale["students_count"]
    if students_count != scale["students_count"]:
        raise ValueError(
            f"Для профиля {DATASET_SCALE!r} число студентов должно быть "
            f"{scale['students_count']}"
        )

    rng = random.Random(seed)
    ds: dict[str, list[dict[str, Any]]] = {key: [] for key in (
        "universities", "institutes", "departments", "specialties", "department_specialties",
        "student_groups", "student_group_specialties", "students", "lecture_courses",
        "lectures", "lecture_materials", "schedule", "schedule_groups", "attendance",
    )}
    branches = (
        {
            "key": "mirea", "university_id": IDS["university"], "institute_id": IDS["institute"], "department_id": IDS["department"], "specialty_id": IDS["specialty"],
            "university": ("Российский технологический университет", "РТУ МИРЭА", "Москва, проспект Вернадского, 78", "https://www.mirea.ru", 1947),
            "institute": ("Институт информационных технологий", "ИИТ", "Сергей Викторович Орлов"),
            "department": ("Кафедра программной инженерии", "КПИ", "Ирина Александровна Белова", "А-401"),
            "specialty": ("Информационные системы и технологии", "09.03.02"), "group_prefix": "ИКБО",
            "courses": ((IDS["course"], "Базы данных", "Реляционные и нереляционные модели хранения данных", 3, 72, 36, 18, 18), (IDS["course_architecture"], "Проектирование архитектуры ПО", "Паттерны, сервисы и надёжные системы", 3, 72, 36, 18, 18)),
            "lectures": ((IDS["lecture_1"], IDS["course"], "Реляционные базы данных и SQL", "Таблицы, ключи и нормальные формы", "lecture", 1, True, "Проектор и доступ к SQL-демонстрации"), (IDS["lecture_2"], IDS["course"], "Индексы и оптимизация запросов", "Индексы базы данных и план выполнения запроса", "lecture", 2, False, None), (IDS["lecture_3"], IDS["course_architecture"], "Паттерны проектирования", "Singleton, фабрика и внедрение зависимостей", "lecture", 1, True, "Проектор, доска и интернет"), (_id("lecture-4"), IDS["course_architecture"], "Лабораторная работа: Docker для сервисов", "Контейнеризация приложения", "lab", 2, True, "Компьютерный класс с Docker")),
        },
        {
            "key": "spbstu", "university_id": _id("university-2"), "institute_id": _id("institute-2"), "department_id": _id("department-2"), "specialty_id": _id("specialty-2"),
            "university": ("Санкт-Петербургский политехнический университет Петра Великого", "СПбПУ", "Санкт-Петербург, Политехническая улица, 29", "https://www.spbstu.ru", 1899),
            "institute": ("Институт компьютерных наук и кибербезопасности", "ИКНК", "Алексей Игоревич Соколов"),
            "department": ("Высшая школа кибербезопасности", "ВШКБ", "Наталья Павловна Орлова", "Н-217"),
            "specialty": ("Программная инженерия", "09.03.04"), "group_prefix": "ПИ",
            "courses": ((_id("course-networks"), "Компьютерные сети", "Сетевые протоколы, адресация и маршрутизация", 3, 72, 36, 18, 18), (_id("course-security"), "Основы информационной безопасности", "Защита информации и безопасная разработка", 3, 72, 36, 18, 18)),
            "lectures": ((_id("lecture-networks-1"), _id("course-networks"), "Маршрутизация и сетевые протоколы", "IP-адресация, маршрутизация и диагностика сети", "lecture", 1, True, "Проектор и демонстрационный сетевой стенд"), (_id("lecture-networks-2"), _id("course-networks"), "Практика: настройка VLAN", "Сегментация сети и настройка коммутатора", "practice", 2, True, "Компьютерный класс и сетевые коммутаторы"), (_id("lecture-security-1"), _id("course-security"), "Модели угроз и защита данных", "Моделирование угроз и криптографическая защита", "lecture", 1, True, "Проектор и доступ к демонстрационному стенду"), (_id("lecture-security-2"), _id("course-security"), "Практика: анализ уязвимостей", "Поиск и устранение типовых уязвимостей", "practice", 2, True, "Компьютерный класс с Linux")),
        },
    )

    groups: list[dict[str, Any]] = []
    for branch in branches[:scale["universities"]]:
        university_name, university_short, address, website, founded_year = branch["university"]
        institute_name, institute_short, dean = branch["institute"]
        department_name, department_short, head, room = branch["department"]
        specialty_name, specialty_code = branch["specialty"]
        ds["universities"].append(dict(id=branch["university_id"], name=university_name, short_name=university_short, address=address, website=website, founded_year=founded_year))
        ds["institutes"].append(dict(id=branch["institute_id"], university_id=branch["university_id"], name=institute_name, short_name=institute_short, dean=dean))
        ds["departments"].append(dict(id=branch["department_id"], institute_id=branch["institute_id"], name=department_name, short_name=department_short, head=head, room=room))
        ds["specialties"].append(dict(id=branch["specialty_id"], name=specialty_name, code=specialty_code, degree_level="bachelor", duration_years=4))
        ds["department_specialties"].append(dict(id=_id(f"dept-spec-{branch['key']}"), department_id=branch["department_id"], specialty_id=branch["specialty_id"], is_primary=True))
        for number in range(1, scale["groups_per_university"] + 1):
            group_id = IDS["group"] if branch["key"] == "mirea" and number == 1 else _id(f"group-{branch['key']}-{number}")
            group = {"id": group_id, "department_id": branch["department_id"], "specialty_id": branch["specialty_id"], "name": f"{branch['group_prefix']}-{number:02d}-23", "enrollment_year": 2023, "curator": f"Куратор {branch['key'].upper()}-{number:02d}", "branch_key": branch["key"]}
            groups.append(group)
            ds["student_groups"].append({key: value for key, value in group.items() if key != "branch_key"})
            ds["student_group_specialties"].append(dict(id=_id(f"group-spec-{branch['key']}-{number}"), group_id=group_id, specialty_id=branch["specialty_id"], is_primary=True))
        for course_id, name, description, semester, total, lecture, practice, lab in branch["courses"]:
            ds["lecture_courses"].append(dict(
                id=course_id, specialty_id=branch["specialty_id"],
                reading_department_id=branch["department_id"],
                name=name, description=description, semester=semester,
                total_hours=total, lecture_hours=lecture,
                practice_hours=practice, lab_hours=lab,
            ))
        for lecture_id, course_id, title, annotation, lecture_type, order, needs_tech, tech_comment in branch["lectures"]:
            ds["lectures"].append(dict(id=lecture_id, course_id=course_id, title=title, annotation=annotation, lecture_type=lecture_type, order_number=order, duration_minutes=90, requires_tech=needs_tech, tech_comment=tech_comment))
            # Материал может иметь технические теги, но признак специальной
            # дисциплины определяется кафедрой, читающей курс, а не тегом.
            tags = ["lecture_material"]
            text = " База данных, SQL и практические примеры." if course_id == IDS["course"] else " Учебный материал и практические примеры."
            ds["lecture_materials"].append(dict(id=_id(f"material-{lecture_id}"), lecture_id=lecture_id, content_type="text", title=f"Материалы: {title}", content_text=f"Конспект занятия. {annotation}.{text}", file_url=None, metadata={"tags": tags}))

    # Студенты распределяются строго по числу, заданному выбранным профилем.
    for n in range(students_count):
        group = groups[(n // scale["students_per_group"]) % len(groups)]
        student_id = IDS["student_1"] if n == 0 else _id(f"student-{n + 1}")
        first, last = FIRST_NAMES[n % len(FIRST_NAMES)], LAST_NAMES[(n * 3) % len(LAST_NAMES)]
        ds["students"].append(dict(id=student_id, group_id=group["id"], first_name=first, last_name=last, patronymic="Алексеевич" if n % 2 == 0 else "Сергеевна", email=f"student{n + 1}@university.example", phone=f"+7999{1000000 + n:07d}", student_card_number=f"STU-2023-{n + 1:04d}", enrollment_date=date(2023, 9, 1), status="active"))

    students_by_group: dict[str, list[dict[str, Any]]] = {group["id"]: [] for group in groups}
    for student in ds["students"]:
        students_by_group[student["group_id"]].append(student)
    start = date(2026, 2, 9)
    lectures_by_branch = {branch["key"]: branch["lectures"] for branch in branches}
    groups_by_branch = {
        branch["key"]: [group for group in groups if group["branch_key"] == branch["key"]]
        for branch in branches[:scale["universities"]]
    }
    for branch_key, branch_groups in groups_by_branch.items():
        for number, lecture_spec in enumerate(lectures_by_branch[branch_key]):
            lecture_id = lecture_spec[0]
            lecture_type = lecture_spec[4]
            # Лекции и лабораторные могут проводиться потоками для двух групп.
            # Благодаря schedule_groups одна запись schedule описывает одно
            # занятие, а не дублируется для каждой группы потока.
            stream_size = 2 if lecture_type in {"lecture", "lab"} else 1
            for week in range(6):
                scheduled = start + timedelta(days=week * 7 + number % 3)
                for stream_number, stream_groups in enumerate(
                    (branch_groups[index:index + stream_size] for index in range(0, len(branch_groups), stream_size)),
                    start=1,
                ):
                    primary_group = stream_groups[0]
                    # Сохраняем UUID исходного занятия первой группы для старых примеров.
                    suffix = (
                        f"schedule-{lecture_id}-{scheduled.isoformat()}"
                        if primary_group["id"] == IDS["group"]
                        else f"schedule-{primary_group['id']}-{lecture_id}-{scheduled.isoformat()}"
                    )
                    schedule_id = _id(suffix)
                    ds["schedule"].append(dict(
                        id=schedule_id, lecture_id=lecture_id,
                        scheduled_date=scheduled,
                        week_start_date=scheduled - timedelta(days=scheduled.weekday()),
                        start_time="10:00", end_time="11:30",
                        classroom=f"А-{304 + stream_number}",
                        teacher_name="Ирина Белова" if branch_key == "mirea" else "Наталья Орлова",
                        status="completed",
                    ))
                    for group in stream_groups:
                        ds["schedule_groups"].append(dict(schedule_id=schedule_id, group_id=group["id"]))
                        for student in students_by_group[group["id"]]:
                            probability = 0.35 if student["id"] in {IDS["student_1"], _id("student-2"), _id("student-3")} else 0.82
                            ds["attendance"].append(dict(id=_id(f"attendance-{schedule_id}-{student['id']}"), schedule_id=schedule_id, student_id=student["id"], week_start_date=scheduled - timedelta(days=scheduled.weekday()), is_present=rng.random() < probability, marked_by="Электронный журнал", note=None))
    return ds
