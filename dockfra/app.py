#!/usr/bin/env python3
"""Dockfra Setup Wizard — http://localhost:5050

This is the main entry point. All logic is split across:
- core.py      — shared state, Flask app, UI helpers, env, docker utils
- steps.py     — wizard step functions
- fixes.py     — fix/repair/diagnostic functions
- discover.py  — SSH role discovery + console
"""
from .core import (
    app, socketio, _tl, _state, _conversation, _logs, _log_buffer,
    _sid_emit, _ENV_TO_STATE, _STATE_TO_ENV, reset_state,
    ENV_SCHEMA, load_env, save_env,
    ROOT, MGMT, _PKG_DIR, cname,
    _llm_chat, _llm_config, _LLM_AVAILABLE, _WIZARD_SYSTEM_PROMPT,
    msg, buttons, progress, mask, clear_widgets,
    run_cmd, docker_ps, _analyze_container_log,
    _local_interfaces, _arp_devices, _devices_env_ip, _subnet_ping_sweep,
    _docker_container_env,
    json, subprocess, threading, request, emit, render_template, _socket,
)
from .steps import (
    step_welcome, step_status, step_pick_logs, step_show_logs,
    step_settings, step_save_settings,
    step_setup_creds, step_save_creds,
    step_launch_all, step_launch_configure, step_do_launch,
    step_deploy_device, step_test_device, step_do_deploy,
    step_launch_devices,
    step_post_launch_creds, step_run_post_creds,
    step_preflight_fill,
)
from .fixes import (
    step_fix_container, _do_restart_container,
    step_suggest_commands, _run_suggested_cmd,
    diag_port, show_missing_env, _prompt_api_key, _ensure_llm_key,
    validate_llm_connection, validate_docker,
    fix_network_overlap, retry_launch, fix_vnc_port,
    fix_acme_storage, fix_readonly_volume, fix_docker_perms,
)
from .discover import (
    _step_ssh_info, step_ssh_console, run_ssh_cmd, _SSH_ROLES, _refresh_ssh_roles, _get_role,
)
import os as _os, sys as _sys
from . import tickets as _tickets
from .pipeline import PipelineState, StepResult, run_step, evaluate_implementation, evaluate_test_output, build_retry_prompt
from . import engines as _engines

STEPS = {
    "welcome":          lambda f: step_welcome(),
    "back":             lambda f: step_welcome(),
    "status":           lambda f: step_status(),
    "pick_logs":        lambda f: step_pick_logs(),
    "settings":         lambda f: step_settings(),
    "setup_creds":      lambda f: step_setup_creds(),
    "save_creds":       step_save_creds,
    "launch_all":       lambda f: step_launch_all(),
    "launch_configure": lambda f: step_launch_configure(),
    "do_launch":        step_do_launch,
    "retry_launch":     lambda f: retry_launch(f),
    "deploy_device":    lambda f: step_deploy_device(),
    "test_device":      step_test_device,
    "do_deploy":        step_do_deploy,
    "launch_devices":   step_launch_devices,
    "post_launch_creds":lambda f: step_post_launch_creds(),
    "run_post_creds":   lambda f: step_run_post_creds(),
    "fix_docker_perms":    lambda f: fix_docker_perms(),
    "fix_vnc_port":        lambda f: fix_vnc_port(),
    "fix_acme_storage":    lambda f: fix_acme_storage(),
    "fix_readonly_volume": lambda f: fix_readonly_volume(),
    "fix_readonly_volume::":lambda f: fix_readonly_volume(),
}

# ── socket events ─────────────────────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    _tl.sid = request.sid
    try:
        if not _conversation:
            reset_state()
            step_welcome()
        else:
            # Replay conversation to THIS client only
            for m in _conversation:
                emit("message", m)
            emit("clear_widgets", {})
            step = _state.get("step","welcome")
            if step in ("welcome", None, ""):
                buttons([
                    {"label":"🚀 Uruchom infrastrukturę",  "value":"launch_all"},
                    {"label":"📦 Wdróż na urządzenie",      "value":"deploy_device"},
                    {"label":"⚙️ Ustawienia (.env)",         "value":"settings"},
                ])
            else:
                # For other steps, just replay messages, don't re-execute step logic
                pass
    finally:
        _tl.sid = None

@socketio.on("disconnect")
def on_disconnect():
    _tl.sid = None

@socketio.on("action")
def on_action(data):
    _tl.sid = request.sid
    try:
        value = data.get("value","")
        form  = data.get("form", {})
        if _dispatch(value, form):
            return
        # Async-only actions (need threading for SocketIO mode)
        if value.startswith("ai_analyze::"):
            cname = value.split("::",1)[1]
            _tl_sid = getattr(_tl, 'sid', None)
            def _ai_analyze_thread(name=cname):
                _tl.sid = _tl_sid
                key = _state.get("openrouter_key", "") or _state.get("openrouter_api_key", "")
                if key: os.environ["OPENROUTER_API_KEY"] = key
                if not _LLM_AVAILABLE or not _llm_config().get("api_key"):
                    _prompt_api_key(return_action=f"ai_analyze::{name}")
                    return
                try:
                    out = subprocess.check_output(
                        ["docker","logs","--tail","60",name],
                        text=True, stderr=subprocess.STDOUT)
                except Exception as e:
                    msg(f"❌ Nie można pobrać logów: {e}"); return
                progress("🧠 AI analizuje logi...")
                prompt = (f"Kontener Docker `{name}` ma problem. Ostatnie logi:\n"
                          f"```\n{out[-3000:]}\n```\n"
                          "Określ przyczynę błędu i podaj konkretne kroki naprawy.")
                reply = _llm_chat(prompt, system_prompt=_WIZARD_SYSTEM_PROMPT)
                progress("🧠 AI", done=True)
                msg(f"### 🧠 Analiza AI: `{name}`\n{reply}")
                buttons([{"label": "💡 Zaproponuj komendy", "value": f"suggest_commands::{name}"},
                         {"label": "📋 Logi",               "value": f"logs::{name}"}])
                _tl.sid = None
            threading.Thread(target=_ai_analyze_thread, daemon=True).start()
            return
        if value.strip():
            # Free-text → route to LLM
            _tl_sid = getattr(_tl, 'sid', None)
            user_text = value.strip()
            def _llm_thread():
                _tl.sid = _tl_sid
                # Inject API key from wizard state into env so llm_client finds it
                key = _state.get("openrouter_key", "") or _state.get("openrouter_api_key", "")
                if key:
                    os.environ["OPENROUTER_API_KEY"] = key
                if not _LLM_AVAILABLE or not _llm_config().get("api_key"):
                    _prompt_api_key()
                    return
                progress("🧠 LLM myśli...")
                history = [{"role": m["role"] if m["role"] != "bot" else "assistant",
                            "content": m["text"]}
                           for m in _conversation[-10:]
                           if m.get("text") and m["role"] in ("user","bot")]
                reply = _llm_chat(user_text,
                                  system_prompt=_WIZARD_SYSTEM_PROMPT,
                                  history=history[:-1])
                progress("🧠 LLM", done=True)
                msg(reply)
                _tl.sid = None
            threading.Thread(target=_llm_thread, daemon=True).start()
    finally:
        _tl.sid = None

# ── routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    import time as _t
    return render_template("index.html", cache_bust=int(_t.time()))

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/containers")
def api_containers():
    return json.dumps(docker_ps())

@app.route("/api/logs/<container>")
def api_logs(container):
    try:
        out = subprocess.check_output(
            ["docker","logs","--tail","100",container],
            text=True, stderr=subprocess.STDOUT)
        return json.dumps({"ok": True, "lines": out.splitlines()[-100:]})
    except Exception as e:
        return json.dumps({"ok": False, "lines": [str(e)]})

@app.route("/api/events")
def api_events():
    log_file = ROOT / "management" / "logs" / "decisions.jsonl"
    events = []
    if log_file.exists():
        for line in log_file.read_text().splitlines()[-200:]:
            try: events.append(json.loads(line))
            except: pass
    return json.dumps(events)

@app.route("/api/env")
def api_env():
    env = load_env()
    # Mask passwords/keys
    safe = {}
    for e in ENV_SCHEMA:
        val = env.get(e["key"], e.get("default",""))
        safe[e["key"]] = {
            "value":  mask(val) if e["type"] == "password" and val else val,
            "label":  e["label"],
            "group":  e["group"],
            "empty":  not val,
            "required_for": e.get("required_for", []),
        }
    return json.dumps(safe)

@app.route("/api/env", methods=["POST"])
def api_env_post():
    data = request.get_json(silent=True) or {}
    valid = {k: str(v) for k, v in data.items() if k in {e["key"] for e in ENV_SCHEMA}}
    if valid:
        save_env(valid)
        for env_key, val in valid.items():
            sk = _ENV_TO_STATE.get(env_key)
            if sk:
                _state[sk] = val
    return json.dumps({"ok": True, "updated": list(valid.keys())})

@app.route("/api/history")
def api_history():
    return json.dumps({
        "conversation": _conversation,
        "logs": _logs,
        "current_step": _state.get("step", "welcome")
    })

@app.route("/api/processes")
def api_processes():
    processes = []
    
    # Check Docker containers
    try:
        containers = docker_ps()
        for container in containers:
            status = "running" if "Up" in container["status"] else "stopped"
            processes.append({
                "name": container["name"],
                "status": status,
                "details": container["status"],
                "type": "container",
                "ports": container["ports"]
            })
    except:
        pass
    
    # Check wizard process
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'python' in proc.info['name'] and '5050' in ' '.join(proc.info['cmdline'] or []):
                    processes.append({
                        "name": "wizard",
                        "status": "running",
                        "details": f"PID {proc.info['pid']}",
                        "type": "process"
                    })
                    break
            except:
                continue
    except ImportError:
        processes.append({
            "name": "wizard",
            "status": "unknown",
            "details": "psutil not available",
            "type": "process"
        })
    
    return json.dumps(processes)

@app.route("/api/detect/<key>")
def api_detect(key):
    result: dict = {}
    try:
        if key == "GIT_REPO_URL":
            url = subprocess.check_output(
                ["git", "remote", "get-url", "origin"],
                text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip()
            result = {"value": url, "hint": "git remote origin"}
        elif key == "GIT_BRANCH":
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip()
            all_out = subprocess.check_output(
                ["git", "branch", "-a", "--format=%(refname:short)"],
                text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip()
            branches = list(dict.fromkeys(
                b.strip().replace("origin/", "") for b in all_out.splitlines() if b.strip()))[:8]
            result = {
                "value": branch or (branches[0] if branches else ""),
                "options": [{"value": b, "label": b} for b in branches],
                "hint": f"aktualna ga\u0142\u0105\u017c: {branch}" if branch else "dost\u0119pne ga\u0142\u0119zie",
            }
        elif key == "APP_VERSION":
            tag = subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0"],
                text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip().lstrip("v")
            if tag:
                result = {"value": tag, "hint": f"ostatni git tag: v{tag}"}
        elif key == "APP_NAME":
            name = ROOT.name.lower().replace("-", "_")
            result = {"value": name, "hint": f"z nazwy katalogu: {ROOT.name}"}
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result)

@app.route("/api/ssh-options/<kind>")
@app.route("/api/ssh-options/<kind>/<role>")
def api_ssh_options(kind, role="developer"):
    import glob as _glob
    if kind == "tickets":
        tickets_dir = ROOT / "shared" / "tickets"
        options = []
        if tickets_dir.exists():
            status_icon = {"open": "○", "in_progress": "◐", "closed": "●"}
            for path in sorted(_glob.glob(str(tickets_dir / "T-*.json"))):
                try:
                    with open(path) as f:
                        t = json.load(f)
                    if t.get("status") == "closed":
                        continue
                    icon = status_icon.get(t.get("status", "open"), "○")
                    options.append({
                        "value": t["id"],
                        "label": f"{icon} {t['id']} — {t['title'][:45]}"
                    })
                except Exception:
                    pass
        return json.dumps({"options": options})

    elif kind == "files":
        ri = _SSH_ROLES.get(role, {})
        container = ri.get("container", cname(f"ssh-{role}"))
        options = []
        # Try docker exec first (container running)
        try:
            out = subprocess.check_output(
                ["docker", "exec", container,
                 "find", "/workspace/app",
                 "-type", "f",
                 "(",
                 "-name", "*.py", "-o", "-name", "*.js", "-o", "-name", "*.ts",
                 "-o", "-name", "*.tsx", "-o", "-name", "*.jsx",
                 "-o", "-name", "*.css", "-o", "-name", "*.html",
                 "-o", "-name", "*.yml", "-o", "-name", "*.yaml",
                 ")",
                 "!", "-path", "*/node_modules/*",
                 "!", "-path", "*/__pycache__/*",
                 "!", "-path", "*/.git/*"],
                text=True, stderr=subprocess.DEVNULL, timeout=6)
            paths = sorted(p.strip() for p in out.splitlines() if p.strip())
            for p in paths[:120]:
                rel = p.replace("/workspace/app/", "", 1)
                options.append({"value": rel, "label": rel})
        except Exception:
            pass
        # Fallback: scan local app/ directory
        if not options:
            import glob as _glob2
            app_dir = ROOT / "app"
            if app_dir.is_dir():
                exts = (".py",".js",".ts",".tsx",".jsx",".css",".html",".yml",".yaml")
                skip = {"node_modules", "__pycache__", ".git", ".venv", "dist", "build"}
                for f in sorted(app_dir.rglob("*")):
                    if not f.is_file(): continue
                    if any(p in f.parts for p in skip): continue
                    if f.suffix not in exts: continue
                    try:
                        rel = str(f.relative_to(app_dir))
                        options.append({"value": rel, "label": rel})
                        if len(options) >= 120: break
                    except ValueError:
                        pass
        return json.dumps({"options": options})

    elif kind == "containers":
        # Running containers for SVC/TARGET params
        try:
            out = subprocess.check_output(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                text=True, stderr=subprocess.DEVNULL, timeout=5)
            options = []
            prefix = _state.get("app_name", "") or ""
            for line in out.splitlines():
                parts = line.split("\t", 1)
                name = parts[0].strip()
                status = parts[1].strip() if len(parts) > 1 else ""
                # Short name: strip project prefix
                short = name
                for pfx in (prefix + "-", "dockfra-", "management-", "app-"):
                    if short.startswith(pfx):
                        short = short[len(pfx):]
                        break
                icon = "✅" if "Up" in status else "⚠️"
                options.append({"value": short, "label": f"{icon} {short}"})
            return json.dumps({"options": options})
        except Exception as e:
            return json.dumps({"options": [], "error": str(e)})

    elif kind == "branches":
        # Git branches from app/ repo
        try:
            app_dir = ROOT / "app"
            scan_dir = app_dir if (app_dir / ".git").exists() else ROOT
            out = subprocess.check_output(
                ["git", "-C", str(scan_dir), "branch", "-a",
                 "--format=%(refname:short)"],
                text=True, stderr=subprocess.DEVNULL, timeout=5)
            branches = list(dict.fromkeys(
                b.strip().replace("origin/", "")
                for b in out.splitlines() if b.strip()
            ))[:20]
            options = [{"value": b, "label": b} for b in branches]
            return json.dumps({"options": options})
        except Exception as e:
            return json.dumps({"options": [], "error": str(e)})

    return json.dumps({"options": []})

@app.route("/api/device-ips")
def api_device_ips():
    import re
    local_ips = set(_local_interfaces())
    do_scan = request.args.get("scan") == "1"

    def _is_docker_internal(ip: str) -> bool:
        p = ip.split(".")
        if len(p) != 4: return False
        a, b = int(p[0]), int(p[1])
        return (a == 172 and 16 <= b <= 31) or (a == 10 and b in (0, 1, 88, 89))

    # ── Used IPs (where already referenced) ──────────────────────────────────
    used: dict[str, list[str]] = {}
    # wizard/.env
    env_ip = _devices_env_ip()
    if env_ip:
        used.setdefault(env_ip, []).append("devices/.env (RPI3_HOST)")
    # wizard state
    state_ip = _state.get("device_ip", "")
    if state_ip and state_ip != env_ip:
        used.setdefault(state_ip, []).append("wizard session")
    # scan all *.env* files for IP-like values
    for env_file in list(ROOT.glob("**/.env*")) + list(ROOT.glob("**/*.env")):
        if ".venv" in str(env_file) or ".git" in str(env_file): continue
        try:
            for line in env_file.read_text(errors="ignore").splitlines():
                m = re.match(r'^\w+=(\d+\.\d+\.\d+\.\d+)$', line.strip())
                if m:
                    ip = m.group(1)
                    if ip not in local_ips:
                        used.setdefault(ip, []).append(str(env_file.relative_to(ROOT)))
        except: pass

    # ── Docker containers with their IPs ─────────────────────────────────────
    docker_entries = []
    try:
        names_out = subprocess.check_output(
            ["docker","ps","--format","{{.Names}}"],
            text=True, stderr=subprocess.DEVNULL).strip().splitlines()
        for name in names_out:
            try:
                info = json.loads(subprocess.check_output(
                    ["docker","inspect","--format",
                     '{"ip":"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",'
                     '"net":"{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}",'
                     '"ports":"{{range $p,$_ := .NetworkSettings.Ports}}{{$p}} {{end}}",'
                     '"status":"{{.State.Status}}"}',
                     name], text=True, stderr=subprocess.DEVNULL))
                ip = info.get("ip","").strip()
                if ip:
                    docker_entries.append({
                        "name": name, "ip": ip,
                        "network": info.get("net","").strip(),
                        "ports": info.get("ports","").strip(),
                        "status": info.get("status","unknown"),
                        "used_in": used.get(ip, []),
                        "is_local": ip in local_ips,
                    })
            except: pass
    except: pass

    # ── ARP / local network ───────────────────────────────────────────────────
    arp = _arp_devices()
    container_ips = {e["ip"] for e in docker_entries}
    # Optional: ping-sweep the local subnet and add new IPs not in ARP
    if do_scan:
        seen_ips = {d["ip"] for d in arp} | local_ips | container_ips
        swept = _subnet_ping_sweep()
        for ip in swept:
            if ip not in seen_ips:
                arp.append({"ip": ip, "iface": "", "mac": "", "state": "REACHABLE"})
                seen_ips.add(ip)

    raw_arp = [d for d in arp if d["ip"] not in local_ips and d["ip"] not in container_ips]

    # Probe hostnames + open ports in parallel
    # Build scan ports dynamically from ENV_SCHEMA port defaults + standard ports
    _schema_ports = set()
    for e in ENV_SCHEMA:
        if e.get("group") == "Ports" and e.get("default","").isdigit():
            _schema_ports.add(int(e["default"]))
    COMMON_PORTS = sorted(_schema_ports | {22, 80, 443, 2222, 3000, 5000, 8000, 8080, 9000})

    def _probe(d: dict) -> dict:
        ip = d["ip"]
        hostname = ""
        open_ports: list[int] = []
        try:
            h = _socket.gethostbyaddr(ip)[0]
            if h != ip: hostname = h
        except: pass
        # port scan only for real (non-CNI) REACHABLE devices
        if d.get("state") in ("REACHABLE","DELAY") and d.get("iface","") not in ("cni0","flannel.1","docker0"):
            for port in COMMON_PORTS:
                try:
                    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
                        s.settimeout(0.35)
                        if s.connect_ex((ip, port)) == 0:
                            open_ports.append(port)
                except: pass
        return {**d, "hostname": hostname, "open_ports": open_ports,
                "is_docker_internal": _is_docker_internal(ip),
                "is_cni": d.get("iface","") in ("cni0","flannel.1","weave","calico"),
                "used_in": used.get(ip, [])}

    from concurrent.futures import ThreadPoolExecutor
    arp_entries: list[dict] = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        arp_entries = list(ex.map(_probe, raw_arp))

    return json.dumps({
        "docker": docker_entries,
        "arp": arp_entries,
        "local_ips": list(local_ips),
        "current": _state.get("device_ip", ""),
    })

@app.route("/api/process/<action>/<process_name>", methods=["POST"])
def api_process_action(action, process_name):
    try:
        if action == "stop":
            result = subprocess.run(["docker", "stop", process_name], capture_output=True, text=True)
            return json.dumps({"success": result.returncode == 0, "message": result.stdout or result.stderr})
        elif action == "restart":
            result = subprocess.run(["docker", "restart", process_name], capture_output=True, text=True)
            return json.dumps({"success": result.returncode == 0, "message": result.stdout or result.stderr})
        elif action == "change_port":
            # For port changes, we need to get the new port from the request
            data = request.get_json()
            new_port = data.get("port")
            if not new_port:
                return json.dumps({"success": False, "message": "New port required"})
            
            # This is a simplified implementation - in reality, you'd need to
            # update the docker-compose.yml and restart the container
            return json.dumps({"success": False, "message": "Port change not implemented yet"})
        else:
            return json.dumps({"success": False, "message": f"Unknown action: {action}"})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})

def _load_integration_env():
    """Load integration credentials from .env into os.environ and refresh _tickets."""
    env = load_env()
    for k in ("GITHUB_TOKEN", "GITHUB_REPO", "JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN",
              "JIRA_PROJECT", "TRELLO_KEY", "TRELLO_TOKEN", "TRELLO_BOARD", "TRELLO_LIST",
              "LINEAR_TOKEN", "LINEAR_TEAM"):
        val = env.get(k, "") or _os.environ.get(k, "")
        if val:
            _os.environ[k] = val
    _tickets.reload_env()


def _step_ticket_create_wizard(form):
    """Show ticket creation form in the wizard chat."""
    clear_widgets()
    msg("## 📝 Utwórz nowy ticket")
    from .core import text_input, select
    text_input("ticket_title", "Tytuł ticketu", "Fix login bug", "")
    text_input("ticket_desc", "Opis (opcjonalny)", "Szczegółowy opis zadania...", "")
    select("ticket_priority", "Priorytet", [
        {"value": "low", "label": "🟢 Low"},
        {"value": "normal", "label": "🟡 Normal"},
        {"value": "high", "label": "🟠 High"},
        {"value": "critical", "label": "🔴 Critical"},
    ], "normal")
    select("ticket_assigned", "Przydziel do", [
        {"value": "developer", "label": "🔧 Developer"},
        {"value": "monitor", "label": "📡 Monitor"},
        {"value": "autopilot", "label": "🤖 Autopilot"},
    ], "developer")
    buttons([
        {"label": "✅ Utwórz ticket", "value": "ticket_create_do"},
        {"label": "🏠 Menu", "value": "back"},
    ])

def _step_ticket_create_do(form):
    """Actually create the ticket from form data."""
    title = form.get("ticket_title", "").strip()
    if not title:
        msg("❌ Tytuł ticketu jest wymagany.")
        return
    clear_widgets()
    try:
        ticket = _tickets.create(
            title=title,
            description=form.get("ticket_desc", ""),
            priority=form.get("ticket_priority", "normal"),
            assigned_to=form.get("ticket_assigned", "developer"),
        )
        msg(f"## ✅ Ticket utworzony!\n\n"
            f"**{ticket['id']}** — {title}\n"
            f"Priorytet: {ticket['priority']} | Przydzielony: {ticket['assigned_to']}")
    except Exception as e:
        msg(f"❌ Błąd tworzenia ticketu: {e}")
    buttons([
        {"label": "📝 Utwórz kolejny", "value": "ticket_create_wizard"},
        {"label": "📋 Lista ticketów", "value": "ssh_cmd::manager::ticket-list::"},
        {"label": "🔗 Sync do GitHub/Jira", "value": "ticket_sync"},
        {"label": "🏠 Menu", "value": "back"},
    ])

def _step_integrations_setup():
    """Show integrations configuration form."""
    clear_widgets()
    env = load_env()
    msg("## 🔗 Integracje z systemami zadań\n\n"
        "Skonfiguruj połączenia z zewnętrznymi systemami zarządzania zadaniami.\n"
        "Tickety będą synchronizowane automatycznie.")
    from .core import text_input
    # GitHub
    msg("### GitHub Issues")
    text_input("GITHUB_TOKEN", "GitHub Personal Access Token", "ghp_xxx...", env.get("GITHUB_TOKEN", ""), sec=True,
               help_url="https://github.com/settings/tokens/new?scopes=repo&description=dockfra")
    text_input("GITHUB_REPO", "Repozytorium (owner/repo)", "myorg/myapp", env.get("GITHUB_REPO", ""))
    # Jira
    msg("### Jira Cloud")
    text_input("JIRA_URL", "Jira URL", "https://your-org.atlassian.net", env.get("JIRA_URL", ""))
    text_input("JIRA_EMAIL", "Jira Email", "user@company.com", env.get("JIRA_EMAIL", ""))
    text_input("JIRA_TOKEN", "Jira API Token", "xxx...", env.get("JIRA_TOKEN", ""), sec=True,
               help_url="https://id.atlassian.com/manage-profile/security/api-tokens")
    text_input("JIRA_PROJECT", "Jira Project Key", "PROJ", env.get("JIRA_PROJECT", ""))
    # Trello
    msg("### Trello")
    text_input("TRELLO_KEY", "Trello API Key", "xxx...", env.get("TRELLO_KEY", ""), sec=True,
               help_url="https://trello.com/power-ups/admin")
    text_input("TRELLO_TOKEN", "Trello Token", "xxx...", env.get("TRELLO_TOKEN", ""), sec=True,
               help_url="https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&key=YOUR_KEY&name=dockfra")
    text_input("TRELLO_BOARD", "Trello Board ID", "board_id", env.get("TRELLO_BOARD", ""))
    text_input("TRELLO_LIST", "Trello List ID (for new cards)", "list_id", env.get("TRELLO_LIST", ""))
    # Linear
    msg("### Linear")
    text_input("LINEAR_TOKEN", "Linear API Token", "lin_api_xxx...", env.get("LINEAR_TOKEN", ""), sec=True,
               help_url="https://linear.app/settings/api")
    text_input("LINEAR_TEAM", "Linear Team ID", "team_id", env.get("LINEAR_TEAM", ""))
    buttons([
        {"label": "💾 Zapisz integracje", "value": "integrations_save"},
        {"label": "🔄 Synchronizuj teraz", "value": "ticket_sync"},
        {"label": "🏠 Menu", "value": "back"},
    ])

def _step_integrations_save(form):
    """Save integration credentials to .env."""
    integration_keys = [
        "GITHUB_TOKEN", "GITHUB_REPO",
        "JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT",
        "TRELLO_KEY", "TRELLO_TOKEN", "TRELLO_BOARD", "TRELLO_LIST",
        "LINEAR_TOKEN", "LINEAR_TEAM",
    ]
    updates = {}
    for k in integration_keys:
        val = form.get(k, "").strip()
        if val:
            updates[k] = val
    if updates:
        save_env(updates)
        configured = []
        if updates.get("GITHUB_TOKEN") and updates.get("GITHUB_REPO"):
            configured.append("GitHub Issues")
        if updates.get("JIRA_URL") and updates.get("JIRA_TOKEN"):
            configured.append("Jira")
        if updates.get("TRELLO_KEY") and updates.get("TRELLO_TOKEN"):
            configured.append("Trello")
        if updates.get("LINEAR_TOKEN"):
            configured.append("Linear")
        msg(f"## ✅ Integracje zapisane\n\nSkonfigurowano: **{', '.join(configured) if configured else 'brak'}**")
    else:
        msg("⚠️ Brak danych do zapisania.")
    buttons([
        {"label": "🔄 Synchronizuj teraz", "value": "ticket_sync"},
        {"label": "🔗 Edytuj integracje", "value": "integrations_setup"},
        {"label": "🏠 Menu", "value": "back"},
    ])

def _step_ticket_sync():
    """Sync tickets with configured external services."""
    clear_widgets()
    progress("🔄 Synchronizuję tickety z zewnętrznymi usługami...")
    _load_integration_env()
    try:
        results = _tickets.sync_all()
        progress("🔄 Synchronizacja", done=True)
        lines = []
        for svc, info in results.items():
            if info.get("ok"):
                lines.append(f"✅ **{svc.capitalize()}** — pobrano {info.get('pulled', 0)} nowych ticketów")
            else:
                lines.append(f"❌ **{svc.capitalize()}** — {info.get('error', 'błąd')}")
        if not results:
            lines.append("⚠️ Brak skonfigurowanych integracji. Kliknij **🔗 Konfiguruj integracje** aby dodać.")
        msg("## 🔄 Wyniki synchronizacji\n\n" + "\n".join(lines))
    except Exception as e:
        progress("🔄 Synchronizacja", error=True)
        msg(f"❌ Błąd synchronizacji: {e}")
    buttons([
        {"label": "📝 Utwórz ticket", "value": "ticket_create_wizard"},
        {"label": "🔗 Konfiguruj integracje", "value": "integrations_setup"},
        {"label": "📊 Statystyki", "value": "project_stats"},
        {"label": "🏠 Menu", "value": "back"},
    ])

def _step_project_stats():
    """Show project statistics in the chat."""
    clear_widgets()
    msg("## 📊 Statystyki projektu")
    # Tickets (via dockfra.tickets)
    ts = _tickets.stats()
    by_status = ts["by_status"]
    by_prio = ts["by_priority"]
    by_assignee = ts["by_assignee"]
    status_icons = {"open": "○", "in_progress": "◐", "closed": "●"}
    prio_icons = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "🟢"}

    ticket_lines = f"**Razem:** {ts['total']} ticketów\n"
    if by_status:
        ticket_lines += " | ".join(f"{status_icons.get(s,'?')} {s}: **{c}**" for s, c in by_status.items()) + "\n"
    if by_prio:
        ticket_lines += " | ".join(f"{prio_icons.get(p,'⚪')} {p}: **{c}**" for p, c in by_prio.items()) + "\n"
    if by_assignee:
        ticket_lines += " | ".join(f"{a}: **{c}**" for a, c in by_assignee.items())
    msg(f"### 🎫 Tickety\n{ticket_lines}")

    # Containers
    containers = docker_ps()
    running = [c for c in containers if "Up" in c["status"] and "Restarting" not in c["status"]]
    failing = [c for c in containers if "Restarting" in c["status"] or "Exit" in c["status"]]
    msg(f"### 🐳 Kontenery\n"
        f"**Razem:** {len(containers)} | ✅ Działające: **{len(running)}** | 🔴 Problemy: **{len(failing)}**")

    # Git
    try:
        app_dir = ROOT / "app"
        git_dir = app_dir if (app_dir / ".git").exists() else ROOT
        branch = subprocess.check_output(
            ["git", "-C", str(git_dir), "branch", "--show-current"],
            text=True, stderr=subprocess.DEVNULL).strip()
        log_out = subprocess.check_output(
            ["git", "-C", str(git_dir), "log", "--oneline", "-5"],
            text=True, stderr=subprocess.DEVNULL).strip()
        commits_today = subprocess.check_output(
            ["git", "-C", str(git_dir), "rev-list", "--count", "--since=midnight", "HEAD"],
            text=True, stderr=subprocess.DEVNULL).strip()
        msg(f"### 📂 Git\n"
            f"**Gałąź:** `{branch}` | **Commity dziś:** {commits_today}\n"
            f"```\n{log_out}\n```")
    except Exception:
        msg("### 📂 Git\n⚠️ Brak repozytorium git lub błąd odczytu.")

    # Integrations
    env = load_env()
    int_status = []
    if env.get("GITHUB_TOKEN") and env.get("GITHUB_REPO"):
        int_status.append("✅ GitHub Issues")
    if env.get("JIRA_URL") and env.get("JIRA_TOKEN"):
        int_status.append("✅ Jira")
    if env.get("TRELLO_KEY") and env.get("TRELLO_TOKEN"):
        int_status.append("✅ Trello")
    if env.get("LINEAR_TOKEN"):
        int_status.append("✅ Linear")
    if not int_status:
        int_status.append("⚠️ Brak skonfigurowanych integracji")
    msg(f"### 🔗 Integracje\n{' | '.join(int_status)}")

    buttons([
        {"label": "📝 Utwórz ticket", "value": "ticket_create_wizard"},
        {"label": "🔗 Konfiguruj integracje", "value": "integrations_setup"},
        {"label": "🔄 Synchronizuj tickety", "value": "ticket_sync"},
        {"label": "🏠 Menu", "value": "back"},
    ])


# ── Ticket management steps (software house workflow) ─────────────────────────

def _step_show_ticket(tid: str):
    """Show detailed ticket view with status-aware actions."""
    clear_widgets()
    t = _tickets.get(tid)
    if not t:
        msg(f"❌ Ticket `{tid}` nie znaleziony.")
        buttons([{"label": "🏠 Menu", "value": "back"}])
        return
    si = {"open": "○", "in_progress": "◐", "review": "◑", "closed": "●", "done": "●"}.get(t["status"], "?")
    pi = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "🟢"}.get(t.get("priority", "normal"), "⚪")
    gh_num = t.get("github_issue_number")
    gh_repo = _state.get("github_repo", "") or _os.environ.get("GITHUB_REPO", "")
    gh_link = f" | [GH#{gh_num}](https://github.com/{gh_repo}/issues/{gh_num})" if gh_num and gh_repo else ""
    msg(f"## {si} {tid} — {t['title']}\n"
        f"**Status:** {t['status']} | **Priorytet:** {pi} {t.get('priority','normal')} | **Przypisany:** {t.get('assigned_to','?')}{gh_link}\n\n"
        f"**Opis:** {t.get('description','(brak)')}")
    # Show comments
    comments = t.get("comments", [])
    if comments:
        msg("### 💬 Komentarze")
        for c in comments[-10:]:
            ts = c.get("timestamp", "")[:16].replace("T", " ")
            msg(f"**{c.get('author','?')}** ({ts}): {c.get('text','')}")
    # Status-aware buttons
    btn_items = []
    if t["status"] == "open":
        btn_items.append({"label": "▶ Pracuj (pełny pipeline)", "value": f"ssh_cmd::developer::ticket-work::{tid}"})
    elif t["status"] == "in_progress":
        btn_items.append({"label": "▶ Kontynuuj pipeline", "value": f"ssh_cmd::developer::ticket-work::{tid}"})
        btn_items.append({"label": "🤖 Implement", "value": f"ssh_cmd::developer::implement::{tid}"})
    elif t["status"] == "review":
        btn_items.append({"label": "✅ Zatwierdź (manager)", "value": f"manager_approve::{tid}"})
        btn_items.append({"label": "🔄 Odrzuć → ponów", "value": f"manager_reject::{tid}"})
        if gh_repo:
            btn_items.append({"label": "🔗 Zobacz na GitHub", "value": f"open_github::{gh_repo}"})
    elif t["status"] in ("closed", "done"):
        btn_items.append({"label": "🔄 Otwórz ponownie", "value": f"ssh_cmd::developer::ticket-work::{tid}"})
    btn_items.append({"label": "📋 Wszystkie tickety do review", "value": "tickets_review"})
    btn_items.append({"label": "🏠 Menu", "value": "back"})
    buttons(btn_items)


def _step_tickets_review():
    """Show all tickets in 'review' status — manager dashboard."""
    clear_widgets()
    all_tickets = _tickets.list_tickets()
    review_tickets = [t for t in all_tickets if t.get("status") == "review"]
    in_progress = [t for t in all_tickets if t.get("status") == "in_progress"]
    open_tickets = [t for t in all_tickets if t.get("status") == "open"]
    done_tickets = [t for t in all_tickets if t.get("status") in ("closed", "done")]

    msg(f"## 📋 Panel Managera — Przegląd Ticketów\n"
        f"**Do review:** {len(review_tickets)} | **W trakcie:** {len(in_progress)} | "
        f"**Otwarte:** {len(open_tickets)} | **Zakończone:** {len(done_tickets)}")

    gh_repo = _state.get("github_repo", "") or _os.environ.get("GITHUB_REPO", "")

    if review_tickets:
        msg("### 👁️ Czekają na review")
        for t in review_tickets:
            gh_num = t.get("github_issue_number")
            gh_link = f" [GH#{gh_num}](https://github.com/{gh_repo}/issues/{gh_num})" if gh_num and gh_repo else ""
            msg(f"- **◑ {t['id']}** — {t['title']}{gh_link}")

    if in_progress:
        msg("### 🔄 W trakcie pracy")
        for t in in_progress:
            msg(f"- **◐ {t['id']}** — {t['title']} → {t.get('assigned_to','?')}")

    if open_tickets:
        msg("### ○ Otwarte (gotowe do przydzielenia)")
        for t in open_tickets:
            msg(f"- **○ {t['id']}** — {t['title']}")

    # Action buttons
    btn_items = []
    for t in review_tickets:
        btn_items.append({"label": f"✅ Zatwierdź {t['id']}", "value": f"manager_approve::{t['id']}"})
        btn_items.append({"label": f"🔄 Odrzuć {t['id']}", "value": f"manager_reject::{t['id']}"})
    btn_items.append({"label": "📝 Utwórz nowy ticket", "value": "ticket_create_wizard"})
    btn_items.append({"label": "🤖 AI: zaproponuj features", "value": "manager_suggest_features"})
    if gh_repo:
        btn_items.append({"label": "🔗 GitHub", "value": f"open_github::{gh_repo}"})
    btn_items.append({"label": "🏠 Menu", "value": "back"})
    buttons(btn_items)


def _step_manager_approve(tid: str, form: dict):
    """Manager approves a ticket — marks as done, pushes to GitHub, syncs."""
    clear_widgets()
    t = _tickets.get(tid)
    if not t:
        msg(f"❌ Ticket `{tid}` nie znaleziony.")
        buttons([{"label": "🏠 Menu", "value": "back"}])
        return
    _tickets.update(tid, status="done")
    _tickets.add_comment(tid, "manager", "✅ Review zatwierdzony przez managera. Ticket zamknięty.")
    # Push status to GitHub Issues
    gh_repo = _state.get("github_repo", "") or _os.environ.get("GITHUB_REPO", "")
    gh_num = t.get("github_issue_number")
    gh_link = ""
    if gh_repo and gh_num:
        try:
            _tickets.push_to_github(tid)
            gh_link = f"\n🔗 [GitHub Issue #{gh_num}](https://github.com/{gh_repo}/issues/{gh_num})"
        except Exception:
            pass
    msg(f"## ✅ Ticket `{tid}` zatwierdzony\n"
        f"**{t['title']}** — status: **done**{gh_link}\n\n"
        f"Implementacja zatwierdzona przez managera. Ticket zamknięty.")
    buttons([
        {"label": "📋 Panel review", "value": "tickets_review"},
        {"label": "🏠 Menu", "value": "back"},
    ])


def _step_manager_reject(tid: str):
    """Manager rejects a ticket — sends back to in_progress for rework."""
    clear_widgets()
    t = _tickets.get(tid)
    if not t:
        msg(f"❌ Ticket `{tid}` nie znaleziony.")
        buttons([{"label": "🏠 Menu", "value": "back"}])
        return
    _tickets.update(tid, status="in_progress")
    _tickets.add_comment(tid, "manager", "🔄 Review odrzucony. Wymaga poprawek.")
    msg(f"## 🔄 Ticket `{tid}` odrzucony → in_progress\n"
        f"**{t['title']}** wraca do developera.\n\n"
        f"Developer może ponownie uruchomić pipeline klikając **▶ Pracuj**.")
    buttons([
        {"label": f"▶ Pracuj ponownie {tid}", "value": f"ssh_cmd::developer::ticket-work::{tid}"},
        {"label": "📋 Panel review", "value": "tickets_review"},
        {"label": "🏠 Menu", "value": "back"},
    ])


def _step_manager_suggest_features():
    """Manager uses LLM to analyze the project and suggest new features/tickets."""
    clear_widgets()
    msg("## 🤖 AI: Analiza projektu i propozycje features")
    llm_ok, llm_key = _ensure_llm_key(return_action="manager_suggest_features")
    if not llm_ok:
        return
    # Gather project context
    existing_tickets = _tickets.list_tickets()
    ticket_summary = "\n".join(
        f"- [{t['status']}] {t['id']}: {t['title']}" for t in existing_tickets
    ) or "(brak ticketów)"
    # Read project structure
    app_dir = ROOT / "app"
    project_files = ""
    try:
        out = subprocess.check_output(
            ["find", str(app_dir), "-maxdepth", "3", "-name", "*.py", "-o", "-name", "*.js",
             "-o", "-name", "*.ts", "-o", "-name", "docker-compose*.yml"],
            text=True, stderr=subprocess.DEVNULL, timeout=5)
        project_files = out.strip()[:2000]
    except Exception:
        project_files = "(nie udało się odczytać struktury)"

    progress("🧠 AI analizuje projekt...")
    prompt = (
        f"Jesteś managerem projektu software house. Przeanalizuj strukturę projektu i istniejące tickety.\n\n"
        f"**Istniejące tickety:**\n{ticket_summary}\n\n"
        f"**Pliki projektu:**\n```\n{project_files}\n```\n\n"
        f"Zaproponuj 3-5 nowych features/ticketów, które powinny być zrealizowane.\n"
        f"Dla każdego podaj:\n"
        f"- Tytuł (krótki, po angielsku)\n"
        f"- Opis (1-2 zdania)\n"
        f"- Priorytet: critical/high/normal/low\n\n"
        f"Format: JSON array: [{{\"title\": \"...\", \"description\": \"...\", \"priority\": \"...\"}}]"
    )
    reply = _llm_chat(prompt, system_prompt="You are a project manager. Respond ONLY with a valid JSON array.")
    progress("🧠 AI", done=True)

    # Try to parse and create tickets
    created = []
    try:
        # Extract JSON from reply (might be wrapped in markdown)
        import re as _re_local
        json_match = _re_local.search(r'\[.*\]', reply, _re_local.DOTALL)
        if json_match:
            features = json.loads(json_match.group())
            for feat in features[:5]:
                t = _tickets.create(
                    title=feat.get("title", "Untitled"),
                    description=feat.get("description", ""),
                    priority=feat.get("priority", "normal"),
                    assigned_to="developer",
                    created_by="manager-ai",
                )
                created.append(t)
    except Exception as e:
        msg(f"⚠️ Nie udało się sparsować propozycji AI: {e}\n\nSurowa odpowiedź:\n```\n{reply[:2000]}\n```")
        buttons([{"label": "🔄 Spróbuj ponownie", "value": "manager_suggest_features"},
                 {"label": "🏠 Menu", "value": "back"}])
        return

    if created:
        msg(f"### ✅ Utworzono {len(created)} nowych ticketów:")
        for t in created:
            pi = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "🟢"}.get(t.get("priority", "normal"), "⚪")
            msg(f"- {pi} **{t['id']}** — {t['title']}\n  {t.get('description','')}")
        # Push to GitHub if configured
        gh_repo = _state.get("github_repo", "") or _os.environ.get("GITHUB_REPO", "")
        if gh_repo:
            for t in created:
                try:
                    _tickets.push_to_github(t["id"])
                except Exception:
                    pass
            msg("🔗 Tickety wysłane do GitHub Issues")
    else:
        msg("⚠️ Brak propozycji features.")

    btn_items = [
        {"label": "📋 Panel review", "value": "tickets_review"},
        {"label": "🤖 Zaproponuj więcej", "value": "manager_suggest_features"},
        {"label": "🏠 Menu", "value": "back"},
    ]
    buttons(btn_items)


def _step_test_llm_key(form: dict, return_action: str = ""):
    """Test LLM key + model from the form in real-time. Shows result inline."""
    clear_widgets()
    # Read key and model from form
    key = (form.get("OPENROUTER_API_KEY", "").strip()
           or _state.get("openrouter_key", "")
           or _os.environ.get("OPENROUTER_API_KEY", ""))
    model_sel = form.get("LLM_MODEL", "").strip()
    model_custom = form.get("LLM_MODEL_CUSTOM", "").strip()
    model = model_custom if (model_sel == "__custom__" or model_custom) else model_sel
    if not model:
        model = _state.get("llm_model", "") or "google/gemini-flash-1.5"

    if not key:
        msg("❌ **Brak klucza API** — wpisz klucz `OPENROUTER_API_KEY` i spróbuj ponownie.")
        _prompt_api_key(return_action=return_action)
        return

    msg(f"🧪 Testuję połączenie...\n**Klucz:** `{key[:12]}...{key[-4:]}`\n**Model:** `{model}`")
    progress("🧪 Testowanie LLM...")

    # Real API call
    try:
        import urllib.request, urllib.error
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "Say OK"}],
            "max_tokens": 5,
        }).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            actual_model = data.get("model", model)
            progress("🧪 Test", done=True)
            msg(f"✅ **Połączenie OK!**\n"
                f"- Model: `{actual_model}`\n"
                f"- Odpowiedź: `{reply[:100]}`")
            # Auto-save the working key+model
            _state["openrouter_key"] = key
            _state["llm_model"] = model
            _os.environ["OPENROUTER_API_KEY"] = key
            save_env({"OPENROUTER_API_KEY": key, "LLM_MODEL": model})
            msg("💾 Klucz i model zapisane.")
            btn_items = [{"label": "🏠 Menu", "value": "back"}]
            if return_action:
                btn_items.insert(0, {"label": "▶️ Kontynuuj", "value": return_action})
            buttons(btn_items)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        progress("🧪 Test", error=True)
        if e.code == 401:
            msg(f"❌ **Nieprawidłowy klucz API** (401 Unauthorized)\n```\n{body}\n```")
        elif e.code == 402:
            msg(f"❌ **Brak środków** na koncie OpenRouter (402)\n```\n{body}\n```")
        elif e.code == 400 and "model" in body.lower():
            msg(f"❌ **Nieznany model** `{model}` — sprawdź identyfikator na openrouter.ai/models\n```\n{body}\n```")
        else:
            msg(f"❌ **Błąd HTTP {e.code}**\n```\n{body}\n```")
        _prompt_api_key(return_action=return_action, reason=f"test nieudany (HTTP {e.code})")
    except Exception as e:
        progress("🧪 Test", error=True)
        msg(f"❌ **Błąd połączenia:** {e}")
        _prompt_api_key(return_action=return_action, reason=str(e))


def _step_engine_select(form: dict):
    """Show engine selection UI with auto-test results."""
    clear_widgets()
    msg("## 🔧 Silniki deweloperskie — wybierz narzędzie AI")
    ri = _get_role("developer")
    container = ri["container"]
    user = ri["user"]

    llm_key = (_state.get("openrouter_key", "") or _os.environ.get("OPENROUTER_API_KEY", ""))
    llm_model = _state.get("llm_model", "") or "google/gemini-2.0-flash-001"
    env = ["-e", f"OPENROUTER_API_KEY={llm_key}",
           "-e", f"LLM_MODEL={llm_model}"]
    if _state.get("anthropic_api_key"):
        env += ["-e", f"ANTHROPIC_API_KEY={_state['anthropic_api_key']}"]

    progress("🔍 Wykrywam dostępne silniki...")
    discovered = _engines.discover_engines(container, user)
    progress("🔍 Wykrywanie", done=True)

    progress("🧪 Testuję silniki...")
    test_results = _engines.test_all_engines(container, user, env)
    progress("🧪 Testy", done=True)

    # Merge discover + test results
    current_pref = _engines.get_preferred_engine()
    first_ok = ""
    for d, t in zip(discovered, test_results):
        icon = "✅" if t["ok"] else ("⚠️" if d["available"] else "❌")
        current = " ← aktualny" if d["id"] == current_pref else ""
        msg(f"### {icon} {d['name']}{current}\n"
            f"- **Status:** {'zainstalowany' if d['available'] else 'brak'} | "
            f"**Test:** {t['message'][:120]}\n"
            f"- {d['desc']}\n"
            f"- Wymaga: `{d['needs_key']}`")
        if t["ok"] and not first_ok:
            first_ok = d["id"]

    # Auto-select first working
    if first_ok and not current_pref:
        _engines.set_preferred_engine(first_ok)
        msg(f"\n🎯 **Auto-wybrano:** `{first_ok}` (pierwszy działający)")
    elif current_pref:
        msg(f"\n🎯 **Aktualny silnik:** `{current_pref}`")

    # Selection buttons
    btn_items = []
    for d, t in zip(discovered, test_results):
        if t["ok"]:
            label = f"✅ Użyj {d['name']}"
        elif d["available"]:
            label = f"⚠️ Użyj {d['name']} (test nieudany)"
        else:
            label = f"📦 Zainstaluj {d['name']}"
        btn_items.append({"label": label, "value": f"set_engine::{d['id']}"})
    btn_items.append({"label": "🔄 Testuj ponownie", "value": "engine_select"})
    btn_items.append({"label": "🏠 Menu", "value": "back"})
    buttons(btn_items)


def _step_set_engine(engine_id: str):
    """Set preferred dev engine."""
    clear_widgets()
    _engines.set_preferred_engine(engine_id)
    info = _engines.get_engine_info(engine_id)
    name = info["name"] if info else engine_id
    msg(f"✅ **Silnik ustawiony:** `{name}`\n\n"
        f"Pipeline będzie używał tego silnika do implementacji.")
    buttons([
        {"label": "🔧 Zmień silnik", "value": "engine_select"},
        {"label": "📋 Tickety", "value": "tickets_review"},
        {"label": "🏠 Menu", "value": "back"},
    ])


def _step_engine_autotest():
    """Auto-test all engines and auto-select first working one. Threaded."""
    clear_widgets()
    msg("## 🧪 Auto-test silników deweloperskich")
    ri = _get_role("developer")
    container = ri["container"]
    user = ri["user"]
    llm_key = (_state.get("openrouter_key", "") or _os.environ.get("OPENROUTER_API_KEY", ""))
    llm_model = _state.get("llm_model", "") or "google/gemini-2.0-flash-001"
    env = ["-e", f"OPENROUTER_API_KEY={llm_key}",
           "-e", f"LLM_MODEL={llm_model}"]

    progress("🧪 Testuję silniki...")
    engine_id, message = _engines.select_first_working(container, user, env)
    progress("🧪 Auto-test", done=True)

    if engine_id:
        _engines.set_preferred_engine(engine_id)
        info = _engines.get_engine_info(engine_id)
        msg(f"✅ **Silnik gotowy:** `{info['name'] if info else engine_id}`\n"
            f"- {message}")
        buttons([
            {"label": "🔧 Zmień silnik", "value": "engine_select"},
            {"label": "📋 Tickety", "value": "tickets_review"},
            {"label": "🏠 Menu", "value": "back"},
        ])
    else:
        msg(f"❌ **Żaden silnik nie działa.**\n{message}\n\n"
            "Sprawdź `OPENROUTER_API_KEY` i instalację narzędzi.")
        _prompt_api_key(return_action="engine_autotest")


def _dispatch(value: str, form: dict):
    """Shared dispatch logic for both SocketIO and REST actions."""
    if value.startswith("logs::"):          step_show_logs(value.split("::",1)[1]); return True
    if value.startswith("fix_container::"): step_fix_container(value.split("::",1)[1]); return True
    if value.startswith("fix_network_overlap::"): fix_network_overlap(value.split("::",1)[1]); return True
    if value.startswith("fix_readonly_volume::"): fix_readonly_volume(value.split("::",1)[1]); return True
    # ── LLM key test action ─────────────────────────────────────────────────
    if value.startswith("test_llm_key::"):
        return_action = value.split("::", 1)[1]
        _step_test_llm_key(form, return_action)
        return True
    # ── Engine selection / auto-test ──────────────────────────────────────
    if value == "engine_select":
        _tl_sid = getattr(_tl, 'sid', None)
        def _es():
            _tl.sid = _tl_sid
            _step_engine_select(form)
            _tl.sid = None
        threading.Thread(target=_es, daemon=True).start()
        return True
    if value == "engine_autotest":
        _tl_sid = getattr(_tl, 'sid', None)
        def _ea():
            _tl.sid = _tl_sid
            _step_engine_autotest()
            _tl.sid = None
        threading.Thread(target=_ea, daemon=True).start()
        return True
    if value.startswith("set_engine::"):
        engine_id = value.split("::", 1)[1]
        _step_set_engine(engine_id)
        return True
    # ── Ticket management actions ─────────────────────────────────────────────
    if value.startswith("show_ticket::"):
        tid = value.split("::", 1)[1]
        _step_show_ticket(tid)
        return True
    if value == "tickets_review":
        _step_tickets_review()
        return True
    if value.startswith("manager_approve::"):
        tid = value.split("::", 1)[1]
        _step_manager_approve(tid, form)
        return True
    if value.startswith("manager_reject::"):
        tid = value.split("::", 1)[1]
        _step_manager_reject(tid)
        return True
    if value.startswith("open_github::"):
        repo = value.split("::", 1)[1]
        msg(f"🔗 **GitHub:** [https://github.com/{repo}](https://github.com/{repo})")
        buttons([{"label": "🏠 Menu", "value": "back"}])
        return True
    if value == "manager_suggest_features":
        _tl_sid = getattr(_tl, 'sid', None)
        def _suggest():
            _tl.sid = _tl_sid
            _step_manager_suggest_features()
            _tl.sid = None
        threading.Thread(target=_suggest, daemon=True).start()
        return True
    if value == "clone_and_launch_app":
        def _clone_and_launch():
            repo_url = _state.get("git_repo_url", "")
            branch   = _state.get("git_branch", "main") or "main"
            app_dir  = ROOT / "app"
            if not repo_url:
                msg("❌ `GIT_REPO_URL` nie jest ustawiony.")
                buttons([{"label": "⚙️ Ustaw GIT_REPO_URL", "value": "settings_group::Git"}])
                return
            if not app_dir.exists() or not any(app_dir.iterdir()):
                progress(f"📥 Klonuję {repo_url}…")
                rc = subprocess.run(
                    ["git", "clone", "--branch", branch, "--depth", "1", repo_url, str(app_dir)],
                    capture_output=True, text=True)
                if rc.returncode != 0:
                    progress("clone", error=True)
                    msg(f"❌ Błąd klonowania:\n```\n{rc.stderr[:1000]}\n```")
                    buttons([{"label": "⚙️ Zmień GIT_REPO_URL", "value": "settings_group::Git"},
                             {"label": "🏠 Menu", "value": "back"}])
                    return
                progress("clone", done=True)
                msg(f"✅ Sklonowano do `{app_dir}`")
            _refresh_ssh_roles()
            step_do_launch({"stacks": "app", "environment": _state.get("environment", "local")})
        threading.Thread(target=_clone_and_launch, daemon=True).start()
        return True
    if value.startswith("ssh_info::"):      _step_ssh_info(value); return True
    if value.startswith("ssh_console::"):   step_ssh_console(value); return True
    if value.startswith("run_ssh_cmd::"):   run_ssh_cmd(value, form); return True
    if value.startswith("ssh_cmd::"):
        # ssh_cmd::role::cmd_name::arg — shortcut from ticket cards / inline buttons
        parts = value.split("::", 3)
        role_  = parts[1] if len(parts) > 1 else "developer"
        cmd_   = parts[2] if len(parts) > 2 else ""
        arg_   = parts[3] if len(parts) > 3 else ""
        ri_    = _get_role(role_)
        # ── Full Software House Pipeline: ticket-work → implement → test → commit → review ──
        if cmd_ == "ticket-work" and arg_:
            _tl_sid = getattr(_tl, 'sid', None)
            container_ = ri_['container']
            user_ = ri_['user']
            def _chain_work():
                _tl.sid = _tl_sid
                def _exec(script_name, script_arg="", extra_env=None):
                    """Run a script in the developer container. Returns (rc, output)."""
                    script = f"/home/{user_}/scripts/{script_name}.sh"
                    if script_arg:
                        inner = f"'{script}' {script_arg}"
                    else:
                        inner = f"'{script}'"
                    shell = f"if [ -x '{script}' ]; then {inner}; else source ~/.bashrc 2>/dev/null; {script_name} {script_arg}; fi"
                    cmd_parts = ["docker", "exec"] + (extra_env or []) + ["-u", user_, container_, "bash", "-lc", shell]
                    return run_cmd(cmd_parts)

                pstate = PipelineState(arg_)
                pstate.start_iteration()

                try:
                    # ─── Step 1: Validate LLM key ─────────────────────────
                    llm_ok, llm_key = _ensure_llm_key(return_action=f"ssh_cmd::{role_}::ticket-work::{arg_}")
                    if not llm_ok:
                        return

                    llm_model = _state.get("llm_model", "") or "google/gemini-2.0-flash-001"
                    llm_env = ["-e", f"OPENROUTER_API_KEY={llm_key}",
                               "-e", f"DEVELOPER_LLM_API_KEY={llm_key}",
                               "-e", f"LLM_MODEL={llm_model}"]
                    if _state.get("anthropic_api_key"):
                        llm_env += ["-e", f"ANTHROPIC_API_KEY={_state['anthropic_api_key']}"]

                    # ─── Step 0: Auto-select dev engine ────────────────────
                    engine_id = _engines.get_preferred_engine()
                    if not engine_id:
                        # Auto-test and pick the first working engine
                        engine_id, eng_msg = _engines.select_first_working(container_, user_, llm_env)
                        if engine_id:
                            _engines.set_preferred_engine(engine_id)
                        else:
                            msg(f"❌ **Żaden silnik deweloperski nie działa** — {eng_msg}")
                            pstate.record_decision("abort", "no working engine")
                            buttons([
                                {"label": "🔧 Wybierz silnik", "value": "engine_select"},
                                {"label": "🏠 Menu", "value": "back"},
                            ])
                            return

                    eng_info = _engines.get_engine_info(engine_id)
                    eng_name = eng_info["name"] if eng_info else engine_id

                    msg(f"## 🔄 Pipeline `{arg_}` — iteracja #{pstate.iteration}\n"
                        f"**Silnik:** `{eng_name}` | **Model:** `{llm_model}`")

                    # ─── Step 1: Pre-flight engine test ────────────────────
                    msg(f"### 🧪 Krok 0/5: pre-flight test silnika")
                    eng_ok, eng_test_msg = _engines.test_engine(engine_id, container_, user_, llm_env)
                    if eng_ok:
                        msg(f"✅ Silnik `{eng_name}` — {eng_test_msg[:120]}")
                    else:
                        msg(f"⚠️ Silnik `{eng_name}` nie przeszedł testu: {eng_test_msg[:200]}")
                        pstate.record_decision("engine_fallback", f"{engine_id} test failed, trying fallback")
                        # Try fallback to first working engine
                        engine_id, eng_msg = _engines.select_first_working(container_, user_, llm_env)
                        if engine_id:
                            _engines.set_preferred_engine(engine_id)
                            eng_info = _engines.get_engine_info(engine_id)
                            eng_name = eng_info["name"] if eng_info else engine_id
                            msg(f"🔄 Przełączam na: `{eng_name}` — {eng_msg[:120]}")
                        else:
                            msg("❌ **Żaden silnik nie działa.** Sprawdź API key.")
                            _prompt_api_key(return_action=f"ssh_cmd::{role_}::ticket-work::{arg_}")
                            return

                    # ─── Step 2: Mark ticket as in_progress ───────────────
                    msg(f"### ⏳ Krok 1/5: status → in_progress")
                    r1 = run_step(_exec, "ticket-work", "ticket-work", arg_)
                    pstate.record_step(r1)
                    if r1.ok():
                        msg(f"✅ Ticket `{arg_}` → **in_progress**")
                    else:
                        msg(f"⚠️ ticket-work (kod {r1.rc}): {r1.output[:500]}")

                    # ─── Step 3: AI implementation (engine-driven, adaptive) ─
                    strategy = pstate.get_strategy_adjustment("implement")
                    if strategy == "change_model":
                        msg("⚠️ **Wykryto powtarzający się błąd** — zmieniam model.")
                        pstate.record_decision("change_model", "powtarzający się błąd implement >2x")
                        fallback_models = ["google/gemini-2.0-flash-001", "anthropic/claude-3-5-haiku",
                                           "openai/gpt-4o-mini", "deepseek/deepseek-chat-v3-0324"]
                        for fm in fallback_models:
                            if fm != llm_model:
                                llm_model = fm
                                break
                        llm_env = ["-e", f"OPENROUTER_API_KEY={llm_key}",
                                   "-e", f"DEVELOPER_LLM_API_KEY={llm_key}",
                                   "-e", f"LLM_MODEL={llm_model}"]
                        msg(f"🔄 Model: `{llm_model}`")
                    elif strategy == "skip":
                        pstate.record_decision("skip_implement", "powtarzający się błąd — pomijam")
                        msg("⚠️ Pomijam implementację z powodu powtarzających się błędów.")
                        r2 = StepResult("implement", 0, "(pominięto)", 0, "", 0.3)
                        pstate.record_step(r2)
                    elif strategy == "ask_user":
                        can_retry, reason = pstate.should_retry("implement")
                        if not can_retry:
                            msg(f"🛑 **Pipeline zatrzymany** — {reason}\n\nWymagana ręczna interwencja.")
                            pstate.record_decision("abort", reason)
                            buttons([
                                {"label": "🔄 Wymuś ponowienie", "value": f"ssh_cmd::{role_}::ticket-work::{arg_}"},
                                {"label": "🔧 Zmień silnik", "value": "engine_select"},
                                {"label": "🏠 Menu", "value": "back"},
                            ])
                            return

                    if strategy != "skip":
                        # Use engine-specific implement command
                        impl_cmd = _engines.get_implement_cmd(engine_id, arg_)
                        msg(f"### 🤖 Krok 2/5: AI implementacja (`{eng_name}`, model: `{llm_model}`)")
                        progress(f"🤖 {eng_name} implementuje...")

                        def _engine_exec(cmd=impl_cmd, env=llm_env):
                            shell = f"if [ -x '/home/{user_}/scripts/engine-implement.sh' ]; then '/home/{user_}/scripts/engine-implement.sh' {engine_id} {arg_}; else {cmd}; fi"
                            cmd_parts = ["docker", "exec"] + (env or []) + ["-u", user_, container_, "bash", "-lc", shell]
                            return run_cmd(cmd_parts)

                        r2 = run_step(_engine_exec, "implement")
                        progress(f"🤖 {eng_name}", done=True)
                        r2.score = evaluate_implementation(r2.output)
                        r2.meta["engine"] = engine_id
                        pstate.record_step(r2)
                        if r2.ok():
                            msg(f"✅ Implementacja via `{eng_name}` (wynik: {r2.score:.0%})\n```\n{r2.output[:3000]}\n```")
                        else:
                            msg(f"⚠️ implement via `{eng_name}` (kod {r2.rc}, wynik: {r2.score:.0%}): {r2.output[:1500]}")

                    # ─── Step 4: Run tests (scored) ───────────────────────
                    msg(f"### 🧪 Krok 3/5: testy lokalne")
                    r3 = run_step(_exec, "test-local", "test-local")
                    r3.score = evaluate_test_output(r3.output, r3.rc)
                    pstate.record_step(r3)
                    if r3.ok():
                        msg(f"✅ Testy (wynik: {r3.score:.0%})\n```\n{r3.output[:1000]}\n```" if r3.output else f"✅ Testy (wynik: {r3.score:.0%})")
                    else:
                        msg(f"⚠️ Testy (wynik: {r3.score:.0%}) — kontynuuję\n```\n{r3.output[:1000]}\n```" if r3.output else f"⚠️ Testy (wynik: {r3.score:.0%})")

                    # ─── Step 5: Git commit & push ────────────────────────
                    ticket_data = _tickets.get(arg_)
                    commit_title = ticket_data.get("title", arg_) if ticket_data else arg_
                    commit_msg = f"feat({arg_}): {commit_title}"
                    msg(f"### 📤 Krok 4/5: commit & push")
                    r4 = run_step(_exec, "commit-push", "commit-push", f'"{commit_msg}"')
                    pstate.record_step(r4)
                    gh_repo = _state.get("github_repo", "") or _os.environ.get("GITHUB_REPO", "")
                    if r4.rc == 0 and r4.output:
                        commit_line = r4.output.strip().split("\n")[-1]
                        commit_hash = commit_line.split()[0] if commit_line else ""
                        gh_link = f"https://github.com/{gh_repo}/commit/{commit_hash}" if gh_repo and commit_hash else ""
                        link_text = f"\n🔗 [Zobacz na GitHub]({gh_link})" if gh_link else ""
                        msg(f"✅ Commit: `{commit_line}`{link_text}")
                    elif "Nothing to commit" in (r4.output or ""):
                        msg("ℹ️ Brak zmian do commitowania")
                    else:
                        msg(f"⚠️ commit-push (kod {r4.rc}): {r4.output[:500]}")

                    # ─── Step 6: Update ticket → review ───────────────────
                    msg(f"### 📋 Krok 5/5: status → review")
                    _tickets.update(arg_, status="review")
                    _tickets.add_comment(arg_, "developer",
                        f"Pipeline iteracja #{pstate.iteration} zakończona (wynik: {pstate.compute_overall_score():.0%}). "
                        f"Silnik: {eng_name}. Model: {llm_model}. Gotowe do review.")
                    r5 = StepResult("status-review", 0, "review", 0, "", 1.0)
                    pstate.record_step(r5)
                    if gh_repo:
                        try:
                            _tickets.push_to_github(arg_)
                        except Exception:
                            pass

                    # ─── Adaptive Summary ─────────────────────────────────
                    overall = pstate.compute_overall_score()
                    pstate.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
                    pstate.save()

                    score_icon = "🟢" if overall >= 0.7 else "🟡" if overall >= 0.4 else "🔴"
                    msg(f"---\n## {score_icon} Pipeline `{arg_}` — iteracja #{pstate.iteration}\n"
                        f"**Wynik:** {overall:.0%} | **Silnik:** `{eng_name}` | **Model:** `{llm_model}`\n\n"
                        f"{pstate.summary()}")

                    btn_items = [
                        {"label": f"👁️ Pokaż ticket {arg_}", "value": f"show_ticket::{arg_}"},
                        {"label": "📋 Tickety do review", "value": "tickets_review"},
                    ]
                    if overall < 0.5:
                        btn_items.insert(0, {"label": "🔄 Ponów pipeline (adaptacyjnie)", "value": f"ssh_cmd::{role_}::ticket-work::{arg_}"})
                    btn_items.append({"label": "🔧 Zmień silnik", "value": "engine_select"})
                    if gh_repo:
                        btn_items.append({"label": "🔗 GitHub", "value": f"open_github::{gh_repo}"})
                    btn_items.append({"label": "🏠 Menu", "value": "back"})
                    buttons(btn_items)

                except Exception as e:
                    msg(f"❌ Pipeline błąd: {e}")
                    pstate.record_step(StepResult("pipeline", -1, "", 0, str(e), 0.0))
                    pstate.save()
                finally:
                    _tl.sid = None
            threading.Thread(target=_chain_work, daemon=True).start()
        else:
            synth_form = {"ssh_cmd": cmd_, "ssh_arg": arg_}
            run_value_ = f"run_ssh_cmd::{role_}::{ri_['container']}::{ri_['user']}"
            run_ssh_cmd(run_value_, synth_form)
        return True
    if value == "ticket_create_wizard":
        _tl_sid = getattr(_tl, 'sid', None)
        def _tcw():
            _tl.sid = _tl_sid
            import time; time.sleep(0.3)   # let any concurrent launch thread finish
            _step_ticket_create_wizard(form)
        threading.Thread(target=_tcw, daemon=True).start()
        return True
    if value == "ticket_create_do":
        _tl_sid = getattr(_tl, 'sid', None)
        def _tcd():
            _tl.sid = _tl_sid
            _step_ticket_create_do(form)
        threading.Thread(target=_tcd, daemon=True).start()
        return True
    if value == "integrations_setup":
        _tl_sid = getattr(_tl, 'sid', None)
        def _is():
            _tl.sid = _tl_sid
            import time; time.sleep(0.3)
            _step_integrations_setup()
        threading.Thread(target=_is, daemon=True).start()
        return True
    if value == "integrations_save":
        _tl_sid = getattr(_tl, 'sid', None)
        def _isave():
            _tl.sid = _tl_sid
            _step_integrations_save(form)
        threading.Thread(target=_isave, daemon=True).start()
        return True
    if value == "ticket_sync":
        _tl_sid = getattr(_tl, 'sid', None)
        def _tsync():
            _tl.sid = _tl_sid
            _step_ticket_sync()
        threading.Thread(target=_tsync, daemon=True).start()
        return True
    if value == "project_stats":
        _tl_sid = getattr(_tl, 'sid', None)
        def _pstats():
            _tl.sid = _tl_sid
            import time; time.sleep(0.3)
            _step_project_stats()
        threading.Thread(target=_pstats, daemon=True).start()
        return True
    if value.startswith("ticket_push_github::"):
        ticket_id = value.split("::", 1)[1]
        _tl_sid = getattr(_tl, 'sid', None)
        def _push_gh(tid=ticket_id):
            _tl.sid = _tl_sid
            _load_integration_env()
            if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_REPO"):
                msg("❌ Brak konfiguracji GitHub.\n"
                    "[[🔗 Konfiguruj integracje|integrations_setup]]")
                return
            progress(f"🔗 Wysyłam {tid} do GitHub Issues…")
            result = _tickets.push_to_github(tid)
            if result and result.get("github_issue_number"):
                repo = os.environ.get("GITHUB_REPO", "")
                num = result["github_issue_number"]
                msg(f"✅ **{tid}** → [GitHub Issue #{num}](https://github.com/{repo}/issues/{num})")
            else:
                msg(f"❌ Nie udało się wypchnąć {tid} do GitHub. Sprawdź `GITHUB_TOKEN` i `GITHUB_REPO`.")
        threading.Thread(target=_push_gh, daemon=True).start()
        return True
    if value.startswith("suggest_commands::"): step_suggest_commands(value.split("::",1)[1]); return True
    if value.startswith("run_suggested_cmd::"): _run_suggested_cmd(value.split("::",1)[1]); return True
    if value.startswith("restart_container::"): _do_restart_container(value.split("::",1)[1]); return True
    if value.startswith("diag_port::"):     diag_port(value.split("::",1)[1]); return True
    if value.startswith("show_missing_env::"): show_missing_env(value.split("::",1)[1]); return True
    if value.startswith("logs_stack::"):    step_show_logs(value.split("::",1)[1]); return True
    if value.startswith("fix_compose::"):
        msg(f"ℹ️ Plik `{value.split('::',1)[1]}/docker-compose.yml` ma błąd — sprawdź sieć lub usługi.")
        buttons([{"label":"📋 Pokaż logi","value":f"logs_stack::{value.split('::',1)[1]}"},{"label":"← Wróć","value":"back"}])
        return True
    if value.startswith("settings_group::"): step_settings(value.split("::",1)[1]); return True
    if value.startswith("save_settings::"):  step_save_settings(value.split("::",1)[1], form); return True
    if value.startswith("preflight_save_launch::"):
        env_updates: dict[str, str] = {}
        for k, v in form.items():
            if k in _ENV_TO_STATE:
                _state[_ENV_TO_STATE[k]] = str(v).strip()
                env_updates[k] = str(v).strip()
        if env_updates:
            save_env(env_updates)
        stacks_str = value.split("::",1)[1]
        _state["stacks"] = stacks_str.split(",")[0] if len(stacks_str.split(","))==1 else "all"
        step_do_launch({"stacks": _state["stacks"], "environment": _state.get("environment","local")})
        return True
    handler = STEPS.get(value)
    if handler:
        handler(form); return True
    return False

def _run_action_sync(value: str, form: dict, timeout: float = 30.0) -> list[dict]:
    """Run a wizard action synchronously (for REST API). Returns collected events."""
    _tl.collector = []
    _tl.sid = None
    try:
        if not _dispatch(value, form):
            if value.startswith("ai_analyze::"):
                name = value.split("::",1)[1]
                try:
                    out = subprocess.check_output(["docker","logs","--tail","60",name],
                                                  text=True, stderr=subprocess.STDOUT)
                except Exception as e:
                    msg(f"❌ {e}"); out = ""
                if out:
                    reply = _llm_chat(out[-3000:], system_prompt=_WIZARD_SYSTEM_PROMPT)
                    msg(f"### 🧠 AI: `{name}`\n{reply}")
            elif value.strip():
                reply = _llm_chat(value, system_prompt=_WIZARD_SYSTEM_PROMPT)
                msg(reply)
            else:
                msg(f"⚠️ Nieznana akcja: `{value}`")
    finally:
        collected = list(_tl.collector or [])
        _tl.collector = None
        _tl.sid = None
    return collected

def _events_to_rest(events: list[dict]) -> list[dict]:
    """Convert raw collected events to a clean REST-friendly list."""
    out = []
    for e in events:
        ev, d = e["event"], e["data"]
        if ev == "message":
            out.append({"type": "message", "role": d.get("role","bot"), "text": d.get("text","")})
        elif ev == "widget":
            wt = d.get("type","")
            if wt == "buttons":
                out.append({"type": "buttons",
                            "items": [{"label": i["label"], "value": i["value"]}
                                      for i in d.get("items",[])]})
            elif wt == "progress":
                out.append({"type": "progress", "label": d.get("label",""),
                            "done": d.get("done",False), "error": d.get("error",False)})
            elif wt == "status_row":
                out.append({"type": "status_row", "items": d.get("items",[])})
            elif wt in ("input","select","code"):
                out.append({"type": wt, **{k:v for k,v in d.items() if k != "type"}})
    return out

@app.route("/api/action", methods=["POST"])
def api_action():
    """Synchronous action endpoint for CLI/REST clients."""
    data = request.get_json(silent=True) or {}
    value = str(data.get("action", data.get("message", data.get("value", "")))).strip()
    form  = data.get("form", {})
    if not value:
        return json.dumps({"ok": False, "error": "Missing action/message"}), 400
    events = _run_action_sync(value, form)
    return json.dumps({"ok": True, "result": _events_to_rest(events)})

@app.route("/api/logs/tail")
def api_logs_tail():
    """Return last N lines from the internal log buffer."""
    n = min(int(request.args.get("n", 100)), 2000)
    lines = list(_log_buffer)[-n:]
    return json.dumps({"lines": lines, "total": len(_log_buffer)})

@app.route("/api/health")
def api_health():
    """Return algorithmic health analysis of running containers."""
    containers = docker_ps()
    running = [c for c in containers if "Up" in c["status"] and "Restarting" not in c["status"]]
    failing = [c for c in containers if "Restarting" in c["status"] or "Exit" in c["status"]]
    findings = []
    for c in failing:
        text, btns = _analyze_container_log(c["name"])
        findings.append({"container": c["name"], "status": c["status"],
                         "finding": text, "solutions": btns})
    return json.dumps({
        "ok": len(failing) == 0,
        "running": len(running), "failing": len(failing),
        "containers": containers,
        "findings": findings,
    })

# ── Ticket CRUD API (uses dockfra.tickets module) ─────────────────────────────

@app.route("/api/tickets")
def api_tickets():
    """List all tickets with optional filters."""
    status_f = request.args.get("status")
    assigned_f = request.args.get("assigned_to")
    priority_f = request.args.get("priority")
    tickets = _tickets.list_tickets(status=status_f, assigned_to=assigned_f, priority=priority_f)
    return json.dumps(tickets)

@app.route("/api/tickets", methods=["POST"])
def api_tickets_create():
    """Create a ticket directly from the wizard."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return json.dumps({"ok": False, "error": "Title required"}), 400
    try:
        ticket = _tickets.create(
            title=title,
            description=data.get("description", ""),
            priority=data.get("priority", "normal"),
            assigned_to=data.get("assigned_to", "developer"),
            labels=data.get("labels", []),
            created_by=data.get("created_by", "manager"),
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}), 500
    return json.dumps({"ok": True, "ticket": ticket})

@app.route("/api/tickets/<ticket_id>")
def api_ticket_get(ticket_id):
    """Get a single ticket by ID."""
    ticket = _tickets.get(ticket_id)
    if not ticket:
        return json.dumps({"ok": False, "error": "Not found"}), 404
    return json.dumps(ticket)

@app.route("/api/tickets/<ticket_id>", methods=["PUT"])
def api_ticket_update(ticket_id):
    """Update ticket fields."""
    data = request.get_json(silent=True) or {}
    ticket = _tickets.update(ticket_id, **{k: v for k, v in data.items()
                                           if k not in ("id", "created_at", "created_by")})
    if not ticket:
        return json.dumps({"ok": False, "error": "Not found"}), 404
    return json.dumps({"ok": True, "ticket": ticket})

@app.route("/api/tickets/<ticket_id>/comment", methods=["POST"])
def api_ticket_comment(ticket_id):
    """Add a comment to a ticket."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return json.dumps({"ok": False, "error": "Text required"}), 400
    ticket = _tickets.add_comment(ticket_id, data.get("author", "wizard"), text)
    if not ticket:
        return json.dumps({"ok": False, "error": "Not found"}), 404
    return json.dumps({"ok": True, "ticket": ticket})

@app.route("/api/stats")
def api_stats():
    """Project statistics: tickets, containers, git, integrations."""
    # Tickets (via dockfra.tickets)
    ts = _tickets.stats()

    # Containers
    containers = docker_ps()
    running = [c for c in containers if "Up" in c["status"] and "Restarting" not in c["status"]]
    failing = [c for c in containers if "Restarting" in c["status"] or "Exit" in c["status"]]

    # Git stats
    git_stats = {}
    try:
        app_dir = ROOT / "app"
        git_dir = app_dir if (app_dir / ".git").exists() else ROOT
        log_out = subprocess.check_output(
            ["git", "-C", str(git_dir), "log", "--oneline", "--since=midnight"],
            text=True, stderr=subprocess.DEVNULL).strip()
        commits_today = len(log_out.splitlines()) if log_out else 0
        branch = subprocess.check_output(
            ["git", "-C", str(git_dir), "branch", "--show-current"],
            text=True, stderr=subprocess.DEVNULL).strip()
        last_commit = subprocess.check_output(
            ["git", "-C", str(git_dir), "log", "-1", "--format=%h %s"],
            text=True, stderr=subprocess.DEVNULL).strip()
        git_stats = {"branch": branch, "commits_today": commits_today, "last_commit": last_commit}
    except Exception:
        pass

    # Integrations
    env = load_env()
    integrations = {
        "github": bool(env.get("GITHUB_TOKEN") and env.get("GITHUB_REPO")),
        "jira": bool(env.get("JIRA_URL") and env.get("JIRA_EMAIL") and env.get("JIRA_TOKEN")),
        "trello": bool(env.get("TRELLO_KEY") and env.get("TRELLO_TOKEN")),
        "linear": bool(env.get("LINEAR_TOKEN")),
    }

    # Suggestions
    suggestions = []
    if ts["total"] == 0:
        suggestions.append({"icon": "📝", "text": "Utwórz pierwszy ticket", "action": "ticket_create_wizard"})
    if failing:
        suggestions.append({"icon": "🔧", "text": f"Napraw {len(failing)} kontener(ów)", "action": "status"})
    if not any(integrations.values()):
        suggestions.append({"icon": "🔗", "text": "Podłącz system zadań (GitHub/Jira/Trello/Linear)", "action": "integrations_setup"})
    if not git_stats.get("commits_today"):
        suggestions.append({"icon": "💻", "text": "Zacznij kodować — otwórz SSH Developer", "action": "ssh_info::developer::2200"})
    open_tickets = ts["by_status"].get("open", 0)
    if open_tickets > 0:
        suggestions.append({"icon": "▶️", "text": f"Rozpocznij pracę nad {open_tickets} otwartym ticketem", "action": "ssh_cmd::developer::my-tickets::"})
    if len(running) > 0 and not failing:
        suggestions.append({"icon": "📊", "text": "Sprawdź status infrastruktury", "action": "status"})

    return json.dumps({
        "tickets": ts,
        "containers": {
            "total": len(containers),
            "running": len(running),
            "failing": len(failing),
        },
        "git": git_stats,
        "integrations": integrations,
        "suggestions": suggestions,
    })

@app.route("/api/ticket-diff/<ticket_id>")
def api_ticket_diff(ticket_id):
    """Return git commits and unified diff for a given ticket ID from the app repo."""
    import subprocess as _sp
    ticket = _tickets.get(ticket_id)
    if not ticket:
        return json.dumps({"ok": False, "error": "Not found"}), 404
    # Search in app repo first, then root repo
    search_dirs = [APP, ROOT]
    commits = []
    diff_text = ""
    for repo_dir in search_dirs:
        if not (repo_dir / ".git").exists():
            continue
        try:
            # Find commits mentioning the ticket ID
            log_out = _sp.check_output(
                ["git", "log", "--oneline", "--all", f"--grep={ticket_id}", "--format=%H %s"],
                cwd=str(repo_dir), text=True, stderr=_sp.DEVNULL, timeout=10
            ).strip()
            if not log_out:
                continue
            for line in log_out.splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    commits.append({"hash": parts[0][:12], "subject": parts[1], "repo": repo_dir.name})
            # Get unified diff for all matching commits
            hashes = [c["hash"] for c in commits if c["repo"] == repo_dir.name]
            if hashes:
                diff_parts = []
                for h in hashes[:5]:  # limit to 5 commits
                    try:
                        d = _sp.check_output(
                            ["git", "show", "--stat", "--patch", h],
                            cwd=str(repo_dir), text=True, stderr=_sp.DEVNULL, timeout=10
                        )
                        diff_parts.append(d[:8000])
                    except Exception:
                        pass
                diff_text = "\n\n".join(diff_parts)
            break
        except Exception:
            continue
    return json.dumps({
        "ok": True,
        "ticket_id": ticket_id,
        "title": ticket.get("title", ""),
        "status": ticket.get("status", ""),
        "commits": commits,
        "diff": diff_text,
    })


@app.route("/api/tickets/sync", methods=["POST"])
def api_tickets_sync():
    """Sync tickets with external services (GitHub, Jira, Trello, Linear)."""
    _load_integration_env()
    try:
        results = _tickets.sync_all()
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}), 500
    return json.dumps({"ok": True, "results": results})

if __name__ == "__main__":
    print("🧙 Dockfra Wizard → http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
