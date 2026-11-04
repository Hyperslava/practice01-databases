FROM python:3.12-slim
WORKDIR /app
COPY lab1_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lab1_api/ .
ARG APP_MODULE=lab1_app:app
ENV APP_MODULE=${APP_MODULE}
CMD ["sh", "-c", "uvicorn $APP_MODULE --host 0.0.0.0 --port 8000"]
