#!/bin/bash
echo "─── Service Health (read-only) ───"
for s in "frontend:80" "backend:${BACKEND_PORT:-8081}" "mobile-backend:${MOBILE_BACKEND_PORT:-8082}"; do
    IFS=':' read -r n p <<< "$s"
    st=$(curl -sf "http://$n:$p/health" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('status','?'))" 2>/dev/null || echo "down")
    printf "  %-20s %s\n" "$n" "$st"
done
