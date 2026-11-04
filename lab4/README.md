# Лабораторная №4: PostgreSQL → Kafka → Elasticsearch

Команды выполняются в Ubuntu WSL из корня проекта `~/practice01-databases`. Перед запуском убедитесь, что в WSL находится **вся обновлённая папка проекта**, включая `postgres/postgresql.conf`. Файл конфигурации хранится в проекте и монтируется в PostgreSQL через `all-in-one/docker-compose.yaml`; копировать его из работающего контейнера больше не требуется.

## Предпосылки

- Docker Desktop с WSL Integration; `docker compose version` работает из Ubuntu.
- Порты 5433, 9092, 8083, 8084 и 9200 свободны либо заняты контейнерами этого же проекта.
- База `university_system` уже создана и заполнена генератором схемы предыдущего семестра. Скрипт проверит наличие таблиц и остановится, если их нет. Он не запускает генератор повторно, поскольку это может изменить уже созданные данные.

## Развёртывание

Как устроена цепочка: PostgreSQL пишет изменения в WAL → Debezium читает WAL через `wal2json` → Kafka хранит события в топиках `university.public.*` → Elasticsearch Sink обрабатывает все таблицы, а Redis Sink только `students`. Удаления из Redis выполняет `redis-delete-worker`.

Основные файлы:

| Файл | Назначение |
| --- | --- |
| `setup-wal2json.sh` | Собирает PostgreSQL с `wal2json`, проверяет `postgresql.conf` и публикацию `pub`. |
| `setup-kafka.sh` | Поднимает Kafka и Connect, проверяет наличие плагинов Debezium и Elasticsearch. |
| `setup-connectors.sh` | Применяет `postgres-source.json` и `elasticsearch-sink.json`. |
| `setup-all.sh` | Запускает предыдущие этапы и Elasticsearch в нужном порядке. |
| `setup-redis.sh` | Запускает Redis, устанавливает Lenses Sink, применяет `redis-sink.json` и поднимает обработчик удалений. |
| `test-cdc.sh`, `test-redis.sh` | Проверяют полный цикл Create/Update/Delete на новых тестовых строках. |
| `wait-for-connector.py` | Ждёт состояния `RUNNING` у коннектора и его задачи; при ошибке печатает `trace`. |

```bash
cd ~/practice01-databases
bash lab4/setup-all.sh
```

Можно запускать этапы по отдельности:

```bash
bash lab4/setup-wal2json.sh    # PostgreSQL 16, wal2json, конфиг и публикация
docker compose -f all-in-one/docker-compose.yaml up --no-deps --wait elasticsearch
bash lab4/setup-kafka.sh       # Kafka, Schema Registry, Connect и плагины
bash lab4/setup-connectors.sh  # Debezium source и Elasticsearch sink
```

`setup-all.sh` запускает эти этапы в нужном порядке и ждёт готовности Elasticsearch. Скрипты повторяемы: они не удаляют Docker volumes и данные. При повторном запуске используется существующий replication slot и offsets Kafka Connect; initial snapshot не запускается заново автоматически.

Настройки источника: `lab4/postgres-source.json`. Настройки приёмника: `lab4/elasticsearch-sink.json`. Изменения в этих файлах применяются повторным запуском скрипта.

## Проверка

```bash
docker exec practice01-postgres psql -U admin -d university_system -c 'SHOW config_file'
docker exec practice01-postgres psql -U admin -d university_system -c "SELECT name, setting, sourcefile FROM pg_settings WHERE name IN ('wal_level', 'max_wal_senders', 'max_replication_slots', 'output_plugin_libraries') ORDER BY name"
docker exec practice01-postgres psql -U admin -d university_system -c 'SELECT pubname, puballtables FROM pg_publication'
curl -fsS http://localhost:8083/connector-plugins | python3 -m json.tool
curl -fsS http://localhost:8083/connectors/lab4-postgres-wal2json/status | python3 -m json.tool
curl -fsS http://localhost:8083/connectors/lab4-elasticsearch-sink/status | python3 -m json.tool
curl -fsS 'http://localhost:9200/_cat/indices?v'
```

Ожидается `config_file=/etc/postgresql/postgresql.conf`, `wal_level=logical`, библиотека `wal2json`, публикация `pub` с `puballtables=t` и оба коннектора вместе с задачами в состоянии `RUNNING`. Kafka UI: <http://localhost:8084>. Топики имеют вид `university.public.<таблица>`.

Для проверки Create/Update/Delete создайте отдельную тестовую строку в PostgreSQL, проверьте события `c/u/d` в Kafka UI и изменения документа в Elasticsearch. В текущей проверенной конфигурации Elasticsearch использует полный JSON ключ Kafka как `_id`, например `{"id":"UUID"}`; запрос по одному UUID в `_doc/<UUID>` не найдёт документ. Поиск по полю `after.id.keyword` или просмотр `_search` покажет его.

Автоматическая проверка snapshot и полного цикла Create/Update/Delete:

```bash
bash lab4/test-cdc.sh
```

Скрипт печатает UUID тестовой строки и проверяет события в топике `university.public.universities` и документ Elasticsearch после каждой операции. После успешного теста строка удалена из PostgreSQL и Elasticsearch.

## Redis

Для Redis есть отдельный этап:

```bash
bash lab4/setup-redis.sh
bash lab4/test-redis.sh
```

`setup-redis.sh` запускает уже описанный в `all-in-one/docker-compose.yaml` Redis, скачивает Redis Sink из релиза 10.0.1 [Stream Reactor](https://github.com/lensesio/stream-reactor/releases), пересобирает Kafka Connect и регистрирует sink только для `university.public.students`. Lenses Sink записывает и обновляет Redis cache с ключом `id`. Отдельный `redis-delete-worker` читает CDC-события `op=d` из того же топика и удаляет ключ; [документация Lenses](https://docs.lenses.io/latest/connectors/kafka-connectors/sinks/redis) не обещает удаление по tombstone. Тест создаёт отдельного студента и проверяет Redis после каждой операции. Если GitHub изменит имя архива релиза, установщик покажет список доступных файлов.

Оба теста проверены в Ubuntu WSL: `test-cdc.sh` вывел `PASS` для snapshot и Create/Update/Delete в Kafka и Elasticsearch; `test-redis.sh` вывел `PASS` для Create/Update/Delete студента в Redis. Для отчёта дополнительно сохраните статус задачи `lab4-redis-students` и лог `redis-delete-worker` с UUID теста. Генератор университетских данных запускается отдельно, только если схема отсутствует.
