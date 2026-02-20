#!/bin/bash
# run-tests.sh — Complete E2E test suite
set -euo pipefail

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  INFRA-DEPLOY E2E TEST SUITE                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$PROJECT"
source .env 2>/dev/null || true

SSH_KEY="${PROJECT}/keys/deployer"
PASS=0 FAIL=0 SKIP=0 TOTAL=0
G='\033[0;32m'; R='\033[0;31m'; Y='\033[1;33m'; N='\033[0m'

t() { TOTAL=$((TOTAL+1)); if ( eval "$2" ) >/dev/null 2>&1; then printf "  ${G}✓${N} %-55s PASS\n" "$1"; PASS=$((PASS+1)); else printf "  ${R}✗${N} %-55s FAIL\n" "$1"; FAIL=$((FAIL+1)); fi; }
s() { TOTAL=$((TOTAL+1)); SKIP=$((SKIP+1)); printf "  ${Y}○${N} %-55s SKIP (%s)\n" "$1" "$2"; }
sx() { local p=$1 u=$2; ssh -i "$SSH_KEY" -p "$p" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$u@localhost" "${@:3}" 2>/dev/null; }

# ═══ 1. UNIT TESTS ═══
echo ""; echo "  1. UNIT TESTS"
if python3 -c "import flask" 2>/dev/null; then
    t "Backend: health tests" "cd '$PROJECT/backend' && python3 -m pytest tests/test_api.py::TestHealthEndpoints -x -q"
    t "Backend: info tests" "cd '$PROJECT/backend' && python3 -m pytest tests/test_api.py::TestInfoEndpoint -x -q"
    t "Backend: echo tests" "cd '$PROJECT/backend' && python3 -m pytest tests/test_api.py::TestEchoEndpoint -x -q"
else s "Backend unit tests" "flask not installed"; fi

# ═══ 2. SHARED LIB ═══
echo ""; echo "  2. SHARED LIBRARY"
t "llm_client.py exists" "test -f '$PROJECT/shared/lib/llm_client.py'"
t "ticket_system.py exists" "test -f '$PROJECT/shared/lib/ticket_system.py'"
t "llm_client importable" "PYTHONPATH='$PROJECT/shared/lib' python3 -c 'import llm_client; llm_client.get_config()'"
t "ticket_system importable" "PYTHONPATH='$PROJECT/shared/lib' python3 -c 'import ticket_system'"
t "ticket_system: create/list/get" "PYTHONPATH='$PROJECT/shared/lib' TICKETS_DIR=/tmp/test-tickets python3 -c \"
import ticket_system as ts
t = ts.create('Test ticket', description='E2E test', priority='high')
assert t['id'].startswith('T-')
assert ts.get(t['id'])['title'] == 'Test ticket'
assert len(ts.list_tickets()) >= 1
ts.update(t['id'], status='closed')
assert ts.get(t['id'])['status'] == 'closed'
\""
rm -rf /tmp/test-tickets

# ═══ 3. CONFIGURATION ═══
echo ""; echo "  3. CONFIGURATION"
t "docker-compose.yml valid" "python3 -c \"import yaml; yaml.safe_load(open('docker-compose.yml'))\""
t "15 services" "python3 -c \"import yaml; d=yaml.safe_load(open('docker-compose.yml')); assert len(d['services'])==15, len(d['services'])\""
t "9 networks" "python3 -c \"import yaml; d=yaml.safe_load(open('docker-compose.yml')); assert len(d['networks'])==9\""
t ".env has SSH_MANAGER_PORT" "grep -q SSH_MANAGER_PORT .env"
t ".env has SSH_AUTOPILOT_PORT" "grep -q SSH_AUTOPILOT_PORT .env"
t ".env has SSH_MONITOR_PORT" "grep -q SSH_MONITOR_PORT .env"
t "ssh-developer/.env has LLM_MODEL" "grep -q LLM_MODEL ssh-developer/.env"
t "ssh-monitor/.env has LLM_MODEL" "grep -q LLM_MODEL ssh-monitor/.env"
t "ssh-manager/.env has LLM_MODEL" "grep -q LLM_MODEL ssh-manager/.env"
t "ssh-autopilot/.env has AUTOPILOT_INTERVAL" "grep -q AUTOPILOT_INTERVAL ssh-autopilot/.env"

# ═══ 4. NETWORK ISOLATION ═══
echo ""; echo "  4. NETWORK ISOLATION"
t "Developer NOT on ssh-net" "python3 -c \"
import yaml; d=yaml.safe_load(open('docker-compose.yml'))
nets=d['services']['ssh-developer']['networks']
assert 'ssh-net' not in nets, f'developer on ssh-net: {nets}'
\""
t "Monitor IS on ssh-net" "python3 -c \"
import yaml; d=yaml.safe_load(open('docker-compose.yml'))
assert 'ssh-net' in d['services']['ssh-monitor']['networks']
\""
t "Manager IS on mgmt-net" "python3 -c \"
import yaml; d=yaml.safe_load(open('docker-compose.yml'))
assert 'mgmt-net' in d['services']['ssh-manager']['networks']
\""
t "Autopilot IS on mgmt-net" "python3 -c \"
import yaml; d=yaml.safe_load(open('docker-compose.yml'))
assert 'mgmt-net' in d['services']['ssh-autopilot']['networks']
\""
t "Developer NO docker socket" "python3 -c \"
import yaml; d=yaml.safe_load(open('docker-compose.yml'))
vols=str(d['services']['ssh-developer'].get('volumes',''))
assert 'docker.sock' not in vols
\""
t "Each role has shared-tickets volume" "python3 -c \"
import yaml; d=yaml.safe_load(open('docker-compose.yml'))
for svc in ['ssh-manager','ssh-autopilot','ssh-developer','ssh-monitor']:
    vols=str(d['services'][svc]['volumes'])
    assert 'shared-tickets' in vols, f'{svc} missing shared-tickets'
\""
t "Each role has shared/lib bind mount" "python3 -c \"
import yaml; d=yaml.safe_load(open('docker-compose.yml'))
for svc in ['ssh-manager','ssh-autopilot','ssh-developer','ssh-monitor']:
    vols=str(d['services'][svc]['volumes'])
    assert 'shared/lib' in vols, f'{svc} missing shared/lib'
\""

# ═══ 5. PER-SERVICE .ENV ═══
echo ""; echo "  5. PER-SERVICE ENV FILES"
for svc in developer monitor manager autopilot; do
    t "ssh-${svc}/.env exists" "test -f ssh-${svc}/.env"
    t "ssh-${svc}/.env has SERVICE_ROLE" "grep -q 'SERVICE_ROLE=${svc}' ssh-${svc}/.env"
done

# ═══ 6. DOCKER INTEGRATION (optional) ═══
HAS_DOCKER=false
command -v docker &>/dev/null && docker compose ps 2>/dev/null | grep -q "Up" && HAS_DOCKER=true

echo ""; echo "  6. DOCKER INTEGRATION"
if $HAS_DOCKER && [ -f "$SSH_KEY" ]; then
    t "SSH Manager (:2202) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2202'"
    t "SSH Autopilot (:2203) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2203'"
    t "SSH Developer (:2200) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2200'"
    t "SSH Monitor (:2201) open" "timeout 5 bash -c 'echo >/dev/tcp/localhost/2201'"

    t "Manager: login works" "sx 2202 manager 'echo ok'"
    t "Manager: scripts exist" "sx 2202 manager 'test -f ~/scripts/ticket-create.sh'"
    t "Manager: can reach developer" "sx 2202 manager 'ssh ssh-developer echo ok'"
    t "Manager: can reach monitor" "sx 2202 manager 'ssh ssh-monitor echo ok'"

    t "Developer: login works" "sx 2200 developer 'echo ok'"
    t "Developer: has /shared/lib" "sx 2200 developer 'test -f /shared/lib/llm_client.py'"
    t "Developer: has /shared/tickets" "sx 2200 developer 'test -d /shared/tickets'"
    t "Developer: NO deploy scripts" "! sx 2200 developer 'test -f ~/deploy/deploy-all.sh'"

    t "Monitor: login works" "sx 2201 monitor 'echo ok'"
    t "Monitor: has deploy scripts" "sx 2201 monitor 'test -f ~/deploy/deploy-all.sh'"
    t "Monitor: daemon running" "sx 2201 monitor 'pgrep -f monitor-daemon'"

    t "Autopilot: login works" "sx 2203 autopilot 'echo ok'"
    t "Autopilot: daemon running" "sx 2203 autopilot 'pgrep -f autopilot-daemon'"

    # Ticket flow: Manager creates → Developer sees
    t "Ticket flow: create on manager" "sx 2202 manager 'PYTHONPATH=/shared/lib TICKETS_DIR=/shared/tickets python3 /shared/lib/ticket_system.py create \"E2E test ticket\" --priority=high'"
    t "Ticket flow: visible on developer" "sx 2200 developer 'PYTHONPATH=/shared/lib TICKETS_DIR=/shared/tickets python3 /shared/lib/ticket_system.py list | grep -q \"E2E test\"'"
else
    s "Docker integration tests (18)" "Docker not running"
fi

# ═══ SUMMARY ═══
echo ""
echo "══════════════════════════════════════════════════════════"
printf "  ${G}%d PASSED${N}  ${R}%d FAILED${N}  ${Y}%d SKIPPED${N}  (total %d)\n" "$PASS" "$FAIL" "$SKIP" "$TOTAL"
echo "══════════════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ] && echo -e "  ${G}ALL TESTS PASSED ✓${N}" || echo -e "  ${R}SOME TESTS FAILED ✗${N}"
echo ""; exit "$FAIL"
