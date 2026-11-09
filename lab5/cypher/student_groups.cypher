WITH __value AS e
WHERE e IS NOT NULL
WITH e, CASE WHEN e.op = 'd' THEN e.before ELSE e.after END AS r
OPTIONAL MATCH (old:StudentGroup {id: r.id})
FOREACH (_ IN CASE WHEN e.op = 'd' THEN [1] ELSE [] END | DETACH DELETE old)
WITH e, r
FOREACH (_ IN CASE WHEN e.op IN ['c', 'r', 'u'] THEN [1] ELSE [] END |
  MERGE (d:Department {id: r.department_id})
  MERGE (n:StudentGroup {id: r.id})
  SET n = r
  MERGE (d)-[:HAS_GROUP]->(n)
)
