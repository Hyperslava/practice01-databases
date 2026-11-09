## Создание студента в postgres (Create)
export TEST_ID=$(uuidgen)
export GROUP_ID=$(docker exec practice01-postgres psql -X -At -U admin -d university_system \
  -c 'SELECT id FROM public.student_groups ORDER BY id LIMIT 1')

docker exec practice01-postgres psql -U admin -d university_system -c \
"INSERT INTO public.students
 (id, group_id, first_name, last_name, email, student_card_number, enrollment_date, status)
 VALUES
 ('$TEST_ID', '$GROUP_ID', 'Manual created', 'CDC',
  'manual-$TEST_ID@example.invalid', 'MANUAL-${TEST_ID:0:8}', CURRENT_DATE, 'active')"

## Увидеть событие в kafka - сразу в другом терминале:
docker compose -f lab5/docker-compose.kafka.yml exec -T broker \
  kafka-console-consumer --bootstrap-server broker:29092 \
  --topic university.public.students --from-beginning --timeout-ms 3000 \
  | grep "$TEST_ID"

## Проверить Neo4j:
docker exec practice01-neo4j cypher-shell -u neo4j -p neo4jsecret \
  "MATCH (s:Student {id: '$TEST_ID'})-[:MEMBER_OF]->(g:StudentGroup)
   RETURN s.first_name, s.last_name, g.name"

## Проверить Mongodb:
docker exec practice01-mongodb mongosh --quiet -u appuser -p appsecret \
  --authenticationDatabase admin \
  --eval "db.getSiblingDB('university_system').students_cdc.findOne({_id:{id:'$TEST_ID'}})"

## Update:
docker exec practice01-postgres psql -U admin -d university_system -c \
"UPDATE public.students
 SET first_name='Manual updated', updated_at=NOW()
 WHERE id='$TEST_ID'"

## Delete:
docker exec practice01-postgres psql -U admin -d university_system -c \
"DELETE FROM public.students WHERE id='$TEST_ID'"

## Просмотр иерархии mongodb

docker exec practice01-mongodb mongosh --quiet -u appuser -p appsecret \
  --authenticationDatabase admin \
  --eval "db.getSiblingDB('university_system').university_hierarchy_cdc.findOne()"

Если иерархия не отображается полностью:  

docker exec practice01-postgres psql -U admin -d university_system -c \
"UPDATE public.universities SET updated_at = NOW()"
docker exec practice01-postgres psql -U admin -d university_system -c \
"UPDATE public.institutes SET updated_at = NOW()"
docker exec practice01-postgres psql -U admin -d university_system -c \
"UPDATE public.departments SET updated_at = NOW()"