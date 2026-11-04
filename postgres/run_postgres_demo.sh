#!/bin/bash
# Автоматический запуск всех команд из раздела 4.5.3–4.5.4

echo "=== Проверка логов PostgreSQL ==="
docker compose logs postgres

echo "=== Проверка готовности PostgreSQL ==="
docker exec practice01-postgres pg_isready -U admin -d practice_db

echo "=== Выполнение SQL-команд ==="

docker exec -i practice01-postgres psql -U admin -d practice_db <<'EOF'

-- === Информация о системе ===
SELECT version();
\l
SELECT current_database(), current_user;

-- === Создание таблиц ===

CREATE TABLE groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE,
    department VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    age INTEGER CHECK (age > 0 AND age < 150),
    email VARCHAR(100) UNIQUE,
    group_id INTEGER REFERENCES groups(id),
    enrolled_at DATE DEFAULT CURRENT_DATE
);

CREATE TABLE grades (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    subject VARCHAR(100) NOT NULL,
    grade INTEGER CHECK (grade >= 1 AND grade <= 5),
    exam_date DATE
);

-- === Вставка данных ===

INSERT INTO groups (name, department) VALUES
    ('ИКБО-01-22', 'Институт информационных технологий'),
    ('ИКБО-02-22', 'Институт информационных технологий'),
    ('ИМБО-01-22', 'Институт математики');

INSERT INTO students (first_name, last_name, age, email, group_id) VALUES
    ('Иван', 'Иванов', 20, 'ivanov@mirea.ru', 1),
    ('Мария', 'Петрова', 21, 'petrova@mirea.ru', 2),
    ('Алексей', 'Сидоров', 19, 'sidorov@mirea.ru', 1),
    ('Елена', 'Козлова', 20, 'kozlova@mirea.ru', 3);

INSERT INTO grades (student_id, subject, grade, exam_date) VALUES
    (1, 'Базы данных', 5, '2024-01-15'),
    (1, 'Программирование', 5, '2024-01-20'),
    (1, 'Математика', 4, '2024-01-10'),
    (2, 'Базы данных', 4, '2024-01-15'),
    (2, 'Программирование', 4, '2024-01-20'),
    (3, 'Базы данных', 3, '2024-01-15'),
    (3, 'Программирование', 5, '2024-01-20'),
    (4, 'Математика', 5, '2024-01-10');

-- === Чтение данных ===

SELECT * FROM students;

SELECT s.first_name, s.last_name, g.name AS group_name
FROM students s
JOIN groups g ON s.group_id = g.id;

SELECT s.first_name, s.last_name, ROUND(AVG(gr.grade), 2) AS avg_grade
FROM students s
JOIN grades gr ON s.id = gr.student_id
GROUP BY s.id, s.first_name, s.last_name
ORDER BY avg_grade DESC;

SELECT s.first_name, s.last_name
FROM students s
JOIN grades gr ON s.id = gr.student_id
WHERE gr.subject = 'Базы данных' AND gr.grade = 5;

SELECT g.name, COUNT(s.id) AS student_count
FROM groups g
LEFT JOIN students s ON g.id = s.group_id
GROUP BY g.name;

-- === Обновление данных ===
UPDATE students SET age = 21 WHERE first_name = 'Иван' AND last_name = 'Иванов';

-- === Полезные мета-команды psql ===
\dt
\d students
\dn
\s

-- Выход
\q
EOF

echo "=== Скрипт завершён ==="
