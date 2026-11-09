WITH __value AS e
WHERE e IS NOT NULL
WITH e, CASE WHEN e.op = 'd' THEN e.before ELSE e.after END AS r
OPTIONAL MATCH (old:Department {id: r.id})
FOREACH (_ IN CASE WHEN e.op = 'd' THEN [1] ELSE [] END | DETACH DELETE old)
WITH e, r
FOREACH (_ IN CASE WHEN e.op IN ['c', 'r', 'u'] THEN [1] ELSE [] END |
  MERGE (i:Institute {id: r.institute_id})
  MERGE (n:Department {id: r.id})
  SET n = r
  MERGE (i)-[:HAS_DEPARTMENT]->(n)
)
