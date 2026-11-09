#!/usr/bin/env bash
# Проверяет Create/Update/Delete: PostgreSQL -> Kafka -> MongoDB PostgresHandler.
set -euo pipefail
cd "$(dirname "$0")/.."

topic=university.public.students
test_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
group_id=$(docker exec practice01-postgres psql -X -At -U admin -d university_system \
  -c 'SELECT id FROM public.student_groups ORDER BY id LIMIT 1')
[[ -n "$group_id" ]] || { echo 'No student_groups rows found.' >&2; exit 1; }

pg_sql() { docker exec practice01-postgres psql -X -v ON_ERROR_STOP=1 -U admin -d university_system "$@"; }
events() {
  docker compose -f lab5/docker-compose.kafka.yml exec -T broker kafka-console-consumer \
    --bootstrap-server broker:29092 --topic "$topic" --partition 0 --offset earliest \
    --timeout-ms 1000 2>/dev/null || true
}
wait_kafka() {
  local operation=$1
  for ((i=0; i<30; i++)); do
    if events | python3 -c '
import json,sys
op, identifier=sys.argv[1:]
for line in sys.stdin:
  try: event=json.loads(line)
  except json.JSONDecodeError: continue
  if not isinstance(event,dict): continue
  row=event.get("after") or event.get("before") or {}
  if event.get("op")==op and row.get("id")==identifier: sys.exit(0)
sys.exit(1)
' "$operation" "$test_id"; then echo "Kafka: op=$operation"; return; fi
    sleep 2
  done
  return 1
}
mongo_count() {
  local name=$1
  docker exec practice01-mongodb mongosh --quiet -u appuser -p appsecret --authenticationDatabase admin \
    --eval "db.getSiblingDB('university_system').students_cdc.countDocuments({_id:{id:'$test_id'}${name:+,first_name:'$name'}})" | tr -d '[:space:]'
}
wait_mongo() {
  local name=$1 expected=$2
  for ((i=0; i<30; i++)); do
    [[ "$(mongo_count "$name")" == "$expected" ]] && { echo "MongoDB: count=$expected"; return; }
    sleep 2
  done
  echo "MongoDB did not reach expected state." >&2; return 1
}

echo "Test UUID: $test_id"
pg_sql -c "INSERT INTO public.students (id, group_id, first_name, last_name, email, student_card_number, enrollment_date, status) VALUES ('$test_id', '$group_id', 'Mongo created', 'CDC', 'mongo-$test_id@example.invalid', 'MONGO-${test_id:0:8}', CURRENT_DATE, 'active')"
wait_kafka c; wait_mongo 'Mongo created' 1
pg_sql -c "UPDATE public.students SET first_name='Mongo updated', updated_at=NOW() WHERE id='$test_id'"
wait_kafka u; wait_mongo 'Mongo updated' 1
pg_sql -c "DELETE FROM public.students WHERE id='$test_id'"
wait_kafka d; wait_mongo '' 0
echo 'PASS: Create/Update/Delete reached MongoDB.'
