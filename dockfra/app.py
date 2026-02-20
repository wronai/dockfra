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
    if value.startswith("ssh_cmd::"):
        # ssh_cmd::role::cmd_name::arg — shortcut from ticket cards / inline buttons
        parts = value.split("::", 3)
        role_  = parts[1] if len(parts) > 1 else "developer"
        cmd_   = parts[2] if len(parts) > 2 else ""
        arg_   = parts[3] if len(parts) > 3 else ""
        ri_    = _get_role(role_)
        synth_form = {"ssh_cmd": cmd_, "ssh_arg": arg_}
        run_value_ = f"run_ssh_cmd::{role_}::{ri_['container']}::{ri_['user']}"
        run_ssh_cmd(run_value_, synth_form)
        return True
    if value == "ticket_create_wizard":
        _step_ticket_create_wizard(form); return True
    if value == "ticket_create_do":
        _step_ticket_create_do(form); return True
    if value == "integrations_setup":
        _step_integrations_setup(); return True
    if value == "integrations_save":
        _step_integrations_save(form); return True
    if value == "ticket_sync":
        _step_ticket_sync(); return True
    if value == "project_stats":
        _step_project_stats(); return True
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

# ── Ticket CRUD API (wizard-side, bypasses container permissions) ──────────────
import sys as _sys, os as _os

def _tickets_dir():
    """Return tickets directory, ensuring it exists with proper permissions."""
    d = ROOT / "shared" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o1777)
    except OSError:
        pass
    return d

def _ticket_path(ticket_id):
    return _tickets_dir() / f"{ticket_id}.json"

def _next_ticket_id():
    d = _tickets_dir()
    import glob as _g
    nums = []
    for f in _g.glob(str(d / "T-*.json")):
        try:
            nums.append(int(_os.path.basename(f).replace(".json", "").split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"T-{max(nums, default=0) + 1:04d}"

@app.route("/api/tickets")
def api_tickets():
    """List all tickets with optional filters."""
    status_f = request.args.get("status")
    assigned_f = request.args.get("assigned_to")
    d = _tickets_dir()
    tickets = []
    for p in sorted(d.glob("T-*.json")):
        try:
            t = json.loads(p.read_text())
            if status_f and t.get("status") != status_f:
                continue
            if assigned_f and t.get("assigned_to") != assigned_f:
                continue
            tickets.append(t)
        except Exception:
            pass
    return json.dumps(tickets)

@app.route("/api/tickets", methods=["POST"])
def api_tickets_create():
    """Create a ticket directly from the wizard (bypasses SSH container perms)."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return json.dumps({"ok": False, "error": "Title required"}), 400
    from datetime import datetime, timezone
    ticket_id = _next_ticket_id()
    ticket = {
        "id": ticket_id,
        "title": title,
        "description": data.get("description", ""),
        "status": "open",
        "priority": data.get("priority", "normal"),
        "assigned_to": data.get("assigned_to", "developer"),
        "labels": data.get("labels", []),
        "created_by": data.get("created_by", "manager"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "comments": [],
        "github_issue_number": None,
    }
    try:
        _ticket_path(ticket_id).write_text(json.dumps(ticket, indent=2))
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}), 500
    return json.dumps({"ok": True, "ticket": ticket})

@app.route("/api/tickets/<ticket_id>")
def api_ticket_get(ticket_id):
    """Get a single ticket by ID."""
    p = _ticket_path(ticket_id)
    if not p.exists():
        return json.dumps({"ok": False, "error": "Not found"}), 404
    return json.dumps(json.loads(p.read_text()))

@app.route("/api/tickets/<ticket_id>", methods=["PUT"])
def api_ticket_update(ticket_id):
    """Update ticket fields."""
    p = _ticket_path(ticket_id)
    if not p.exists():
        return json.dumps({"ok": False, "error": "Not found"}), 404
    data = request.get_json(silent=True) or {}
    from datetime import datetime, timezone
    ticket = json.loads(p.read_text())
    for k, v in data.items():
        if k not in ("id", "created_at", "created_by"):
            ticket[k] = v
    ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(ticket, indent=2))
    return json.dumps({"ok": True, "ticket": ticket})

@app.route("/api/tickets/<ticket_id>/comment", methods=["POST"])
def api_ticket_comment(ticket_id):
    """Add a comment to a ticket."""
    p = _ticket_path(ticket_id)
    if not p.exists():
        return json.dumps({"ok": False, "error": "Not found"}), 404
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return json.dumps({"ok": False, "error": "Text required"}), 400
    from datetime import datetime, timezone
    ticket = json.loads(p.read_text())
    ticket.setdefault("comments", []).append({
        "author": data.get("author", "wizard"),
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(ticket, indent=2))
    return json.dumps({"ok": True, "ticket": ticket})

@app.route("/api/stats")
def api_stats():
    """Project statistics: tickets, containers, git, integrations."""
    # Tickets
    d = _tickets_dir()
    tickets = []
    for p in sorted(d.glob("T-*.json")):
        try:
            tickets.append(json.loads(p.read_text()))
        except Exception:
            pass
    by_status = {}
    by_priority = {}
    by_assignee = {}
    for t in tickets:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        by_priority[t["priority"]] = by_priority.get(t["priority"], 0) + 1
        by_assignee[t["assigned_to"]] = by_assignee.get(t["assigned_to"], 0) + 1

    # Containers
    containers = docker_ps()
    running = [c for c in containers if "Up" in c["status"] and "Restarting" not in c["status"]]
    failing = [c for c in containers if "Restarting" in c["status"] or "Exit" in c["status"]]

    # Git stats
    git_stats = {}
    try:
        app_dir = ROOT / "app"
        git_dir = app_dir if (app_dir / ".git").exists() else ROOT
        commits_today = subprocess.check_output(
            ["git", "-C", str(git_dir), "log", "--oneline", "--since=midnight"],
            text=True, stderr=subprocess.DEVNULL).strip().count("\n") + (1 if subprocess.check_output(
            ["git", "-C", str(git_dir), "log", "--oneline", "--since=midnight"],
            text=True, stderr=subprocess.DEVNULL).strip() else 0)
        branch = subprocess.check_output(
            ["git", "-C", str(git_dir), "branch", "--show-current"],
            text=True, stderr=subprocess.DEVNULL).strip()
        last_commit = subprocess.check_output(
            ["git", "-C", str(git_dir), "log", "-1", "--format=%h %s"],
            text=True, stderr=subprocess.DEVNULL).strip()
        git_stats = {"branch": branch, "commits_today": commits_today, "last_commit": last_commit}
    except Exception:
        pass

    # Integrations check (via env vars)
    env = load_env()
    integrations = {
        "github": bool(env.get("GITHUB_TOKEN") and env.get("GITHUB_REPO")),
        "jira": bool(env.get("JIRA_URL") and env.get("JIRA_EMAIL") and env.get("JIRA_TOKEN")),
        "trello": bool(env.get("TRELLO_KEY") and env.get("TRELLO_TOKEN")),
        "linear": bool(env.get("LINEAR_TOKEN")),
    }

    # Suggestions
    suggestions = []
    if not tickets:
        suggestions.append({"icon": "📝", "text": "Utwórz pierwszy ticket", "action": "ticket_create_wizard"})
    if failing:
        suggestions.append({"icon": "🔧", "text": f"Napraw {len(failing)} kontener(ów)", "action": "status"})
    if not any(integrations.values()):
        suggestions.append({"icon": "🔗", "text": "Podłącz system zadań (GitHub/Jira/Trello/Linear)", "action": "integrations_setup"})
    if not git_stats.get("commits_today"):
        suggestions.append({"icon": "💻", "text": "Zacznij kodować — otwórz SSH Developer", "action": "ssh_info::developer::2200"})
    open_tickets = by_status.get("open", 0)
    if open_tickets > 0:
        suggestions.append({"icon": "▶️", "text": f"Rozpocznij pracę nad {open_tickets} otwartym ticketem", "action": "ssh_cmd::developer::my-tickets::"})
    if len(running) > 0 and not failing:
        suggestions.append({"icon": "📊", "text": "Sprawdź status infrastruktury", "action": "status"})

    return json.dumps({
        "tickets": {
            "total": len(tickets),
            "by_status": by_status,
            "by_priority": by_priority,
            "by_assignee": by_assignee,
        },
        "containers": {
            "total": len(containers),
            "running": len(running),
            "failing": len(failing),
        },
        "git": git_stats,
        "integrations": integrations,
        "suggestions": suggestions,
    })

@app.route("/api/tickets/sync", methods=["POST"])
def api_tickets_sync():
    """Sync tickets with external services (GitHub, Jira, Trello, Linear)."""
    env = load_env()
    results = {}
    # Set env vars for ticket_system imports
    for k in ("GITHUB_TOKEN", "GITHUB_REPO", "JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN",
              "JIRA_PROJECT", "TRELLO_KEY", "TRELLO_TOKEN", "TRELLO_BOARD", "TRELLO_LIST",
              "LINEAR_TOKEN", "LINEAR_TEAM"):
        val = env.get(k, "") or _os.environ.get(k, "")
        if val:
            _os.environ[k] = val
    try:
        _sys.path.insert(0, str(ROOT / "shared" / "lib"))
        import importlib
        ts = importlib.import_module("ticket_system")
        importlib.reload(ts)  # pick up new env vars
        results = ts.sync_all()
    except Exception as e:
        results["error"] = str(e)
    return json.dumps({"ok": True, "results": results})

if __name__ == "__main__":
    print("🧙 Dockfra Wizard → http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
