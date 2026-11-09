#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Общая PostgreSQL-подготовка: wal2json, logical WAL и публикация pub.
bash lab4/setup-wal2json.sh

# Neo4j мог быть поднят ранее другим Compose-проектом. У него задано
# фиксированное имя practice01-neo4j, поэтому нельзя безусловно выполнять
# `compose up`: Docker попытается создать второй контейнер с тем же именем.
if docker inspect practice01-neo4j >/dev/null 2>&1; then
  docker start practice01-neo4j >/dev/null 2>&1 || true
else
  docker compose -f neo4j/docker-compose.yml up -d --wait --wait-timeout 180
fi

# Дождаться доступности Bolt, в том числе если существующий контейнер только
# что был запущен выше.
for ((i=0; i<45; i++)); do
  if docker exec practice01-neo4j cypher-shell -u neo4j -p neo4jsecret \
    'RETURN 1' >/dev/null 2>&1; then
    break
  fi
  if (( i == 44 )); then
    echo 'Neo4j practice01-neo4j did not become ready.' >&2
    exit 1
  fi
  sleep 2
done

# Использовать существующий MongoDB, если его уже подняла другая лабораторная.
if docker inspect practice01-mongodb >/dev/null 2>&1; then
  docker start practice01-mongodb >/dev/null 2>&1 || true
else
  docker compose -f mongodb/docker-compose.yaml up -d --wait --wait-timeout 180 mongodb
fi
for ((i=0; i<45; i++)); do
  if docker exec practice01-mongodb mongosh --quiet -u appuser -p appsecret \
    --authenticationDatabase admin --eval 'db.adminCommand({ping: 1}).ok' | grep -qx '1'; then break; fi
  if (( i == 44 )); then echo 'MongoDB practice01-mongodb did not become ready.' >&2; exit 1; fi
  sleep 2
done

bash lab5/setup-kafka.sh
bash lab5/setup-connectors.sh
echo 'Lab 5 PostgreSQL -> Kafka -> Neo4j is ready. Neo4j Browser: http://localhost:7474'
