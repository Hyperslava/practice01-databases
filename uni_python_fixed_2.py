#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import redis
import pymongo
from neo4j import GraphDatabase
from elasticsearch import Elasticsearch
from psycopg import sql as pg_sql

from data_generators import (
    IDS,
)

from data_seeders import (
    seed_postgres_data,
    seed_redis_cache,
    seed_neo4j_graph,
    seed_mongodb_read_models,
    seed_elasticsearch_document,
)


def default_host() -> str:
    """Use Docker Desktop's Windows gateway when seeding from WSL."""
    if "microsoft" in Path("/proc/version").read_text(errors="ignore").lower():
        try:
            return subprocess.check_output(
                ["ip", "route", "show", "default"], text=True,
            ).split()[2]
        except (OSError, IndexError, subprocess.CalledProcessError):
            pass
    return "127.0.0.1"


HOST = default_host()

REDIS_HOST = os.getenv("REDIS_HOST", HOST)
REDIS_PORT = 6379
REDIS_PASSWORD = "mystrongredis"

MONGO_URI = os.getenv(
    "MONGO_URI",
    f"mongodb://appuser:appsecret@{HOST}:27017/?authSource=admin",
)
MONGO_DB = "university_system"

NEO4J_URI = os.getenv("NEO4J_URI", f"bolt://{HOST}:7687")
NEO4J_AUTH = (
    os.getenv("NEO4J_USER", "neo4j"),
    os.getenv("NEO4J_PASSWORD", "neo4jsecret"),
)

ES_URL = os.getenv("ES_URL", f"http://{HOST}:9200")

PG_CONFIG = {
    "dbname": os.getenv("PG_DATABASE", "university_system"),
    "user": os.getenv("PG_USER", "admin"),
    "password": os.getenv("PG_PASSWORD", "secret"),
    "host": os.getenv("PG_HOST", HOST),
    "port": int(os.getenv("PG_PORT", "5433")),
}



def print_rows(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("(нет строк)")
        return
    for row in rows:
        print(row)


def pg_query(cur: psycopg.Cursor, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    cur.execute(sql, params or ())
    if cur.description is None:
        return []
    columns = [d.name for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def create_postgres_database() -> None:
    """Создать рабочую БД, если её ещё нет."""
    admin_config = dict(PG_CONFIG)
    admin_config["dbname"] = "postgres"
    with psycopg.connect(**admin_config, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (PG_CONFIG["dbname"],),
            )
            if cur.fetchone() is None:
                cur.execute(
                    pg_sql.SQL("CREATE DATABASE {}").format(
                        pg_sql.Identifier(PG_CONFIG["dbname"])
                    )
                )


def create_postgres_schema(cur: psycopg.Cursor) -> None:
    cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    cur.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS universities (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(500) NOT NULL,
            short_name VARCHAR(100),
            address TEXT,
            website VARCHAR(255),
            founded_year INT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS institutes (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            university_id UUID NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
            name VARCHAR(500) NOT NULL,
            short_name VARCHAR(100),
            dean VARCHAR(300),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_institutes_university ON institutes(university_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            institute_id UUID NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
            name VARCHAR(500) NOT NULL,
            short_name VARCHAR(100),
            head VARCHAR(300),
            room VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_departments_institute ON departments(institute_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS specialties (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(500) NOT NULL,
            code VARCHAR(20) NOT NULL,
            degree_level VARCHAR(20) NOT NULL
                CHECK (degree_level IN ('bachelor', 'master', 'specialist')),
            duration_years INT NOT NULL DEFAULT 4,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_specialties_code ON specialties(code)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS department_specialties (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
            specialty_id UUID NOT NULL REFERENCES specialties(id) ON DELETE CASCADE,
            is_primary BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (department_id, specialty_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_dept_spec_department ON department_specialties(department_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_dept_spec_specialty ON department_specialties(specialty_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lecture_courses (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            specialty_id UUID NOT NULL REFERENCES specialties(id) ON DELETE CASCADE,
            reading_department_id UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
            name VARCHAR(500) NOT NULL,
            description TEXT,
            semester INT NOT NULL CHECK (semester BETWEEN 1 AND 12),
            total_hours INT NOT NULL,
            lecture_hours INT DEFAULT 0,
            practice_hours INT DEFAULT 0,
            lab_hours INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_courses_specialty ON lecture_courses(specialty_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_courses_reading_department ON lecture_courses(reading_department_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lectures (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            course_id UUID NOT NULL REFERENCES lecture_courses(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            annotation TEXT,
            lecture_type VARCHAR(20) NOT NULL
                CHECK (lecture_type IN ('lecture', 'practice', 'lab')),
            order_number INT NOT NULL,
            duration_minutes INT DEFAULT 90,
            requires_tech BOOLEAN NOT NULL DEFAULT FALSE,
            tech_comment TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lectures_course ON lectures(course_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lectures_type ON lectures(lecture_type)")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_lectures_fulltext_ru
        ON lectures USING GIN (
            to_tsvector('russian', COALESCE(title, '') || ' ' || COALESCE(annotation, ''))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lecture_materials (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            lecture_id UUID NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            content_type VARCHAR(50) NOT NULL
                CHECK (content_type IN ('text', 'presentation', 'pdf', 'video_link')),
            title VARCHAR(500),
            content_text TEXT,
            file_url VARCHAR(1000),
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_materials_lecture ON lecture_materials(lecture_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_materials_type ON lecture_materials(content_type)")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_materials_fulltext_ru
        ON lecture_materials USING GIN (to_tsvector('russian', COALESCE(content_text, '')))
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS student_groups (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            department_id UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
            specialty_id UUID NOT NULL REFERENCES specialties(id) ON DELETE CASCADE,
            name VARCHAR(50) NOT NULL UNIQUE,
            enrollment_year INT NOT NULL,
            curator VARCHAR(300),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_groups_department ON student_groups(department_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_groups_specialty ON student_groups(specialty_id)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS student_group_specialties (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            group_id UUID NOT NULL REFERENCES student_groups(id) ON DELETE CASCADE,
            specialty_id UUID NOT NULL REFERENCES specialties(id) ON DELETE CASCADE,
            is_primary BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (group_id, specialty_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sgs_group ON student_group_specialties(group_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sgs_specialty ON student_group_specialties(specialty_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            group_id UUID NOT NULL REFERENCES student_groups(id) ON DELETE CASCADE,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            patronymic VARCHAR(100),
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(20),
            student_card_number VARCHAR(20) UNIQUE,
            enrollment_date DATE NOT NULL,
            status VARCHAR(20) DEFAULT 'active'
                CHECK (status IN ('active', 'academic_leave', 'expelled', 'graduated')),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_students_group ON students(group_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_students_name ON students(last_name, first_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_students_status ON students(status)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            lecture_id UUID NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            scheduled_date DATE NOT NULL,
            week_start_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            classroom VARCHAR(50),
            teacher_name VARCHAR(300),
            status VARCHAR(20) DEFAULT 'scheduled'
                CHECK (status IN ('scheduled', 'completed', 'cancelled')),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (id, week_start_date)
        )
    """)
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(scheduled_date)",
        "CREATE INDEX IF NOT EXISTS idx_schedule_week ON schedule(week_start_date)",
        "CREATE INDEX IF NOT EXISTS idx_schedule_lecture ON schedule(lecture_id)",
    ):
        cur.execute(sql)
    # Одно занятие может быть назначено нескольким группам: потоковая лекция
    # или лабораторная работа.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schedule_groups (
            schedule_id UUID NOT NULL REFERENCES schedule(id) ON DELETE CASCADE,
            group_id UUID NOT NULL REFERENCES student_groups(id) ON DELETE CASCADE,
            PRIMARY KEY (schedule_id, group_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedule_groups_group ON schedule_groups(group_id)")

    cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id UUID NOT NULL DEFAULT uuid_generate_v4(),
                schedule_id UUID NOT NULL,
                student_id UUID NOT NULL,
                week_start_date DATE NOT NULL,
                is_present BOOLEAN NOT NULL DEFAULT FALSE,
                marked_at TIMESTAMP DEFAULT NOW(),
                marked_by VARCHAR(300),
                note VARCHAR(500),
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (id, week_start_date),
                CONSTRAINT fk_attendance_schedule
                    FOREIGN KEY (schedule_id, week_start_date)
                    REFERENCES schedule (id, week_start_date)
                    ON DELETE CASCADE,
                CONSTRAINT fk_attendance_student
                    FOREIGN KEY (student_id)
                    REFERENCES students (id)
                    ON DELETE CASCADE
            ) PARTITION BY RANGE (week_start_date)
    """)

    for start, end in (
        ("2026-02-09", "2026-02-16"),
        ("2026-02-16", "2026-02-23"),
        ("2026-02-23", "2026-03-02"),
        ("2026-03-02", "2026-03-09"),
        ("2026-03-09", "2026-03-16"),
        ("2026-03-16", "2026-03-23"),
    ):
        part = f"attendance_w{start.replace('-', '_')}"
        cur.execute(
            pg_sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} PARTITION OF attendance "
                "FOR VALUES FROM ({}) TO ({})"
            ).format(
                pg_sql.Identifier(part),
                pg_sql.Literal(start),
                pg_sql.Literal(end),
            )
        )

    for sql in (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_schedule_student ON attendance(schedule_id, student_id, week_start_date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_schedule ON attendance(schedule_id)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_present ON attendance(is_present)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_week ON attendance(week_start_date)",
    ):
        cur.execute(sql)

    cur.execute("""
        CREATE OR REPLACE VIEW v_full_schedule AS
        SELECT s.id AS schedule_id,
            s.scheduled_date, s.start_time, s.end_time,
            s.classroom, s.teacher_name,
            s.status AS schedule_status,
            l.title AS lecture_title, l.lecture_type,
            lc.name AS course_name, lc.semester,
            string_agg(DISTINCT sg.name, ', ' ORDER BY sg.name) AS group_name,
            sp.name AS specialty_name, sp.code AS specialty_code,
            d.name AS department_name, i.name AS institute_name,
            u.name AS university_name
        FROM schedule s
        JOIN lectures l ON s.lecture_id = l.id
        JOIN lecture_courses lc ON l.course_id = lc.id
        JOIN specialties sp ON lc.specialty_id = sp.id
        JOIN departments d ON d.id = lc.reading_department_id
        JOIN institutes i ON d.institute_id = i.id
        JOIN universities u ON i.university_id = u.id
        JOIN schedule_groups sgrp ON sgrp.schedule_id = s.id
        JOIN student_groups sg ON sg.id = sgrp.group_id
        GROUP BY s.id, s.scheduled_date, s.start_time, s.end_time,
            s.classroom, s.teacher_name, s.status, l.title, l.lecture_type,
            lc.name, lc.semester, sp.name, sp.code, d.name, i.name, u.name
    """)

    cur.execute("""
        CREATE OR REPLACE VIEW v_student_attendance_stats AS
        SELECT
            st.id AS student_id,
            st.last_name || ' ' || st.first_name AS student_name,
            sg.name AS group_name,
            COUNT(a.id) AS total_classes,
            COUNT(CASE WHEN a.is_present THEN 1 END) AS attended,
            COUNT(CASE WHEN NOT a.is_present THEN 1 END) AS missed,
            ROUND(
                COUNT(CASE WHEN a.is_present THEN 1 END)::NUMERIC /
                NULLIF(COUNT(a.id), 0) * 100, 1
            ) AS attendance_percentage
        FROM students st
        JOIN student_groups sg ON st.group_id = sg.id
        LEFT JOIN attendance a ON a.student_id = st.id
        GROUP BY st.id, st.last_name, st.first_name, sg.name
    """)


def run_postgres_queries(cur: psycopg.Cursor) -> None:
    print_rows(
        "PG: v_full_schedule for 2026-03-09",
        pg_query(cur, "SELECT * FROM v_full_schedule WHERE scheduled_date = %s", ("2026-03-09",)),
    )
    print_rows("PG: v_student_attendance_stats", pg_query(cur, "SELECT * FROM v_student_attendance_stats"))

    print_rows(
        "1. Расписание группы на дату с занятиями",
        pg_query(cur, """
            SELECT * FROM v_full_schedule
            WHERE group_name = %s AND scheduled_date = %s
        """, ("ИКБО-01-23", "2026-03-09")),
    )
    print_rows(
        "1a. Посещаемость группы за неделю",
        pg_query(cur, """
            SELECT st.last_name || ' ' || st.first_name AS student,
                   st.student_card_number,
                   s.scheduled_date, l.title AS lecture, a.is_present
            FROM attendance a
            JOIN schedule s ON a.schedule_id = s.id
            JOIN lectures l ON s.lecture_id = l.id
            JOIN students st ON a.student_id = st.id
            JOIN student_groups sg ON st.group_id = sg.id
            WHERE a.week_start_date = %s
              AND sg.name = %s
            ORDER BY s.scheduled_date, s.start_time, st.last_name
        """, ("2026-03-09", "ИКБО-01-23")),
    )
    print_rows(
        "2. Все лабораторные работы",
        pg_query(cur, """
            SELECT l.title, lc.name AS course, l.order_number
            FROM lectures l
            JOIN lecture_courses lc ON l.course_id = lc.id
            WHERE l.lecture_type = 'lab'
            ORDER BY l.order_number
        """),
    )
    print_rows(
        "3. Посещаемость группы за семестр",
        pg_query(cur, """
            SELECT student_name, attendance_percentage
            FROM v_student_attendance_stats
            WHERE group_name = %s
            ORDER BY attendance_percentage DESC
        """, ("ИКБО-01-23",)),
    )
    print_rows(
        "4. Иерархия специальностей института",
        pg_query(cur, """
            SELECT sp.code, sp.name AS specialty,
                   d.name AS department, ds.is_primary
            FROM specialties sp
            JOIN department_specialties ds ON sp.id = ds.specialty_id
            JOIN departments d ON ds.department_id = d.id
            JOIN institutes i ON d.institute_id = i.id
            WHERE i.short_name = %s
        """, ("ИИТ",)),
    )
    print_rows(
        "5. Специальности учебной группы",
        pg_query(cur, """
            SELECT sg.name AS group_name, sp.code,
                   sp.name AS specialty, sgs.is_primary
            FROM student_group_specialties sgs
            JOIN student_groups sg ON sg.id = sgs.group_id
            JOIN specialties sp ON sp.id = sgs.specialty_id
            WHERE sg.id = %s
        """, (IDS["group"],)),
    )

def run_postgres() -> None:
    print("\n============================================================")
    print("== PostgreSQL: схема, генерация fixture-данных, запросы")
    print("============================================================")

    prepare_postgres_source()
    db_config = university_pg_config()
    with psycopg.connect(**db_config) as conn:
        with conn.cursor() as cur:
            run_postgres_queries(cur)


def university_pg_config() -> dict[str, Any]:
    return dict(PG_CONFIG)


def prepare_postgres_source() -> None:
    create_postgres_database()
    with psycopg.connect(**university_pg_config()) as conn:
        with conn.cursor() as cur:
            create_postgres_schema(cur)
            seed_postgres_data(cur)
        conn.commit()

# ---------------------------------------------------------------------------
# 2. Redis
# ---------------------------------------------------------------------------
def redis_lab1_report(
    r: redis.Redis,
    attendance_stats: list[dict[str, Any]],
    period_from: date,
    period_to: date,
    term: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stat in attendance_stats:
        student_id = str(stat["student_id"])
        profile = r.hgetall(f"students_cache:{student_id}")
        if not profile:
            continue
        rows.append({
            **profile,
            "planned_classes": stat["planned_classes"],
            "attended_classes": stat["attended_classes"],
            "attendance_percent": float(stat["attendance_percent"]),
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
            "search_term": term,
        })
    return rows


def run_redis(prepare_source: bool = True) -> None:
    print("\n============================================================")
    print("== Redis: кэш студентов и состава групп")
    print("============================================================")

    if prepare_source:
        prepare_postgres_source()
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )
    try:
        seed_redis_cache(r, university_pg_config())
        print("GET student cache:", r.hgetall(f"students_cache:{IDS['student_1']}"))
        print("SCARD students_cache:all:", r.scard("students_cache:all"))
    finally:
        r.close()


def search_lecture_ids(es: Elasticsearch, index_name: str, term: str) -> list[str]:
    """Только полнотекстовая часть ЛР1: Elasticsearch → идентификаторы лекций."""
    response = es.search(
        index=index_name,
        size=1_000,
        query={
            "bool": {
                "must": [{
                    "multi_match": {
                        "query": term,
                        "fields": ["title^3", "annotation^2", "content_text"],
                    }
                }],
                "filter": [{"term": {"lecture_type": "lecture"}}],
            }
        },
    )
    return [hit["_source"]["lecture_id"] for hit in response.body["hits"]["hits"]]


def lab1_expected_student_sessions_from_neo4j(
    lecture_ids: list[str],
    period_from: date,
    period_to: date,
) -> list[dict[str, Any]]:
    """Один обход графа: кому назначено каждое найденное занятие."""
    if not lecture_ids:
        return []
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        return neo4j_execute(driver, """
            MATCH (l:Lecture)-[:HELD_AS]->(s:ClassSession)-[:FOR_GROUP]->(g:StudentGroup)
            MATCH (st:Student)-[:MEMBER_OF]->(g)
            WHERE l.id IN $lecture_ids
              AND l.lecture_type = 'lecture'
              AND s.scheduled_date >= $period_from
              AND s.scheduled_date <= $period_to
            RETURN DISTINCT st.id AS student_id, s.id AS session_id
        """, {
            "lecture_ids": lecture_ids,
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
        })
    finally:
        driver.close()


def lab1_attendance_stats_from_postgres(
    expected_student_sessions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Считает посещаемость только по составу пар, полученному из Neo4j."""
    if not expected_student_sessions:
        return []
    assignments_json = json.dumps(expected_student_sessions)
    with psycopg.connect(**university_pg_config()) as conn:
        with conn.cursor() as cur:
            return pg_query(cur, """
                WITH graph_assignments AS (
                    SELECT DISTINCT
                        (item ->> 'student_id')::uuid AS student_id,
                        (item ->> 'session_id')::uuid AS session_id
                    FROM jsonb_array_elements(%s::jsonb) AS item
                ), ranked AS (
                    SELECT ga.student_id,
                        COUNT(*) AS planned_classes,
                        COUNT(a.id) FILTER (WHERE a.is_present) AS attended_classes,
                        ROUND(
                            100.0 * COUNT(a.id) FILTER (WHERE a.is_present)
                            / NULLIF(COUNT(*), 0), 1
                        ) AS attendance_percent
                    FROM graph_assignments ga
                    LEFT JOIN attendance a
                        ON a.schedule_id = ga.session_id AND a.student_id = ga.student_id
                    GROUP BY ga.student_id
                )
                SELECT *
                FROM ranked
                ORDER BY attendance_percent NULLS FIRST, student_id
                LIMIT 10
            """, (assignments_json,))


def run_lab1(term: str, period_from: date, period_to: date) -> None:
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )
    es = Elasticsearch(ES_URL)
    try:
        lecture_ids = search_lecture_ids(es, "lectures", term)
        expected_student_sessions = lab1_expected_student_sessions_from_neo4j(
            lecture_ids, period_from, period_to,
        )
        attendance_stats = lab1_attendance_stats_from_postgres(
            expected_student_sessions,
        )
        print_rows(
            "ЛР1: 10 студентов с минимальной посещаемостью",
            redis_lab1_report(r, attendance_stats, period_from, period_to, term),
        )
    finally:
        r.close()
        es.close()


def neo4j_execute(driver: Any, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with driver.session() as session:
        result = session.run(cypher, params or {})
        return [record.data() for record in result]


def run_neo4j_queries(driver: Any) -> None:
    queries = [
        ("1. Курс и его занятия", """
            MATCH (c:LectureCourse {id: $course_id})-[:HAS_LECTURE]->(l:Lecture)
            RETURN c.name AS course, c.semester AS semester,
                   l.title AS lecture, l.lecture_type AS type
            ORDER BY l.title
        """, {"course_id": IDS["course"]}),
        ("2. Проведённые занятия курса за период", """
            MATCH (c:LectureCourse {id: $course_id})-[:HAS_LECTURE]->(:Lecture)
                -[:HELD_AS]->(s:ClassSession)-[:FOR_GROUP]->(g:StudentGroup)
            WHERE s.scheduled_date >= $period_from
              AND s.scheduled_date <= $period_to
            RETURN s.scheduled_date AS date, g.name AS group,
                   s.classroom AS classroom, s.status AS status
            ORDER BY date
        """, {"course_id": IDS["course"], "period_from": "2026-02-09", "period_to": "2026-03-22"}),
        ("3. ЛР1: кто должен был быть на лекциях по курсу за период", """
            MATCH (c:LectureCourse {id: $course_id})-[:HAS_LECTURE]->(l:Lecture {lecture_type: 'lecture'})
                -[:HELD_AS]->(s:ClassSession)-[:FOR_GROUP]->(g:StudentGroup)
            MATCH (st:Student)-[:MEMBER_OF]->(g)
            WHERE s.scheduled_date >= $period_from
              AND s.scheduled_date <= $period_to
            RETURN s.scheduled_date AS date, l.title AS lecture, g.name AS group,
                   st.last_name + ' ' + st.first_name AS student,
                   st.student_card_number AS student_card_number
            ORDER BY date, lecture, student
        """, {"course_id": IDS["course"], "period_from": "2026-02-09", "period_to": "2026-03-22"}),
        ("4. ЛР1: плановая и фактическая посещаемость занятий", """
            MATCH (c:LectureCourse {id: $course_id})-[:HAS_LECTURE]->(l:Lecture {lecture_type: 'lecture'})
                -[:HELD_AS]->(s:ClassSession)-[:FOR_GROUP]->(g:StudentGroup)
            MATCH (st:Student)-[:MEMBER_OF]->(g)
            WHERE s.scheduled_date >= $period_from
              AND s.scheduled_date <= $period_to
            OPTIONAL MATCH (st)-[a:ATTENDED]->(s)
            RETURN s.scheduled_date AS date, l.title AS lecture,
                   st.last_name + ' ' + st.first_name AS student,
                   a IS NOT NULL AS attended, a.marked_at AS marked_at
            ORDER BY date, lecture, student
        """, {"course_id": IDS["course"], "period_from": "2026-02-09", "period_to": "2026-03-22"}),
    ]
    for title, query, params in queries:
        print_rows(f"Neo4j {title}", neo4j_execute(driver, query, params))


def run_neo4j(prepare_source: bool = True) -> None:
    print("\n============================================================")
    print("== Neo4j: академическая graph read-model")
    print("============================================================")
    if prepare_source:
        prepare_postgres_source()
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        seed_neo4j_graph(driver, university_pg_config())
        run_neo4j_queries(driver)
    finally:
        driver.close()

# ---------------------------------------------------------------------------
# 4. MongoDB
# ---------------------------------------------------------------------------
def run_mongodb_queries(
    lecture_collection: Any,
    hierarchy_collection: Any,
) -> None:
    print(
        "1. Страница лекции:",
        lecture_collection.find_one({"lecture_id": IDS["lecture_3"]}),
    )
    print_rows(
        "2. Лекции курса",
        list(lecture_collection.find(
            {"course.course_id": IDS["course"]},
            {"lecture_title": 1, "lecture_type": 1, "course": 1, "updated_at": 1},
        )),
    )
    print_rows(
        "3. Лекции с PDF",
        list(lecture_collection.find(
            {"materials.content_type": "pdf"},
            {"lecture_title": 1, "materials": 1},
        )),
    )
    print_rows(
        "4. Иерархия университета",
        list(hierarchy_collection.find(
            {"university_id": IDS["university"]},
            {"name": 1, "short_name": 1, "institutes": 1, "updated_at": 1},
        )),
    )


def run_mongodb(prepare_source: bool = True) -> None:
    print("\n============================================================")
    print("== MongoDB: read-model лекций и иерархии")
    print("============================================================")
    if prepare_source:
        prepare_postgres_source()
    client = pymongo.MongoClient(MONGO_URI)
    try:
        db = client[MONGO_DB]
        lecture_collection = db["lecture_read_model"]
        hierarchy_collection = db["university_hierarchy_read_model"]
        seed_mongodb_read_models(lecture_collection, hierarchy_collection, university_pg_config())
        run_mongodb_queries(lecture_collection, hierarchy_collection)
    finally:
        client.close()

# ---------------------------------------------------------------------------
# 5. Elasticsearch
# ---------------------------------------------------------------------------
def build_elasticsearch_mapping() -> dict[str, Any]:
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "russian_custom": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "russian_stop", "russian_stemmer"],
                    }
                },
                "filter": {
                    "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                    "russian_stemmer": {"type": "stemmer", "language": "russian"},
                },
            },
        },
        "mappings": {
            "properties": {
                "lecture_id": {"type": "keyword"},
                "course_id": {"type": "keyword"},
                "course_name": {"type": "text", "analyzer": "russian_custom",
                                "fields": {"keyword": {"type": "keyword"}}},
                "title": {"type": "text", "analyzer": "russian_custom",
                          "fields": {"keyword": {"type": "keyword"}}},
                "annotation": {"type": "text", "analyzer": "russian_custom"},
                "content_text": {"type": "text", "analyzer": "russian_custom"},
                "lecture_type": {"type": "keyword"},
                "order_number": {"type": "integer"},
                "tags": {"type": "keyword"},
                "updated_at": {"type": "date"},
            }
        },
    }


def recreate_elasticsearch_index(es: Elasticsearch, index_name: str) -> None:
    es.indices.delete(index=index_name, ignore_unavailable=True)
    es.indices.create(index=index_name, **build_elasticsearch_mapping())


def run_elasticsearch_queries(es: Elasticsearch, index_name: str) -> None:
    response = es.search(
        index=index_name,
        query={"multi_match": {
            "query": "паттерны проектирования singleton",
            "fields": ["title^3", "annotation^2", "content_text"],
            "type": "best_fields",
            "fuzziness": "AUTO",
        }},
        highlight={"fields": {
            "content_text": {"fragment_size": 200, "number_of_fragments": 3},
            "annotation": {},
        }},
    )
    print("1. Полнотекстовый поиск:", response.body)

    response = es.search(
        index=index_name,
        query={"bool": {
            "must": [{"match": {"content_text": "Docker"}}],
            "filter": [{"term": {"lecture_type": "lab"}}],
        }},
    )
    print("2. Лабораторные по Docker:", response.body)

    response = es.search(
        index=index_name,
        query={"bool": {
            "must": [{"match": {"annotation": "паттерны проектирования"}}],
            "filter": [{"term": {"course_name.keyword": "Проектирование архитектуры ПО"}}],
        }},
    )
    print("3. По аннотациям + фильтр курса:", response.body)

    response = es.search(
        index=index_name,
        size=0,
        aggs={"by_type": {
            "terms": {"field": "lecture_type"},
            "aggs": {"by_course": {"terms": {"field": "course_name.keyword"}}},
        }},
    )
    print("4. Агрегация по типам и курсам:", response.body)


def run_elasticsearch(prepare_source: bool = True) -> None:
    print("\n============================================================")
    print("== ElasticSearch: индекс lectures, документ, поисковые запросы")
    print("============================================================")
    if prepare_source:
        prepare_postgres_source()
    es = Elasticsearch(ES_URL)
    index_name = "lectures"
    recreate_elasticsearch_index(es, index_name)
    seed_elasticsearch_document(es, index_name, university_pg_config())
    run_elasticsearch_queries(es, index_name)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Python-версия запросов из uni.txt")
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["postgres", "redis", "neo4j", "mongodb", "elasticsearch", "lab1", "all"],
    )
    parser.add_argument("--term", default="база данных", help="Термин или фраза для ЛР1")
    parser.add_argument("--from-date", default="2026-02-09", help="Начало периода ЛР1, YYYY-MM-DD")
    parser.add_argument("--to-date", default="2026-03-22", help="Конец периода ЛР1, YYYY-MM-DD")
    args = parser.parse_args()

    handlers = {
        "postgres": run_postgres,
        "redis": run_redis,
        "neo4j": run_neo4j,
        "mongodb": run_mongodb,
        "elasticsearch": run_elasticsearch,
        "lab1": lambda: run_lab1(
            args.term,
            date.fromisoformat(args.from_date),
            date.fromisoformat(args.to_date),
        ),
    }

    if args.target == "all":
        run_postgres()
        run_redis(prepare_source=False)
        run_neo4j(prepare_source=False)
        run_mongodb(prepare_source=False)
        run_elasticsearch(prepare_source=False)
    else:
        handlers[args.target]()


if __name__ == "__main__":
    main()

