"""ЛР №2: PostgreSQL (занятия с техникой) → Neo4j (вместимость потока)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import psycopg
from neo4j import GraphDatabase
from psycopg.rows import dict_row

from settings import LAB2_LOG_PATH, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER, PG_CONFIG


logger = logging.getLogger("lab2.pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    Path(LAB2_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LAB2_LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def _technical_sessions(course_id: str, semester: int, year: int) -> list[dict[str, Any]]:
    """PostgreSQL — источник расписания и полной карточки курса/лекции."""
    sql = """
        SELECT
            s.id AS session_id, s.scheduled_date, s.start_time, s.end_time,
            s.classroom, s.teacher_name, s.status,
            c.id AS course_id, c.name AS course_name, c.description AS course_description,
            c.semester, c.total_hours, c.lecture_hours, c.practice_hours, c.lab_hours,
            l.id AS lecture_id, l.title AS lecture_title, l.annotation AS lecture_annotation,
            l.lecture_type, l.order_number, l.duration_minutes,
            l.requires_tech, l.tech_comment
        FROM lecture_courses c
        JOIN lectures l ON l.course_id = c.id
        JOIN schedule s ON s.lecture_id = l.id
        WHERE c.id = %s::uuid
          AND c.semester = %s
          AND l.requires_tech = TRUE
          AND s.status <> 'cancelled'
          AND s.scheduled_date >= make_date(%s, 1, 1)
          AND s.scheduled_date < make_date(%s + 1, 1, 1)
        ORDER BY s.scheduled_date, s.start_time, l.order_number
    """
    with psycopg.connect(**PG_CONFIG, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (course_id, semester, year, year))
            return list(cur.fetchall())


def _room_capacities(session_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Neo4j — занятие → все группы потока ← активные студенты."""
    if not session_ids:
        return {}
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            result = session.run("""
                UNWIND $session_ids AS session_id
                MATCH (s:ClassSession {id: session_id})-[:FOR_GROUP]->(g:StudentGroup)
                OPTIONAL MATCH (st:Student)-[:MEMBER_OF]->(g)
                RETURN s.id AS session_id,
                       collect(DISTINCT {id: g.id, name: g.name}) AS groups,
                       COUNT(DISTINCT CASE WHEN st.status = 'active' THEN st END)
                           AS listeners_count
            """, {"session_ids": session_ids})
            return {record["session_id"]: record.data() for record in result}
    finally:
        driver.close()


def build_lab2_report(course_id: str, semester: int, year: int) -> dict[str, Any]:
    logger.info("LAB2 started: course_id=%s semester=%d year=%d", course_id, semester, year)
    try:
        sessions = _technical_sessions(course_id, semester, year)
        logger.info("Step 1 PostgreSQL: technical_sessions=%d", len(sessions))

        capacities = _room_capacities([str(row["session_id"]) for row in sessions])
        logger.info("Step 2 Neo4j: capacities=%d", len(capacities))
    except Exception:
        logger.exception("LAB2 failed")
        raise

    report_rows = []
    for row in sessions:
        capacity = capacities.get(str(row["session_id"]))
        if capacity is None:
            raise RuntimeError(f"Neo4j session projection is missing: {row['session_id']}")
        report_rows.append({
            "course": {
                "id": str(row["course_id"]), "name": row["course_name"],
                "description": row["course_description"], "semester": row["semester"],
                "total_hours": row["total_hours"], "lecture_hours": row["lecture_hours"],
                "practice_hours": row["practice_hours"], "lab_hours": row["lab_hours"],
            },
            "lecture": {
                "id": str(row["lecture_id"]), "title": row["lecture_title"],
                "annotation": row["lecture_annotation"], "type": row["lecture_type"],
                "order_number": row["order_number"], "duration_minutes": row["duration_minutes"],
                "technical_requirements": row["tech_comment"],
            },
            "session": {
                "id": str(row["session_id"]), "date": row["scheduled_date"].isoformat(),
                "start_time": str(row["start_time"]), "end_time": str(row["end_time"]),
                "classroom": row["classroom"], "teacher": row["teacher_name"],
                "groups": capacity["groups"],
            },
            "required_room_capacity": capacity["listeners_count"],
        })
    return {"sessions": report_rows}
