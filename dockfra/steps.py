"""Wizard step functions — welcome, status, settings, launch, deploy."""
from .core import *
from .i18n import t, set_lang, get_lang, llm_lang_instruction, _STRINGS
from .discover import _SSH_ROLES, _get_role, _refresh_ssh_roles

def step_welcome():
    _state["step"] = "welcome"
    cfg = detect_config()
    _state.update({k:v for k,v in cfg.items() if v})
    _refresh_ssh_roles()  # re-scan now that _state has git_repo_url
    msg(t('welcome_title'))

    # ── Pre-flight connectivity checks ────────────────────────────────────────
    from .fixes import validate_docker, validate_llm_connection
    docker_ok, docker_msg = validate_docker()
    llm_ok, llm_msg = validate_llm_connection()
    checks = []
    checks.append({"name": t('status_check_docker'), "ok": docker_ok, "detail": docker_msg})
    checks.append({"name": t('status_check_llm'), "ok": llm_ok, "detail": llm_msg})
    status_row(checks)

    if not docker_ok:
        msg(t('docker_unavailable', detail=docker_msg))
        buttons([{"label": t('check_again'), "value": "back"}])
        return

    all_missing = [e for e in ENV_SCHEMA
                   if e.get("required_for")
                   and not _state.get(_ENV_TO_STATE.get(e["key"], e["key"].lower()))]

    # LLM key missing or invalid → show prompt inline alongside other missing fields
    if not llm_ok:
        from .fixes import _prompt_api_key
        if all_missing:
            msg(t('fill_missing_n', n=len(all_missing)))
            _emit_missing_fields(all_missing)
        _prompt_api_key(return_action="back")
        return

    if all_missing:
        msg(t('fill_missing_n', n=len(all_missing)))
        _emit_missing_fields(all_missing)
        buttons([
            {"label": t('save_and_run'),    "value": "preflight_save_launch::all"},
            {"label": t('all_settings'), "value": "settings"},
        ])
    else:
        msg(t('config_complete'))
        buttons([
            {"label": t('launch_infra'), "value": "launch_all"},
            {"label": t('deploy_device'),     "value": "deploy_device"},
            {"label": t('settings'),        "value": "settings"},
        ])


def step_status():
    _state["step"] = "status"
    clear_widgets()
    containers = docker_ps()
    if not containers:
        msg(t('no_containers'))
        buttons([{"label": t('launch_now'),"value":"launch_all"},{"label": t('menu'),"value":"back"}])
        return
    running = [c for c in containers if "Up" in c["status"] and "Restarting" not in c["status"]]
    failing = [c for c in containers if "Restarting" in c["status"] or "Exit" in c["status"]]
    msg(t('system_status', ok=len(running), fail=len(failing)))
    if failing:
        msg(t('problem_analysis', n=len(failing)))
        for c in failing:
            finding, btns = _analyze_container_log(c["name"])
            msg(f"#### `{c['name']}` — {c['status']}\n{finding}")
            if btns:
                btns.insert(0, {"label": t('logs_for_container', name=c['name']), "value": f"logs::{c['name']}"})
                buttons(btns)
    buttons([
        {"label": t('launch_infra'),  "value":"launch_all"},
        {"label": t('deploy_device'),      "value":"deploy_device"},
        {"label": t('settings'),         "value":"settings"},
    ])

def step_pick_logs():
    clear_widgets()
    containers = docker_ps()
    if not containers:
        msg(t('no_containers_short')); buttons([{"label": t('back'),"value":"back"}]); return
    msg(t('pick_container'))
    items = [{"label":c["name"],"value":f"logs::{c['name']}"} for c in containers]
    items.append({"label": t('back'),"value":"back"})
    buttons(items)

def step_show_logs(container):
    clear_widgets()
    msg(t('logs_title', name=container, n=60))
    try:
        out = subprocess.check_output(["docker","logs","--tail","60",container],text=True,stderr=subprocess.STDOUT)
        code_block(out[-4000:])
    except Exception as e: msg(t('cannot_get_logs', err=e))
    buttons([{"label": t('refresh'),"value":f"logs::{container}"},{"label": t('other_logs'),"value":"pick_logs"}])

def step_settings(group: str = ""):
    """Show env editor for a specific group or group selector."""
    _state["step"] = "settings"
    clear_widgets()
    groups = list(dict.fromkeys(e["group"] for e in ENV_SCHEMA))
    if not group:
        # Find first group with missing required fields; otherwise use first group
        first_group = groups[0] if groups else None
        for g in groups:
            g_entries = [e for e in ENV_SCHEMA if e["group"] == g]
            missing = [e for e in g_entries
                       if e.get("required_for") and not _state.get(_ENV_TO_STATE.get(e["key"],e["key"].lower()))]
            if missing:
                first_group = g
                break
        if first_group:
            step_settings(first_group)
        return
    else:
        entries = [e for e in ENV_SCHEMA if e["group"] == group]
        msg(t('settings_group_title', group=group))
        suggestions = _detect_suggestions()
        for e in entries:
            sk  = _ENV_TO_STATE.get(e["key"], e["key"].lower())
            cur = _state.get(sk, e.get("default", ""))
            sug = suggestions.get(e["key"], {})
            if not cur and sug.get("value"):
                cur = sug["value"]
            _lbl = t(e["label"]) if e["label"] in _STRINGS else e["label"]
            if e["type"] == "select":
                opts = [{"label": (t(lbl) if lbl in _STRINGS else lbl), "value": val} for val, lbl in e["options"]]
                select(e["key"], _lbl, opts, cur,
                       desc=e.get("desc", ""), autodetect=e.get("autodetect", False))
            else:
                text_input(e["key"], _lbl,
                           e.get("placeholder", ""), cur,
                           sec=(e["type"] == "password"),
                           hint=sug.get("hint", ""),
                           chips=sug.get("chips", []),
                           modal_type="ip_picker" if e["key"] == "DEVICE_IP" else "",
                           desc=e.get("desc", ""), autodetect=e.get("autodetect", False))
        buttons([
            {"label": t('save'),         "value": f"save_settings::{group}"},
            {"label": t('all_sections'), "value": "settings_nav"},
            {"label": t('menu'),         "value": "back"},
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
    save_state()
    lines = []
    for e in entries:
        sk = _ENV_TO_STATE.get(e["key"], e["key"].lower())
        val = _state.get(sk, "")
        display = mask(val) if e["type"] == "password" and val else (val or t('empty_val'))
        lines.append(f"{e['key']} = {display}")
    msg(t('saved_to_env', group=group) + "\n" + "\n".join(f"- `{l}`" for l in lines))
    buttons([
        {"label": t('edit_more'),  "value": f"settings_group::{group}"},
        {"label": t('all_sections'),"value": "settings_nav"},
        {"label": t('launch_infra'),       "value": "launch_all"},
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
    msg(t('missing_vars_title'))
    msg(t('fill_missing_n', n=len(missing)))
    for e in missing:
        _lbl = t(e["label"]) if e["label"] in _STRINGS else e["label"]
        msg(f"- **{_lbl}** (`{e['key']}`)", role="bot")
    msg("")
    suggestions = _detect_suggestions()
    for e in missing:
        sk  = _ENV_TO_STATE.get(e["key"], e["key"].lower())
        cur = _state.get(sk, e.get("default", ""))
        sug = suggestions.get(e["key"], {})
        if not cur and sug.get("value"):
            cur = sug["value"]
        _lbl = t(e["label"]) if e["label"] in _STRINGS else e["label"]
        if e["type"] == "select":
            opts = [{"label": lbl, "value": val} for val, lbl in e["options"]]
            select(e["key"], _lbl, opts, cur)
        else:
            text_input(e["key"], _lbl,
                       e.get("placeholder", ""), cur,
                       sec=(e["type"] == "password"),
                       hint=sug.get("hint", ""), chips=sug.get("chips", []),
                       modal_type="ip_picker" if e["key"] == "DEVICE_IP" else "",
                       desc=e.get("desc", ""))
    buttons([
        {"label": t('save_and_run'),  "value": f"preflight_save_launch::{','.join(stacks)}"},
        {"label": t('full_settings'),  "value": "settings"},
        {"label": t('back'),              "value": "back"},
    ])
    return True  # showed form, caller should stop


def step_setup_creds():
    _state["step"] = "setup_creds"
    clear_widgets()
    msg(t('creds_shortcut_title'))
    msg(t('creds_shortcut_desc'))
    sug = _detect_suggestions()
    git_name_sug = sug.get("GIT_NAME", {})
    text_input("GIT_NAME","Git user.name","Jan Kowalski",
               _state.get("git_name","") or git_name_sug.get("value",""),
               hint=git_name_sug.get("hint",""), autodetect=True)
    git_email_sug = sug.get("GIT_EMAIL", {})
    text_input("GIT_EMAIL","Git user.email","jan@example.com",
               _state.get("git_email","") or git_email_sug.get("value",""),
               hint=git_email_sug.get("hint",""), autodetect=True)
    ssh_sug = sug.get("GITHUB_SSH_KEY", {})
    text_input("GITHUB_SSH_KEY",t('ssh_key_path'),"~/.ssh/id_ed25519",
               _state.get("github_key","") or ssh_sug.get("value",""),
               hint=ssh_sug.get("hint",""), chips=ssh_sug.get("chips",[]))
    or_sug = sug.get("OPENROUTER_API_KEY", {})
    text_input("OPENROUTER_API_KEY","OpenRouter API Key","sk-or-v1-...",
               _state.get("openrouter_key","") or or_sug.get("value",""),
               sec=True, hint=or_sug.get("hint",""),
               help_url="https://openrouter.ai/keys")
    opts = [{"label": lbl, "value": val}
            for val,lbl in next(e["options"] for e in ENV_SCHEMA if e["key"]=="LLM_MODEL")]
    select("LLM_MODEL","Model LLM", opts, _state.get("llm_model",_schema_defaults().get("LLM_MODEL","")))
    buttons([{"label":t('save'),"value":"save_creds"},{"label":t('all_settings'),"value":"settings"},{"label":t('back'),"value":"back"}])

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
    msg(t('creds_saved'))
    key = _state.get("openrouter_key","")
    msg(f"- Git: `{_state.get('git_name','')}` <{_state.get('git_email','')}>")
    msg(f"- SSH: `{_state.get('github_key','')}`")
    msg(f"- API: `{mask(key) if key else t('no_key_short')}`")
    msg(f"- Model: `{_state.get('llm_model','')}`")
    buttons([{"label": t('launch_stacks_btn'),"value":"launch_all"},{"label": t('settings'),"value":"settings"},{"label": t('menu'),"value":"back"}])

def step_launch_all():
    _state["step"] = "launch_all"
    clear_widgets()
    msg(t('launching_stacks'))
    select("stacks", t('stacks_select_label'), [
        {"label": t('launch_option_all_full'),  "value": "all"},
        {"label": t('launch_option_management'),"value": "management"},
        {"label": t('launch_option_app'),       "value": "app"},
        {"label": t('launch_option_devices'),   "value": "devices"},
    ], _state.get("stacks", "all"))
    select("environment", t('environment_label'), [
        {"label": t('launch_env_local'),      "value": "local"},
        {"label": t('launch_env_production'), "value": "production"},
    ], _state.get("environment", "local"))
    buttons([
        {"label": t('run_btn'), "value": "do_launch"},
        {"label": t('back'),    "value": "back"},
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
        analysis.append(t('port_busy', port=port_num))
        solutions.append({"label":t('show_port_blocker', port=port_num),"value":f"diag_port::{port_num}"})
        if port_num == "6080" and name == "devices":
            solutions.append({"label":t('auto_vnc_port'),"value":"fix_vnc_port"})
        solutions.append({"label":t('change_port_retry'),"value":f"retry_launch"})

    if "Pool overlaps" in lines or "invalid pool request" in lines:
        import re
        net_m = re.search(r"failed to create network ([\w_-]+)", lines)
        net_name = net_m.group(1) if net_m else ""
        if net_name:
            analysis.append(t('network_conflict', net=net_name))
            solutions.append({"label": t('remove_network', net=net_name), "value": f"fix_network_overlap::{net_name}"})
        else:
            analysis.append(t('network_addr_conflict'))
            solutions.append({"label": t('clean_unused_networks'), "value": "fix_network_overlap::"})

    if "undefined network" in lines or "invalid compose project" in lines:
        import re
        net = re.search(r'"([^"]+)" refers to undefined network ([^:]+)', lines)
        srv = net.group(1) if net else "service"
        netname = net.group(2).strip() if net else "?"
        analysis.append(t('undefined_network', net=netname, stack=name, srv=srv))
        solutions.append({"label":t('auto_fix_compose'),"value":f"fix_compose::{name}"})

    if "variable is not set" in lines or "Defaulting to a blank string" in lines:
        missing = []
        for ln in lines.splitlines():
            if "variable is not set" in ln:
                import re; m = re.search(r'"([A-Z_]+)" variable is not set', ln)
                if m and m.group(1) not in missing: missing.append(m.group(1))
        if missing:
            analysis.append(t('missing_env_vars', vars='`, `'.join(missing[:6])))
            solutions.append({"label":t('configure_creds'),"value":"setup_creds"})
            solutions.append({"label":t('show_missing_vars'),"value":f"show_missing_env::{name}"})

    if "permission denied" in lines.lower():
        analysis.append(t('permission_error'))
        solutions.append({"label":t('fix_docker_perms'),"value":"fix_docker_perms"})

    _base_img = PROJECT["ssh_base_image"]
    if _base_img in lines and ("pull access denied" in lines or "failed to resolve source metadata" in lines):
        analysis.append(t('missing_ssh_base_image', image=_base_img))
        solutions.append({"label":t('build_ssh_base_retry'),"value":"retry_launch"})
    elif "pull access denied" in lines or ("not found" in lines and "image" in lines):
        analysis.append(t('cannot_pull_docker_image'))
        solutions.append({"label":t('retry'),"value":"retry_launch"})

    if not analysis:
        # Show last few lines so user can self-diagnose without clicking "Pokaż logi"
        tail = "\n".join(l for l in lines.splitlines()[-8:] if l.strip())
        analysis.append(t('stack_failed', name=name, tail=tail))
        solutions.append({"label":t('show_full_logs'),"value":f"logs_stack::{name}"})

    solutions.append({"label":t('retry'),"value":"retry_launch"})
    solutions.append({"label":t('skip_continue'),"value":"post_launch_creds"})
    solutions.append({"label":t('menu'),"value":"back"})
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
            msg(t('cloning_repo', url=app_repo_url))
            branch = _state.get("git_branch", "main") or "main"
            rc = subprocess.run(
                ["git", "clone", "--branch", branch, "--depth", "1", app_repo_url, str(app_dir)],
                capture_output=True, text=True)
            if rc.returncode != 0:
                msg(t('clone_error', err=rc.stderr[:1000]))
                buttons([{"label":t('change_git_url'),"value":"settings_group::Git"},
                         {"label":t('menu'),"value":"back"}])
                return
            msg(t('cloned_to', dir=app_dir))
            _refresh_ssh_roles()
        elif (app_dir / ".git").exists():
            progress(t('updating_app_pull'))
            subprocess.run(["git", "-C", str(app_dir), "pull", "--ff-only"],
                           capture_output=True)
            _refresh_ssh_roles()
    elif needs_app and not app_repo_url and not app_dir.exists():
        msg(t('app_no_folder'))
        buttons([{"label":t('set_git_url'),"value":"settings_group::Git"},
                 {"label":t('menu'),"value":"back"}])
        return

    # Re-discover stacks after potential clone (app/ may now exist)
    from dockfra.core import _discover_stacks as _ds
    _current_stacks = _ds()
    targets = [(name, _current_stacks[name]) for name in target_names if name in _current_stacks]
    if not targets:
        msg(t('no_stacks_available'))
        buttons([{"label":t('menu'),"value":"back"}])
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
                progress(t('building_ssh_base', image=PROJECT['ssh_base_image']))
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
                    msg(t('build_ssh_base_error', image=PROJECT['ssh_base_image']))
                    buttons([{"label":t('retry'),"value":"retry_launch"},
                             {"label":t('menu'),"value":"back"}])
                    return
                progress(PROJECT["ssh_base_image"], done=True)
            else:
                progress(t('cached_label', name=PROJECT['ssh_base_image']), done=True)

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
            msg(t('error_analysis'))
            for name, out in failed:
                analysis, solutions = _analyze_launch_error(name, out)
                msg(f"### Stack: `{name}`\n{analysis}")
                msg(t('what_to_do'))
                buttons(solutions)
                time.sleep(0.1)
        else:
            msg(t('all_stacks_ok'))

        # ── Post-launch health check ──────────────────────────────────────────
        # docker compose up -d exits 0 even if containers crash on startup.
        # Wait for containers to stabilise, then check their runtime status.
        progress(t('health_checking'))
        time.sleep(8)
        progress(t('health_checking'), done=True)
        all_containers = docker_ps()
        restarting = [c for c in all_containers
                      if "Restarting" in c["status"] or
                         ("Exit" in c["status"] and c["status"] != "Exited (0)")]
        if restarting:
            msg(t('containers_problems_post', n=len(restarting)))
            for c in restarting:
                finding, btns = _analyze_container_log(c["name"])
                msg(f"#### 🔴 `{c['name']}` — {c['status']}\n{finding}")
                if btns:
                    btns.insert(0, {"label": t('logs_for_container', name=c['name']), "value": f"logs::{c['name']}"})
                time.sleep(0.05)
            # Show single consolidated action bar for failing containers
            fix_btns = []
            for c in restarting:
                fix_btns.append({"label": t('fix_container', name=short_name(c['name'])), "value": f"fix_container::{c['name']}"})
            fix_btns += [
                {"label": t('retry'), "value": "retry_launch"},
                {"label": t('settings'),       "value": "settings"},
            ]
            buttons(fix_btns)
        else:
            msg(t('infra_ready'))
            running_names = {c["name"] for c in all_containers if "Up" in c["status"] or "healthy" in c["status"]}
            # Re-read roles at this point (state is fully loaded)
            _refresh_ssh_roles()
            # Show desktop/VNC info if running
            vnc_port = _state.get("desktop_vnc_port", _state.get("DESKTOP_VNC_PORT", "6081"))
            if cname("desktop") in running_names or cname("desktop-app") in running_names:
                msg(t('desktop_novnc', port=vnc_port))
            if _SSH_ROLES:
                msg(t('what_next'))
            # Config-driven post-launch buttons (dockfra.yaml + SSH roles + built-ins)
            _render_post_launch(running_names, _SSH_ROLES)
    threading.Thread(target=run,daemon=True).start()

def step_deploy_device():
    _state["step"] = "deploy_device"
    clear_widgets()
    msg(t('deploy_title'))
    sug = _detect_suggestions()
    # ── IP urządzenia — with ip_picker modal, chips from ARP/Docker, autodetect ──
    ip_sug = sug.get("DEVICE_IP", {})
    cur_ip = _state.get("device_ip", "") or ip_sug.get("value", "")
    text_input("device_ip", t('device_ip_label'), "192.168.1.100", cur_ip,
               hint=ip_sug.get("hint", ""), chips=ip_sug.get("chips", []),
               modal_type="ip_picker", autodetect=True)
    # ── Użytkownik SSH — with chips for common SBC users ─────────────────────
    user_sug = sug.get("DEVICE_USER", {})
    cur_user = _state.get("device_user", "") or user_sug.get("value", "pi")
    text_input("device_user", t('ssh_user_label'), "pi", cur_user,
               hint=user_sug.get("hint", ""), chips=user_sug.get("chips", []))
    # ── Port SSH — with chips for common ports ───────────────────────────────
    port_sug = sug.get("DEVICE_PORT", {})
    cur_port = str(_state.get("device_port", "") or port_sug.get("value", "22"))
    text_input("device_port", t('ssh_port_label'), "22", cur_port,
               hint=port_sug.get("hint", ""), chips=port_sug.get("chips", []))
    buttons([
        {"label":t('test_connection_btn'),"value":"test_device"},
        {"label":t('deploy_btn'),"value":"do_deploy"},
        {"label":t('back'),"value":"back"},
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
    if not ip: msg(t('provide_ip')); step_deploy_device(); return
    msg(t('testing_connection', target=f'{user}@{ip}:{port}'))
    def run():
        rc, out = run_cmd(["ssh","-i",key,"-p",str(port),"-o","ConnectTimeout=8",
                           "-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
                           f"{user}@{ip}","uname -a && echo DOCKFRA_OK"])
        if rc==0 and "DOCKFRA_OK" in out:
            msg(t('connection_works'))
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":t('deploy_now'),"value":"do_deploy"},{"label":t('change_btn'),"value":"deploy_device"}]})
        else:
            msg(t('no_connection', host=ip, port=port))
            pub = Path(key+".pub")
            if pub.exists():
                msg(t('add_key_to_device'))
                code_block(f"ssh-copy-id -i {key}.pub -p {port} {user}@{ip}")
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":t('retry'),"value":"test_device"},{"label":t('back'),"value":"deploy_device"}]})
    threading.Thread(target=run,daemon=True).start()

def step_do_deploy(form):
    _save_device_form(form); clear_widgets()
    ip, user, port = _state["device_ip"], _state["device_user"], _state["device_port"]
    key = _state.get("github_key", str(Path.home()/".ssh/id_ed25519"))
    if not ip: msg(t('provide_ip')); step_deploy_device(); return
    msg(t('deploy_to', target=f'{user}@{ip}:{port}'))
    def run():
        container = _get_role("developer")["container"]
        if container not in [c["name"] for c in docker_ps()]:
            msg(t('container_not_running', name=container))
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":t('launch_stacks_btn'),"value":"launch_all"},{"label":t('back'),"value":"back"}]}); return
        progress(t('copying_ssh_key'))
        kpath = Path(key).expanduser()
        if kpath.exists():
            subprocess.run(["docker","cp",str(kpath),f"{container}:/tmp/dk"],capture_output=True)
            subprocess.run(["docker","exec",container,"bash","-c",
                "mkdir -p /home/developer/.ssh && cp /tmp/dk /home/developer/.ssh/id_ed25519 && "
                "chmod 600 /home/developer/.ssh/id_ed25519 && rm /tmp/dk"],capture_output=True)
        progress(t('ssh_key_ready'),done=True)
        progress(t('testing_ssh_to', ip=ip))
        rc, out = run_cmd(["docker","exec",container,
            "ssh","-i","/home/developer/.ssh/id_ed25519","-p",str(port),
            "-o","ConnectTimeout=8","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
            f"{user}@{ip}","uname -a && echo DOCKFRA_DEPLOY_OK"])
        if rc!=0 or "DOCKFRA_DEPLOY_OK" not in out:
            progress(t('ssh_failed_to', ip=ip),error=True)
            msg(t('ssh_failed_from_container', ip=ip))
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":t('retry'),"value":"do_deploy"},{"label":t('back'),"value":"deploy_device"}]}); return
        progress(t('ssh_success_to', ip=ip),done=True)
        msg(t('ssh_success_route', ip=ip))
        # Save to devices/.env.local
        _update_device_env(ip, user, port)
        progress(t('device_saved_env'),done=True)
        msg(t('device_configured_target', ip=ip))
        msg(t('device_launch_hint'))
        socketio.emit("widget",{"type":"buttons","items":[
            {"label":t('launch_devices_stack'),"value":"launch_devices"}]})
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
    msg(t('launching_devices_stack'))
    def run():
        subprocess.run(["docker","network","create",PROJECT["network"]],capture_output=True)
        progress(t('launching_devices'))
        rc, _ = run_cmd(["docker","compose","up","-d","--build"],cwd=DEVS)
        progress("devices",done=(rc==0),error=(rc!=0))
        if rc==0:
            vnc_p = _state.get("VNC_RPI3_PORT", "6080")
            msg(t('devices_launched'))
            msg(t('vnc_url', port=vnc_p))
            msg(t('ssh_rpi3_hint', port=_state.get('SSH_RPI3_PORT','2224')))
        else:
            msg(t('launch_devices_error'))
    threading.Thread(target=run,daemon=True).start()

def step_post_launch_creds():
    clear_widgets()
    dev_role = _get_role("developer")
    container = dev_role["container"]
    if container not in [c["name"] for c in docker_ps()]:
        msg(t('container_not_running', name=container))
        buttons([{"label":t('launch_stacks_btn'),"value":"launch_all"},{"label":t('back'),"value":"back"}]); return
    msg(t('post_creds_title', user=dev_role['user']))
    key = _state.get("openrouter_key","")
    status_row([
        {"name":t('status_github_ssh_key'),"ok": Path(_state.get("github_key","~/.ssh/id_ed25519")).expanduser().exists(),"detail":_state.get("github_key","")},
        {"name":t('status_openrouter_key'),"ok": bool(key and key.startswith("sk-")),"detail":mask(key) if key else t('empty_short')},
    ])
    buttons([{"label":t('run_config'),"value":"run_post_creds"},
             {"label":t('change_creds'),"value":"setup_creds"},
             {"label":t('back'),"value":"back"}])

def step_run_post_creds():
    clear_widgets()
    msg(t('configuring_github_llm'))
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
        msg(t('config_done'))
    threading.Thread(target=run,daemon=True).start()

