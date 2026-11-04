"""Дождаться состояния RUNNING у коннектора Kafka Connect и всех его задач."""

import json
import sys
import time
import urllib.error
import urllib.request


# Имя передаёт setup-скрипт; REST API Connect работает на порту 8083.
name = sys.argv[1]
url = f"http://localhost:8083/connectors/{name}/status"

# После регистрации задача появляется с задержкой; опрашивать её статус.
for attempt in range(90):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            status = json.load(response)
    except (urllib.error.URLError, TimeoutError):
        status = None

    if status:
        connector = status["connector"]["state"]
        tasks = status["tasks"]
        if connector == "FAILED" or any(task["state"] == "FAILED" for task in tasks):
            print(json.dumps(status, indent=2), file=sys.stderr)
            sys.exit(1)
        if connector == "RUNNING" and tasks and all(task["state"] == "RUNNING" for task in tasks):
            print(f"{name}: RUNNING ({len(tasks)} task(s))")
            sys.exit(0)

    # Каждые 20 секунд сообщать о ходе ожидания.
    if (attempt + 1) % 10 == 0:
        print(f"Waiting for {name}: {2 * (attempt + 1)} seconds", flush=True)
    time.sleep(2)

print(f"Timed out waiting for {name}", file=sys.stderr)
if status:
    print(json.dumps(status, indent=2), file=sys.stderr)
sys.exit(1)
