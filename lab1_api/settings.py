"""Единые подключения для API ЛР №1.

Значения по умолчанию совпадают с uni_python_fixed_2.py; в контейнере их
переопределяют переменные окружения из docker-compose.lab1.yml.
"""
from __future__ import annotations

import os


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


PG_CONFIG = {
    "dbname": env("PG_DATABASE", "university_system"),
    "user": env("PG_USER", "admin"),
    "password": env("PG_PASSWORD", "secret"),
    "host": env("PG_HOST", "127.0.0.1"),
    "port": int(env("PG_PORT", "5433")),
}

REDIS_CONFIG = {
    "host": env("REDIS_HOST", "localhost"),
    "port": int(env("REDIS_PORT", "6379")),
    "password": env("REDIS_PASSWORD", "mystrongredis"),
    "decode_responses": True,
}

ES_URL = env("ES_URL", "http://localhost:9200")
ES_INDEX = env("ES_INDEX", "lectures")
LAB1_LOG_PATH = env("LAB1_LOG_PATH", "/app/logs/lab1_pipeline.log")

NEO4J_URI = env("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = env("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = env("NEO4J_PASSWORD", "neo4jsecret")

JWT_SECRET = env("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = int(env("JWT_TTL_MINUTES", "30"))
GATEWAY_SERVICE_TOKEN = env("GATEWAY_SERVICE_TOKEN", "lab1-internal-token")
LAB1_SERVICE_URL = env("LAB1_SERVICE_URL", "http://lab1-service:8001")
LAB2_SERVICE_URL = env("LAB2_SERVICE_URL", "http://lab2-service:8000")
LAB3_SERVICE_URL = env("LAB3_SERVICE_URL", "http://lab3-service:8000")
DEMO_USERNAME = env("DEMO_USERNAME", "teacher")
DEMO_PASSWORD = env("DEMO_PASSWORD", "teacher-secret")
