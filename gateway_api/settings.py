"""Настройки общего API Gateway: без подключений к СУБД."""
from __future__ import annotations

import os


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


JWT_SECRET = env("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = int(env("JWT_TTL_MINUTES", "30"))
GATEWAY_SERVICE_TOKEN = env("GATEWAY_SERVICE_TOKEN", "lab1-internal-token")

LAB1_SERVICE_URL = env("LAB1_SERVICE_URL", "http://lab1-service:8000")
LAB2_SERVICE_URL = env("LAB2_SERVICE_URL", "http://lab2-service:8000")
LAB3_SERVICE_URL = env("LAB3_SERVICE_URL", "http://lab3-service:8000")

DEMO_USERNAME = env("DEMO_USERNAME", "teacher")
DEMO_PASSWORD = env("DEMO_PASSWORD", "teacher-secret")
