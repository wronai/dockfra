"""Fix, repair, and diagnostic functions."""
from .core import *
from .i18n import t, set_lang, get_lang, llm_lang_instruction
from .steps import step_do_launch

def step_fix_container(name: str):
    """Interactive fix wizard for a failing container.
    1st attempt: algorithmic diagnosis + fix options.
    2nd+ attempt: auto-trigger LLM analysis.
    """
    clear_widgets()
    attempts = _state.setdefault("fix_attempts", {})
    attempts[name] = attempts.get(name, 0) + 1
    attempt = attempts[name]

    msg(t('fixing_container', name=name, n=attempt))

    # Get current container status
    containers = docker_ps()
    cinfo = next((c for c in containers if c["name"] == name), None)
    status_txt = cinfo["status"] if cinfo else "?"
    msg(t('status_label', status=status_txt))

    finding, btns = _analyze_container_log(name)

    if attempt >= 2:
        # Repeat failure → escalate to LLM immediately
        msg(t('repeat_attempt', n=attempt))
        msg(finding)
        _tl_sid = getattr(_tl, 'sid', None)
        def _fix_llm(n=name, f=finding):
            _tl.sid = _tl_sid
            try:
                out = subprocess.check_output(
                    ["docker", "logs", "--tail", "80", n],
                    text=True, stderr=subprocess.STDOUT)
            except Exception as e:
                out = f"(błąd pobierania logów: {e})"
            progress(t('ai_analyzing_problem'))
            prompt = (
                f"Kontener Docker `{n}` restartuje się i nie daje się naprawić.\n"
                f"To jest próba #{attempts.get(n,1)} naprawy.\n"
                f"Algorytmiczna diagnoza: {f}\n"
                f"Ostatnie logi:\n```\n{out[-3000:]}\n```\n"
                "Zaproponuj dokładne kroki naprawy. Jeśli problem jest konfiguracyjny, "
                "podaj co zmienić i w którym pliku."
            )
            reply = _llm_chat(prompt, system_prompt=_WIZARD_SYSTEM_PROMPT)
            progress("🧠 AI", done=True)
            msg(f"### 🧠 Analiza AI\n{reply}")
            fix_btns = [{"label": f"📋 Pełne logi: {n}", "value": f"logs::{n}"},
                        {"label": "🔄 Restart kontenera", "value": f"restart_container::{n}"},
                        {"label": "⚙️ Ustawienia", "value": "settings"}]
            buttons(fix_btns)
            _tl.sid = None
        threading.Thread(target=_fix_llm, daemon=True).start()
        return

    # 1st attempt: show algorithmic diagnosis + guided questions
    msg(finding)
    if btns:
        btns.insert(0, {"label": f"📋 Logi: {name}", "value": f"logs::{name}"})
    else:
        btns = [{"label": f"📋 Logi: {name}", "value": f"logs::{name}"}]

    # Add context-aware guided questions / quick fixes
    btns.append({"label": t('restart_container'),    "value": f"restart_container::{name}"})
    btns.append({"label": t('suggest_commands'),   "value": f"suggest_commands::{name}"})
    btns.append({"label": t('analyze_ai'),        "value": f"ai_analyze::{name}"})
    msg(t('what_to_do'))
    buttons(btns)


def _do_restart_container(name: str):
    clear_widgets()
    msg(f"🔄 Restartuję `{name}`...")
    def run():
        try:
            try:
                subprocess.check_output(["docker", "restart", name],
                                        text=True, stderr=subprocess.STDOUT)
            except Exception as shell_err:
                msg(f"⚠️ Shell nie zadziałał (`{shell_err}`), próbuję przez Docker SDK...")
                cli = _docker_client()
                if not cli:
                    raise RuntimeError("Docker SDK niedostępne") from shell_err
                cli.containers.get(name).restart()
            msg(f"✅ `{name}` zrestartowany — sprawdzam status za 5s...")
            time.sleep(5)
            containers = docker_ps()
            c = next((c for c in containers if c["name"] == name), None)
            if c:
                ok = "Up" in c["status"] and "Restarting" not in c["status"]
                icon = "✅" if ok else "🔴"
                msg(f"{icon} `{name}`: {c['status']}")
                if not ok:
                    msg("Kontener nadal nie działa. Spróbuj ponownie lub użyj AI.")
                    buttons([{"label": "🔧 Napraw ponownie", "value": f"fix_container::{name}"},
                             {"label": "🧠 Analizuj z AI",   "value": f"ai_analyze::{name}"}])
            else:
                msg(f"⚠️ `{name}` nie pojawił się na liście kontenerów.")
        except Exception as e:
            msg(f"❌ Błąd restartu: {e}")
            buttons([{"label": "🔧 Napraw ponownie", "value": f"fix_container::{name}"}])
    threading.Thread(target=run, daemon=True).start()


def _llm_suggest_commands(name: str, logs: str) -> dict:
    """Send log context to LLM and parse structured JSON with diagnosis + commands."""
    prompt = (
        f"Kontener Docker `{name}` ma problem. Ostatnie logi:\n"
        f"```\n{logs[-3000:]}\n```\n"
        "Przeanalizuj logi i zwróć JSON z diagnozą i komendami naprawczymi."
    )
    raw = _llm_chat(prompt, system_prompt=_CMD_SUGGEST_SYSTEM_PROMPT)
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except Exception:
        # Fallback: return raw text as diagnosis, no commands
        return {"diagnosis": raw[:500], "commands": []}


def step_suggest_commands(name: str):
    """Fetch logs, ask LLM for commands, render each with ▶️ Wykonaj button."""
    clear_widgets()
    msg(f"## 💡 Propozycje komend dla `{name}`")
    _tl_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _tl_sid
        if not _LLM_AVAILABLE or not _llm_config().get("api_key"):
            _prompt_api_key(return_action=f"suggest_commands::{name}")
            _tl.sid = None; return
        try:
            logs = subprocess.check_output(
                ["docker", "logs", "--tail", "80", name],
                text=True, stderr=subprocess.STDOUT)
        except Exception as e:
            msg(t('cannot_get_logs', err=e)); return
        progress(t('ai_analyzing_problem'))
        result = _llm_suggest_commands(name, logs)
        progress("🧠 AI", done=True)
        diagnosis = result.get("diagnosis", "")
        commands  = result.get("commands", [])
        if diagnosis:
            msg(f"**Diagnoza:** {diagnosis}")
        if not commands:
            msg(t('no_commands'))
            buttons([{"label": t('full_ai_analysis'), "value": f"ai_analyze::{name}"}])
            return
        msg(f"### Proponowane komendy ({len(commands)}):")
        btn_items = []
        for i, c in enumerate(commands):
            cmd  = c.get("cmd", "")
            desc = c.get("description", "")
            safe = c.get("safe", False)
            if not cmd:
                continue
            code_block(f"# {desc}\n{cmd}")
            if safe:
                btn_items.append({
                    "label": f"▶️ {desc[:40]}",
                    "value": f"run_suggested_cmd::{cmd}"
                })
            else:
                btn_items.append({
                    "label": f"⚠️ {desc[:35]} (niezabezp.)",
                    "value": f"run_suggested_cmd::{cmd}"
                })
        if btn_items:
            buttons(btn_items)
        _tl.sid = None
    threading.Thread(target=run, daemon=True).start()


def _sdk_fallback_cmd(cmd: str) -> str:
    """Try to execute a docker command via the Python SDK. Returns output string."""
    import re
    cli = _docker_client()
    if not cli:
        raise RuntimeError("Docker SDK niedostępne")
    tokens = cmd.split()
    # docker logs [--tail N] <name>
    if tokens[:2] == ["docker", "logs"]:
        tail = 50
        for i, t in enumerate(tokens):
            if t == "--tail" and i + 1 < len(tokens):
                try: tail = int(tokens[i + 1])
                except ValueError: pass
        cname = tokens[-1]
        raw = cli.containers.get(cname).logs(tail=tail, timestamps=False)
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    # docker inspect <name>
    if tokens[:2] == ["docker", "inspect"]:
        cname = tokens[-1]
        return json.dumps(cli.containers.get(cname).attrs, indent=2)[:4000]
    # docker restart <name>
    if tokens[:2] == ["docker", "restart"]:
        cname = tokens[-1]
        cli.containers.get(cname).restart()
        return f"Kontener `{cname}` zrestartowany przez SDK."
    # docker stop <name>
    if tokens[:2] == ["docker", "stop"]:
        cname = tokens[-1]
        cli.containers.get(cname).stop()
        return f"Kontener `{cname}` zatrzymany przez SDK."
    # docker start <name>
    if tokens[:2] == ["docker", "start"]:
        cname = tokens[-1]
        cli.containers.get(cname).start()
        return f"Kontener `{cname}` uruchomiony przez SDK."
    # docker ps
    if tokens[:2] == ["docker", "ps"]:
        rows = cli.containers.list(all="-a" in tokens)
        return "\n".join(f"{c.name}  {c.status}" for c in rows)
    raise RuntimeError(f"Brak mapowania SDK dla: `{cmd}`")


def _run_suggested_cmd(cmd: str):
    """Execute a command proposed by LLM. Only docker/* and safe system commands allowed."""
    SAFE_PREFIXES = ("docker ", "docker-compose ", "docker compose ")
    if not any(cmd.lstrip().startswith(p) for p in SAFE_PREFIXES):
        msg(f"⛔ Komenda `{cmd}` nie jest dozwolona (tylko docker/*)")
        return
    clear_widgets()
    msg(f"▶️ Wykonuję: `{cmd}`")
    _tl_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _tl_sid
        try:
            out = subprocess.check_output(
                cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=30)
            code_block(out.strip() or "(brak wyjścia)")
            msg("✅ Komenda wykonana.")
        except subprocess.TimeoutExpired:
            msg("⏱️ Timeout — komenda trwała za długo.")
        except subprocess.CalledProcessError as e:
            output = e.output.strip() if e.output else ""
            code_block(output or str(e))
            msg(f"⚠️ Shell zakończył się kodem {e.returncode} — próbuję przez Docker SDK...")
            try:
                sdk_out = _sdk_fallback_cmd(cmd)
                code_block(sdk_out.strip() or "(brak wyjścia)")
                msg("✅ Wykonano przez Docker SDK.")
            except Exception as sdk_err:
                msg(f"❌ SDK też nie zadziałał: {sdk_err}")
        except Exception as e:
            msg(f"⚠️ Shell niedostępny — próbuję przez Docker SDK...")
            try:
                sdk_out = _sdk_fallback_cmd(cmd)
                code_block(sdk_out.strip() or "(brak wyjścia)")
                msg("✅ Wykonano przez Docker SDK.")
            except Exception as sdk_err:
                msg(f"❌ SDK też nie zadziałał: {sdk_err}")
        _tl.sid = None
    threading.Thread(target=run, daemon=True).start()


# ── router ────────────────────────────────────────────────────────────────────
def diag_port(port_num: str):
    clear_widgets()
    msg(f"🔍 Sprawdzam co blokuje port `{port_num}`...")
    def run():
        try:
            out = subprocess.check_output(
                ["bash","-c",f"lsof -i :{port_num} 2>/dev/null || ss -tlnp | grep :{port_num} || echo '(brak wyniku)'"],
                text=True, stderr=subprocess.STDOUT)
            code_block(out.strip() or "(nic nie znaleziono)")
        except Exception as e:
            msg(f"❌ {e}")
        msg(f"Możesz zmienić port w `devices/docker-compose.yml` lub zatrzymać konfliktujący proces.")
        buttons([
            {"label":t('retry'),"value":"retry_launch"},
            {"label":t('menu'),"value":"back"},
        ])
    threading.Thread(target=run,daemon=True).start()


def show_missing_env(stack_name: str):
    """Show inline input form for missing required vars in the given stack."""
    clear_widgets()
    msg(f"## ⚠️ Brakujące zmienne — `{stack_name}`")
    stacks_to_check = [stack_name] if stack_name != "all" else ["management", "app", "devices"]
    missing = preflight_check(stacks_to_check)
    if missing:
        msg(f"Uzupełnij brakujące zmienne dla stacku `{stack_name}`:")
        suggestions = _detect_suggestions()
        for e in missing:
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
                           hint=sug.get("hint", ""), chips=sug.get("chips", []),
                           modal_type="ip_picker" if e["key"] == "DEVICE_IP" else "",
                           desc=e.get("desc", ""), autodetect=e.get("autodetect", False))
        buttons([
            {"label": t('save_and_run'),  "value": f"preflight_save_launch::{stack_name}"},
            {"label": t('full_settings'),   "value": "settings"},
        ])
    else:
        env_file = STACKS.get(stack_name, ROOT / stack_name) / ".env"
        if env_file.exists():
            msg("Nie znaleziono brakujących znanych zmiennych. Zawartość pliku `.env`:")
            code_block(env_file.read_text())
        else:
            msg(f"Brak pliku `.env` w `{stack_name}/`")
        buttons([
            {"label": t('configure_creds'), "value": "setup_creds"},
            {"label": t('retry'),         "value": "retry_launch"},
        ])


def validate_llm_connection() -> tuple[bool, str]:
    """Test LLM key by making a minimal API call. Returns (ok, message)."""
    key = (_state.get("openrouter_key", "") or _state.get("openrouter_api_key", "")
           or os.environ.get("OPENROUTER_API_KEY", ""))
    if not key:
        return False, t('no_key')
    if key: os.environ["OPENROUTER_API_KEY"] = key
    if not _LLM_AVAILABLE:
        return False, t('llm_module_unavailable')
    try:
        import urllib.request, urllib.error
        payload = json.dumps({
            "model": _state.get("llm_model", "") or "google/gemini-flash-1.5",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, t('connection_ok_short')
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, t('invalid_key_401')
        if e.code == 402:
            return False, t('no_funds_402')
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"error: {e}"


def validate_docker() -> tuple[bool, str]:
    """Check if Docker daemon is running. Returns (ok, message)."""
    try:
        out = subprocess.check_output(["docker", "info", "--format", "{{.ServerVersion}}"],
                                      text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
        return True, f"Docker {out}"
    except FileNotFoundError:
        return False, t('docker_not_installed')
    except subprocess.CalledProcessError:
        return False, t('docker_not_running')
    except subprocess.TimeoutExpired:
        return False, t('docker_timeout')
    except Exception as e:
        return False, f"error: {e}"


def _ensure_llm_key(return_action: str = "") -> tuple[bool, str]:
    """Validate LLM key exists and works. If not, prompt user inline.

    Returns (ok, key). When ok=False, an inline prompt has been emitted
    and the caller should return/abort the current operation.
    """
    key = (_state.get("openrouter_key", "") or _state.get("openrouter_api_key", "")
           or _state.get("developer_llm_api_key", "") or os.environ.get("OPENROUTER_API_KEY", ""))
    if not key:
        _prompt_api_key(return_action=return_action, reason="brak klucza API")
        return False, ""
    # Validate key actually works
    ok, reason = validate_llm_connection()
    if not ok:
        _prompt_api_key(return_action=return_action, reason=reason)
        return False, ""
    return True, key


def _prompt_api_key(return_action: str = "", reason: str = ""):
    """Show inline form to enter OPENROUTER_API_KEY when LLM is unavailable."""
    if reason:
        msg(t('llm_unavailable', reason=reason))
    else:
        msg(t('missing_api_key'))
    text_input("OPENROUTER_API_KEY", "OpenRouter API Key",
               "sk-or-v1-...", _state.get("openrouter_key", ""), sec=True,
               help_url="https://openrouter.ai/keys")
    # Combo: select popular models OR type custom model ID
    cur_model = _state.get("llm_model", _schema_defaults().get("LLM_MODEL", ""))
    opts = [{"label": lbl, "value": val}
            for val, lbl in next(e["options"] for e in ENV_SCHEMA if e["key"] == "LLM_MODEL")]
    opts.append({"label": t('type_manually'), "value": "__custom__"})
    select("LLM_MODEL", "Model LLM", opts, cur_model)
    text_input("LLM_MODEL_CUSTOM", "Model (ręcznie)",
               "np. google/gemini-3-flash-preview", cur_model if cur_model and not any(o["value"] == cur_model for o in opts[:-1]) else "",
               hint="Wpisz pełny identyfikator modelu z openrouter.ai/models")
    # Buttons: test first, then save
    btn_items = [
        {"label": t('test_connection'), "value": f"test_llm_key::{return_action}"},
        {"label": t('save_continue'), "value": "save_creds"},
    ]
    if return_action:
        btn_items.append({"label": t('repeat_action'), "value": return_action})
    buttons(btn_items)


def fix_network_overlap(net_name: str = ""):
    """Remove a conflicting Docker network (or prune all unused), then retry launch."""
    clear_widgets()
    _tl_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _tl_sid
        if net_name:
            msg(f"🔧 Usuwam sieć `{net_name}`...")
            try:
                out = subprocess.check_output(
                    ["docker", "network", "rm", net_name],
                    text=True, stderr=subprocess.STDOUT)
                msg(f"✅ Sieć `{net_name}` usunięta.")
            except subprocess.CalledProcessError as e:
                err = e.output.strip() if e.output else str(e)
                # Fallback: SDK
                msg(f"⚠️ Shell nie zadziałał — próbuję przez SDK...")
                cli = _docker_client()
                if cli:
                    try:
                        cli.networks.get(net_name).remove()
                        msg(f"✅ Sieć `{net_name}` usunięta przez SDK.")
                    except Exception as sdk_err:
                        msg(f"❌ Nie można usunąć sieci: {sdk_err}")
                        buttons([{"label": t('retry'), "value": "retry_launch"}])
                        return
                else:
                    msg(f"❌ {err}")
                    buttons([{"label": t('retry'), "value": "retry_launch"}])
                    return
        else:
            msg("🔧 Czyszczę nieużywane sieci Docker (`docker network prune`)...")
            try:
                out = subprocess.check_output(
                    ["docker", "network", "prune", "-f"],
                    text=True, stderr=subprocess.STDOUT)
                msg(f"✅ Sieci wyczyszczone:\n```\n{out.strip()}\n```")
            except Exception as e:
                msg(f"❌ Błąd: {e}")
                buttons([{"label": "🔄 Spróbuj ponownie", "value": "retry_launch"}])
                return
        msg("🚀 Ponawiam uruchamianie stacków...")
        retry_launch()
        _tl.sid = None
    threading.Thread(target=run, daemon=True).start()


def retry_launch(form=None):
    step_do_launch({"stacks": _state.get("stacks","all"), "environment": _state.get("environment","local")})


def fix_vnc_port():
    clear_widgets()
    env_file = DEVS / ".env"
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    lines = [l for l in lines if not l.startswith("VNC_RPI3_PORT=")]
    lines.append("VNC_RPI3_PORT=6082")
    env_file.write_text("\n".join(lines) + "\n")
    msg("✅ Ustawiono `VNC_RPI3_PORT=6082` w `devices/.env`")
    msg("VNC dla RPi3 będzie dostępny pod: **http://localhost:6082**")
    retry_launch()


def fix_acme_storage():
    """Auto-configure ACME_STORAGE: create letsencrypt dir, write to app/.env, restart traefik."""
    clear_widgets()
    msg("## 🔧 Naprawiam konfigurację ACME / Let's Encrypt")
    acme_path = APP / "letsencrypt"
    acme_json  = acme_path / "acme.json"
    try:
        acme_path.mkdir(parents=True, exist_ok=True)
        if not acme_json.exists():
            acme_json.write_text("{}\n")
        acme_json.chmod(0o600)
        msg(f"✅ Katalog `{acme_path}` gotowy, `acme.json` z uprawnieniami 600.")
    except Exception as e:
        msg(f"⚠️ Nie można utworzyć katalogu: {e}")

    # Write ACME_STORAGE to app/.env
    acme_value = "letsencrypt/acme.json"
    env_file = APP / ".env"
    try:
        lines = env_file.read_text().splitlines() if env_file.exists() else []
        lines = [l for l in lines if not l.startswith("ACME_STORAGE=")]
        lines.append(f"ACME_STORAGE={acme_value}")
        env_file.write_text("\n".join(lines) + "\n")
        msg(f"✅ Zapisano `ACME_STORAGE={acme_value}` do `app/.env`")
    except Exception as e:
        msg(f"⚠️ Nie można zapisać do app/.env: {e}")

    # Also persist to dockfra/.env and _state
    _state["acme_storage"] = acme_value
    save_env({"ACME_STORAGE": acme_value})

    _traefik = cname("traefik")
    msg(f"🔄 Restartuję `{_traefik}`...")
    _tl_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _tl_sid
        try:
            subprocess.check_output(["docker", "restart", _traefik],
                                    text=True, stderr=subprocess.STDOUT)
            msg(f"✅ `{_traefik}` zrestartowany.")
        except Exception as shell_err:
            cli = _docker_client()
            if cli:
                try:
                    cli.containers.get(_traefik).restart()
                    msg(f"✅ `{_traefik}` zrestartowany przez SDK.")
                except Exception as sdk_err:
                    msg(f"⚠️ Restart nie powiódł się: {sdk_err}")
            else:
                msg(f"⚠️ {shell_err}")
        time.sleep(5)
        all_c = docker_ps()
        c = next((c for c in all_c if c["name"] == _traefik), None)
        if c:
            ok = "Up" in c["status"] and "Restarting" not in c["status"]
            icon = "✅" if ok else "🔴"
            msg(f"{icon} `{_traefik}`: {c['status']}")
        buttons([{"label": "🔄 Uruchom wszystko", "value": "retry_launch"},
                 {"label": "⚙️ Ustawienia",      "value": "settings"}])
        _tl.sid = None
    threading.Thread(target=run, daemon=True).start()


def fix_readonly_volume(container: str = ""):
    """Find read-only volume mounts for a container and fix host directory permissions."""
    clear_widgets()
    target = container or cname("ssh-developer")
    msg(f"## 🔧 Naprawiam uprawnienia woluminów — `{target}`")
    _tl_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _tl_sid
        # Get mount info via docker inspect
        try:
            raw = subprocess.check_output(
                ["docker", "inspect", "--format",
                 "{{range .Mounts}}{{.Source}}:{{.Destination}}:{{.RW}}\n{{end}}", target],
                text=True, stderr=subprocess.STDOUT).strip()
        except Exception:
            cli = _docker_client()
            if not cli:
                msg("❌ Nie można pobrać informacji o montowaniach."); return
            try:
                attrs = cli.containers.get(target).attrs
                mounts = attrs.get("Mounts", [])
                raw = "\n".join(f"{m.get('Source','')}:{m.get('Destination','')}:{m.get('RW','')}" for m in mounts)
            except Exception as e:
                msg(f"❌ {e}"); return

        fixed = []
        for line in raw.splitlines():
            parts = line.strip().split(":")
            if len(parts) < 2:
                continue
            src, dst = parts[0], parts[1]
            rw  = parts[2] if len(parts) > 2 else "true"
            if not src or not dst:
                continue
            from pathlib import Path as _P
            src_path = _P(src)
            if not src_path.exists():
                continue
            try:
                src_path.chmod(0o755)
                fixed.append(f"`{src}` → `{dst}` (chmod 755)")
            except PermissionError:
                try:
                    subprocess.check_output(["sudo","chmod","-R","755",src], text=True, stderr=subprocess.STDOUT)
                    fixed.append(f"`{src}` → `{dst}` (sudo chmod 755)")
                except Exception as pe:
                    msg(f"⚠️ Brak uprawnień do `{src}`: {pe}")

        if fixed:
            msg("✅ Naprawiono uprawnienia:\n" + "\n".join(f"- {f}" for f in fixed))
        else:
            msg("⚠️ Nie znaleziono montowań do naprawy. Sprawdź czy kontener używa bind-mount.")
            code_block(raw or "(brak montowań)")

        msg(f"🔄 Restartuję `{cname}`...")
        try:
            subprocess.check_output(["docker","restart",cname], text=True, stderr=subprocess.STDOUT)
            msg(f"✅ `{cname}` zrestartowany.")
        except Exception as e:
            msg(f"⚠️ Restart: {e}")
        buttons([{"label": f"🔧 Napraw {cname}", "value": f"fix_container::{cname}"},
                 {"label": "🔄 Uruchom wszystko", "value": "retry_launch"}])
        _tl.sid = None
    threading.Thread(target=run, daemon=True).start()


def fix_docker_perms():
    clear_widgets()
    msg(t('docker_perms_title'))
    msg("Uruchom poniższe komendy na hoście, a następnie wyloguj się i zaloguj ponownie:")
    code_block("sudo usermod -aG docker $USER\nnewgrp docker")
    msg("Lub jeśli jesteś rootem, ustaw socket:")
    code_block("sudo chmod 666 /var/run/docker.sock")
    buttons([{"label":t('retry'),"value":"retry_launch"},{"label":t('menu'),"value":"back"}])

