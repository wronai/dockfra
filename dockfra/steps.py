"""Wizard step functions — welcome, status, settings, launch, deploy."""
from .core import *
from .discover import _SSH_ROLES, _get_role, _refresh_ssh_roles

def step_welcome():
    _state["step"] = "welcome"
    cfg = detect_config()
    _state.update({k:v for k,v in cfg.items() if v})
    _refresh_ssh_roles()  # re-scan now that _state has git_repo_url
    msg("# 👋 Dockfra Setup Wizard")

    # ── Pre-flight connectivity checks ────────────────────────────────────────
    from .fixes import validate_docker, validate_llm_connection
    docker_ok, docker_msg = validate_docker()
    llm_ok, llm_msg = validate_llm_connection()
    checks = []
    checks.append({"name": f"🐳 Docker", "ok": docker_ok, "detail": docker_msg})
    checks.append({"name": f"🤖 LLM", "ok": llm_ok, "detail": llm_msg})
    status_row(checks)

    if not docker_ok:
        msg(f"❌ **Docker niedostępny** — {docker_msg}\n\nUruchom Docker i odśwież.")
        buttons([{"label": "🔄 Sprawdź ponownie", "value": "back"}])
        return

    all_missing = [e for e in ENV_SCHEMA
                   if e.get("required_for")
                   and not _state.get(_ENV_TO_STATE.get(e["key"], e["key"].lower()))]

    # LLM key missing or invalid → show prompt inline alongside other missing fields
    if not llm_ok:
        from .fixes import _prompt_api_key
        if all_missing:
            msg(f"Uzupełnij **{len(all_missing)}** brakujące ustawienia:")
            _emit_missing_fields(all_missing)
        _prompt_api_key(return_action="back")
        return

    if all_missing:
        msg(f"Uzupełnij **{len(all_missing)}** brakujące ustawienia:")
        _emit_missing_fields(all_missing)
        buttons([
            {"label": "✅ Zapisz i uruchom",    "value": "preflight_save_launch::all"},
            {"label": "⚙️ Wszystkie ustawienia", "value": "settings"},
        ])
    else:
        msg("✅ Konfiguracja kompletna. Co chcesz zrobić?")
        buttons([
            {"label": "🚀 Uruchom infrastrukturę", "value": "launch_all"},
            {"label": "📦 Wdróż na urządzenie",     "value": "deploy_device"},
            {"label": "⚙️ Ustawienia (.env)",        "value": "settings"},
        ])


def step_status():
    _state["step"] = "status"
    clear_widgets()
    containers = docker_ps()
    if not containers:
        msg("⚠️ Brak uruchomionych kontenerów.")
        buttons([{"label":"🚀 Uruchom teraz","value":"launch_all"},{"label":"🏠 Menu","value":"back"}])
        return
    running = [c for c in containers if "Up" in c["status"] and "Restarting" not in c["status"]]
    failing = [c for c in containers if "Restarting" in c["status"] or "Exit" in c["status"]]
    msg(f"## 📊 Stan systemu — {len(running)} ✅ OK · {len(failing)} 🔴 problemów")
    if failing:
        msg(f"### 🔍 Analiza problemów ({len(failing)} kontenerów)")
        for c in failing:
            finding, btns = _analyze_container_log(c["name"])
            msg(f"#### `{c['name']}` — {c['status']}\n{finding}")
            if btns:
                btns.insert(0, {"label": f"📋 Logi: {c['name']}", "value": f"logs::{c['name']}"})
                buttons(btns)
    buttons([
        {"label":"🚀 Uruchom infrastrukturę",  "value":"launch_all"},
        {"label":"📦 Wdróż na urządzenie",      "value":"deploy_device"},
        {"label":"⚙️ Ustawienia (.env)",         "value":"settings"},
    ])

def step_pick_logs():
    clear_widgets()
    containers = docker_ps()
    if not containers:
        msg("Brak kontenerów."); buttons([{"label":"← Wróć","value":"back"}]); return
    msg("Wybierz kontener:")
    items = [{"label":c["name"],"value":f"logs::{c['name']}"} for c in containers]
    items.append({"label":"← Wróć","value":"back"})
    buttons(items)

def step_show_logs(container):
    clear_widgets()
    msg(f"📋 **Logi: `{container}`** (ostatnie 60 linii)")
    try:
        out = subprocess.check_output(["docker","logs","--tail","60",container],text=True,stderr=subprocess.STDOUT)
        code_block(out[-4000:])
    except Exception as e: msg(f"❌ {e}")
    buttons([{"label":"🔄 Odśwież","value":f"logs::{container}"},{"label":"← Inne logi","value":"pick_logs"}])

def step_settings(group: str = ""):
    """Show env editor for a specific group or group selector."""
    _state["step"] = "settings"
    clear_widgets()
    groups = list(dict.fromkeys(e["group"] for e in ENV_SCHEMA))
    if not group:
        msg("## ⚙️ Ustawienia — wybierz sekcję")
        msg("Kliknij sekcję aby edytować jej zmienne. Wszystko zapisywane do `dockfra/.env`.")
        btn_items = []
        for g in groups:
            g_entries = [e for e in ENV_SCHEMA if e["group"] == g]
            missing = [e for e in g_entries
                       if e.get("required_for") and not _state.get(_ENV_TO_STATE.get(e["key"],e["key"].lower()))]
            icon = "✅" if not missing else f"🔴{len(missing)}"
            btn_items.append({"label": f"{icon} {g}", "value": f"settings_group::{g}"})
        buttons(btn_items)
    else:
        entries = [e for e in ENV_SCHEMA if e["group"] == group]
        msg(f"## ⚙️ {group}")
        suggestions = _detect_suggestions()
        for e in entries:
            sk  = _ENV_TO_STATE.get(e["key"], e["key"].lower())
            cur = _state.get(sk, e.get("default", ""))
            sug = suggestions.get(e["key"], {})
            if not cur and sug.get("value"):
                cur = sug["value"]
            if e["type"] == "select":
                opts = [{"label": lbl, "value": val} for val, lbl in e["options"]]
                select(e["key"], e["label"], opts, cur,
                       desc=e.get("desc", ""), autodetect=e.get("autodetect", False))
            else:
                text_input(e["key"], e["label"],
                           e.get("placeholder", ""), cur,
                           sec=(e["type"] == "password"),
                           hint=sug.get("hint", ""),
                           chips=sug.get("chips", []),
                           modal_type="ip_picker" if e["key"] == "DEVICE_IP" else "",
                           desc=e.get("desc", ""), autodetect=e.get("autodetect", False))
        buttons([
            {"label": "💾 Zapisz",    "value": f"save_settings::{group}"},
            {"label": "← Sekcje",    "value": "settings"},
        ])


def step_save_settings(group: str, form: dict):
    """Save edited group back to _state and dockfra/.env."""
    clear_widgets()
    entries = [e for e in ENV_SCHEMA if e["group"] == group]
    env_updates: dict[str, str] = {}
    for e in entries:
        raw = form.get(e["key"], "")
        if raw is not None:
            val = str(raw).strip()
            sk = _ENV_TO_STATE.get(e["key"], e["key"].lower())
            _state[sk] = val
            env_updates[e["key"]] = val
    save_env(env_updates)
    lines = []
    for e in entries:
        sk = _ENV_TO_STATE.get(e["key"], e["key"].lower())
        val = _state.get(sk, "")
        display = mask(val) if e["type"] == "password" and val else (val or "(puste)")
        lines.append(f"{e['key']} = {display}")
    msg(f"✅ **{group}** — zapisano do `dockfra/.env`\n" + "\n".join(f"- `{l}`" for l in lines))
    buttons([
        {"label": "✏️ Edytuj dalej",  "value": f"settings_group::{group}"},
        {"label": "← Sekcje",        "value": "settings"},
        {"label": "🚀 Uruchom",       "value": "launch_all"},
    ])


def preflight_check(stacks: list[str]) -> list[dict]:
    """Return list of missing required vars for the given stacks.
    Each item: {key, label, group, type, placeholder}."""
    missing = []
    for e in ENV_SCHEMA:
        required = e.get("required_for", [])
        if not any(r in stacks or r == "all" for r in required):
            continue
        sk = _ENV_TO_STATE.get(e["key"], e["key"].lower())
        if not _state.get(sk):
            missing.append(e)
    return missing


def step_preflight_fill(stacks: list[str]):
    """Show inline form for all missing required vars before launching."""
    missing = preflight_check(stacks)
    if not missing:
        return False  # nothing missing, proceed
    clear_widgets()
    groups = list(dict.fromkeys(e["group"] for e in missing))
    msg("## ⚠️ Brakujące zmienne")
    msg(f"Przed uruchomieniem stacków `{', '.join(stacks)}` uzupełnij:`")
    for e in missing:
        msg(f"- **{e['label']}** (`{e['key']}`)", role="bot")
    msg("\nUzupełnij poniżej lub przejdź do ⚙️ Ustawienia:")
    for e in missing:
        if e["type"] == "select":
            opts = [{"label": lbl, "value": val} for val, lbl in e["options"]]
            select(e["key"], e["label"], opts, e.get("default", ""))
        else:
            text_input(e["key"], e["label"],
                       e.get("placeholder", ""), _state.get(_ENV_TO_STATE.get(e["key"],""), ""),
                       sec=(e["type"] == "password"))
    buttons([
        {"label": "✅ Zapisz i uruchom",  "value": f"preflight_save_launch::{','.join(stacks)}"},
        {"label": "⚙️ Pełne ustawienia",  "value": "settings"},
        {"label": "← Wróć",              "value": "back"},
    ])
    return True  # showed form, caller should stop


def step_setup_creds():
    _state["step"] = "setup_creds"
    clear_widgets()
    msg("## 🔑 Credentials (skrót)")
    msg("Szybka edycja najważniejszych zmiennych. Pełne ustawienia: ⚙️ Ustawienia.")
    text_input("GIT_NAME","Git user.name","Jan Kowalski",_state.get("git_name",""))
    text_input("GIT_EMAIL","Git user.email","jan@example.com",_state.get("git_email",""))
    text_input("GITHUB_SSH_KEY","Ścieżka klucza SSH","~/.ssh/id_ed25519",_state.get("github_key",""))
    text_input("OPENROUTER_API_KEY","OpenRouter API Key","sk-or-v1-...",_state.get("openrouter_key",""),sec=True)
    opts = [{"label": lbl, "value": val}
            for val,lbl in next(e["options"] for e in ENV_SCHEMA if e["key"]=="LLM_MODEL")]
    select("LLM_MODEL","Model LLM", opts, _state.get("llm_model",_schema_defaults().get("LLM_MODEL","")))
    buttons([{"label":"💾 Zapisz","value":"save_creds"},{"label":"⚙️ Wszystkie ustawienia","value":"settings"},{"label":"← Wróć","value":"back"}])

def step_save_creds(form):
    clear_widgets()
    env_updates: dict[str, str] = {}
    for env_key in ("GIT_NAME","GIT_EMAIL","GITHUB_SSH_KEY","OPENROUTER_API_KEY","LLM_MODEL"):
        raw = form.get(env_key, "")
        if raw:
            val = str(raw).strip()
            sk = _ENV_TO_STATE[env_key]
            _state[sk] = val
            env_updates[env_key] = val
    # Handle custom model input: if LLM_MODEL is __custom__ or LLM_MODEL_CUSTOM is filled, use custom
    model_custom = form.get("LLM_MODEL_CUSTOM", "").strip()
    model_sel = form.get("LLM_MODEL", "").strip()
    if model_custom and (model_sel == "__custom__" or model_custom):
        _state["llm_model"] = model_custom
        env_updates["LLM_MODEL"] = model_custom
    save_env(env_updates)
    msg("✅ Zapisano i zaktualizowano `dockfra/.env`.")
    key = _state.get("openrouter_key","")
    msg(f"- Git: `{_state.get('git_name','')}` <{_state.get('git_email','')}>")
    msg(f"- SSH: `{_state.get('github_key','')}`")
    msg(f"- API: `{mask(key) if key else '(brak)'}`")
    msg(f"- Model: `{_state.get('llm_model','')}`")
    buttons([{"label":"🚀 Uruchom stacki","value":"launch_all"},{"label":"⚙️ Ustawienia","value":"settings"},{"label":"🏠 Menu","value":"back"}])

def step_launch_all():
    _state["step"] = "launch_all"
    clear_widgets()
    msg("## 🚀 Uruchamianie stacków")
    select("stacks", "Stacki do uruchomienia", [
        {"label": "Wszystkie (management + app + devices)", "value": "all"},
        {"label": "Management",                            "value": "management"},
        {"label": "App",                                   "value": "app"},
        {"label": "Devices",                               "value": "devices"},
    ], _state.get("stacks", "all"))
    select("environment", "Środowisko", [
        {"label": "Local",      "value": "local"},
        {"label": "Production", "value": "production"},
    ], _state.get("environment", "local"))
    buttons([
        {"label": "▶️ Uruchom", "value": "do_launch"},
        {"label": "← Wróć",    "value": "back"},
    ])

def step_launch_configure():
    step_launch_all()

def _analyze_launch_error(name: str, output: str) -> tuple[str, list]:
    """Parse docker compose output and return (analysis_text, solution_buttons)."""
    lines = output[-3000:]
    analysis = []
    solutions = []

    if "port is already allocated" in lines or "address already in use" in lines:
        import re
        port = re.search(r"Bind for [\d.]+:(\d+) failed", lines)
        port_num = port.group(1) if port else "?"
        analysis.append(f"⚠️ **Port `{port_num}` zajęty** — inny proces już go używa.")
        solutions.append({"label":f"🔍 Pokaż co blokuje port {port_num}","value":f"diag_port::{port_num}"})
        if port_num == "6080" and name == "devices":
            solutions.append({"label":"🔧 Auto: użyj portu 6082 dla VNC","value":"fix_vnc_port"})
        solutions.append({"label":f"🔄 Zmień port i spróbuj ponownie","value":f"retry_launch"})

    if "Pool overlaps" in lines or "invalid pool request" in lines:
        import re
        net_m = re.search(r"failed to create network ([\w_-]+)", lines)
        net_name = net_m.group(1) if net_m else ""
        if net_name:
            analysis.append(f"⚠️ **Konflikt sieci Docker** — `{net_name}` nakłada się z istniejącą siecią.\nUsuń starą sieć i spróbuj ponownie.")
            solutions.append({"label": f"🔧 Usuń sieć `{net_name}`", "value": f"fix_network_overlap::{net_name}"})
        else:
            analysis.append("⚠️ **Konflikt przestrzeni adresowej sieci Docker** — stare sieci blokują nowe.")
            solutions.append({"label": "🔧 Wyczyść nieużywane sieci", "value": "fix_network_overlap::"})

    if "undefined network" in lines or "invalid compose project" in lines:
        import re
        net = re.search(r'"([^"]+)" refers to undefined network ([^:]+)', lines)
        srv = net.group(1) if net else "service"
        netname = net.group(2).strip() if net else "?"
        analysis.append(f"⚠️ **Sieć `{netname}` niezdefiniowana** w `{name}/docker-compose.yml` (service: `{srv}`).")
        solutions.append({"label":f"🔧 Auto-napraw compose","value":f"fix_compose::{name}"})

    if "variable is not set" in lines or "Defaulting to a blank string" in lines:
        missing = []
        for ln in lines.splitlines():
            if "variable is not set" in ln:
                import re; m = re.search(r'"([A-Z_]+)" variable is not set', ln)
                if m and m.group(1) not in missing: missing.append(m.group(1))
        if missing:
            analysis.append(f"⚠️ **Brakujące zmienne env:** `{'`, `'.join(missing[:6])}`")
            solutions.append({"label":"🔑 Skonfiguruj credentials","value":"setup_creds"})
            solutions.append({"label":"📄 Pokaż brakujące zmienne","value":f"show_missing_env::{name}"})

    if "permission denied" in lines.lower():
        analysis.append("⚠️ **Błąd uprawnień** — sprawdź czy Docker działa bez sudo lub dodaj użytkownika do grupy `docker`.")
        solutions.append({"label":"🔧 Napraw uprawnienia Docker","value":"fix_docker_perms"})

    _base_img = PROJECT["ssh_base_image"]
    if _base_img in lines and ("pull access denied" in lines or "failed to resolve source metadata" in lines):
        analysis.append(
            f"⚠️ **Brak lokalnego obrazu `{_base_img}`** — obraz bazowy SSH musi być zbudowany lokalnie "
            "z `shared/Dockerfile.ssh-base`. Kliknij **Spróbuj ponownie** — kreator zbuduje go automatycznie.")
        solutions.append({"label":"🔨 Zbuduj ssh-base i uruchom ponownie","value":"retry_launch"})
    elif "pull access denied" in lines or ("not found" in lines and "image" in lines):
        analysis.append("⚠️ **Nie można pobrać obrazu Docker** — sprawdź nazwę obrazu i dostęp do registry.")
        solutions.append({"label":"🔄 Spróbuj ponownie","value":"retry_launch"})

    if not analysis:
        # Show last few lines so user can self-diagnose without clicking "Pokaż logi"
        tail = "\n".join(l for l in lines.splitlines()[-8:] if l.strip())
        analysis.append(f"❌ **Stack `{name}` nie uruchomił się** — ostatnie logi:\n```\n{tail}\n```")
        solutions.append({"label":"📋 Pokaż pełne logi","value":f"logs_stack::{name}"})

    solutions.append({"label":"🔄 Spróbuj ponownie","value":"retry_launch"})
    solutions.append({"label":"⏭ Pomiń i kontynuuj","value":"post_launch_creds"})
    solutions.append({"label":"🏠 Menu","value":"back"})
    return "\n".join(analysis), solutions


def step_do_launch(form):
    clear_widgets()
    stacks = form.get("stacks", form.get("STACKS", _state.get("stacks","all")))
    env    = form.get("environment", form.get("ENVIRONMENT", _state.get("environment","local")))
    _state.update({"stacks":stacks,"environment":env})
    save_env({"STACKS": stacks, "ENVIRONMENT": env})

    target_names = list(STACKS.keys()) if stacks == "all" else [stacks]
    # Pre-flight: check for missing required vars
    if step_preflight_fill(target_names):
        return  # form shown, wait for user

    cf = "docker-compose.yml" if env == "local" else "docker-compose-production.yml"

    # ── If app stack is requested but folder missing, clone from GIT_REPO_URL ─
    app_repo_url = _state.get("git_repo_url", "")
    app_dir = ROOT / "app"
    needs_app = "app" in target_names
    if needs_app and app_repo_url:
        if not app_dir.exists() or not any(app_dir.iterdir()):
            msg(f"📥 Klonuję repozytorium aplikacji z `{app_repo_url}`…")
            branch = _state.get("git_branch", "main") or "main"
            rc = subprocess.run(
                ["git", "clone", "--branch", branch, "--depth", "1", app_repo_url, str(app_dir)],
                capture_output=True, text=True)
            if rc.returncode != 0:
                msg(f"❌ Błąd klonowania:\n```\n{rc.stderr[:1000]}\n```")
                buttons([{"label":"⚙️ Zmień GIT_REPO_URL","value":"settings_group::Git"},
                         {"label":"🏠 Menu","value":"back"}])
                return
            msg(f"✅ Sklonowano do `{app_dir}`")
            _refresh_ssh_roles()
        elif (app_dir / ".git").exists():
            progress("🔄 Aktualizuję app/ (git pull)…")
            subprocess.run(["git", "-C", str(app_dir), "pull", "--ff-only"],
                           capture_output=True)
            _refresh_ssh_roles()
    elif needs_app and not app_repo_url and not app_dir.exists():
        msg("⚠️ Stack `app` wybrany, ale brak folderu `app/` i `GIT_REPO_URL` nie jest ustawiony.")
        buttons([{"label":"⚙️ Ustaw GIT_REPO_URL","value":"settings_group::Git"},
                 {"label":"🏠 Menu","value":"back"}])
        return

    # Re-discover stacks after potential clone (app/ may now exist)
    from dockfra.core import _discover_stacks as _ds
    _current_stacks = _ds()
    targets = [(name, _current_stacks[name]) for name in target_names if name in _current_stacks]
    if not targets:
        msg("⚠️ Brak dostępnych stacków do uruchomienia.")
        buttons([{"label":"🏠 Menu","value":"back"}])
        return

    _launch_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _launch_sid  # propagate SID so _emit_log_error targets the right client
        subprocess.run(["docker","network","create",PROJECT["network"]],capture_output=True)

        # ── Build shared SSH base image (required by all ssh-* roles) ─────────
        ssh_base_dockerfile = ROOT / "shared" / "Dockerfile.ssh-base"
        ssh_base_context    = ROOT / "shared"
        needs_base = any(
            any(sd.name.startswith("ssh-") and (sd / "Dockerfile").exists()
                for sd in path.iterdir() if sd.is_dir())
            for _, path in targets)
        if needs_base and ssh_base_dockerfile.exists():
            # Only rebuild if the image doesn't already exist
            check = subprocess.run(
                ["docker","image","inspect",PROJECT["ssh_base_image"]],
                capture_output=True)
            if check.returncode != 0:
                progress(f"🔨 Buduję {PROJECT['ssh_base_image']}...")
                proc = subprocess.Popen(
                    ["docker","build","-t",PROJECT["ssh_base_image"],
                     "-f", str(ssh_base_dockerfile), str(ssh_base_context)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=str(ROOT))
                for line in proc.stdout:
                    socketio.emit("log_line", {"text": line.rstrip()})
                proc.wait()
                if proc.returncode != 0:
                    progress(PROJECT["ssh_base_image"], error=True)
                    msg(f"❌ **Błąd budowania `{PROJECT['ssh_base_image']}`** — sprawdź logi po prawej.")
                    buttons([{"label":"🔄 Spróbuj ponownie","value":"retry_launch"},
                             {"label":"🏠 Menu","value":"back"}])
                    return
                progress(PROJECT["ssh_base_image"], done=True)
            else:
                progress(f"{PROJECT['ssh_base_image']} (cached)", done=True)

        # ── Create missing env_file stubs for every stack ─────────────────────
        # Scans docker-compose*.yml for `env_file:` entries and touches missing
        # files so docker-compose doesn't abort on "not found".
        def _ensure_env_stubs(stack_path: Path):
            """Touch any env_file paths referenced in compose files that don't exist."""
            import re as _re2
            # Matches: env_file: ./path  OR  - ./path  OR  - path: ./path
            _pat = _re2.compile(
                r'(?:env_file:\s*([^\n\[{#]+))'      # scalar: env_file: ./foo/.env
                r'|(?:-\s*path:\s*([^\n#]+))'         # list path: - path: ./foo/.env
                r'|(?:-\s*(\.{0,2}/[^\n#{]+\.env))'   # list bare: - ./foo/.env
            )
            for cf_name in ("docker-compose.yml", "docker-compose.yaml",
                            "docker-compose-production.yml"):
                cf = stack_path / cf_name
                if not cf.exists():
                    continue
                for m in _pat.finditer(cf.read_text(errors="replace")):
                    raw = (m.group(1) or m.group(2) or m.group(3) or "").strip().strip('"\'')
                    if not raw:
                        continue
                    p = (stack_path / raw).resolve()
                    # Only create stubs inside the stack directory (safety check)
                    try:
                        p.relative_to(stack_path)
                    except ValueError:
                        continue
                    if not p.exists():
                        try:
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.touch()
                        except Exception:
                            pass

        for _, path in targets:
            _ensure_env_stubs(path)

        env_file_args = ["--env-file", str(WIZARD_ENV)] if WIZARD_ENV.exists() else []
        failed = []
        for name, path in targets:
            progress(f"▶️ {name}...")
            rc, out = run_cmd(["docker","compose","-f",cf]+env_file_args+["up","-d","--build"],cwd=path)
            progress(f"{name}", done=(rc==0), error=(rc!=0))
            if rc != 0:
                failed.append((name, out))

        if failed:
            msg("## 🔍 Analiza błędów")
            for name, out in failed:
                analysis, solutions = _analyze_launch_error(name, out)
                msg(f"### Stack: `{name}`\n{analysis}")
                msg("Co chcesz zrobić?")
                buttons(solutions)
                time.sleep(0.1)
        else:
            msg("## ✅ Wszystkie stacki uruchomione!")

        # ── Post-launch health check ──────────────────────────────────────────
        # docker compose up -d exits 0 even if containers crash on startup.
        # Wait for containers to stabilise, then check their runtime status.
        progress("⏳ Sprawdzam zdrowie kontenerów…")
        time.sleep(8)
        progress("⏳ Sprawdzam zdrowie kontenerów…", done=True)
        all_containers = docker_ps()
        restarting = [c for c in all_containers
                      if "Restarting" in c["status"] or
                         ("Exit" in c["status"] and c["status"] != "Exited (0)")]
        if restarting:
            msg(f"### ⚠️ {len(restarting)} kontener(ów) ma problemy po starcie:")
            for c in restarting:
                finding, btns = _analyze_container_log(c["name"])
                msg(f"#### 🔴 `{c['name']}` — {c['status']}\n{finding}")
                if btns:
                    btns.insert(0, {"label": f"📋 Logi: {c['name']}", "value": f"logs::{c['name']}"})
                time.sleep(0.05)
            # Show single consolidated action bar for failing containers
            fix_btns = []
            for c in restarting:
                fix_btns.append({"label": f"🔧 Napraw {short_name(c['name'])}", "value": f"fix_container::{c['name']}"})
            fix_btns += [
                {"label": "🔄 Uruchom ponownie", "value": "retry_launch"},
                {"label": "⚙️ Ustawienia",       "value": "settings"},
            ]
            buttons(fix_btns)
        else:
            msg("## ✅ Infrastruktura gotowa!")
            vnc_port  = _state.get("DESKTOP_VNC_PORT", "6081")
            running_names = {c["name"] for c in all_containers if "Up" in c["status"] or "healthy" in c["status"]}
            sections = []
            # Build sections dynamically from discovered roles
            for role, ri in _SSH_ROLES.items():
                if ri["container"] not in running_names:
                    continue
                port = _state.get(f"SSH_{role.upper()}_PORT", ri["port"])
                rows = "\n".join(f"| {c} | {d} | {m} |" for c, d, m in ri["commands"])
                sections.append(
                    f"### {ri['icon']} {ri['title']}  "
                    f"`ssh {ri['user']}@localhost -p {port}`\n"
                    f"| Komenda | Opis | Host (`make`) |\n|---|---|---|\n{rows}"
                )
            if cname("desktop") in running_names or cname("desktop-app") in running_names:
                sections.append(
                    f"### 🖥️ Desktop (noVNC)  [http://localhost:{vnc_port}](http://localhost:{vnc_port})\n"
                    "Przeglądarkowy pulpit z podglądem dashboardu i logów."
                )
            if sections:
                msg("---\n## 🗺️ Co możesz teraz zrobić?\nWybierz rolę poniżej aby zobaczyć dostępne akcje.")
            # Re-read roles at this point (state is fully loaded)
            _refresh_ssh_roles()
            # Build buttons dynamically from discovered roles
            post_btns = []
            for role, ri in _SSH_ROLES.items():
                p = _state.get(f"SSH_{role.upper()}_PORT", ri["port"])
                post_btns.append({"label": f"{ri['icon']} SSH {role.capitalize()}", "value": f"ssh_info::{role}::{p}"})
            # Virtual developer: app/ not cloned yet but GIT_REPO_URL is set
            if "developer" not in _SSH_ROLES and not (ROOT / "app").is_dir() and _state.get("git_repo_url"):
                dev_port = _state.get("ssh_developer_port", "2200")
                post_btns.insert(0, {"label": "🔧 SSH Developer", "value": f"ssh_info::developer::{dev_port}"})
            post_btns += [
                {"label": "📝 Utwórz ticket",        "value": "ticket_create_wizard"},
                {"label": "📊 Statystyki projektu",   "value": "project_stats"},
                {"label": "🔗 Integracje zadań",      "value": "integrations_setup"},
                {"label": "🔑 Setup GitHub + LLM",    "value": "post_launch_creds"},
                {"label": "📦 Wdróż na urządzenie",   "value": "deploy_device"},
            ]
            buttons(post_btns)
    threading.Thread(target=run,daemon=True).start()

def step_deploy_device():
    _state["step"] = "deploy_device"
    clear_widgets()
    msg("## 📦 Wdrożenie na urządzenie")
    text_input("device_ip",  "IP urządzenia","192.168.1.100",_state.get("device_ip",""))
    text_input("device_user","Użytkownik SSH","pi",           _state.get("device_user","pi"))
    text_input("device_port","Port SSH",      "22",           str(_state.get("device_port","22")))
    buttons([
        {"label":"🔍 Testuj połączenie","value":"test_device"},
        {"label":"🚀 Wdróż","value":"do_deploy"},
        {"label":"← Wróć","value":"back"},
    ])

def _save_device_form(form):
    if form:
        _state.update({
            "device_ip":   form.get("device_ip",  _state.get("device_ip","")).strip(),
            "device_user": form.get("device_user",_state.get("device_user","pi")).strip(),
            "device_port": form.get("device_port",_state.get("device_port","22")).strip(),
        })

def step_test_device(form):
    _save_device_form(form); clear_widgets()
    ip, user, port = _state["device_ip"], _state["device_user"], _state["device_port"]
    key = _state.get("github_key", str(Path.home()/".ssh/id_ed25519"))
    if not ip: msg("❌ Podaj IP!"); step_deploy_device(); return
    msg(f"🔍 Testuję `{user}@{ip}:{port}`...")
    def run():
        rc, out = run_cmd(["ssh","-i",key,"-p",str(port),"-o","ConnectTimeout=8",
                           "-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
                           f"{user}@{ip}","uname -a && echo DOCKFRA_OK"])
        if rc==0 and "DOCKFRA_OK" in out:
            msg(f"✅ Połączenie działa!")
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":"🚀 Wdróż teraz","value":"do_deploy"},{"label":"← Zmień","value":"deploy_device"}]})
        else:
            msg(f"❌ Brak połączenia z `{ip}:{port}`")
            pub = Path(key+".pub")
            if pub.exists():
                msg("Dodaj klucz do urządzenia:")
                code_block(f"ssh-copy-id -i {key}.pub -p {port} {user}@{ip}")
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":"🔄 Spróbuj ponownie","value":"test_device"},{"label":"← Wróć","value":"deploy_device"}]})
    threading.Thread(target=run,daemon=True).start()

def step_do_deploy(form):
    _save_device_form(form); clear_widgets()
    ip, user, port = _state["device_ip"], _state["device_user"], _state["device_port"]
    key = _state.get("github_key", str(Path.home()/".ssh/id_ed25519"))
    if not ip: msg("❌ Brak IP!"); step_deploy_device(); return
    msg(f"## 🚀 Wdrożenie → `{user}@{ip}:{port}`")
    def run():
        container = _get_role("developer")["container"]
        if container not in [c["name"] for c in docker_ps()]:
            msg(f"❌ `{container}` nie działa. Uruchom app stack.")
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":"🚀 Uruchom stacki","value":"launch_all"},{"label":"← Wróć","value":"back"}]}); return
        progress("Kopiuję klucz SSH do developer...")
        kpath = Path(key).expanduser()
        if kpath.exists():
            subprocess.run(["docker","cp",str(kpath),f"{container}:/tmp/dk"],capture_output=True)
            subprocess.run(["docker","exec",container,"bash","-c",
                "mkdir -p /home/developer/.ssh && cp /tmp/dk /home/developer/.ssh/id_ed25519 && "
                "chmod 600 /home/developer/.ssh/id_ed25519 && rm /tmp/dk"],capture_output=True)
        progress("Klucz SSH gotowy",done=True)
        progress(f"Testuję SSH: developer → {ip}...")
        rc, out = run_cmd(["docker","exec",container,
            "ssh","-i","/home/developer/.ssh/id_ed25519","-p",str(port),
            "-o","ConnectTimeout=8","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
            f"{user}@{ip}","uname -a && echo DOCKFRA_DEPLOY_OK"])
        if rc!=0 or "DOCKFRA_DEPLOY_OK" not in out:
            progress(f"SSH do {ip} nieudany",error=True)
            msg(f"❌ Nie można połączyć się z `{ip}` z kontenera developer.")
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":"🔄 Spróbuj ponownie","value":"do_deploy"},{"label":"← Wróć","value":"deploy_device"}]}); return
        progress(f"SSH → {ip} działa!",done=True)
        msg(f"✅ Połączenie `developer → {ip}` działa!")
        # Save to devices/.env.local
        _update_device_env(ip, user, port)
        progress("Konfiguracja zapisana w devices/.env.local",done=True)
        msg(f"\n✅ **Urządzenie `{ip}` skonfigurowane jako cel deployment!**")
        msg("Uruchom `make up-devices` aby wystartować ssh-rpi3 + vnc-rpi3 dla tego urządzenia.")
        socketio.emit("widget",{"type":"buttons","items":[
            {"label":"▶️ Uruchom devices stack","value":"launch_devices"}]})
    threading.Thread(target=run,daemon=True).start()

def _update_device_env(ip, user, port):
    env_path = DEVS/".env.local"
    lines, found = [], {"RPI3_HOST":False,"RPI3_USER":False,"RPI3_SSH_PORT":False}
    if env_path.exists():
        for l in env_path.read_text().splitlines():
            k = l.split("=",1)[0] if "=" in l else ""
            if k in found:
                lines.append(f"{k}={'ip' if k=='RPI3_HOST' else ('user' if k=='RPI3_USER' else port)}")
                lines[-1] = f"{k}={ip if k=='RPI3_HOST' else (user if k=='RPI3_USER' else port)}"
                found[k] = True
            else: lines.append(l)
    for k,v in [("RPI3_HOST",ip),("RPI3_USER",user),("RPI3_SSH_PORT",port)]:
        if not found[k]: lines.append(f"{k}={v}")
    env_path.write_text("\n".join(lines)+"\n")

def step_launch_devices(form=None):
    clear_widgets()
    msg("▶️ Uruchamiam **devices** stack...")
    def run():
        subprocess.run(["docker","network","create",PROJECT["network"]],capture_output=True)
        progress("Uruchamiam devices...")
        rc, _ = run_cmd(["docker","compose","up","-d","--build"],cwd=DEVS)
        progress("devices",done=(rc==0),error=(rc!=0))
        if rc==0:
            vnc_p = _state.get("VNC_RPI3_PORT", "6080")
            msg("✅ Devices stack uruchomiony!")
            msg(f"📺 VNC: http://localhost:{vnc_p}")
            msg(f"🔒 SSH-RPi3: `ssh deployer@localhost -p {_state.get('SSH_RPI3_PORT','2224')}`")
        else:
            msg("❌ Błąd uruchamiania devices stack")
    threading.Thread(target=run,daemon=True).start()

def step_post_launch_creds():
    clear_widgets()
    dev_role = _get_role("developer")
    container = dev_role["container"]
    if container not in [c["name"] for c in docker_ps()]:
        msg(f"❌ `{container}` nie działa.")
        buttons([{"label":"🚀 Uruchom stacki","value":"launch_all"},{"label":"← Wróć","value":"back"}]); return
    msg(f"## 🔑 Setup GitHub + LLM w {dev_role['user']}")
    key = _state.get("openrouter_key","")
    status_row([
        {"name":"GitHub SSH key","ok": Path(_state.get("github_key","~/.ssh/id_ed25519")).expanduser().exists(),"detail":_state.get("github_key","")},
        {"name":"OpenRouter Key","ok": bool(key and key.startswith("sk-")),"detail":mask(key) if key else "brak"},
    ])
    buttons([{"label":"✅ Uruchom konfigurację","value":"run_post_creds"},
             {"label":"✏️ Zmień credentials","value":"setup_creds"},
             {"label":"← Wróć","value":"back"}])

def step_run_post_creds():
    clear_widgets()
    msg("⚙️ Konfiguruję GitHub + LLM...")
    def run():
        env = {**os.environ,
               "DEVELOPER_CONTAINER":_get_role("developer")["container"],"DEVELOPER_USER":_get_role("developer")["user"],
               "GITHUB_SSH_KEY":_state.get("github_key",str(Path.home()/".ssh/id_ed25519")),
               "LLM_MODEL":_state.get("llm_model",_schema_defaults().get("LLM_MODEL","")),
               "OPENROUTER_API_KEY":_state.get("openrouter_key","")}
        for script in ["setup-github-keys.sh","setup-llm.sh","setup-dev-tools.sh"]:
            sp = ROOT/"scripts"/script
            if sp.exists():
                progress(f"{script}...")
                proc = subprocess.Popen(["bash",str(sp)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,cwd=str(ROOT))
                for l in proc.stdout: socketio.emit("log_line",{"text":l.rstrip()})
                proc.wait()
                progress(f"{script}",done=(proc.returncode==0),error=(proc.returncode!=0))
        msg("\n✅ Konfiguracja zakończona!")
    threading.Thread(target=run,daemon=True).start()

