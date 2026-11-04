#!/usr/bin/env bash
# Проверить создание, обновление и удаление студента в кэше Redis.
set -euo pipefail
cd "$(dirname "$0")/.."  # Использовать пути от корня проекта.

# Уникальный UUID отделяет тест от данных генератора.
test_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pg_sql() {
  docker exec practice01-postgres psql -X -v ON_ERROR_STOP=1 \
    -U admin -d university_system "$@"
}
redis_get() {
  docker exec practice01-redis redis-cli --no-auth-warning -a mystrongredis GET "$test_id"
}

# Поле group_id обязательно: взять существующую группу из базы.
group_id=$(pg_sql -Atc 'SELECT id FROM public.student_groups ORDER BY id LIMIT 1')
test -n "$group_id" || { echo 'No student_groups row for test student' >&2; exit 1; }

# Kafka Connect обновляет Redis не сразу; подождать нужного значения.
wait_redis() {
  local expected=$1
  for ((i=0; i<60; i++)); do
    value=$(redis_get 2>/dev/null || true)
    if [ "$expected" = ABSENT ]; then
      if [ -z "$value" ]; then echo "Redis key deleted: $test_id"; return 0; fi
    elif printf '%s' "$value" | python3 -c '
import json,sys
try: row=json.load(sys.stdin)
except (ValueError,TypeError): sys.exit(1)
sys.exit(0 if row.get("first_name")==sys.argv[1] else 1)
' "$expected" 2>/dev/null; then
      echo "Redis first_name=$expected id=$test_id"
      return 0
    fi
    sleep 2
  done
  echo "Redis did not reach expected state $expected for $test_id" >&2
  echo "Current value: $(redis_get 2>/dev/null || true)" >&2
  return 1
}

echo "Test student UUID: $test_id"
# Lenses Redis Sink создаст запись кэша для нового студента.
pg_sql -c "INSERT INTO public.students (id,group_id,first_name,last_name,enrollment_date) VALUES ('$test_id','$group_id','CDC-Create','Redis-Test',CURRENT_DATE)"
wait_redis CDC-Create

# Тот же ключ Redis должен получить новое значение first_name.
pg_sql -c "UPDATE public.students SET first_name='CDC-Update', updated_at=now() WHERE id='$test_id'"
wait_redis CDC-Update

# Обработчик удаления прочитает op=d и удалит ключ Redis.
pg_sql -c "DELETE FROM public.students WHERE id='$test_id'"
wait_redis ABSENT

echo 'PASS: PostgreSQL Create/Update/Delete propagated through Kafka to Redis.'
