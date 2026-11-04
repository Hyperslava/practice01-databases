"""ЛР №3: Neo4j (выпускающая кафедра и часы) → Redis (профили)."""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import redis
import pymongo
from neo4j import GraphDatabase

from settings import (
    LAB3_LOG_PATH, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER,
    MONGO_DB, MONGO_URI, REDIS_CONFIG,
)


logger = logging.getLogger("lab3.pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    Path(LAB3_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LAB3_LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def _student_course_hours(
    group_id: str, period_from: date, period_to: date,
) -> list[dict[str, Any]]:
    """Neo4j отбирает курсы выпускающей кафедры и сопоставляет посещение."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (g:StudentGroup {id: $group_id})
                      -[:GRADUATED_BY]->(d:Department)
                MATCH (st:Student)-[:MEMBER_OF]->(g)
                MATCH (d)-[:TEACHES]->(c:LectureCourse)
                      -[:HAS_LECTURE]->(l:Lecture)
                      -[:HELD_AS]->(s:ClassSession)-[:FOR_GROUP]->(g)
                WHERE l.lecture_type = 'lecture'
                  AND s.scheduled_date >= $period_from
                  AND s.scheduled_date <= $period_to
                OPTIONAL MATCH (st)-[a:ATTENDED]->(s)
                WITH g, st, c, s, COUNT(a) AS attendance_marks
                RETURN g.id AS group_id,
                       g.name AS group_name,
                       st.id AS student_id,
                       st.last_name AS student_last_name,
                       st.first_name AS student_first_name,
                       c.id AS course_id,
                       c.name AS course_name,
                       COUNT(DISTINCT s) * 2 AS planned_hours,
                       SUM(CASE WHEN attendance_marks > 0 THEN 2 ELSE 0 END) AS attended_hours
                ORDER BY student_last_name, student_first_name, course_name
            """, {
                "group_id": group_id,
                "period_from": period_from.isoformat(),
                "period_to": period_to.isoformat(),
            })
            return [record.data() for record in result]
    finally:
        driver.close()


def _profiles(student_ids: list[str]) -> dict[str, dict[str, Any]]:
    client = redis.Redis(**REDIS_CONFIG)
    try:
        pipe = client.pipeline(transaction=False)
        for student_id in student_ids:
            pipe.hgetall(f"students_cache:{student_id}")
        raw_profiles = pipe.execute()
    finally:
        client.close()

    profiles: dict[str, dict[str, Any]] = {}
    for student_id, profile in zip(student_ids, raw_profiles):
        if not profile:
            raise RuntimeError(f"Redis profile is missing for student {student_id}")
        for field in ("courses",):
            profile[field] = json.loads(profile[field])
        profiles[student_id] = profile
    return profiles


def _organization_for_group(group_id: str) -> dict[str, dict[str, str]]:
    """MongoDB — документная иерархия университета для указанной группы."""
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
    try:
        document = client[MONGO_DB]["university_hierarchy_read_model"].find_one(
            {"institutes.departments.groups.id": group_id},
            {"_id": False},
        )
    finally:
        client.close()
    if document is None:
        raise RuntimeError(
            f"MongoDB organization is missing for group {group_id}; "
            "run the MongoDB seeder after loading PostgreSQL data"
        )

    for institute in document["institutes"]:
        for department in institute["departments"]:
            if any(group["id"] == group_id for group in department["groups"]):
                return {
                    "university": {
                        "id": document["university_id"], "name": document["name"],
                        "short_name": document["short_name"],
                    },
                    "institute": {
                        "id": institute["id"], "name": institute["name"],
                        "short_name": institute["short_name"],
                    },
                    "department": {
                        "id": department["id"], "name": department["name"],
                        "short_name": department["short_name"],
                    },
                }
    raise RuntimeError(f"MongoDB group path is inconsistent for group {group_id}")


def build_lab3_report(group_id: str, period_from: date, period_to: date) -> dict[str, Any]:
    if period_from > period_to:
        raise ValueError("period_from must not be after period_to")
    logger.info("LAB3 started: group_id=%s period=%s..%s", group_id, period_from, period_to)
    try:
        rows = _student_course_hours(group_id, period_from, period_to)
        logger.info("Step 1 Neo4j: graduating-department student_course_rows=%d", len(rows))

        student_ids = list(dict.fromkeys(row["student_id"] for row in rows))
        profiles = _profiles(student_ids)
        logger.info("Step 2 Redis: hydrated_profiles=%d", len(profiles))

        organization = _organization_for_group(group_id)
        logger.info("Step 3 MongoDB: organization loaded for group=%s", group_id)
    except Exception:
        logger.exception("LAB3 failed")
        raise

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        profile = {**profiles[row["student_id"]], "organization": organization}
        course_by_id = {str(course["course_id"]): course for course in profile["courses"]}
        course = course_by_id.get(row["course_id"], {
            "course_id": row["course_id"], "name": row["course_name"],
        })
        student = grouped.setdefault(row["student_id"], {
            "student": profile,
            "courses": [],
        })
        student["courses"].append({
            "course": course,
            "planned_hours": row["planned_hours"],
            "attended_hours": row["attended_hours"],
        })

    group = (
        {"id": group_id, "name": rows[0]["group_name"], "organization": organization}
        if rows else {"id": group_id}
    )
    return {"group": group, "students": list(grouped.values())}
