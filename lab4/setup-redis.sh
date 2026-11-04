#!/usr/bin/env bash
# Добавить кэш Redis для топика students к уже запущенной лабораторной.
set -euo pipefail
cd "$(dirname "$0")/.."

# Установщик сохраняет сюда JAR; пользователь WSL должен иметь право записи.
if [ ! -w lab4/plugins ]; then
  echo 'lab4/plugins is not writable. Run: sudo chown -R "$(id -u):$(id -g)" lab4/plugins' >&2
  exit 1
fi

# Compose дождётся, пока Redis начнёт принимать команды.
docker compose -f all-in-one/docker-compose.yaml up \
  --no-deps --wait --wait-timeout 120 redis

# Один раз скачать плагин Lenses и пересобрать Connect с его JAR-файлами.
python3 lab4/install-redis-plugin.py
compose=lab4/docker-compose.kafka.yml
docker compose -f "$compose" up -d --build --no-deps kafka-connect

# Connect ищет плагины при запуске; curl ждёт повторного открытия REST API.
curl -fsS --retry 45 --retry-delay 2 --retry-connrefused --retry-all-errors \
  http://localhost:8083/connector-plugins |
  python3 -c '
import json, sys
plugins = {item["class"] for item in json.load(sys.stdin)}
required = "io.lenses.streamreactor.connect.redis.sink.RedisSinkConnector"
if required not in plugins:
    raise SystemExit("Redis Sink plugin was not loaded")
print("Redis Sink plugin is available")
'

# Подписать sink только на students: он создаёт и обновляет записи кэша.
python3 -c 'import json; print(json.dumps(json.load(open("lab4/redis-sink.json"))["config"]))' |
  curl --fail-with-body -sS -X PUT -H 'Content-Type: application/json' \
    --data-binary @- http://localhost:8083/connectors/lab4-redis-students/config >/dev/null

# Отдельный Kafka consumer обрабатывает удаления, которые здесь не делает Lenses Sink.
docker compose -f "$compose" --profile redis up \
  -d --build --no-deps redis-delete-worker

# Задача коннектора запускается не сразу; дождаться состояния RUNNING.
python3 lab4/wait-for-connector.py lab4-redis-students
echo 'Redis sink and delete worker started.'
