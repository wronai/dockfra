#!/bin/bash
# run-tests.sh — E2E test suite for Dockfra hybrid architecture
set -euo pipefail

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  DOCKFRA E2E TEST SUITE (Hybrid)                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$PROJECT"
MGMT="$PROJECT/management"
APP="$PROJECT/app"

PASS=0 FAIL=0 SKIP=0 TOTAL=0
G='\033[0;32m'; R='\033[0;31m'; Y='\033[1;33m'; N='\033[0m'

t() { TOTAL=$((TOTAL+1)); if ( eval "$2" ) >/dev/null 2>&1; then printf "  ${G}✓${N} %-55s PASS\n" "$1"; PASS=$((PASS+1)); else printf "  ${R}✗${N} %-55s FAIL\n" "$1"; FAIL=$((FAIL+1)); fi; }
s() { TOTAL=$((TOTAL+1)); SKIP=$((SKIP+1)); printf "  ${Y}○${N} %-55s SKIP (%s)\n" "$1" "$2"; }
sx() { local p=$1 u=$2; ssh -i "$SSH_KEY" -p "$p" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$u@localhost" "${@:3}" 2>/dev/null; }

HAS_PYYAML=false
python3 -c "import yaml" >/dev/null 2>&1 && HAS_PYYAML=true

HAS_DOCKER_COMPOSE=false
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    HAS_DOCKER_COMPOSE=true
fi

compose_assert() {
    local compose_file="$1"
    local check="$2"

    if $HAS_PYYAML; then
        python3 - "$compose_file" "$check" <<'PY'
import sys
import yaml

path, check = sys.argv[1], sys.argv[2]
d = yaml.safe_load(open(path))
exec(check, {"d": d})
PY
    elif $HAS_DOCKER_COMPOSE; then
        docker compose -f "$compose_file" config --format json 2>/dev/null | \
            python3 - "$check" <<'PY'
import json
import sys

check = sys.argv[1]
d = json.load(sys.stdin)
exec(check, {"d": d})
PY
    else
        return 1
    fi
}

# ═══ 1. STRUCTURE ═══
echo ""; echo "  1. PROJECT STRUCTURE"
t "management/ exists" "test -d '$MGMT'"
t "app/ exists" "test -d '$APP'"
t "management/docker-compose.yml exists" "test -f '$MGMT/docker-compose.yml'"
t "management/docker-compose-production.yml exists" "test -f '$MGMT/docker-compose-production.yml'"
t "app/docker-compose.yml exists" "test -f '$APP/docker-compose.yml'"
t "app/docker-compose-production.yml exists" "test -f '$APP/docker-compose-production.yml'"
t "management/scripts/init.sh exists" "test -f '$MGMT/scripts/init.sh'"
t "app/scripts/init.sh exists" "test -f '$APP/scripts/init.sh'"
t "init.sh (root) exists" "test -f '$PROJECT/init.sh'"

# ═══ 2. SHARED LIB ═══
echo ""; echo "  2. SHARED LIBRARY"
t "management: llm_client.py" "test -f '$PROJECT/shared/lib/llm_client.py'"
t "management: ticket_system.py" "test -f '$PROJECT/shared/lib/ticket_system.py'"
t "app: llm_client.py" "test -f '$PROJECT/shared/lib/llm_client.py'"
t "app: ticket_system.py" "test -f '$PROJECT/shared/lib/ticket_system.py'"
t "llm_client importable" "PYTHONPATH='$PROJECT/shared/lib' python3 -c 'import llm_client; llm_client.get_config()'"
t "ticket_system importable" "PYTHONPATH='$PROJECT/shared/lib' python3 -c 'import ticket_system'"
t "ticket_system: create/list/get/update" "PYTHONPATH='$PROJECT/shared/lib' TICKETS_DIR=/tmp/dockfra-test-tickets python3 -c \"
import ticket_system as ts
t = ts.create('Test ticket', description='E2E test', priority='high')
assert t['id'].startswith('T-')
assert ts.get(t['id'])['title'] == 'Test ticket'
assert len(ts.list_tickets()) >= 1
ts.update(t['id'], status='closed')
assert ts.get(t['id'])['status'] == 'closed'
\""
rm -rf /tmp/dockfra-test-tickets

# ═══ 3. UNIT TESTS ═══
echo ""; echo "  3. BACKEND UNIT TESTS"
if python3 -c "import flask; import psycopg2" 2>/dev/null; then
    t "Backend: health tests" "cd '$APP/backend' && python3 -m pytest tests/test_api.py::TestHealthEndpoints -x -q"
    t "Backend: info tests" "cd '$APP/backend' && python3 -m pytest tests/test_api.py::TestInfoEndpoint -x -q"
    t "Backend: echo tests" "cd '$APP/backend' && python3 -m pytest tests/test_api.py::TestEchoEndpoint -x -q"
else s "Backend unit tests (3)" "flask/psycopg2 not installed (run inside container)"; fi

# ═══ 4. COMPOSE VALIDATION ═══
echo ""; echo "  4. DOCKER-COMPOSE VALIDATION"
t "management compose: valid YAML" "compose_assert '$MGMT/docker-compose.yml' 'assert isinstance(d, dict)'"
t "management compose: 4 services" "compose_assert '$MGMT/docker-compose.yml' 'assert len(d[\"services\"]) == 4, len(d[\"services\"])'"
t "management prod compose: valid YAML" "compose_assert '$MGMT/docker-compose-production.yml' 'assert isinstance(d, dict)'"
t "app compose: valid YAML" "compose_assert '$APP/docker-compose.yml' 'assert isinstance(d, dict)'"
t "app compose: 8 services" "compose_assert '$APP/docker-compose.yml' 'assert len(d[\"services\"]) == 8, len(d[\"services\"])'"
t "app prod compose: valid YAML" "compose_assert '$APP/docker-compose-production.yml' 'assert isinstance(d, dict)'"
t "devices compose: valid YAML" "compose_assert '$PROJECT/devices/docker-compose.yml' 'assert isinstance(d, dict)'"
t "devices compose: 3 services" "compose_assert '$PROJECT/devices/docker-compose.yml' 'assert len(d[\"services\"]) == 3, len(d[\"services\"])'"

# ═══ 5. NETWORK ISOLATION ═══
echo ""; echo "  5. NETWORK ISOLATION"
t "Management uses dockfra-shared (external)" "compose_assert '$MGMT/docker-compose.yml' 'assert d[\"networks\"][\"dockfra-shared\"][\"external\"] is True'"
t "App uses dockfra-shared (external)" "compose_assert '$APP/docker-compose.yml' 'assert d[\"networks\"][\"dockfra-shared\"][\"external\"] is True'"
t "ssh-developer on dockfra-shared" "compose_assert '$APP/docker-compose.yml' 'nets=d[\"services\"][\"ssh-developer\"][\"networks\"]; assert \"dockfra-shared\" in nets, f\"developer not on dockfra-shared: {nets}\"'"
t "ssh-manager on dockfra-shared" "compose_assert '$MGMT/docker-compose.yml' 'nets=d[\"services\"][\"ssh-manager\"][\"networks\"]; assert \"dockfra-shared\" in nets'"
t "Production: no external network" "compose_assert '$MGMT/docker-compose-production.yml' 'for name, cfg in d.get(\"networks\", {}).items(): assert not cfg.get(\"external\", False), f\"{name} is external in production\"'"

# ═══ 6. DOCKERFILES ═══
echo ""; echo "  6. DOCKERFILES"
t "ssh-manager Dockerfile" "test -f '$MGMT/ssh-manager/Dockerfile'"
t "ssh-autopilot Dockerfile" "test -f '$MGMT/ssh-autopilot/Dockerfile'"
t "ssh-monitor Dockerfile" "test -f '$MGMT/ssh-monitor/Dockerfile'"
t "ssh-developer Dockerfile" "test -f '$APP/ssh-developer/Dockerfile'"
t "frontend Dockerfile" "test -f '$APP/frontend/Dockerfile'"
t "backend Dockerfile" "test -f '$APP/backend/Dockerfile'"
t "mobile-backend Dockerfile" "test -f '$APP/mobile-backend/Dockerfile'"
t "desktop-app Dockerfile" "test -f '$APP/desktop-app/Dockerfile'"
t "ssh-rpi3 Dockerfile" "test -f '$PROJECT/devices/ssh-rpi3/Dockerfile'"
t "vnc-rpi3 Dockerfile" "test -f '$PROJECT/devices/vnc-rpi3/Dockerfile'"
t "desktop Dockerfile" "test -f '$MGMT/desktop/Dockerfile'"

# ═══ 7. PER-SERVICE .ENV ═══
echo ""; echo "  7. PER-SERVICE ENV FILES"
for svc in developer; do
    t "app/ssh-${svc}/.env exists" "test -f '$APP/ssh-${svc}/.env'"
    t "app/ssh-${svc}/.env has SERVICE_ROLE" "grep -q 'SERVICE_ROLE=${svc}' '$APP/ssh-${svc}/.env'"
done
for svc in monitor manager autopilot; do
    t "management/ssh-${svc}/.env exists" "test -f '$MGMT/ssh-${svc}/.env'"
    t "management/ssh-${svc}/.env has SERVICE_ROLE" "grep -q 'SERVICE_ROLE=${svc}' '$MGMT/ssh-${svc}/.env'"
done

# ═══ 8. SCRIPTS ═══
echo ""; echo "  8. SCRIPTS"
t "management/scripts/init.sh executable" "test -x '$MGMT/scripts/init.sh'"
t "management/scripts/generate-keys.sh executable" "test -x '$MGMT/scripts/generate-keys.sh'"
t "management/scripts/setup-local.sh executable" "test -x '$MGMT/scripts/setup-local.sh'"
t "management/scripts/setup-production.sh executable" "test -x '$MGMT/scripts/setup-production.sh'"
t "management/scripts/sync-keys-to-developer.sh executable" "test -x '$MGMT/scripts/sync-keys-to-developer.sh'"
t "app/scripts/init.sh executable" "test -x '$APP/scripts/init.sh'"
t "app/scripts/generate-developer-keys.sh executable" "test -x '$APP/scripts/generate-developer-keys.sh'"
t "root init.sh executable" "test -x '$PROJECT/init.sh'"

# ═══ 9. DOCKER INTEGRATION (optional) ═══
echo ""; echo "  9. DOCKER INTEGRATION"
HAS_MGMT=false; HAS_APP=false
if command -v docker &>/dev/null; then
    docker compose -f "$MGMT/docker-compose.yml" ps 2>/dev/null | grep -q "Up" && HAS_MGMT=true
    docker compose -f "$APP/docker-compose.yml" ps 2>/dev/null | grep -q "Up" && HAS_APP=true
fi

SSH_KEY="$MGMT/keys/manager/id_ed25519"
[ ! -f "$SSH_KEY" ] && SSH_KEY="$MGMT/keys/deployer"

if $HAS_MGMT && $HAS_APP && [ -f "$SSH_KEY" ]; then
    t "SSH Manager (:2202) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2202'"
    t "SSH Autopilot (:2203) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2203'"
    t "SSH Developer (:2200) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2200'"
    t "SSH Monitor (:2201) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2201'"

    t "Manager: login works" "sx 2202 manager 'echo ok'"
    t "Developer: login works" "sx 2200 developer 'echo ok'"
    t "Monitor: login works" "sx 2201 monitor 'echo ok'"
    t "Autopilot: login works" "sx 2203 autopilot 'echo ok'"

    t "Cross-stack: manager can reach developer" "sx 2202 manager 'ssh ssh-developer echo ok'"
    t "Developer: has /shared/lib" "sx 2200 developer 'test -f /shared/lib/llm_client.py'"
    t "Developer: has /shared/tickets" "sx 2200 developer 'test -d /shared/tickets'"

    t "Ticket flow: create on manager" "sx 2202 manager 'PYTHONPATH=/shared/lib TICKETS_DIR=/shared/tickets python3 /shared/lib/ticket_system.py create \"E2E test ticket\" --priority=high'"
    t "Ticket flow: visible on developer" "sx 2200 developer 'PYTHONPATH=/shared/lib TICKETS_DIR=/shared/tickets python3 /shared/lib/ticket_system.py list | grep -q \"E2E test\"'"
else
    s "Docker integration tests (13)" "Docker stacks not running"
fi

# ═══ SUMMARY ═══
echo ""
echo "══════════════════════════════════════════════════════════"
printf "  ${G}%d PASSED${N}  ${R}%d FAILED${N}  ${Y}%d SKIPPED${N}  (total %d)\n" "$PASS" "$FAIL" "$SKIP" "$TOTAL"
echo "══════════════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ] && echo -e "  ${G}ALL TESTS PASSED ✓${N}" || echo -e "  ${R}SOME TESTS FAILED ✗${N}"
echo ""; exit "$FAIL"
