#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
echo "─── Local Tests ───"
PASS=0; FAIL=0
run() { local n="$1"; shift; echo -n "  $n... "; if "$@" >/dev/null 2>&1; then echo "✓"; PASS=$((PASS+1)); else echo "✗"; FAIL=$((FAIL+1)); fi; }
[ -d /repo/backend/tests ] && run "Backend tests" python3 -m pytest /repo/backend/tests/ -x -q
for s in "backend:${BACKEND_PORT:-8081}" "mobile-backend:${MOBILE_BACKEND_PORT:-8082}"; do
    IFS=':' read -r n p <<< "$s"; run "HTTP $n" curl -sf "http://$n:$p/health"
done
echo ""; echo "  Passed: $PASS | Failed: $FAIL"
