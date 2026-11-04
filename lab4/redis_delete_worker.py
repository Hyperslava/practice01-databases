import json
import os
import time

import redis
from confluent_kafka import Consumer


# Compose передаёт имя топика и параметры подключения к Redis.
topic = os.environ["KAFKA_TOPIC"]
client = redis.Redis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ.get("REDIS_PORT", "6379")),
    password=os.environ["REDIS_PASSWORD"],
    decode_responses=True,
)
# Отдельная consumer group позволяет sink и обработчику читать один топик.
# Offset подтверждается после успешной команды Redis.
consumer = Consumer(
    {
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "group.id": "lab4-redis-delete-worker",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
)
consumer.subscribe([topic])

# Читать CDC-события всё время работы контейнера.
while True:
    message = consumer.poll(1)
    if message is None:
        continue
    if message.error():
        print(message.error(), flush=True)
        time.sleep(2)
        continue
    try:
        # Debezium кладёт удалённую строку в before и устанавливает op=d.
        event = json.loads(message.value()) if message.value() else None
        if event and event.get("op") == "d":
            row = event.get("before") or {}
            student_id = row.get("id")
            if student_id is None and message.key():
                student_id = json.loads(message.key()).get("id")
            if student_id is None:
                raise ValueError("Delete event has no student id")
            # В cache mode ключ Redis равен id студента.
            client.delete(str(student_id))
            print(f"Deleted Redis key {student_id}", flush=True)
        consumer.commit(message=message, asynchronous=False)
    except Exception as exc:
        # Offset остаётся неподтверждённым; перезапуск может повторить событие.
        print(f"Cannot process Kafka offset {message.offset()}: {exc}", flush=True)
        time.sleep(2)
