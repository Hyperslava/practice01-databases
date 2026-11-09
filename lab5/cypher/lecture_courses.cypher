WITH __value AS e
WHERE e IS NOT NULL
WITH e, CASE WHEN e.op = 'd' THEN e.before ELSE e.after END AS r
OPTIONAL MATCH (old:LectureCourse {id: r.id})
FOREACH (_ IN CASE WHEN e.op = 'd' THEN [1] ELSE [] END | DETACH DELETE old)
WITH e, r
FOREACH (_ IN CASE WHEN e.op IN ['c', 'r', 'u'] THEN [1] ELSE [] END |
  MERGE (d:Department {id: r.reading_department_id})
  MERGE (n:LectureCourse {id: r.id})
  SET n = r
  MERGE (d)-[:READS]->(n)
)
