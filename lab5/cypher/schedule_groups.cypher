WITH __value AS e
WHERE e IS NOT NULL
WITH e, CASE WHEN e.op = 'd' THEN e.before ELSE e.after END AS r
OPTIONAL MATCH (:ClassSession {id: r.schedule_id})-[old:FOR_GROUP]->(:StudentGroup {id: r.group_id})
FOREACH (_ IN CASE WHEN e.op = 'd' THEN [1] ELSE [] END | DELETE old)
WITH e, r
FOREACH (_ IN CASE WHEN e.op IN ['c', 'r', 'u'] THEN [1] ELSE [] END |
  MERGE (s:ClassSession {id: r.schedule_id})
  MERGE (g:StudentGroup {id: r.group_id})
  MERGE (s)-[:FOR_GROUP]->(g)
)
