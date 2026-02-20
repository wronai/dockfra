"""Dynamic SSH role & command discovery from Makefiles, motd, scripts."""
from .core import *

# ══════════════════════════════════════════════════════════════════════════════
# Dynamic SSH role / command discovery — parses Makefiles, motd, scripts dirs
# so that adding scripts or Makefile targets automatically updates the wizard.
# ══════════════════════════════════════════════════════════════════════════════

_SKIP_MAKE_TARGETS = frozenset({"help", "logs", "shell", ".PHONY", ".DEFAULT_GOAL"})
_MAKE_SKIP_VARS    = frozenset({
    "EXEC", "SSH", "MAKE", "CONTAINER", "USER", "SSH_PORT", "APP", "MGMT",
    "ROOT", "MAKEFILE_LIST", "SHELL", "DEFAULT_GOAL",
})
_PARAM_HINTS = {
    "T":       ("Ticket ID",       "T-0001"),
    "Q":       ("Pytanie",         "Jak naprawić X?"),
    "F":       ("Plik / opis",     "src/main.py"),
    "MSG":     ("Wiadomość",       "feat: add feature"),
    "TITLE":   ("Tytuł",           "Fix login bug"),
    "FEATURE": ("Opis funkcji",    "user authentication"),
    "SVC":     ("Nazwa serwisu",   "developer"),
    "TARGET":  ("Cel",             "developer"),
    "ARTIFACT":("Ścieżka artefaktu", "/artifacts/app.tar.gz"),
}
_PARAM_OPTIONS_API = {
    "T":      "/api/ssh-options/tickets",
    "F":      "/api/ssh-options/files/{role}",
    "SVC":    "/api/ssh-options/containers",
    "TARGET": "/api/ssh-options/containers",
}
_FALLBACK_ICONS = {"developer": "🔧", "manager": "👤", "monitor": "📡", "autopilot": "🤖"}
_FALLBACK_PORTS = {"developer": "2200", "manager": "2202", "monitor": "2201", "autopilot": "2203"}


def _parse_ssh_makefile(path: Path):
    """Parse an ssh-* Makefile. Returns (container, user, port, targets_dict)."""
    if not path.exists():
        return None, None, None, {}
    text = path.read_text(errors="replace")
    container = user = port = None
    for m in _re.finditer(r'^(\w+)\s*\?=\s*(.+)', text, _re.MULTILINE):
        k, v = m.group(1), m.group(2).strip()
        if k == "CONTAINER": container = v
        elif k == "USER":    user = v
        elif k == "SSH_PORT": port = v

    targets = {}
    for m in _re.finditer(r'^([\w][\w-]*)\s*:[^#\n]*##\s*(.+)$', text, _re.MULTILINE):
        name, desc = m.group(1), m.group(2).strip()
        if name in _SKIP_MAKE_TARGETS or name.isupper():
            continue
        body_start = m.end()
        body_lines = []
        for line in text[body_start:].splitlines():
            if line.startswith('\t') or (line.startswith('    ') and not _re.match(r'^\S', line)):
                body_lines.append(line)
            elif line.strip() == "":
                continue
            else:
                break
        body = "\n".join(body_lines)
        params = [p for p in _re.findall(r'\$\((\w+)\)', body) if p not in _MAKE_SKIP_VARS]
        params = list(dict.fromkeys(params))
        tty = bool(_re.search(r'docker exec -it|\$\(SSH\)|\$\{SSH\}', body))
        targets[name] = {"desc": desc, "params": params, "tty": tty}
    return container, user, port, targets


def _parse_ssh_motd(path: Path, role: str):
    """Parse a motd file for icon and title."""
    icon  = _FALLBACK_ICONS.get(role, "🖥️")
    title = role.capitalize()
    if not path.exists():
        return icon, title
    text = path.read_text(errors="replace")
    m = _re.search(r'║\s*(\S+)\s+\w+\s*[—–-]\s*(.+?)\s*║', text)
    if m:
        icon  = m.group(1)
        title = f"{role.capitalize()} — {m.group(2).strip()}"
    return icon, title


def _discover_extra_scripts(ssh_dir: Path, known_targets: set):
    """Find .sh scripts not already covered by Makefile targets."""
    extra = {}
    for sub in ("scripts",):
        sd = ssh_dir / sub
        if not sd.is_dir():
            continue
        for f in sorted(sd.glob("*.sh")):
            name = f.stem
            if name in known_targets:
                continue
            extra[name] = {"desc": name.replace("-", " ").replace("_", " ").title(), "params": []}
    return extra


def _discover_ssh_roles():
    """Scan app/ and management/ for ssh-* dirs, parse Makefiles + motd + scripts.
    Returns unified dict: role → {container, user, port, icon, title, makefile, targets, commands}
    """
    roles = {}

    # ── Virtual developer role when app/ not yet cloned ──────────────────────
    # Show the developer role in the wizard even before app/ exists,
    # so the user can trigger clone+launch from the UI.
    if not APP.is_dir() and _state.get("git_repo_url"):
        roles["developer"] = {
            "container": cname("ssh-developer"), "user": "developer",
            "port": _state.get("ssh_developer_port", "2200"),
            "icon": "🔧", "title": "Developer — SSH Workspace",
            "makefile": "", "commands": [], "cmd_meta": {},
            "virtual": True,  # flag: app/ not cloned yet
        }

    for parent in (APP, MGMT):
        if not parent.is_dir():
            continue
        for d in sorted(parent.iterdir()):
            if not d.is_dir() or not d.name.startswith("ssh-"):
                continue
            role = d.name[4:]  # "ssh-developer" → "developer"
            makefile = d / "Makefile"
            motd     = d / "motd"

            container, user, port, targets = _parse_ssh_makefile(makefile)
            icon, title                    = _parse_ssh_motd(motd, role)
            container = container or cname(f"ssh-{role}")
            user      = user or role
            port      = port or _FALLBACK_PORTS.get(role, "2222")

            extra = _discover_extra_scripts(d, set(targets))
            targets.update(extra)

            mk_rel = str(makefile.relative_to(ROOT)) if makefile.exists() else ""

            # Build commands list: (ssh_col, desc, make_col)
            commands = []
            for cmd, info in targets.items():
                params = info["params"]
                if params:
                    param_display = " ".join(f"<{p}>" for p in params)
                    ssh_col = f"`{cmd} {param_display}`"
                    param_example = " ".join(f"{p}={_PARAM_HINTS.get(p,('',''))[1] or p}" for p in params)
                    make_col = f"`make -f {mk_rel} {cmd} {param_example}`" if mk_rel else ""
                else:
                    ssh_col  = f"`{cmd}`"
                    make_col = f"`make -f {mk_rel} {cmd}`" if mk_rel else ""
                commands.append((ssh_col, info["desc"], make_col))

            # Build cmd_meta: cmd → (label, [params], hint, placeholder, tty)
            cmd_meta = {}
            for cmd, info in targets.items():
                params = info["params"]
                hint, placeholder = "", ""
                if params:
                    hint, placeholder = _PARAM_HINTS.get(params[0], (params[0], ""))
                cmd_meta[cmd] = (info["desc"], params, hint, placeholder, info.get("tty", False))

            roles[role] = {
                "container": container, "user": user, "port": port,
                "icon": icon, "title": title, "makefile": mk_rel,
                "commands": commands, "cmd_meta": cmd_meta,
            }
    return roles

# Cache: rebuilt once at import, call _refresh_ssh_roles() to reload
_SSH_ROLES = _discover_ssh_roles()

def _refresh_ssh_roles():
    """Re-scan the filesystem and update the cached role data."""
    global _SSH_ROLES
    _SSH_ROLES = _discover_ssh_roles()

def _get_role(role: str):
    """Get role data, falling back to a minimal stub."""
    if role in _SSH_ROLES:
        return _SSH_ROLES[role]
    # Virtual developer: app/ not cloned yet but GIT_REPO_URL is set
    if role == "developer" and not APP.is_dir() and _state.get("git_repo_url"):
        return {
            "container": cname("ssh-developer"), "user": "developer",
            "port": _state.get("ssh_developer_port", "2200"),
            "icon": "🔧", "title": "Developer — SSH Workspace",
            "makefile": "", "commands": [], "cmd_meta": {},
            "virtual": True,
        }
    return {
        "container": cname(f"ssh-{role}"), "user": role,
        "port": _FALLBACK_PORTS.get(role, "2222"),
        "icon": _FALLBACK_ICONS.get(role, "🖥️"),
        "title": role.capitalize(), "makefile": "",
        "commands": [], "cmd_meta": {},
    }


def _step_ssh_info(value: str):
    """Handle ssh_info::role::port button — show action grid for role commands."""
    parts = value.split("::")
    role = parts[1] if len(parts) > 1 else "developer"
    port = parts[2] if len(parts) > 2 else "2200"
    info = _get_role(role)

    # ── Virtual developer: app/ not cloned yet — offer clone+launch ──────────
    if info.get("virtual"):
        clear_widgets()
        repo_url = _state.get("git_repo_url", "")
        branch   = _state.get("git_branch", "main") or "main"
        msg(
            f"## 🔧 Developer — SSH Workspace\n\n"
            f"Repozytorium aplikacji nie jest jeszcze sklonowane lokalnie.\n\n"
            f"**Repo:** `{repo_url}`  •  **Branch:** `{branch}`\n\n"
            f"[[📥 Sklonuj i uruchom app|clone_and_launch_app]]  "
            f"[[⚙️ Zmień GIT_REPO_URL|settings_group::Git]]  "
            f"[[🏠 Menu|back]]"
        )
        return

    if not info["cmd_meta"]:
        msg(f"❓ Nieznana rola lub brak komend: `{role}`")
        return
    clear_widgets()
    ssh_cmd = f"ssh {info['user']}@localhost -p {port}"
    msg(f"## {info['icon']} {info['title']}\n`{ssh_cmd}`")

    cmds_data = []
    for cmd, meta in info["cmd_meta"].items():
        desc, params, hint, placeholder, tty = meta if len(meta) == 5 else (*meta, False)
        options_endpoint = None
        if not tty and params:
            tmpl = _PARAM_OPTIONS_API.get(params[0])
            if tmpl:
                options_endpoint = tmpl.format(role=role)
        cmds_data.append({
            "cmd": cmd, "desc": desc,
            "params": params, "hint": hint, "placeholder": placeholder,
            "options_endpoint": options_endpoint,
            "tty": tty,
        })
    run_value = f"run_ssh_cmd::{role}::{info['container']}::{info['user']}"
    action_grid(run_value, cmds_data)

    role_btns = []
    for r, ri in sorted(_SSH_ROLES.items()):
        p = _state.get(f"SSH_{r.upper()}_PORT", ri["port"])
        role_btns.append({"label": f"{ri['icon']} SSH {r.capitalize()}", "value": f"ssh_info::{r}::{p}"})
    role_btns.append({"label": "🏠 Menu", "value": "back"})
    buttons(role_btns)


def step_ssh_console(value: str):
    """Alias — redirect to action grid view."""
    parts = value.split("::")
    role  = parts[1] if len(parts) > 1 else "developer"
    port  = parts[2] if len(parts) > 2 else "2200"
    _step_ssh_info(f"ssh_info::{role}::{port}")


def run_ssh_cmd(value: str, form: dict):
    """Execute selected command via docker exec and stream output to chat."""
    parts     = value.split("::")
    role      = parts[1] if len(parts) > 1 else "developer"
    container = parts[2] if len(parts) > 2 else cname("ssh-developer")
    user      = parts[3] if len(parts) > 3 else "developer"
    cmd_name  = (form.get("ssh_cmd") or "").strip()
    arg       = (form.get("ssh_arg") or "").strip()

    if not cmd_name:
        msg("❌ Wybierz komendę."); return

    ri     = _get_role(role)
    meta   = ri["cmd_meta"].get(cmd_name)
    if not meta:
        msg(f"❌ Nieznana komenda: `{cmd_name}`"); return

    desc, params, hint, placeholder = meta[:4]
    tty = meta[4] if len(meta) > 4 else False

    # Build shell argument string
    if params and arg:
        needs_quote = params[0] in ("Q", "TITLE", "MSG", "F", "FEATURE")
        shell_arg   = f'"{arg}"' if needs_quote else arg
        cmd_str = f"{cmd_name} {shell_arg}"
    else:
        cmd_str = cmd_name

    msg(f"▶️ Uruchamiam: `{cmd_str}`")
    _tl_sid = getattr(_tl, 'sid', None)

    def _run():
        _tl.sid = _tl_sid
        try:
            if tty:
                # TTY command (docker exec -it / SSH): run docker exec directly from host
                # Parse the container name from the Makefile body pattern exec-<svc>
                svc_map = {
                    "exec-backend":  (cname("backend"),        ["bash", "-c", "echo '=== /app ===' && ls /app 2>/dev/null && echo && echo '=== processes ===' && ps aux 2>/dev/null | head -6"]),
                    "exec-frontend": (cname("frontend"),       ["sh", "-c", "echo '=== /usr/share/nginx/html ===' && ls /usr/share/nginx/html 2>/dev/null | head -20"]),
                    "exec-mobile":   (cname("mobile-backend"), ["bash", "-c", "echo '=== /app ===' && ls /app 2>/dev/null && echo && ps aux 2>/dev/null | head -6"]),
                    "exec-db":       (cname("db"),             ["psql", "-U", "postgres", "-c", "\\l"]),
                    "exec-redis":    (cname("redis"),          ["redis-cli", "ping"]),
                }
                if cmd_name in svc_map:
                    tgt_container, tgt_cmd = svc_map[cmd_name]
                    rc, out = run_cmd(["docker", "exec", tgt_container] + tgt_cmd)
                    if rc == 0:
                        msg(f"✅ `{cmd_name}` — wynik:\n```\n{out[:2000]}\n```")
                    else:
                        msg(f"⚠️ `{cmd_name}` — kontener `{tgt_container}` niedostępny lub błąd (kod {rc}).")
                else:
                    ssh_port = _state.get(f"SSH_{role.upper()}_PORT", ri["port"])
                    msg(f"🖥️ `{cmd_name}` wymaga terminala TTY.\n"
                        f"Otwórz terminal i wpisz:\n```\nssh {user}@localhost -p {ssh_port}\n```\n"
                        f"Następnie uruchom: `{cmd_str}`")
                    rc = 0
            else:
                # Try direct script path first (works without .bash_profile / extensionless symlinks),
                # fall back to sourcing .bashrc (works after container rebuild with new ssh-base-init.sh)
                script = f"/home/{user}/scripts/{cmd_name}.sh"
                if params and arg:
                    needs_quote = params[0] in ("Q", "TITLE", "MSG", "F", "FEATURE")
                    _sa = f'"{arg}"' if needs_quote else arg
                    inner = f"'{script}' {_sa}"
                else:
                    inner = f"'{script}'"
                shell = (
                    f"if [ -x '{script}' ]; then {inner}; "
                    f"else source ~/.bashrc 2>/dev/null; {cmd_str}; fi"
                )
                rc, out = run_cmd(
                    ["docker", "exec", "-u", user, container, "bash", "-lc", shell],
                )
            if not tty:
                if rc == 0:
                    msg(f"✅ `{cmd_str}` — zakończono.")
                else:
                    msg(f"⚠️ `{cmd_str}` zakończyło się z kodem {rc}.")
        except Exception as e:
            msg(f"❌ Błąd: {e}")
        port = _state.get(f"SSH_{role.upper()}_PORT", _get_role(role)["port"])
        buttons([
            {"label": f"{_get_role(role)['icon']} Wróć do akcji", "value": f"ssh_info::{role}::{port}"},
            {"label": "🏠 Menu",                                   "value": "back"},
        ])
        _tl.sid = None
    threading.Thread(target=_run, daemon=True).start()

