# docker compose -f docker-compose.lab1.yml up -d

TOKEN=$(curl -s -X POST \
  "http://localhost:8088/auth/token?username=teacher&password=teacher-secret" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  
curl -G "http://localhost:8088/api/v1/lab1/report"   --data-urlencode "term=база данных"   --data-urlencode "from=2026-02-09"   --data-urlencode "to=2026-03-22"   -H "Authorization: Bearer $TOKEN"