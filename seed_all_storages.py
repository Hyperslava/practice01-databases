#!/usr/bin/env python3

from __future__ import annotations

import pymongo
import redis
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase

import uni_python_fixed_2 as university


ELASTICSEARCH_INDEX = "lectures"


def seed_postgresql() -> None:
    """Создать БД, схему и исходные данные PostgreSQL."""
    university.prepare_postgres_source()


def seed_redis() -> None:
    """Создать HASH-кэш полных карточек студентов."""
    client = redis.Redis(
        host=university.REDIS_HOST,
        port=university.REDIS_PORT,
        password=university.REDIS_PASSWORD,
        decode_responses=True,
    )
    try:
        university.seed_redis_cache(client, university.university_pg_config())
    finally:
        client.close()


def seed_mongodb() -> None:
    """Создать документные read-model материалов и структуры университета."""
    client = pymongo.MongoClient(university.MONGO_URI)
    try:
        database = client[university.MONGO_DB]
        university.seed_mongodb_read_models(
            database["lecture_read_model"],
            database["university_hierarchy_read_model"],
            university.university_pg_config(),
        )
    finally:
        client.close()


def seed_elasticsearch() -> None:
    """Пересоздать индекс лекций и загрузить поисковые документы."""
    client = Elasticsearch(university.ES_URL)
    try:
        university.recreate_elasticsearch_index(client, ELASTICSEARCH_INDEX)
        university.seed_elasticsearch_document(
            client,
            ELASTICSEARCH_INDEX,
            university.university_pg_config(),
        )
    finally:
        client.close()


def seed_neo4j() -> None:
    """Создать графовую проекцию учебного участия."""
    driver = GraphDatabase.driver(university.NEO4J_URI, auth=university.NEO4J_AUTH)
    try:
        university.seed_neo4j_graph(driver, university.university_pg_config())
    finally:
        driver.close()


def main() -> None:
    print("1/5 PostgreSQL: схема и исходные данные")
    seed_postgresql()

    print("2/5 Redis: кэш карточек студентов")
    seed_redis()

    print("3/5 MongoDB: документы материалов и структуры")
    seed_mongodb()

    print("4/5 Elasticsearch: поисковый индекс лекций")
    seed_elasticsearch()

    print("5/5 Neo4j: граф учебного участия")
    seed_neo4j()

    print("Все пять хранилищ заполнены.")


if __name__ == "__main__":
    main()
