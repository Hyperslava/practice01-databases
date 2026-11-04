#!/bin/bash
# Автоматический запуск всех команд из раздела 4.1.3–4.1.4

echo "=== Проверка логов Redis ==="
docker compose logs redis

echo "=== Проверка ответа Redis ==="
docker exec practice01-redis redis-cli -a mystrongredis ping

echo "=== Выполнение Redis-команд ==="

docker exec -i practice01-redis redis-cli -a mystrongredis <<'EOF'

# === Работа со строками ===
SET mykey "Hello, Redis!"
GET mykey

SET session:user1 "token123" EX 3600
TTL session:user1

# === Работа с хешами ===
HSET user:1 name "Ivanov" age "20" group "IKBO-01-22"
HGETALL user:1
HGET user:1 name

# === Работа со списками ===
LPUSH tasks "task1" "task2" "task3"
LRANGE tasks 0 -1

# === Работа с множествами ===
SADD languages "Python" "Java" "Go" "Python"
SMEMBERS languages

# === Служебные команды ===
KEYS *
DBSIZE
INFO server

EXIT
EOF

echo "=== Скрипт завершён ==="
