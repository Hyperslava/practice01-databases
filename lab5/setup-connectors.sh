#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

connect_url=http://localhost:8085
register_connector() {
  local file=$1 name=$2
  python3 -c '
import json, sys
from pathlib import Path
payload = json.load(open(sys.argv[1]))
config = payload["config"]
for topic, query_file in payload.get("cypher_files", {}).items():
    # Kafka Connect получает одну строку, но исходный Cypher хранится читаемо.
    config[f"neo4j.cypher.topic.{topic}"] = " ".join(Path(query_file).read_text().split())
json.dump(config, sys.stdout)
' "$file" |
    curl --fail-with-body -sS -X PUT -H 'Content-Type: application/json' \
      --data-binary @- "$connect_url/connectors/$name/config" >/dev/null
}
wait_running() {
  local name=$1
  for ((i=0; i<45; i++)); do
    if curl -fsS "$connect_url/connectors/$name/status" | python3 -c '
import json,sys
d=json.load(sys.stdin)
raise SystemExit(not (d["connector"]["state"] == "RUNNING" and d["tasks"] and all(t["state"] == "RUNNING" for t in d["tasks"])))
'; then echo "$name: RUNNING"; return; fi
    sleep 2
  done
  echo "$name did not reach RUNNING" >&2; return 1
}

register_connector lab5/postgres-source.json lab5-postgres-wal2json
register_connector lab5/neo4j-sink.json lab5-neo4j-sink
register_connector lab5/mongodb-sink.json lab5-mongodb-students-cdc
register_connector lab5/mongodb-hierarchy-sink.json lab5-mongodb-university-hierarchy
wait_running lab5-postgres-wal2json
wait_running lab5-neo4j-sink
wait_running lab5-mongodb-students-cdc
wait_running lab5-mongodb-university-hierarchy
