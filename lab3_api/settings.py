from __future__ import annotations

import os


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


REDIS_CONFIG = {
    "host": env("REDIS_HOST", "localhost"),
    "port": int(env("REDIS_PORT", "6379")),
    "password": env("REDIS_PASSWORD", "mystrongredis"),
    "decode_responses": True,
}
MONGO_URI = env("MONGO_URI", "mongodb://appuser:appsecret@localhost:27017/")
MONGO_DB = env("MONGO_DB", "university_system")
NEO4J_URI = env("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = env("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = env("NEO4J_PASSWORD", "neo4jsecret")
GATEWAY_SERVICE_TOKEN = env("GATEWAY_SERVICE_TOKEN", "lab1-internal-token")
LAB3_LOG_PATH = env("LAB3_LOG_PATH", "/app/logs/lab3_pipeline.log")
