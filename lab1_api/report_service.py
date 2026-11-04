"""Аналитический конвейер ЛР №1: Elasticsearch → Neo4j → PostgreSQL → Redis."""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import redis
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from psycopg.rows import dict_row

from settings import (
    ES_INDEX, ES_URL, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER,
    LAB1_LOG_PATH, PG_CONFIG, REDIS_CONFIG,
)


logger = logging.getLogger("lab1.pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    Path(LAB1_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LAB1_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
    ))
    logger.addHandler(file_handler)
    logger.propagate = False


def _search_lecture_ids(term: str) -> list[str]:
    """Полнотекстовый поиск фразы только в Elasticsearch."""
    client = Elasticsearch(ES_URL)
    try:
        response = client.search(
            index=ES_INDEX,
            size=1_000,
            query={
                "bool": {
                    "must": [{"multi_match": {
                        "query": term,
                        "fields": ["title^3", "annotation^2", "content_text"],
                    }}],
                    "filter": [{"term": {"lecture_type": "lecture"}}],
                }
            },
        )
        return [hit["_source"]["lecture_id"] for hit in response.body["hits"]["hits"]]
    finally:
        client.close()


def _expected_student_sessions(
    lecture_ids: list[str], period_from: date, period_to: date,
) -> list[dict[str, Any]]:
    """Neo4j возвращает пары студент–занятие, запланированные для его группы."""
    if not lecture_ids:
        return []
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            result = session.run("""
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
            return [record.data() for record in result]
    finally:
        driver.close()


def _rank_student_ids(expected_student_sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PostgreSQL считает процент по парам студент–занятие из Neo4j."""
    if not expected_student_sessions:
        return []
    sql = """
        WITH graph_assignments AS (
            SELECT DISTINCT
                (item ->> 'student_id')::uuid AS student_id,
                (item ->> 'session_id')::uuid AS session_id
            FROM jsonb_array_elements(%s::jsonb) AS item
        ), ranked AS (
            SELECT ga.student_id,
                   COUNT(*) AS planned_classes,
                   COUNT(a.id) FILTER (WHERE a.is_present) AS attended_classes,
                   ROUND(100.0 * COUNT(a.id) FILTER (WHERE a.is_present)
                         / NULLIF(COUNT(*), 0), 1) AS attendance_percent
            FROM graph_assignments ga
            LEFT JOIN attendance a
                ON a.schedule_id = ga.session_id AND a.student_id = ga.student_id
            GROUP BY ga.student_id
        )
        SELECT * FROM ranked
        ORDER BY attendance_percent NULLS FIRST, student_id
        LIMIT 10
    """
    with psycopg.connect(**PG_CONFIG, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (json.dumps(expected_student_sessions),))
            return list(cur.fetchall())


def _profile_students(stats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Получает полные денормализованные карточки только из Redis HASH."""
    client = redis.Redis(**REDIS_CONFIG)
    try:
        pipe = client.pipeline(transaction=False)
        for stat in stats:
            pipe.hgetall(f"students_cache:{stat['student_id']}")
        profiles = pipe.execute()
    finally:
        client.close()

    result: list[dict[str, Any]] = []
    for stat, profile in zip(stats, profiles):
        if not profile:
            # Read-model не синхронизирован, поэтому не выдаём неполный отчёт.
            raise RuntimeError(f"Redis profile is missing for student {stat['student_id']}")
        for field in ("courses",):
            profile[field] = json.loads(profile[field])
        result.append({
            **profile,
            "planned_classes": int(stat["planned_classes"]),
            "attended_classes": int(stat["attended_classes"]),
            "attendance_percent": float(stat["attendance_percent"]),
        })
    return result


def build_lab1_report(term: str, period_from: date, period_to: date) -> dict[str, Any]:
    """Формирует краткий пользовательский отчёт; техническую трассу пишет в лог."""
    if period_from > period_to:
        raise ValueError("period_from must not be after period_to")
    logger.info(
        "LAB1 started: term=%r period=%s..%s",
        term, period_from.isoformat(), period_to.isoformat(),
    )
    try:
        lecture_ids = _search_lecture_ids(term)
        logger.info("Step 1 Elasticsearch: lecture_ids=%s count=%d", lecture_ids, len(lecture_ids))

        expected_student_sessions = _expected_student_sessions(lecture_ids, period_from, period_to)
        logger.info(
            "Step 2 Neo4j: student_session_pairs=%d unique_students=%d",
            len(expected_student_sessions),
            len({row["student_id"] for row in expected_student_sessions}),
        )

        stats = _rank_student_ids(expected_student_sessions)
        logger.info("Step 3 PostgreSQL: bottom_students=%s", [
            {"student_id": str(row["student_id"]), "percent": float(row["attendance_percent"])}
            for row in stats
        ])

        students = _profile_students(stats)
        logger.info("Step 4 Redis: hydrated_profiles=%d", len(students))
    except Exception:
        logger.exception("LAB1 failed")
        raise

    return {
        "students": [
            {
                "first_name": student["first_name"],
                "last_name": student["last_name"],
                "attendance_percent": student["attendance_percent"],
            }
            for student in students
        ]
    }
