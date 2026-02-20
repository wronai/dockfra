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
        targets[name] = {"desc": desc, "params": params}
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
    for sub in ("scripts", "manager-scripts", "deploy-scripts", "autopilot-scripts"):
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
            container = container or f"dockfra-ssh-{role}"
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

            # Build cmd_meta: cmd → (label, [params], hint, placeholder)
            cmd_meta = {}
            for cmd, info in targets.items():
                params = info["params"]
                hint, placeholder = "", ""
                if params:
                    hint, placeholder = _PARAM_HINTS.get(params[0], (params[0], ""))
                cmd_meta[cmd] = (info["desc"], params, hint, placeholder)

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
    return _SSH_ROLES.get(role, {
        "container": f"dockfra-ssh-{role}", "user": role,
        "port": _FALLBACK_PORTS.get(role, "2222"),
        "icon": _FALLBACK_ICONS.get(role, "🖥️"),
        "title": role.capitalize(), "makefile": "",
        "commands": [], "cmd_meta": {},
    })


def _step_ssh_info(value: str):
    """Handle ssh_info::role::port button — show SSH connection card."""
    parts = value.split("::")
    role = parts[1] if len(parts) > 1 else "developer"
    port = parts[2] if len(parts) > 2 else "2200"
    info = _get_role(role)
    if not info["commands"]:
        msg(f"❓ Nieznana rola lub brak komend: `{role}`")
        return
    ssh_cmd = f"ssh {info['user']}@localhost -p {port}"
    mk = info["makefile"]
    rows = "\n".join(f"| {c} | {d} | {m} |" for c, d, m in info["commands"])
    msg(
        f"## {info['icon']} {info['title']}\n\n"
        f"**SSH:**\n```\n{ssh_cmd}\n```\n"
        + (f"**Makefile:** `{mk}` — `make -f {mk} help`\n\n" if mk else "\n")
        + f"| Komenda (w kontenerze) | Opis | Host (`make`) |\n|---|---|---|\n{rows}"
    )
    # Build role buttons dynamically from discovered roles
    role_btns = []
    for r, ri in sorted(_SSH_ROLES.items()):
        p = _state.get(f"SSH_{r.upper()}_PORT", ri["port"])
        role_btns.append({"label": f"{ri['icon']} SSH {r.capitalize()}", "value": f"ssh_info::{r}::{p}"})
    role_btns.append({"label": f"📟 Konsola ({role})", "value": f"ssh_console::{role}::{port}"})
    role_btns.append({"label": "🏠 Menu", "value": "back"})
    buttons(role_btns)


def step_ssh_console(value: str):
    """Show command-runner panel: select + arg input + Run button."""
    parts  = value.split("::")
    role   = parts[1] if len(parts) > 1 else "developer"
    port   = parts[2] if len(parts) > 2 else "2200"
    ri     = _get_role(role)
    cmds   = ri["cmd_meta"]
    clear_widgets()
    msg(f"## {ri['icon']} {ri['title']} — konsola komend")

    options = [{"value": k, "label": v[0]} for k, v in cmds.items()]
    hint_map = {k: v[2] for k, v in cmds.items()}
    arg_placeholder_map = {k: v[3] for k, v in cmds.items()}
    first_cmd = options[0]["value"] if options else ""
    first_hint = cmds[first_cmd][2] if first_cmd and cmds[first_cmd][2] else ""
    first_ph   = cmds[first_cmd][3] if first_cmd else ""

    _sid_emit("widget", {
        "type": "select", "name": "ssh_cmd", "label": "Komenda",
        "options": options, "value": first_cmd,
        "hint_map": hint_map, "arg_placeholder_map": arg_placeholder_map,
    })
    _sid_emit("widget", {
        "type": "input", "name": "ssh_arg", "label": "Argument (opcjonalny)",
        "placeholder": first_ph, "value": "", "hint": first_hint,
    })
    buttons([
        {"label": "▶️ Uruchom",      "value": f"run_ssh_cmd::{role}::{ri['container']}::{ri['user']}"},
        {"label": "◀ Info",         "value": f"ssh_info::{role}::{port}"},
        {"label": "🏠 Menu",         "value": "back"},
    ])


def run_ssh_cmd(value: str, form: dict):
    """Execute selected command via docker exec and stream output to chat."""
    parts     = value.split("::")
    role      = parts[1] if len(parts) > 1 else "developer"
    container = parts[2] if len(parts) > 2 else "dockfra-ssh-developer"
    user      = parts[3] if len(parts) > 3 else "developer"
    cmd_name  = (form.get("ssh_cmd") or "").strip()
    arg       = (form.get("ssh_arg") or "").strip()

    if not cmd_name:
        msg("❌ Wybierz komendę."); return

    ri     = _get_role(role)
    meta   = ri["cmd_meta"].get(cmd_name)
    if not meta:
        msg(f"❌ Nieznana komenda: `{cmd_name}`"); return

    params = meta[1]
    # Build the shell command
    if params and arg:
        # If the param suggests quoting (multi-word args), wrap in quotes
        needs_quote = params[0] in ("Q", "TITLE", "MSG", "F", "FEATURE")
        shell_arg   = f'"{arg}"' if needs_quote else arg
        cmd_str = f"{cmd_name} {shell_arg}"
    else:
        cmd_str = cmd_name

    label = meta[0]
    msg(f"▶️ Uruchamiam: `{cmd_str}` na `{container}`")
    _tl_sid = getattr(_tl, 'sid', None)

    def _run():
        _tl.sid = _tl_sid
        try:
            rc, out = run_cmd(
                ["docker", "exec", "-u", user, container,
                 "bash", "-lc", cmd_str],
            )
            if rc == 0:
                msg(f"✅ `{cmd_str}` — zakończono.")
            else:
                msg(f"⚠️ `{cmd_str}` zakończyło się z kodem {rc}.")
        except Exception as e:
            msg(f"❌ Błąd: {e}")
        buttons([
            {"label": "▶️ Uruchom ponownie", "value": f"run_ssh_cmd::{role}::{container}::{user}"},
            {"label": "📟 Konsola",           "value": f"ssh_console::{role}"},
            {"label": "🏠 Menu",              "value": "back"},
        ])
        _tl.sid = None
    threading.Thread(target=_run, daemon=True).start()

