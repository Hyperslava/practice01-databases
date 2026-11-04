from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Query

from report_service import build_lab2_report
from settings import GATEWAY_SERVICE_TOKEN

app = FastAPI(title="University Lab 2 Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/lab2/report")
def lab2_report(
    course_id: str = Query(min_length=36, max_length=36),
    semester: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
    x_gateway_token: str | None = Header(default=None),
) -> dict:
    if x_gateway_token != GATEWAY_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Gateway token is invalid")
    try:
        return build_lab2_report(course_id, semester, year)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Storage pipeline failed: {type(error).__name__}: {error}",
        ) from error
