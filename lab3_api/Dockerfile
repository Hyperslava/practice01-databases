FROM python:3.12-slim
WORKDIR /app
COPY lab3_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lab3_api/ .
CMD ["uvicorn", "lab3_app:app", "--host", "0.0.0.0", "--port", "8000"]
