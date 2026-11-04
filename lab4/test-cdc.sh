#!/usr/bin/env bash
# Проверить snapshot и Create/Update/Delete через PostgreSQL, Kafka и Elasticsearch.
set -euo pipefail
cd "$(dirname "$0")/.."  # Использовать пути Compose от корня проекта.

# Новый UUID позволяет не трогать данные генератора.
topic=university.public.universities
test_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
es_id=$(printf '{"id":"%s"}' "$test_id")
pg_sql() {
  docker exec practice01-postgres psql -X -v ON_ERROR_STOP=1 \
    -U admin -d university_system "$@"
}

# Читать партицию 0 с начала; consumer завершится после паузы без событий.
get_events() {
  docker compose -f lab4/docker-compose.kafka.yml exec -T broker \
    kafka-console-consumer --bootstrap-server broker:29092 --topic "$topic" \
      --partition 0 --offset earliest --timeout-ms 10000 2>/dev/null || true
}

# Событие приходит в Kafka после SQL-команды, поэтому чтение повторяется.
wait_kafka() {
  local operation=$1 record_id=$2
  for ((i=0; i<30; i++)); do
    if get_events | python3 -c '
import json,sys
operation,record_id=sys.argv[1:]
for line in sys.stdin:
    try: event=json.loads(line)
    except json.JSONDecodeError: continue
    if not isinstance(event,dict): continue  # Пропустить tombstone со значением null.
    row=event.get("after") or event.get("before") or {}
    if event.get("op")==operation and (not record_id or row.get("id")==record_id):
        sys.exit(0)
sys.exit(1)
' "$operation" "$record_id"; then
      echo "Kafka: op=$operation id=${record_id:-snapshot}"
      return 0
    fi
    sleep 2
  done
  echo "No Kafka event op=$operation id=$record_id in $topic" >&2
  # При ошибке показать состояние источника Debezium.
  curl -fsS http://localhost:8083/connectors/lab4-postgres-wal2json/status 2>/dev/null |
    python3 -c 'import json,sys; d=json.load(sys.stdin); print("Debezium:", d["connector"]["state"], [(t["state"], t.get("trace", "").splitlines()[-1:] ) for t in d["tasks"]])' >&2 || true
  return 1
}

# Elasticsearch использует JSON-ключ Kafka как _id; искать точное значение.
es_document() {
  python3 -c 'import json,sys; print(json.dumps({"query":{"ids":{"values":[sys.argv[1]]}}}))' "$es_id" |
    curl -fsS -H 'Content-Type: application/json' --data-binary @- \
      "http://localhost:9200/$topic/_search" 2>/dev/null
}

# Refresh делает свежую запись видимой в поиске; затем сравнить документ.
wait_elasticsearch() {
  local expected_name=$1
  for ((i=0; i<60; i++)); do
    curl -fsS -X POST "http://localhost:9200/$topic/_refresh" >/dev/null 2>&1 || true
    if es_document | python3 -c '
import json,sys
expected=sys.argv[1]
hits=json.load(sys.stdin)["hits"]["hits"]
if expected == "ABSENT": sys.exit(0 if not hits else 1)
if len(hits)!=1: sys.exit(1)
source=hits[0]["_source"]
row=source.get("after") if isinstance(source.get("after"),dict) else source
sys.exit(0 if row.get("name")==expected else 1)
' "$expected_name" 2>/dev/null; then
      echo "Elasticsearch: ${expected_name}"
      return 0
    fi
    sleep 2
  done
  echo "Elasticsearch did not reach expected state: $expected_name, id=$test_id" >&2
  return 1
}

echo "Test UUID: $test_id"
echo "Elasticsearch _id: $es_id"
echo 'Checking initial snapshot in Kafka...'
wait_kafka r ''

# Создать университет и дождаться его появления в Kafka и Elasticsearch.
pg_sql -c "INSERT INTO public.universities (id,name,short_name) VALUES ('$test_id','CDC test: created','CDC-TEST')"
wait_kafka c "$test_id"
wait_elasticsearch 'CDC test: created'

# Обновить эту же строку; в Elasticsearch изменится тот же документ.
pg_sql -c "UPDATE public.universities SET name='CDC test: updated', updated_at=now() WHERE id='$test_id'"
wait_kafka u "$test_id"
wait_elasticsearch 'CDC test: updated'

# Удалить строку; в Kafka нужен op=d, а в Elasticsearch документа уже нет.
pg_sql -c "DELETE FROM public.universities WHERE id='$test_id'"
wait_kafka d "$test_id"
wait_elasticsearch ABSENT

echo 'PASS: snapshot and Create/Update/Delete reached Kafka and Elasticsearch.'
