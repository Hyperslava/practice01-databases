#!/usr/bin/env bash
# Проверить Create/Update/Delete студента по цепочке PostgreSQL -> Kafka -> Neo4j.
set -euo pipefail
cd "$(dirname "$0")/.."

topic=university.public.students
test_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
group_id=$(docker exec practice01-postgres psql -X -At -U admin -d university_system \
  -c 'SELECT id FROM public.student_groups ORDER BY id LIMIT 1')
if [[ -z "$group_id" ]]; then
  echo 'No student_groups rows found; seed the PostgreSQL schema first.' >&2
  exit 1
fi

pg_sql() {
  docker exec practice01-postgres psql -X -v ON_ERROR_STOP=1 -U admin -d university_system "$@"
}

get_events() {
  docker compose -f lab5/docker-compose.kafka.yml exec -T broker \
    kafka-console-consumer --bootstrap-server broker:29092 --topic "$topic" \
    --partition 0 --offset earliest --timeout-ms 1000 2>/dev/null || true
}

wait_kafka() {
  local operation=$1
  for ((i=0; i<30; i++)); do
    if get_events | python3 -c '
import json,sys
operation, record_id = sys.argv[1:]
for line in sys.stdin:
    try: event=json.loads(line)
    except json.JSONDecodeError: continue
    if not isinstance(event, dict): continue
    row=event.get("after") or event.get("before") or {}
    if event.get("op") == operation and row.get("id") == record_id: sys.exit(0)
sys.exit(1)
' "$operation" "$test_id"; then
      echo "Kafka: op=$operation id=$test_id"
      return 0
    fi
    sleep 2
  done
  echo "No Kafka event op=$operation id=$test_id" >&2
  return 1
}

neo4j_count() {
  local query=$1
  docker exec practice01-neo4j cypher-shell -u neo4j -p neo4jsecret \
    --format plain "$query" 2>/dev/null | sed -n '2p' | tr -d '[:space:]"'
}

wait_graph() {
  local expected_name=$1 expected_count=$2
  for ((i=0; i<45; i++)); do
    local count name
    count=$(neo4j_count "MATCH (s:Student {id: '$test_id'}) RETURN count(s)")
    name=$(neo4j_count "MATCH (s:Student {id: '$test_id'})-[:MEMBER_OF]->(:StudentGroup {id: '$group_id'}) RETURN s.first_name")
    if [[ "$count" == "$expected_count" ]] && { [[ "$expected_count" == 0 ]] || [[ "$name" == "$expected_name" ]]; }; then
      echo "Neo4j: count=$count name=${name:-ABSENT}"
      return 0
    fi
    sleep 2
  done
  echo "Neo4j did not reach expected state: count=$expected_count name=$expected_name" >&2
  return 1
}

echo "Test UUID: $test_id"
pg_sql -c "INSERT INTO public.students (id, group_id, first_name, last_name, email, student_card_number, enrollment_date, status) VALUES ('$test_id', '$group_id', 'CDC created', 'Neo4j', 'cdc-$test_id@example.invalid', 'CDC-${test_id:0:8}', CURRENT_DATE, 'active')"
wait_kafka c
wait_graph 'CDCcreated' 1

pg_sql -c "UPDATE public.students SET first_name='CDC updated', updated_at=NOW() WHERE id='$test_id'"
wait_kafka u
wait_graph 'CDCupdated' 1

pg_sql -c "DELETE FROM public.students WHERE id='$test_id'"
wait_kafka d
wait_graph '' 0

echo 'PASS: Create/Update/Delete reached Kafka and Neo4j, including MEMBER_OF.'
