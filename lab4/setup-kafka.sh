#!/usr/bin/env bash
# Запустить Kafka и проверить плагины, нужные лабораторной.
set -euo pipefail
cd "$(dirname "$0")/.."

# Compose собирает образ Kafka Connect из Dockerfile.connect.
docker compose -f lab4/docker-compose.kafka.yml up -d --build

# REST API Connect появляется позже контейнера; curl повторяет попытки подключения.
curl -fsS --retry 45 --retry-delay 2 --retry-connrefused --retry-all-errors \
  http://localhost:8083/connector-plugins |
  python3 -c '
import json, sys
plugins = {item["class"] for item in json.load(sys.stdin)}
required = {
    "io.debezium.connector.postgresql.PostgresConnector",
    "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
}
missing = required - plugins
if missing:
    raise SystemExit(f"Missing Kafka Connect plugins: {sorted(missing)}")
print("Debezium and Elasticsearch Sink plugins are available")
'

echo 'Kafka, Schema Registry, Kafka Connect and Kafka UI are ready.'
