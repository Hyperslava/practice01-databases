#!/bin/bash
# Автоматический запуск всех команд из раздела 4.4.3–4.4.4

echo "=== Проверка Elasticsearch ==="
curl -s http://localhost:9200
curl -s http://localhost:9200/_cluster/health?pretty

echo "Создание индекса students"
curl -X PUT "http://localhost:9200/students" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "properties": {
        "name": { "type": "text", "analyzer": "standard" },
        "age": { "type": "integer" },
        "group": { "type": "keyword" },
        "bio": { "type": "text" },
        "enrolled_at": { "type": "date" }
      }
    }
  }'

echo "=== Добавление документов ==="

curl -X POST "http://localhost:9200/students/_doc" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Иванов Иван Иванович",
    "age": 20,
    "group": "ИКБО-01-22",
    "bio": "Студент третьего курса, увлекается программированием и машинным обучением",
    "enrolled_at": "2022-09-01"
  }'

curl -X PUT "http://localhost:9200/students/_doc/2" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Петрова Мария Сергеевна",
    "age": 21,
    "group": "ИКБО-02-22",
    "bio": "Студентка, занимается анализом данных и визуализацией",
    "enrolled_at": "2022-09-01"
  }'

curl -X PUT "http://localhost:9200/students/_doc/3" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Сидоров Алексей Петрович",
    "age": 19,
    "group": "ИКБО-01-22",
    "bio": "Первокурсник, интересуется веб-разработкой и базами данных",
    "enrolled_at": "2023-09-01"
  }'

echo "=== Получение всех документов ==="
curl "http://localhost:9200/students/_search?pretty"

echo "=== Полнотекстовый поиск по bio ==="
curl -X GET "http://localhost:9200/students/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match": {
        "bio": "программирование"
      }
    }
  }'

echo "=== Точное совпадение по group ==="
curl -X GET "http://localhost:9200/students/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "term": {
        "group": "ИКБО-01-22"
      }
    }
  }'

echo "=== Комбинированный запрос (bool) ==="
curl -X GET "http://localhost:9200/students/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "bool": {
        "must": [
          { "term": { "group": "ИКБО-01-22" } },
          { "range": { "age": { "gt": 19 } } }
        ]
      }
    }
  }'

echo "=== Агрегации: количество студентов по группам ==="
curl -X GET "http://localhost:9200/students/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "students_per_group": {
        "terms": {
          "field": "group"
        }
      }
    }
  }'

echo "=== Список индексов ==="
curl "http://localhost:9200/_cat/indices?v"

echo "=== Маппинг индекса students ==="
curl "http://localhost:9200/students/_mapping?pretty"

echo "=== Количество документов ==="
curl "http://localhost:9200/students/_count?pretty"

echo "Все"
