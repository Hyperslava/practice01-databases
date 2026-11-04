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

NEO4J_URI = env("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = env("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = env("NEO4J_PASSWORD", "neo4jsecret")
GATEWAY_SERVICE_TOKEN = env("GATEWAY_SERVICE_TOKEN", "lab1-internal-token")
LAB2_LOG_PATH = env("LAB2_LOG_PATH", "/app/logs/lab2_pipeline.log")
