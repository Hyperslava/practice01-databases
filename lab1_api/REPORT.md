# ЛР №1: сервис аналитического отчёта

## Назначение

`GET /api/v1/lab1/report` возвращает десять студентов с минимальной
посещаемостью лекций, найденных по фразе, за заданный период. В HTTP-ответе
остаются только имя, фамилия и процент; диагностическая трасса четырёх
хранилищ записывается в `Logs/lab1_pipeline.log`. Метод доступен только с
JWT Bearer-токеном.

## C4: контейнерная диаграмма

```mermaid
C4Container
  title ЛР №1 — контейнерная диаграмма
  Person(user, "Преподаватель или студент")
  System_Boundary(system, "University analytics") {
    Container(gateway, "API Gateway", "FastAPI", "JWT-аутентификация и HTTP API")
    Container(lab1, "Lab 1 Service", "FastAPI", "Оркестрация отчёта")
    ContainerDb(es, "Elasticsearch", "search index", "Полнотекстовый поиск лекций")
    ContainerDb(neo, "Neo4j", "graph read-model", "Состав студентов, групп и занятий")
    ContainerDb(pg, "PostgreSQL", "relational DB", "Посещаемость и расчёт процента")
    ContainerDb(redis, "Redis", "HASH read-model", "Полные профили студентов")
  }
  Rel(user, gateway, "HTTPS + JWT")
  Rel(gateway, lab1, "HTTP, внутренний gateway token")
  Rel(lab1, es, "Поиск term")
  Rel(lab1, neo, "Кому назначены найденные занятия")
  Rel(lab1, pg, "Расчёт процента по парам student/session")
  Rel(lab1, redis, "HGETALL профилей")
```

## DFD Йордана–Кода

```mermaid
flowchart LR
  U[Внешняя сущность: пользователь] -->|JWT, term, from, to| G((1. API Gateway))
  G -->|проверенный запрос| L((2. ЛР №1))
  L -->|термин| ES[(D1 Elasticsearch)]
  ES -->|lecture_id| L
  L -->|lecture_id, период| N[(D2 Neo4j)]
  N -->|student_id, session_id| L
  L -->|пары student_id/session_id| PG[(D3 PostgreSQL)]
  PG -->|10 student_id + проценты| L
  L -->|student_id| R[(D4 Redis)]
  R -->|полные профили HASH| L
  L -->|отчёт + execution_trace| G
  G -->|JSON-отчёт| U
```

## Обоснование хранилищ

1. **Elasticsearch** ищет термин в `title`, `annotation`, `content_text` и
   возвращает `lecture_id`. Это полнотекстовая задача с русским анализатором.
2. **Neo4j** одним обходом графа получает пары `student_id`–`session_id`:
   студент состоит в группе, а занятие назначено этой группе и входит в период.
   Это определяет, кто **должен был** быть на найденных лекциях.
3. **PostgreSQL** по полученным парам и таблице `attendance` считает только
   критерий ранжирования: UUID студента, количество плановых и посещённых
   занятий, процент. Поля профиля студента здесь не выбираются.
4. **Redis** хранит денормализованный `students_cache:<uuid>` HASH: студент,
   группа, специальность, организационный путь и курсы. Он возвращает полную
   информацию по десяти UUID без повторения большого JOIN из PostgreSQL.

## Подготовка и тест

Сначала нужно подготовить read-models исходным скриптом:

```powershell
python uni_python_fixed_2.py postgres
python uni_python_fixed_2.py redis
python uni_python_fixed_2.py neo4j
python uni_python_fixed_2.py elasticsearch
```

Запуск контейнеров:

```powershell
docker compose -f docker-compose.lab1.yml up --build
```

Gateway доступен на `http://localhost:8088` по умолчанию. Порт можно изменить
без редактирования Compose-файла, например `GATEWAY_PORT=8080 docker compose
-f docker-compose.lab1.yml up --build`. Сначала проверьте, что отвечает именно
этот Gateway:

```powershell
curl http://localhost:8088/health
```

Ожидаемый результат: `{"status":"ok","service":"university-api-gateway"}`.

Получение JWT:

```powershell
curl -X POST "http://localhost:8088/auth/token?username=teacher&password=teacher-secret"
```

Запрос отчёта:

```powershell
curl "http://localhost:8088/api/v1/lab1/report?term=база%20данных&from=2026-02-09&to=2026-03-22" -H "Authorization: Bearer <JWT>"
```

В поле `execution_trace` ответа видны результаты всех трёх стадий: найденные
лекции, десять UUID с процентами и число профилей, полученных из Redis.
