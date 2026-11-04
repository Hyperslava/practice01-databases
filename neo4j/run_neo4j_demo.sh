#!/bin/bash

echo "=== Проверка логов Neo4j ==="
docker compose logs neo4j | grep "Started" && echo "Neo4j уже запущен" || echo "Ожидание запуска Neo4j..."
docker compose logs -f neo4j &

echo "=== Проверка HTTP-интерфейса ==="
curl -I http://localhost:7474

echo "=== Выполнение Cypher-команд ==="

docker exec -i practice01-neo4j cypher-shell -u neo4j -p mysecretpassword <<'EOF'

// === Создание узлов ===
CREATE (s:Student {name: "Иванов Иван", age: 20, group: "ИКБО-01-22"});
CREATE (s1:Student {name: "Петрова Мария", age: 21, group: "ИКБО-02-22"});
CREATE (s2:Student {name: "Сидоров Алексей", age: 19, group: "ИКБО-01-22"});
CREATE (c1:Course {title: "Базы данных", credits: 4});
CREATE (c2:Course {title: "Программирование", credits: 5});
CREATE (c3:Course {title: "Математика", credits: 6});

// === Создание связей ===
MATCH (s:Student {name: "Иванов Иван"}), (c:Course {title: "Базы данных"})
CREATE (s)-[:ENROLLED_IN {grade: 5, semester: "весна 2024"}]->(c);

MATCH (s:Student {name: "Иванов Иван"}), (c:Course {title: "Программирование"})
CREATE (s)-[:ENROLLED_IN {grade: 5, semester: "весна 2024"}]->(c);

MATCH (s:Student {name: "Петрова Мария"}), (c:Course {title: "Базы данных"})
CREATE (s)-[:ENROLLED_IN {grade: 4, semester: "весна 2024"}]->(c);

MATCH (s:Student {name: "Петрова Мария"}), (c:Course {title: "Математика"})
CREATE (s)-[:ENROLLED_IN {grade: 5, semester: "весна 2024"}]->(c);

MATCH (s1:Student {name: "Иванов Иван"}), (s2:Student {name: "Сидоров Алексей"})
CREATE (s1)-[:FRIENDS_WITH {since: "2022-09-01"}]->(s2);

// === Чтение данных ===
MATCH (s:Student) RETURN s;
MATCH (n)-[r]->(m) RETURN n, r, m;
MATCH (s:Student {name: "Иванов Иван"})-[r:ENROLLED_IN]->(c:Course)
RETURN c.title AS course, r.grade AS grade;
MATCH (s:Student)-[:ENROLLED_IN]->(c:Course {title: "Базы данных"})
RETURN s.name AS student, s.group AS studentGroup;
MATCH (s:Student {name: "Иванов Иван"})-[:FRIENDS_WITH*1..2](friend:Student)
RETURN friend.name AS friendName;
MATCH (s:Student)-[:ENROLLED_IN]->(c:Course)
RETURN c.title AS course, count(s) AS studentCount
ORDER BY studentCount DESC;

// === Выход ===
:exit
EOF

echo "=== Скрипт завершён ==="
