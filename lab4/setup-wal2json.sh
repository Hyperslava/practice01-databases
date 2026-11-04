#!/usr/bin/env bash
# Подготовить существующую университетскую базу к CDC.
set -euo pipefail
cd "$(dirname "$0")/.."  # Далее пути считаются от корня проекта.

# Compose подключает этот файл в контейнер PostgreSQL только для чтения.
test -r postgres/postgresql.conf || { echo 'Missing postgres/postgresql.conf' >&2; exit 1; }
chmod a+r postgres/postgresql.conf

# Собрать PostgreSQL 16 с wal2json и дождаться проверки готовности Compose.
docker compose -f all-in-one/docker-compose.yaml up \
  --build --no-deps --wait --wait-timeout 180 postgres

# Выполнять SQL в уже заполненной базе university_system.
pg_sql() {
  docker exec practice01-postgres psql -X -v ON_ERROR_STOP=1 \
    -U admin -d university_system "$@"
}

# Проверить, что сервер читает настройки CDC именно из подключённого файла.
pg_sql -Atc 'SHOW wal_level' | grep -qx logical
pg_sql -Atc 'SHOW output_plugin_libraries' | grep -q wal2json
pg_sql -Atc "SELECT sourcefile FROM pg_settings WHERE name='wal_level'" |
  grep -qx /etc/postgresql/postgresql.conf
docker exec practice01-postgres sh -c 'test -f "$(pg_config --pkglibdir)/wal2json.so"'

# Схема создана ранее генератором; пустая база не подходит для этой лабораторной.
table_count=$(pg_sql -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
if [ "$table_count" -eq 0 ]; then
  echo 'Database university_system has no public tables. Generate the university schema and data first.' >&2
  exit 1
fi

# Создать публикацию для всех таблиц один раз; другой вариант pub считать ошибкой.
all_tables=$(pg_sql -Atc "SELECT count(*) FROM pg_publication WHERE pubname='pub' AND puballtables")
if [ "$all_tables" -eq 0 ]; then
  existing=$(pg_sql -Atc "SELECT count(*) FROM pg_publication WHERE pubname='pub'")
  if [ "$existing" -ne 0 ]; then
    echo 'Publication pub exists but is not FOR ALL TABLES.' >&2
    exit 1
  fi
  pg_sql -c 'CREATE PUBLICATION pub FOR ALL TABLES'
fi
echo 'PostgreSQL 16, wal2json, postgresql.conf and publication pub are ready.'
