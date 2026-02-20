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
    ROOT, MGMT, _PKG_DIR,
    _llm_chat, _llm_config, _LLM_AVAILABLE, _WIZARD_SYSTEM_PROMPT,
    msg, buttons, progress, mask,
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
    diag_port, show_missing_env, _prompt_api_key,
    fix_network_overlap, retry_launch, fix_vnc_port,
    fix_acme_storage, fix_readonly_volume, fix_docker_perms,
)
from .discover import (
    _step_ssh_info, step_ssh_console, run_ssh_cmd, _SSH_ROLES, _refresh_ssh_roles,
)

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
    return render_template("index.html")

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
            options = []
            for p in paths[:120]:
                rel = p.replace("/workspace/app/", "", 1)
                options.append({"value": rel, "label": rel})
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

def _dispatch(value: str, form: dict):
    """Shared dispatch logic for both SocketIO and REST actions."""
    if value.startswith("logs::"):          step_show_logs(value.split("::",1)[1]); return True
    if value.startswith("fix_container::"): step_fix_container(value.split("::",1)[1]); return True
    if value.startswith("fix_network_overlap::"): fix_network_overlap(value.split("::",1)[1]); return True
    if value.startswith("fix_readonly_volume::"): fix_readonly_volume(value.split("::",1)[1]); return True
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

if __name__ == "__main__":
    print("🧙 Dockfra Wizard → http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
