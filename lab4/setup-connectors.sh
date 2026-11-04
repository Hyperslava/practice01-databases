#!/usr/bin/env bash
# Зарегистрировать источник Debezium и приёмник Elasticsearch в Kafka Connect.
set -euo pipefail
cd "$(dirname "$0")/.."

connect_url=http://localhost:8083
curl -fsS "$connect_url/connector-plugins" >/dev/null  # Проверить доступность Connect.

# REST PUT принимает внутренний объект config и обновляет существующий коннектор.
register_connector() {
  file=$1
  name=$2
  python3 -c 'import json,sys; json.dump(json.load(open(sys.argv[1]))["config"],sys.stdout)' "$file" |
    curl --fail-with-body -sS -X PUT -H 'Content-Type: application/json' \
      --data-binary @- "$connect_url/connectors/$name/config" >/dev/null
}

# Удалить старый источник, если он остался от предыдущей версии лабораторной.
if curl -fsS "$connect_url/connectors/lab4-postgres-source/status" >/dev/null 2>&1; then
  curl --fail-with-body -sS -X DELETE \
    "$connect_url/connectors/lab4-postgres-source" >/dev/null
fi

# Применить два конфига; помощник дождётся запуска каждой задачи.
register_connector lab4/postgres-source.json lab4-postgres-wal2json
register_connector lab4/elasticsearch-sink.json lab4-elasticsearch-sink
python3 lab4/wait-for-connector.py lab4-postgres-wal2json
python3 lab4/wait-for-connector.py lab4-elasticsearch-sink
