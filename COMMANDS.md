

Все команды выполняются в WSL из `~/practice01-databases`.

## Чистый запуск и генерация данных

При необходимости сбросить все БД и начать с нуля:

```bash
docker compose -f all-in-one/docker-compose.yaml down -v --remove-orphans
docker compose -f all-in-one/docker-compose.yaml up -d --build
```

Подготовить схему и заполнить все пять хранилищ. Seed сам определяет адрес Windows-хоста из WSL; повторный запуск пересоздаёт fixture-данные:

```bash
python seed_all_storages.py
```

## Лабораторные 1–3: API

```bash
docker compose -f docker-compose.lab.yml up -d --build
./api_console.sh
```

В консоли выберите `2`, `3`, `4` или `5` для отчётов ЛР1, ЛР2, ЛР3 или запуска всех трёх.

## Лабораторная 4: CDC

```bash
bash lab4/setup-all.sh
bash lab4/setup-redis.sh
bash lab4/test-cdc.sh
bash lab4/test-redis.sh
```

ЛР4 передаёт изменения из PostgreSQL через Kafka в Elasticsearch и Redis. Проверка должна завершиться строками `PASS`.

## Логи и остановка

Логи API: `Logs/lab1_pipeline.log`, `Logs/lab2_pipeline.log`, `Logs/lab3_pipeline.log`.

```bash
docker compose -f docker-compose.lab.yml logs --tail=100
docker compose -f all-in-one/docker-compose.yaml down
```
