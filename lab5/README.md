# Лабораторная №5: PostgreSQL → Kafka → Neo4j CDC

Лабораторная разворачивает отдельный Kafka Connect с Debezium и Neo4j Sink. Neo4j описан существующим файлом `neo4j/docker-compose.yml`; Kafka Connect соединяется с ним по `bolt://host.docker.internal:7687`. Внешние порты Lab5: Kafka `9093`, Kafka Connect `8085` — это позволяет запускать её одновременно с Lab4 (`9092` и `8083`).

Если контейнер `practice01-neo4j` уже существует (например, его создала предыдущая лабораторная), `setup-all.sh` использует и при необходимости запускает его. Второй контейнер с тем же именем не создаётся.

Запуск из корня проекта:

```bash
bash lab5/setup-all.sh
```

После изменения `Dockerfile.connect` или `mongo-handler/` пересоберите образ явно:

```bash
docker compose -f lab5/docker-compose.kafka.yml build kafka-connect
```

Конфигурация [neo4j-sink.json](neo4j-sink.json) читает только топики таблиц, из которых получается граф:

```text
University -[:HAS_INSTITUTE]-> Institute -[:HAS_DEPARTMENT]-> Department
Department -[:HAS_GROUP]-> StudentGroup <-[:MEMBER_OF]- Student
Department -[:READS]-> LectureCourse -[:HAS_LECTURE]-> Lecture
Lecture -[:HELD_AS]-> ClassSession -[:FOR_GROUP]-> StudentGroup
```

Cypher-правила вынесены в каталог `cypher/`: по одному файлу на топик. При регистрации `setup-connectors.sh` компактно передаёт их содержимое в свойства `neo4j.cypher.topic.<topic>`, поэтому JSON-конфигурация остаётся короткой и читаемой.

Для `c`, `r` и `u` выполняются `MERGE` и обновление свойств; для `d` удаляется узел или связь. Проверка полного цикла:

```bash
bash lab5/test-cdc.sh
```

## MongoDB Sink и иерархический CDC-документ

`mongodb-sink.json` использует штатный обработчик Debezium PostgreSQL:

```text
com.mongodb.kafka.connect.sink.cdc.debezium.rdbms.postgres.PostgresHandler
```

Для MongoDB Kafka Connector 1.11.2 корректное имя класса коннектора — `com.mongodb.kafka.connect.MongoSinkConnector`; вариант с `.sink.MongoSinkConnector` из некоторых примеров не соответствует установленному JAR.

Он доставляет `university.public.students` в `university_system.students_cdc` и применяет Create, Update и Delete. Проверка:

```bash
bash lab5/test-mongodb-cdc.sh
```

`mongodb-hierarchy-sink.json` использует `ru.mirea.lab5.mongo.UniversityHierarchyCdcHandler`. Его исходный код находится в `mongo-handler/`; Dockerfile собирает JAR и помещает его в тот же plugin directory, что и MongoDB Kafka Connector. Обработчик получает события `universities`, `institutes` и `departments`, сохраняет их состояние и заменяет один документ `university_hierarchy_cdc` с вложенными объектами institute → department. При `d` дочерний объект удаляется, а при удалении университета удаляется весь документ. События `student_groups` в эту иерархию не входят.

Статус коннектора:

```bash
curl -fsS http://localhost:8085/connectors/lab5-neo4j-sink/status | python3 -m json.tool
curl -fsS http://localhost:8085/connectors/lab5-mongodb-students-cdc/status | python3 -m json.tool
```
