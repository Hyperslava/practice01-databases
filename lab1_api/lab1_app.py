from __future__ import annotations

from datetime import date

from fastapi import FastAPI, Header, HTTPException, Query

from report_service import build_lab1_report
from settings import GATEWAY_SERVICE_TOKEN

app = FastAPI(title="University Lab 1 Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/lab1/report")
def lab1_report(
    term: str = Query(min_length=1, max_length=250),
    period_from: date = Query(alias="from"),
    period_to: date = Query(alias="to"),
    x_gateway_token: str | None = Header(default=None),
) -> dict:
    if x_gateway_token != GATEWAY_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Gateway token is invalid")
    try:
        return build_lab1_report(term, period_from, period_to)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        # Для лабораторной работы сообщаем класс ошибки: это позволяет увидеть,
        # какое подключение (ES, PostgreSQL или Redis) надо проверить.
        raise HTTPException(
            status_code=503,
            detail=f"Storage pipeline failed: {type(error).__name__}: {error}",
        ) from error
