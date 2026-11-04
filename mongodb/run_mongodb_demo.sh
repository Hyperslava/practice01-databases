#!/bin/bash
# Автоматический запуск всех команд из раздела 4.2.3–4.2.4

echo "=== Проверка логов MongoDB ==="
docker compose logs mongodb

echo "=== Проверка готовности MongoDB ==="
docker exec practice01-mongodb mongosh -u appuser -p appsecret --authenticationDatabase admin --eval "db.runCommand({ping: 1})"

echo "=== Выполнение MongoDB-команд ==="

docker exec -i practice01-mongodb mongosh -u appuser -p appsecret --authenticationDatabase admin <<'EOF'

//
// === Работа с базами данных ===
//

show dbs;
use practice_db;

//
// === Вставка документов ===
//

db.students.insertOne({
    name: "Иванов Иван",
    age: 20,
    group: "ИКБО-01-22",
    grades: {
        math: 5,
        physics: 4,
        programming: 5
    },
    hobbies: ["программирование", "шахматы"]
});

db.students.insertMany([
    {
        name: "Петрова Мария",
        age: 21,
        group: "ИКБО-02-22",
        grades: { math: 4, physics: 5, programming: 4 },
        hobbies: ["рисование", "волейбол"]
    },
    {
        name: "Сидоров Алексей",
        age: 19,
        group: "ИКБО-01-22",
        grades: { math: 3, physics: 4, programming: 5 },
        hobbies: ["программирование", "музыка"]
    }
]);

//
// === Чтение данных ===
//

db.students.find();
db.students.find().pretty();
db.students.find({ group: "ИКБО-01-22" });
db.students.find({ age: { $gt: 19 } });
db.students.find({ "grades.programming": 5 });
db.students.countDocuments();

//
// === Обновление данных ===
//

db.students.updateOne(
    { name: "Иванов Иван" },
    { $set: { age: 21 } }
);

db.students.updateOne(
    { name: "Иванов Иван" },
    { $push: { hobbies: "фотография" } }
);

//
// === Информация о коллекции ===
//

show collections;
db.students.stats();

exit;
EOF

echo "=== Скрипт завершён ==="
