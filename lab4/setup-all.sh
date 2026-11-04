#!/usr/bin/env bash
# Запустить часть лабораторной PostgreSQL → Kafka → Elasticsearch.
set -euo pipefail
cd "$(dirname "$0")/.."  # Работать из корня проекта при запуске из любой папки.

# Подготовить PostgreSQL, wal2json, конфигурацию и публикацию.
bash lab4/setup-wal2json.sh

# Compose дождётся готовности Elasticsearch по его healthcheck.
docker compose -f all-in-one/docker-compose.yaml up \
  --no-deps --wait --wait-timeout 180 elasticsearch

# Запустить Kafka Connect и зарегистрировать источник и приёмник Elasticsearch.
bash lab4/setup-kafka.sh
bash lab4/setup-connectors.sh

echo 'Lab 4 PostgreSQL → Kafka → Elasticsearch is ready. Kafka UI: http://localhost:8084'
