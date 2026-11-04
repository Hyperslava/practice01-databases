from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from data_generators import build_dataset


def _insert(cur: Any, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('%s' for _ in columns)})"
    values = []
    for row in rows:
        values.append(tuple(json.dumps(row[c], ensure_ascii=False) if c == "metadata" else row[c] for c in columns))
    cur.executemany(sql, values)


def seed_postgres_data(cur: Any, seed: int = 20260926, students_count: int = 1000) -> None:
    # Seed is a reproducible snapshot: replace its tables in one transaction so
    # retries do not accumulate duplicate rows or leave partial fixtures.
    cur.execute("""
        TRUNCATE TABLE attendance, schedule_groups, schedule,
            students, student_group_specialties, student_groups,
            lecture_materials, lectures, lecture_courses,
            department_specialties, specialties, departments,
            institutes, universities
        RESTART IDENTITY CASCADE
    """)
    for table, rows in build_dataset(seed, students_count).items():
        _insert(cur, table, rows)


def _pg_rows(pg_config: dict[str, Any], sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    config = dict(pg_config)
    config["dbname"] = "university_system"
    with psycopg.connect(**config, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def seed_redis_cache(client: Any, pg_config: dict[str, Any]) -> None:
    for pattern in ("students_cache:*",):
        keys = list(client.scan_iter(match=pattern, count=500))
        if keys:
            client.delete(*keys)

    students = _pg_rows(
        pg_config,
        """
        SELECT
            st.id AS student_id, st.first_name, st.last_name, st.patronymic,
            st.email, st.phone, st.student_card_number, st.enrollment_date,
            st.status,
            g.id AS group_id, g.name AS group_name, g.enrollment_year,
            g.curator,
            sp.id AS specialty_id, sp.name AS specialty_name, sp.code AS specialty_code,
            sp.degree_level, sp.duration_years,
            COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'course_id', c.id, 'name', c.name, 'description', c.description,
                    'semester', c.semester, 'total_hours', c.total_hours,
                    'lecture_hours', c.lecture_hours, 'practice_hours', c.practice_hours,
                    'lab_hours', c.lab_hours
                ) ORDER BY c.semester, c.name)
                FROM lecture_courses c
                WHERE c.specialty_id = sp.id
            ), '[]'::jsonb) AS courses
        FROM students st
        JOIN student_groups g ON g.id = st.group_id
        JOIN specialties sp ON sp.id = g.specialty_id
        """
    )

    pipe = client.pipeline(transaction=True)

    for student in students:
        student = {k: _json_safe(v) for k, v in student.items()}

        student_id = str(student.pop("student_id"))
        student["id"] = student_id
        for field in ("courses",):
            student[field] = json.dumps(student[field], ensure_ascii=False)

        pipe.hset(
            f"students_cache:{student_id}",
            mapping={
                k: "" if v is None else str(v)
                for k, v in student.items()
            },
        )

        pipe.sadd(
            "students_cache:all",
            student_id,
        )

    pipe.execute()

from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


def _neo4j_safe(value):
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(k): _neo4j_safe(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _neo4j_safe(v)
            for v in value
        ]

    return value


def seed_neo4j_graph(driver: Any, pg_config: dict[str, Any]) -> None:
    course_rows = _pg_rows(pg_config, """
        SELECT c.id AS course_id, c.name AS course_name, c.semester,
               d.id AS reading_department_id, d.name AS reading_department_name,
               l.id AS lecture_id, l.title, l.lecture_type,
               l.requires_tech, l.tech_comment
        FROM lecture_courses c
        JOIN departments d ON d.id = c.reading_department_id
        JOIN lectures l ON l.course_id = c.id
    """)
    student_rows = _pg_rows(pg_config, """
        SELECT st.id AS student_id, st.first_name, st.last_name, st.patronymic,
               st.student_card_number, st.status,
               g.id AS group_id, g.name AS group_name, g.enrollment_year,
               d.id AS graduating_department_id, d.name AS graduating_department_name
        FROM students st
        JOIN student_groups g ON g.id = st.group_id
        JOIN departments d ON d.id = g.department_id
    """)
    session_rows = _pg_rows(pg_config, """
        SELECT sch.id AS session_id, sch.scheduled_date, sch.start_time, sch.end_time,
               sch.classroom, sch.status,
               g.id AS group_id, g.name AS group_name,
               l.id AS lecture_id, l.title AS lecture_title,
               c.id AS course_id, c.name AS course_name, c.semester
        FROM schedule sch
        JOIN schedule_groups sgrp ON sgrp.schedule_id = sch.id
        JOIN student_groups g ON g.id = sgrp.group_id
        JOIN lectures l ON l.id = sch.lecture_id
        JOIN lecture_courses c ON c.id = l.course_id
        WHERE sch.status <> 'cancelled'
    """)
    attendance_rows = _pg_rows(pg_config, """
        SELECT a.student_id, a.schedule_id AS session_id, a.marked_at, a.marked_by
        FROM attendance a
        WHERE a.is_present = TRUE
    """)

    course_query = """UNWIND $rows AS r
        MERGE (d:Department {id:r.reading_department_id})
            SET d.name=r.reading_department_name
        MERGE (c:LectureCourse {id:r.course_id})
            SET c.name=r.course_name, c.semester=r.semester
        MERGE (l:Lecture {id:r.lecture_id})
            SET l.title=r.title, l.lecture_type=r.lecture_type,
                l.requires_tech=r.requires_tech, l.tech_comment=r.tech_comment
        MERGE (d)-[:TEACHES]->(c)
        MERGE (c)-[:HAS_LECTURE]->(l)"""
    student_query = """UNWIND $rows AS r
        MERGE (d:Department {id:r.graduating_department_id})
            SET d.name=r.graduating_department_name
        MERGE (g:StudentGroup {id:r.group_id})
            SET g.name=r.group_name, g.enrollment_year=r.enrollment_year
        MERGE (st:Student {id:r.student_id})
            SET st.first_name=r.first_name, st.last_name=r.last_name,
                st.patronymic=r.patronymic,
                st.student_card_number=r.student_card_number, st.status=r.status
        MERGE (g)-[:GRADUATED_BY]->(d)
        MERGE (st)-[:MEMBER_OF]->(g)"""
    session_query = """UNWIND $rows AS r
        MERGE (c:LectureCourse {id:r.course_id})
            SET c.name=r.course_name, c.semester=r.semester
        MERGE (l:Lecture {id:r.lecture_id}) SET l.title=r.lecture_title
        MERGE (g:StudentGroup {id:r.group_id}) SET g.name=r.group_name
        MERGE (s:ClassSession {id:r.session_id})
            SET s.scheduled_date=r.scheduled_date, s.start_time=r.start_time,
                s.end_time=r.end_time, s.classroom=r.classroom, s.status=r.status
        MERGE (c)-[:HAS_LECTURE]->(l)
        MERGE (l)-[:HELD_AS]->(s)
        MERGE (s)-[:FOR_GROUP]->(g)"""
    attendance_query = """UNWIND $rows AS r
        MATCH (st:Student {id:r.student_id})
        MATCH (s:ClassSession {id:r.session_id})
        MERGE (st)-[a:ATTENDED]->(s)
            SET a.marked_at=r.marked_at, a.marked_by=r.marked_by"""

    course_rows = _neo4j_safe(course_rows)
    student_rows = _neo4j_safe(student_rows)
    session_rows = _neo4j_safe(session_rows)
    attendance_rows = _neo4j_safe(attendance_rows)

    with driver.session() as session:
        # Полностью пересоздаём графовую проекцию из PostgreSQL.
        session.run("""
            MATCH (n)
            WHERE n:University OR n:Institute OR n:Department OR n:Specialty
               OR n:StudentGroup OR n:LectureCourse OR n:Lecture
               OR n:Student OR n:ClassSession
            DETACH DELETE n
        """).consume()
        session.run(course_query, rows=course_rows).consume()
        session.run(student_query, rows=student_rows).consume()
        session.run(session_query, rows=session_rows).consume()
        session.run(attendance_query, rows=attendance_rows).consume()
        
from uuid import UUID


def _mongo_safe(value):
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, dict):
        return {
            k: _mongo_safe(v)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [
            _mongo_safe(v)
            for v in value
        ]

    if isinstance(value, tuple):
        return [
            _mongo_safe(v)
            for v in value
        ]

    return value


def seed_mongodb_read_models(lectures: Any, hierarchies: Any, pg_config: dict[str, Any]) -> None:
    lecture_rows = _pg_rows(pg_config, """SELECT l.id lecture_id,l.title lecture_title,l.annotation,l.lecture_type,l.order_number,l.requires_tech,l.tech_comment,
      c.id course_id,c.name course_name,c.semester,COALESCE(jsonb_agg(jsonb_build_object('id',m.id,'content_type',m.content_type,'title',m.title,'content_text',m.content_text,'file_url',m.file_url,'metadata',m.metadata)) FILTER (WHERE m.id IS NOT NULL),'[]') materials
      FROM lectures l JOIN lecture_courses c ON c.id=l.course_id LEFT JOIN lecture_materials m ON m.lecture_id=l.id GROUP BY l.id,c.id""")
    lectures.delete_many({})

    lecture_rows = [_mongo_safe(doc) for doc in lecture_rows]
    if lecture_rows:
        lectures.insert_many([{**row, "course": {"course_id": row.pop("course_id"), "name": row.pop("course_name"), "semester": row.pop("semester")}, "updated_at": datetime.utcnow()} for row in lecture_rows])

    rows = _pg_rows(pg_config, """
        SELECT u.id university_id, u.name university_name, u.short_name university_short_name,
               i.id institute_id, i.name institute_name, i.short_name institute_short_name,
               d.id department_id, d.name department_name, d.short_name department_short_name,
               sp.id specialty_id, sp.name specialty_name, sp.code specialty_code,
               g.id group_id, g.name group_name, g.enrollment_year, g.curator
        FROM universities u
        JOIN institutes i ON i.university_id = u.id
        JOIN departments d ON d.institute_id = i.id
        LEFT JOIN department_specialties ds ON ds.department_id = d.id
        LEFT JOIN specialties sp ON sp.id = ds.specialty_id
        LEFT JOIN student_groups g ON g.department_id = d.id
    """)
    rows = [_mongo_safe(doc) for doc in rows]
    universities: dict[str, dict[str, Any]] = {}

    for row in rows:
        university = universities.setdefault(row["university_id"], {
            "university_id": row["university_id"], "name": row["university_name"],
            "short_name": row["university_short_name"], "institutes": {},
            "updated_at": datetime.utcnow(),
        })
        institute = university["institutes"].setdefault(row["institute_id"], {
            "id": row["institute_id"], "name": row["institute_name"],
            "short_name": row["institute_short_name"], "departments": {},
        })
        department = institute["departments"].setdefault(row["department_id"], {
            "id": row["department_id"], "name": row["department_name"],
            "short_name": row["department_short_name"], "specialties": {}, "groups": {},
        })
        if row["specialty_id"]:
            department["specialties"].setdefault(row["specialty_id"], {
                "id": row["specialty_id"], "name": row["specialty_name"],
                "code": row["specialty_code"],
            })
        if row["group_id"]:
            department["groups"].setdefault(row["group_id"], {
                "id": row["group_id"], "name": row["group_name"],
                "enrollment_year": row["enrollment_year"], "curator": row["curator"],
            })

    hierarchies.delete_many({})
    hierarchy_documents = []
    for university in universities.values():
        institutes = []
        for institute in university["institutes"].values():
            departments = []
            for department in institute["departments"].values():
                departments.append({
                    **department,
                    "specialties": list(department["specialties"].values()),
                    "groups": list(department["groups"].values()),
                })
            institutes.append({**institute, "departments": departments})
        hierarchy_documents.append({
            "university_id": university["university_id"], "name": university["name"],
            "short_name": university["short_name"], "institutes": institutes,
            "updated_at": university["updated_at"],
        })
    if hierarchy_documents:
        hierarchies.insert_many(hierarchy_documents)


def seed_elasticsearch_document(es: Any, index: str, pg_config: dict[str, Any]) -> None:
    rows = _pg_rows(pg_config, """SELECT l.id lecture_id,c.id course_id,c.name course_name,l.title,l.annotation,l.lecture_type,l.order_number,l.updated_at,
       COALESCE(string_agg(m.content_text, ' '), '') content_text,
       COALESCE(jsonb_agg(m.metadata) FILTER (WHERE m.id IS NOT NULL), '[]') AS metadata
       FROM lectures l JOIN lecture_courses c ON c.id=l.course_id LEFT JOIN lecture_materials m ON m.lecture_id=l.id GROUP BY l.id,c.id""")
    for row in rows:
        row["tags"] = sorted({tag for meta in row.pop("metadata") for tag in meta.get("tags", [])})
        row["updated_at"] = _json_safe(row["updated_at"])
        es.index(index=index, id=row["lecture_id"], document=row)
    es.indices.refresh(index=index)
