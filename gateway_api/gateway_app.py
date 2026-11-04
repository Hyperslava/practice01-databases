from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from settings import (
    DEMO_PASSWORD, DEMO_USERNAME, GATEWAY_SERVICE_TOKEN, JWT_ALGORITHM,
    JWT_SECRET, JWT_TTL_MINUTES, LAB1_SERVICE_URL, LAB2_SERVICE_URL,
    LAB3_SERVICE_URL,
)

app = FastAPI(title="University API Gateway", version="1.0.0")
bearer = HTTPBearer()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "university-api-gateway"}


def authenticated(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail="Invalid or expired JWT") from error


@app.post("/auth/token")
def issue_token(username: str, password: str) -> dict[str, str]:
    if username != DEMO_USERNAME or password != DEMO_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    expires_at = datetime.now(UTC) + timedelta(minutes=JWT_TTL_MINUTES)
    token = jwt.encode({"sub": username, "exp": expires_at}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


async def _forward_report(service_url: str, path: str, params: dict[str, object]) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{service_url}{path}", params=params,
                headers={"X-Gateway-Token": GATEWAY_SERVICE_TOKEN},
            )
    except httpx.RequestError as error:
        raise HTTPException(status_code=503, detail="Laboratory service is unavailable") from error
    if response.is_error:
        try:
            detail = response.json().get("detail", "Laboratory service failed")
        except ValueError:
            detail = response.text or "Laboratory service failed without an error body"
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


@app.get("/api/v1/lab1/report")
async def lab1_report(
    term: str = Query(min_length=1, max_length=250),
    period_from: str = Query(alias="from"),
    period_to: str = Query(alias="to"),
    _: dict = Depends(authenticated),
) -> dict:
    return await _forward_report(
        LAB1_SERVICE_URL,
        "/internal/lab1/report",
        {"term": term, "from": period_from, "to": period_to},
    )


@app.get("/api/v1/lab2/report")
async def lab2_report(
    course_id: str = Query(min_length=36, max_length=36),
    semester: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
    _: dict = Depends(authenticated),
) -> dict:
    return await _forward_report(
        LAB2_SERVICE_URL,
        "/internal/lab2/report",
        {"course_id": course_id, "semester": semester, "year": year},
    )


@app.get("/api/v1/lab3/report")
async def lab3_report(
    group_id: str = Query(min_length=36, max_length=36),
    period_from: str = Query(alias="from"),
    period_to: str = Query(alias="to"),
    _: dict = Depends(authenticated),
) -> dict:
    return await _forward_report(
        LAB3_SERVICE_URL,
        "/internal/lab3/report",
        {"group_id": group_id, "from": period_from, "to": period_to},
    )
