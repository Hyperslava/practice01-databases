WITH __value AS e
WHERE e IS NOT NULL
WITH e, CASE WHEN e.op = 'd' THEN e.before ELSE e.after END AS r
OPTIONAL MATCH (old:Institute {id: r.id})
FOREACH (_ IN CASE WHEN e.op = 'd' THEN [1] ELSE [] END | DETACH DELETE old)
WITH e, r
FOREACH (_ IN CASE WHEN e.op IN ['c', 'r', 'u'] THEN [1] ELSE [] END |
  MERGE (u:University {id: r.university_id})
  MERGE (n:Institute {id: r.id})
  SET n = r
  MERGE (u)-[:HAS_INSTITUTE]->(n)
)
