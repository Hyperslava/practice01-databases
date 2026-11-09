#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Не пересобирать уже готовый образ при каждом запуске: это делает повторный
# setup зависимым от Docker Hub. При первом запуске Compose соберёт образ;
# после изменения Dockerfile или mongo-handler выполните `docker compose ... build`.
docker compose -f lab5/docker-compose.kafka.yml up -d

# REST API начинает отвечать до завершения сканирования plugin.path. Ждём не
# только HTTP 200, а появления каждого нужного класса в ответе API.
for ((i=0; i<60; i++)); do
  if curl -fsS http://localhost:8085/connector-plugins 2>/dev/null | python3 -c '
import json, sys
required = {
    "io.debezium.connector.postgresql.PostgresConnector",
    "org.neo4j.connectors.kafka.sink.Neo4jConnector",
    "com.mongodb.kafka.connect.MongoSinkConnector",
}
actual = {item["class"] for item in json.load(sys.stdin)}
missing = required - actual
if missing:
    raise SystemExit(f"Missing plugins: {sorted(missing)}")
' 2>/dev/null; then
    echo 'Debezium, Neo4j Sink and MongoDB Sink plugins are available'
    exit 0
  fi
  sleep 2
done

echo 'Kafka Connect did not discover all required plugins.' >&2
exit 1
