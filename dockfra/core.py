"""Dockfra core — shared state, Flask app, UI helpers, env, docker utils."""
import os, json, re as _re, subprocess, threading, time, socket as _socket, secrets as _secrets, sys
from typing import TYPE_CHECKING

__all__ = [
    # re-exported stdlib
    '_re', '_secrets', '_socket', 'subprocess', 'threading', 'time', 'json', 'os', 'sys',
    'Path', 'deque',
    # flask
    'Flask', 'render_template', 'request', 'SocketIO', 'emit',
    'app', 'socketio',
    # LLM
    '_llm_chat', '_llm_config', '_LLM_AVAILABLE',
    '_WIZARD_SYSTEM_PROMPT', '_CMD_SUGGEST_SYSTEM_PROMPT',
    # Docker
    '_docker_client', '_docker_sdk', '_DOCKER_SDK_AVAILABLE',
    # State
    '_state', '_conversation', '_logs', '_tl', '_log_buffer',
    '_sid_emit', 'reset_state',
    '_ENV_TO_STATE', '_STATE_TO_ENV',
    # Paths & project config
    'ROOT', 'MGMT', 'APP', 'DEVS', 'WIZARD_DIR', 'WIZARD_ENV', '_PKG_DIR',
    'DEPLOY_TARGETS', 'load_deploy_targets',
    'PROJECT', 'STACKS', 'cname', 'short_name',
    # ENV
    'ENV_SCHEMA', '_schema_defaults', 'load_env', 'save_env',
    'save_state', 'load_state', '_STATE_FILE', '_STATE_SKIP_PERSIST',
    # Helpers
    'detect_config', '_emit_log_error', 'run_cmd', 'docker_ps',
    'mask', 'msg', 'widget', 'buttons', 'text_input', 'select',
    'code_block', 'status_row', 'progress', 'action_grid', 'clear_widgets',
    '_env_status_summary',
    '_arp_devices', '_devices_env_ip', '_docker_container_env',
    '_local_interfaces', '_subnet_ping_sweep',
    '_detect_suggestions', '_emit_missing_fields',
    # Post-launch hooks
    '_render_post_launch', '_expand_env_vars', '_eval_post_launch_condition',
    '_PROJECT_CONFIG',
    # Health
    '_HEALTH_PATTERNS', '_docker_logs', '_analyze_container_log',
]
from collections import deque
from pathlib import Path
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from .i18n import t as _t_i18n, set_lang as _set_lang, get_lang as _get_lang, llm_lang_instruction as _llm_lang_instruction, _STRINGS

if TYPE_CHECKING:
    from .deployers.base import DeployTarget, PlatformOS

# Allow importing shared lib without installation
_SHARED_LIB = Path(__file__).parent.parent / "shared" / "lib"
if str(_SHARED_LIB) not in sys.path:
    sys.path.insert(0, str(_SHARED_LIB))
try:
    from llm_client import chat as _llm_chat, get_config as _llm_config
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False
    def _llm_chat(*a, **kw): return "[LLM] llm_client not found"
    def _llm_config(): return {}

try:
    import docker as _docker_sdk
    _DOCKER_SDK_AVAILABLE = True
except ImportError:
    _docker_sdk = None
    _DOCKER_SDK_AVAILABLE = False

def _docker_client():
    """Return a docker SDK client, or None if unavailable."""
    if not _DOCKER_SDK_AVAILABLE:
        return None
    try:
        return _docker_sdk.from_env()
    except Exception:
        return None

def _build_wizard_prompt() -> str:
    """Build system prompt dynamically from discovered stacks."""
    try:
        stacks_desc = ", ".join(STACKS.keys()) if STACKS else "none discovered yet"
    except NameError:
        stacks_desc = "not yet discovered"
    return (
        "You are the Dockfra Setup Wizard assistant. Dockfra is a multi-stack Docker infrastructure "
        "managed through this chat UI.\n"
        "Help the user configure environment variables, troubleshoot Docker errors, understand "
        "service roles, and launch stacks. Be concise and practical. Use Markdown.\n"
        f"Available stacks: {stacks_desc}.\n"
        "If asked about a Docker error, suggest the most likely fix.\n\n"
        "IMPORTANT — Interactive buttons: You can embed clickable action buttons anywhere in your "
        "response using the syntax: [[Button label|action_value]]\n"
        "Available actions:\n"
        "  [[⚙️ Ustawienia|settings]] — open settings group selector\n"
        "  [[🔑 LLM / API Key|settings_group::LLM]] — edit LLM and API key fields\n"
        "  [[🌐 Git|settings_group::Git]] — edit Git settings\n"
        "  [[🏗️ Infrastructure|settings_group::Infrastructure]] — edit infrastructure settings\n"
        "  [[🔌 Ports|settings_group::Ports]] — edit port settings\n"
        "  [[🔗 Integrations|settings_group::Integrations]] — edit integration tokens\n"
        "  [[🚀 Uruchom|launch_all]] — launch all stacks\n"
        "  [[📊 Status|status]] — show container status\n"
        "RULE: Whenever the user asks about environment variables, configuration, API keys, or "
        "settings — ALWAYS include at least one [[button|action]] to open the relevant settings "
        "form directly. Do NOT just describe variables in text — show the form button."
    )

# Lazy: rebuilt after STACKS is populated (see module bottom)
_WIZARD_SYSTEM_PROMPT = _build_wizard_prompt()

_CMD_SUGGEST_SYSTEM_PROMPT = """You are a Docker infrastructure troubleshooting expert.
Analyze the container logs provided by the user and respond ONLY with a valid JSON object.
No markdown, no explanation outside the JSON. Format:
{
  "diagnosis": "Krótka diagnoza po polsku (1-2 zdania)",
  "commands": [
    {"cmd": "docker restart <container>", "description": "Opis po polsku co to robi", "safe": true},
    {"cmd": "docker logs --tail 50 <container>", "description": "Opis", "safe": true}
  ]
}
Rules:
- "safe": true for read-only or reversible commands (docker logs, docker inspect, docker ps, docker restart)
- "safe": false for destructive commands (docker rm, volume rm, system prune)
- Include 2-5 concrete commands specific to the actual error in the logs
- Commands must be immediately runnable (no placeholders like <value>)
"""

_FIX_LLM_SYSTEM_PROMPT = """You are Dockfra Fix LLM — an incident response assistant.
Analyze command output and identify the most likely root cause.
Provide concise, actionable repair steps for a technical user.
If the fix requires credentials, login, or missing input, ask short, direct questions at the end.
Use Markdown with short bullet lists. Keep it under 12 lines.
"""

# Thread-local: when set, emit helpers target this SID instead of broadcasting
_tl = threading.local()

# Global log buffer (circular, last 2000 lines) for /api/logs/tail
_log_buffer: deque = deque(maxlen=2000)

def _sid_emit(event, data):
    """Emit to all clients, persist to SQLite, and optionally collect for REST."""
    # Determine source: 'cli' when in REST/collector mode, 'web' otherwise
    src = 'cli' if getattr(_tl, 'collector', None) is not None else 'web'
    # Persist to SQLite (always — shared between CLI and web)
    try:
        from . import db as _db
        _db.append_event(event, data, src=src)
    except Exception:
        pass
    # REST API collector mode: capture all emitted events
    collector = getattr(_tl, 'collector', None)
    if collector is not None:
        collector.append({"event": event, "data": data})
    # Capture log lines to global buffer
    if event == "log_line":
        _log_buffer.append({"text": data.get("text",""), "ts": time.time()})
    if event == "widget" and isinstance(data, dict) and data.get("type") == "buttons":
        try:
            _tl.last_buttons_items = list(data.get("items", []) or [])
        except Exception:
            _tl.last_buttons_items = []
    # Always broadcast via SocketIO — web clients see CLI actions in real-time
    try:
        socketio.emit(event, data)
    except Exception:
        pass

_PKG_DIR   = Path(__file__).parent.resolve()
ROOT       = Path(os.environ.get("DOCKFRA_ROOT", str(_PKG_DIR.parent))).resolve()
WIZARD_DIR = _PKG_DIR
WIZARD_ENV = WIZARD_DIR / ".env"

# ── Project naming ───────────────────────────────────────────────────────────
# Override with DOCKFRA_PREFIX env var to rebrand all container/image/network names.
_PREFIX = os.environ.get("DOCKFRA_PREFIX", "dockfra")
PROJECT = {
    "prefix":         _PREFIX,
    "network":        f"{_PREFIX}-shared",
    "ssh_base_image": f"{_PREFIX}-ssh-base",
}

def cname(service: str) -> str:
    """Container name from service: cname('traefik') → 'dockfra-traefik'"""
    return f"{PROJECT['prefix']}-{service}"

def short_name(container: str) -> str:
    """Strip project prefix: 'dockfra-traefik' → 'traefik'"""
    pfx = PROJECT['prefix'] + '-'
    return container[len(pfx):] if container.startswith(pfx) else container

# ── A: Auto-discover stacks ────────────────────────────────────────────────
# Scan ROOT for subdirs containing docker-compose.yml.
# dockfra.yaml can override/extend stack definitions.
def _discover_stacks() -> dict:
    """Auto-discover stacks: subdirs of ROOT that contain docker-compose.yml."""
    stacks = {}
    skip = {".git", ".venv", "__pycache__", "node_modules", "dockfra", "shared",
            "scripts", "tests", "keys", ".github"}
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in skip:
            continue
        if (d / "docker-compose.yml").exists() or (d / "docker-compose.yaml").exists():
            stacks[d.name] = d
    return stacks

STACKS = _discover_stacks()
# Backward-compatible aliases (used by existing code)
MGMT = STACKS.get("management", ROOT / "management")
APP  = STACKS.get("app",        ROOT / "app")
DEVS = STACKS.get("devices",    ROOT / "devices")
# Rebuild prompt now that STACKS is known
_WIZARD_SYSTEM_PROMPT = _build_wizard_prompt()

# ── C: Optional project config (dockfra.yaml) ────────────────────────────
def _load_project_config() -> dict:
    """Load optional dockfra.yaml from project root.
    Supports: env (label/type/group overrides), stacks, lang."""
    for name in ("dockfra.yaml", "dockfra.yml"):
        cfg_path = ROOT / name
        if cfg_path.exists():
            try:
                import yaml
                return yaml.safe_load(cfg_path.read_text()) or {}
            except ImportError:
                # Fallback: minimal YAML subset (key: value)
                data = {}
                for line in cfg_path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and ":" in line:
                        k, _, v = line.partition(":")
                        data[k.strip()] = v.strip()
                return data
            except Exception:
                pass
    return {}

_PROJECT_CONFIG = _load_project_config()


def _read_devices_env_var(*keys: str) -> str:
    """Read first matching key from devices/.env.local or devices/.env."""
    wanted = set(keys)
    for path in (DEVS / ".env.local", DEVS / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() in wanted:
                return v.strip().strip('"').strip("'")
    return ""


def _coerce_platform_os(value):
    """Coerce string/os-like value to PlatformOS enum."""
    from .deployers.base import PlatformOS

    if isinstance(value, PlatformOS):
        return value
    raw = str(value or "linux").strip().lower()
    aliases = {
        "darwin": "macos",
        "mac": "macos",
        "windows": "windows_wsl",
        "wsl": "windows_wsl",
    }
    raw = aliases.get(raw, raw)
    try:
        return PlatformOS(raw)
    except Exception:
        return PlatformOS.LINUX


def _default_devices_target():
    """Build fallback deploy target from devices env defaults."""
    from .deployers.base import DeployTarget, PlatformOS

    host = (
        _read_devices_env_var("RPI3_HOST", "DEVICE_HOST", "DEVICE_IP")
        or "192.168.1.100"
    )
    user = _read_devices_env_var("RPI3_USER", "DEVICE_USER") or "pi"
    raw_port = _read_devices_env_var("RPI3_PORT", "DEVICE_PORT", "SSH_PORT") or "22"
    try:
        port = int(str(raw_port))
    except Exception:
        port = 22

    return DeployTarget(
        host=host,
        port=port,
        user=user,
        platform="ssh_raw",
        os=PlatformOS.LINUX,
        labels={"source": "devices", "env": "edge"},
        config={"service_manager": "systemd", "deploy_path": f"/home/{user}/apps"},
    )


def load_deploy_targets() -> dict[str, "DeployTarget"]:
    """Load deploy targets from deploy-targets.yaml.

    Fallback: when config is missing/invalid, create one default target from
    devices/.env(.local).
    """
    from .deployers.base import DeployTarget

    cfg_path = None
    for name in ("deploy-targets.yaml", "deploy-targets.yml"):
        p = ROOT / name
        if p.exists():
            cfg_path = p
            break

    data: dict = {}
    if cfg_path:
        try:
            import yaml

            parsed = yaml.safe_load(cfg_path.read_text())
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = {}

    raw_targets = data.get("targets", {}) if isinstance(data, dict) else {}
    targets: dict[str, DeployTarget] = {}

    if isinstance(raw_targets, dict):
        for target_id, raw in raw_targets.items():
            if not isinstance(raw, dict):
                continue
            host = str(raw.get("host", "")).strip()
            if not host:
                continue
            try:
                port = int(raw.get("port", 22))
            except Exception:
                port = 22
            user = str(raw.get("user", "deployer") or "deployer").strip()
            platform = str(raw.get("platform", "docker_compose") or "docker_compose").strip()
            labels_raw = raw.get("labels", {})
            config_raw = raw.get("config", {})
            labels = labels_raw if isinstance(labels_raw, dict) else {}
            config = config_raw if isinstance(config_raw, dict) else {}
            targets[str(target_id)] = DeployTarget(
                host=host,
                port=port,
                user=user,
                platform=platform,
                os=_coerce_platform_os(raw.get("os", "linux")),
                labels={str(k): str(v) for k, v in labels.items()},
                config=dict(config),
            )

    if not targets:
        targets["edge-rpi3"] = _default_devices_target()

    return targets


DEPLOY_TARGETS = load_deploy_targets()


def _expand_env_vars(text: str) -> str:
    """Expand ${VAR:-default} and $VAR patterns using _state and os.environ."""
    import re as _re2
    def _sub(m):
        var, default = m.group(1), m.group(2) or ""
        return _state.get(var.lower(), os.environ.get(var, default))
    text = _re2.sub(r'\$\{([A-Z_][A-Z0-9_]*)(?::?-([^}]*))?\}', _sub, text)
    text = _re2.sub(r'\$([A-Z_][A-Z0-9_]*)', lambda m: os.environ.get(m.group(1), m.group(0)), text)
    return text


def _eval_post_launch_condition(cond: str, running_names: set) -> bool:
    """Evaluate a post_launch condition string. Returns True if button should show."""
    if not cond:
        return True
    cond = cond.strip()
    func, _, arg = cond.partition("(")
    arg = arg.rstrip(")").strip().strip('"\'')
    if func == "stack_exists":
        return arg in STACKS
    if func == "stack_running":
        return any(arg in n for n in running_names)
    if func == "container_running":
        return cname(arg) in running_names or arg in running_names
    if func == "ssh_roles_exist":
        try:
            from .discover import _SSH_ROLES
            return bool(_SSH_ROLES)
        except Exception:
            return False
    return True


def _render_post_launch(running_names: set, ssh_roles: dict):
    """Build and emit post-launch buttons from SSH roles + dockfra.yaml post_launch hooks."""
    post_btns = []
    # SSH role buttons (auto-discovered)
    for role, ri in ssh_roles.items():
        p = _state.get(f"ssh_{role}_port", ri.get("port", "22"))
        post_btns.append({
            "label": _t_i18n('ssh_role_button', icon=ri['icon'], role=role.capitalize()),
            "value": f"ssh_info::{role}::{p}",
        })
    # Virtual developer: app/ not cloned yet but GIT_REPO_URL is set
    if "developer" not in ssh_roles and not (ROOT / "app").is_dir() and _state.get("git_repo_url"):
        dev_port = _state.get("ssh_developer_port", "2200")
        post_btns.insert(0, {"label": _t_i18n('ssh_developer_button'), "value": f"ssh_info::developer::{dev_port}"})
    # Config-driven hooks from dockfra.yaml
    for hook in _PROJECT_CONFIG.get("post_launch", []):
        cond = hook.get("condition", "")
        if not _eval_post_launch_condition(cond, running_names):
            continue
        label = hook.get("label", "")
        if "url" in hook:
            url = _expand_env_vars(hook["url"])
            post_btns.append({"label": label, "value": f"open_url::{url}"})
        elif "action" in hook:
            post_btns.append({"label": label, "value": hook["action"]})
    # Fallback built-in buttons (always shown unless overridden by config)
    _config_actions = {h.get("action") for h in _PROJECT_CONFIG.get("post_launch", []) if "action" in h}
    _builtin = [
        ("ticket_create_wizard", lambda: True),
        ("project_stats",        lambda: True),
        ("integrations_setup",   lambda: True),
        ("post_launch_creds",    lambda: True),
        ("deploy_device",        lambda: "devices" in STACKS),
    ]
    for action, show_fn in _builtin:
        if action not in _config_actions and show_fn():
            from .i18n import t as _ti
            _labels = {
                "ticket_create_wizard": _ti("create_ticket"),
                "project_stats":        _ti("project_stats"),
                "integrations_setup":   _ti("task_integrations"),
                "post_launch_creds":    _ti("setup_github_llm"),
                "deploy_device":        _ti("deploy_device"),
            }
            post_btns.append({"label": _labels[action], "value": action})
    buttons(post_btns)


# ── B: Auto-discover env vars from docker-compose files ───────────────────
def _parse_compose_env_vars() -> dict:
    """Scan all docker-compose files for ${VAR:-default} patterns.
    Returns dict: VAR_NAME → {"default": ..., "stack": ..., "type": ...}"""
    found: dict[str, dict] = {}
    pattern = _re.compile(r'\$\{([A-Z][A-Z0-9_]*)(?::?-([^}]*))?\}')
    skip_vars = {"UID", "GID", "HOME", "USER", "PWD", "PATH", "HOSTNAME"}
    for stack_name, stack_path in STACKS.items():
        for compose_name in ("docker-compose.yml", "docker-compose.yaml",
                             "docker-compose-production.yml"):
            cf = stack_path / compose_name
            if not cf.exists():
                continue
            try:
                text = cf.read_text(errors="replace")
            except Exception:
                continue
            for m in pattern.finditer(text):
                var, default = m.group(1), m.group(2) or ""
                if var in skip_vars:
                    continue
                if var not in found:
                    # Infer type from name
                    vtype = "text"
                    if any(k in var for k in ("PASSWORD", "SECRET", "KEY", "TOKEN")):
                        vtype = "password"
                    elif any(k in var for k in ("PORT",)):
                        vtype = "text"
                    found[var] = {"default": default, "stack": stack_name, "type": vtype}
    return found

_COMPOSE_VARS = _parse_compose_env_vars()

# ── Field metadata: descriptions, autodetect flags, type overrides ──────────
# Applied to ALL schema entries (core + discovered) by _build_env_schema.
_FIELD_META: dict[str, dict] = {
    "ENVIRONMENT":    {"desc": "Środowisko uruchamiania: local (Docker, bez proxy) lub production (Traefik + HTTPS + domeny)."},
    "STACKS":         {"desc": "Które stacki uruchomić: 'all' = wszystkie znalezione foldery z docker-compose.yml."},
    "GIT_NAME":       {"desc": "Imię i nazwisko do git commit — ustawiane w kontenerach dev (git config user.name)."},
    "GIT_EMAIL":      {"desc": "Email git — ustawiany w kontenerach dev (git config user.email)."},
    "GITHUB_SSH_KEY": {"desc": "Ścieżka do prywatnego klucza SSH GitHub (np. ~/.ssh/id_ed25519). Kopiowany do kontenera developer."},
    "GIT_REPO_URL":   {"desc": "URL repozytorium projektu (SSH lub HTTPS). Np. git@github.com:firma/app.git — klonowane w kontenerach dev.", "autodetect": True},
    "GIT_BRANCH":     {"desc": "Gałąź git do klonowania/checkoutu w kontenerze developer. Domyślnie: main.", "autodetect": True},
    "OPENROUTER_API_KEY": {"desc": "Klucz API OpenRouter.ai — wymagany dla poleceń ask / implement / review w kontenerach SSH."},
    "ANTHROPIC_API_KEY": {"desc": "Klucz API Anthropic — wymagany dla Claude Code CLI oraz modeli Anthropica."},
    "LLM_MODEL":      {"desc": "Model AI asystenta kodu. Gemini Flash 1.5 — szybki i tani. GPT-4o — najlepszy, droższy."},
    "FIX_LLM_ENABLED": {"desc": "Fix LLM: nadzór AI nad błędami shell/pipeline. Włącz, aby LLM analizował problemy i zadawał pytania."},
    "FIX_LLM_MODEL":   {"desc": "Model dla Fix LLM. Puste = użyj LLM_MODEL."},
    "DEPLOY_MODE":    {"desc": "Tryb deployu: local (bez Traefik) lub production (z Traefik, HTTPS, domenami).",
                       "type": "select", "options": [("local", "Local (bez proxy)"), ("production", "Production (Traefik+HTTPS)")]},
    "APP_DEBUG":      {"desc": "Tryb debugowania: false = produkcja (ciche logi); true = szczegółowe logi i stack trace.",
                       "type": "select", "options": [("false", "false (produkcja)"), ("true", "true (debug)")]},
    "APP_NAME":       {"desc": "Nazwa aplikacji (lowercase). Prefix nazw kontenerów, domyślna baza danych i użytkownik PostgreSQL."},
    "APP_VERSION":    {"desc": "Wersja aplikacji (semver). Używana w logach i artefaktach build.", "autodetect": True},
    "POSTGRES_USER":  {"desc": "Nazwa użytkownika PostgreSQL. Zwykle taka sama jak APP_NAME."},
    "POSTGRES_PASSWORD": {"desc": "Hasło PostgreSQL. Generuj losowe — kliknij chip aby wstawić."},
    "POSTGRES_DB":    {"desc": "Nazwa bazy danych PostgreSQL. Zwykle taka sama jak APP_NAME."},
    "POSTGRES_PORT":  {"desc": "Port PostgreSQL eksponowany na hoście (domyślnie 5432)."},
    "REDIS_PASSWORD": {"desc": "Hasło Redis AUTH. Puste = brak uwierzytelniania (OK dla local)."},
    "REDIS_PORT":     {"desc": "Port Redis eksponowany na hoście (domyślnie 6379)."},
    "SECRET_KEY":     {"desc": "Tajny klucz kryptograficzny aplikacji (Django/Flask/FastAPI). Musi być losowy i unikalny. Nigdy nie udostępniaj."},
    "ACME_EMAIL":     {"desc": "Email do certyfikatów TLS Let's Encrypt. Wymagany gdy ENVIRONMENT=production."},
    "ACME_STORAGE":   {"desc": "Ścieżka pliku JSON Traefik dla certyfikatów ACME (np. /certs/acme.json)."},
    "BACKEND_PORT":   {"desc": "Port HTTP backendu eksponowany na hoście. Dostępny: http://localhost:PORT."},
    "MOBILE_BACKEND_PORT": {"desc": "Port mobile backendu eksponowany na hoście."},
    "FRONTEND_HOST":  {"desc": "Domena frontendu w Traefik. Local: frontend.localhost; prod: myapp.com."},
    "BACKEND_HOST":   {"desc": "Domena backendu w Traefik. Local: backend.localhost; prod: api.myapp.com."},
    "MOBILE_HOST":    {"desc": "Domena mobile backendu w Traefik."},
    "DESKTOP_HOST":   {"desc": "Domena kontenera desktop w Traefik."},
    "DESKTOP_APP_PORT": {"desc": "Port aplikacji desktopowej eksponowany na hoście."},
    "TRAEFIK_HTTP_PORT":  {"desc": "Port HTTP Traefika na hoście (domyślnie 80). Zmień jeśli 80 jest zajęty."},
    "TRAEFIK_HTTPS_PORT": {"desc": "Port HTTPS Traefika na hoście (domyślnie 443). Zmień jeśli 443 jest zajęty."},
    "TRAEFIK_DASHBOARD_PORT": {"desc": "Port dashboardu Traefik — http://localhost:PORT po uruchomieniu."},
    "WIZARD_PORT":    {"desc": "Port Dockfra Wizarda na hoście. Zmień jeśli 5050 jest zajęty."},
    "SSH_DEVELOPER_PORT": {"desc": "Port SSH kontenera developer. Połącz: ssh developer@localhost -p PORT."},
    "DEVELOPER_LLM_API_KEY": {"desc": "Klucz API LLM dla asystenta w kontenerze developer. Zwykle = OPENROUTER_API_KEY."},
    "DEVELOPER_LLM_MODEL":   {"desc": "Model LLM dla asystenta w kontenerze developer."},
    "HEALTHCHECK_INTERVAL":  {"desc": "Czas między healthcheckami Docker (np. 30s, 1m)."},
    "HEALTHCHECK_TIMEOUT":   {"desc": "Timeout odpowiedzi healthchecka Docker (np. 10s)."},
    "HEALTHCHECK_RETRIES":   {"desc": "Ile nieudanych healthchecków zanim kontener jest oznaczony jako unhealthy."},
    "SSH_DEPLOY_USER":       {"desc": "Użytkownik SSH do deployu na urządzenia IoT/RPi."},
    # Integrations
    "GITHUB_TOKEN":   {"desc": "GitHub Personal Access Token (classic lub fine-grained). Wymagany do sync ticketów z GitHub Issues. Uprawnienia: repo, issues."},
    "GITHUB_REPO":    {"desc": "Repozytorium GitHub w formacie owner/repo (np. myorg/myapp). Tickety sync z Issues tego repo."},
    "JIRA_URL":       {"desc": "URL instancji Jira Cloud (np. https://your-org.atlassian.net). Wymagany do sync z Jira."},
    "JIRA_EMAIL":     {"desc": "Email użytkownika Jira powiązany z API tokenem."},
    "JIRA_TOKEN":     {"desc": "Jira API Token (generuj w: id.atlassian.com → Ustawienia → Tokeny API)."},
    "JIRA_PROJECT":   {"desc": "Klucz projektu Jira (np. PROJ). Nowe tickety będą tworzone w tym projekcie."},
    "TRELLO_KEY":     {"desc": "Trello API Key (generuj na: trello.com/power-ups/admin)."},
    "TRELLO_TOKEN":   {"desc": "Trello autoryzacyjny token (generuj po uzyskaniu API Key)."},
    "TRELLO_BOARD":   {"desc": "ID tablicy Trello. Znajdź w URL tablicy: trello.com/b/<BOARD_ID>/..."},
    "TRELLO_LIST":    {"desc": "ID listy Trello dla nowych kart. Pobierz przez API: /boards/<ID>/lists."},
    "LINEAR_TOKEN":   {"desc": "Linear API Token (generuj w: linear.app → Settings → API → Personal API keys)."},
    "LINEAR_TEAM":    {"desc": "ID zespołu Linear. Tickety będą tworzone w tym zespole."},
}

# ── ENV schema: core + discovered + dockfra.yaml overrides ───────────────
# Core entries (always present — infrastructure/wizard vars)
_CORE_ENV_SCHEMA = [
    # Infrastructure
    {"key":"ENVIRONMENT",       "label":"env_label_environment",  "group":"Infrastructure",
     "type":"select", "options":[("local","Local"),("production","Production")], "default":"local"},
    {"key":"STACKS",            "label":"env_label_stacks", "group":"Infrastructure",
     "type":"select", "options":[("all","env_option_all")] + [(s,s.capitalize()) for s in STACKS],
     "default":"all"},
    # Git
    {"key":"GIT_REPO_URL",      "label":"Git Repo URL",           "group":"Git",
     "type":"text",  "placeholder":"git@github.com:org/app.git", "default":""},
    {"key":"GIT_BRANCH",        "label":"Git Branch",             "group":"Git",
     "type":"text",  "placeholder":"main",                       "default":"main"},
    {"key":"GIT_NAME",          "label":"Git user.name",          "group":"Git",
     "type":"text",  "placeholder":"Jan Kowalski",               "default":""},
    {"key":"GIT_EMAIL",         "label":"Git user.email",         "group":"Git",
     "type":"text",  "placeholder":"jan@example.com",            "default":""},
    {"key":"GITHUB_SSH_KEY",    "label":"ssh_key_path",     "group":"Git",
     "type":"text",  "placeholder":"~/.ssh/id_ed25519",          "default":str(Path.home()/".ssh/id_ed25519")},
    # LLM
    {"key":"OPENROUTER_API_KEY","label":"OpenRouter API Key",     "group":"LLM",
     "type":"password","placeholder":"sk-or-v1-...",             "default":"",
     "required_for":["management"]},
    {"key":"LLM_MODEL",         "label":"Model LLM",              "group":"LLM",
     "type":"select", "options":[
         ("google/gemini-2.0-flash-001","Gemini 2.0 Flash"),
         ("google/gemini-flash-1.5",   "Gemini Flash 1.5"),
         ("google/gemini-2.5-flash-preview", "Gemini 2.5 Flash Preview"),
         ("anthropic/claude-sonnet-4",  "Claude Sonnet 4"),
         ("anthropic/claude-3-5-haiku","Claude 3.5 Haiku"),
         ("openai/gpt-4o-mini",        "GPT-4o Mini"),
         ("openai/gpt-4o",             "GPT-4o"),
         ("deepseek/deepseek-chat-v3-0324","DeepSeek Chat V3"),
         ("meta-llama/llama-3.1-70b-instruct","Llama 3.1 70B"),
         ("__custom__",                "custom_model_option"),
     ], "default":"google/gemini-2.0-flash-001"},
    # Ports
    {"key":"WIZARD_PORT",       "label":"Port Wizarda",            "group":"Ports",
     "type":"text",  "placeholder":"5050",                       "default":"5050"},
    # Integrations
    {"key":"GITHUB_TOKEN",      "label":"GitHub Personal Access Token","group":"Integrations",
     "type":"password","placeholder":"ghp_xxx...",               "default":""},
    {"key":"GITHUB_REPO",       "label":"GitHub Repo (owner/repo)",   "group":"Integrations",
     "type":"text",  "placeholder":"myorg/myapp",                "default":""},
    {"key":"JIRA_URL",          "label":"Jira URL",                   "group":"Integrations",
     "type":"text",  "placeholder":"https://your-org.atlassian.net","default":""},
    {"key":"JIRA_EMAIL",        "label":"Jira Email",                 "group":"Integrations",
     "type":"text",  "placeholder":"user@company.com",           "default":""},
    {"key":"JIRA_TOKEN",        "label":"Jira API Token",             "group":"Integrations",
     "type":"password","placeholder":"xxx...",                    "default":""},
    {"key":"JIRA_PROJECT",      "label":"Jira Project Key",           "group":"Integrations",
     "type":"text",  "placeholder":"PROJ",                       "default":""},
    {"key":"TRELLO_KEY",        "label":"Trello API Key",             "group":"Integrations",
     "type":"password","placeholder":"xxx...",                    "default":""},
    {"key":"TRELLO_TOKEN",      "label":"Trello Token",               "group":"Integrations",
     "type":"password","placeholder":"xxx...",                    "default":""},
    {"key":"TRELLO_BOARD",      "label":"Trello Board ID",            "group":"Integrations",
     "type":"text",  "placeholder":"board_id",                   "default":""},
    {"key":"TRELLO_LIST",       "label":"Trello List ID",             "group":"Integrations",
     "type":"text",  "placeholder":"list_id",                    "default":""},
    {"key":"LINEAR_TOKEN",      "label":"Linear API Token",           "group":"Integrations",
     "type":"password","placeholder":"lin_api_xxx...",            "default":""},
    {"key":"LINEAR_TEAM",       "label":"Linear Team ID",             "group":"Integrations",
     "type":"text",  "placeholder":"team_id",                    "default":""},
]

def _build_env_schema() -> list:
    """Merge core schema + auto-discovered compose vars + dockfra.yaml overrides."""
    # Start with core entries
    schema = list(_CORE_ENV_SCHEMA)
    known_keys = {e["key"] for e in schema}

    # dockfra.yaml env overrides: {VAR: {label:..., type:..., group:...}}
    yaml_env = _PROJECT_CONFIG.get("env", {}) or {}

    # Add discovered compose env vars (not already in core)
    for var, info in sorted(_COMPOSE_VARS.items()):
        if var in known_keys:
            continue
        stack = info["stack"]
        override = yaml_env.get(var, {}) if isinstance(yaml_env, dict) else {}
        entry = {
            "key": var,
            "label": override.get("label", var.replace("_", " ").title()),
            "group": override.get("group", stack.capitalize()),
            "type":  override.get("type", info["type"]),
            "placeholder": override.get("placeholder", info["default"]),
            "default": info["default"],
        }
        req = override.get("required_for")
        if req:
            entry["required_for"] = req if isinstance(req, list) else [req]
        elif stack:
            entry["required_for"] = [stack]
        schema.append(entry)
        known_keys.add(var)

    # Add any dockfra.yaml vars that weren't in compose or core
    if isinstance(yaml_env, dict):
        for var, meta in yaml_env.items():
            if var in known_keys:
                # Apply overrides to existing entries
                for e in schema:
                    if e["key"] == var:
                        if isinstance(meta, dict):
                            for k in ("label", "group", "type", "placeholder"):
                                if k in meta:
                                    e[k] = meta[k]
                        break
                continue
            if isinstance(meta, dict):
                schema.append({
                    "key": var,
                    "label": meta.get("label", var),
                    "group": meta.get("group", "Custom"),
                    "type":  meta.get("type", "text"),
                    "placeholder": meta.get("placeholder", ""),
                    "default": meta.get("default", ""),
                })
    # Apply _FIELD_META to all entries (desc, autodetect, type/options overrides)
    for e in schema:
        fm = _FIELD_META.get(e["key"])
        if not fm:
            continue
        if "desc" in fm:
            e.setdefault("desc", fm["desc"])
        if "autodetect" in fm:
            e.setdefault("autodetect", fm["autodetect"])
        if fm.get("type") == "select" and e.get("type") != "select":
            e["type"] = "select"
            e["options"] = fm["options"]
    return schema

ENV_SCHEMA = _build_env_schema()

# ── env file helpers ──────────────────────────────────────────────────────────
def _schema_defaults() -> dict:
    return {e["key"]: e["default"] for e in ENV_SCHEMA}

def load_env() -> dict:
    """Load dockfra/.env, create from .env.example if missing."""
    example = WIZARD_DIR / ".env.example"
    if not WIZARD_ENV.exists() and example.exists():
        WIZARD_ENV.write_text(example.read_text())
    data = _schema_defaults()
    if WIZARD_ENV.exists():
        for line in WIZARD_ENV.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                data[k.strip()] = v.strip()
    return data

def save_env(updates: dict):
    """Write updates to dockfra/.env preserving comments and unknown keys."""
    existing: dict[str, str] = {}
    lines_out: list[str] = []
    if WIZARD_ENV.exists():
        for line in WIZARD_ENV.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                existing[k.strip()] = line  # keep original line
            lines_out.append(line)
    written: set[str] = set()
    result: list[str] = []
    for line in lines_out:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.partition("=")[0].strip()
            if k in updates:
                result.append(f"{k}={updates[k]}")
                written.add(k)
            else:
                result.append(line)
        else:
            result.append(line)
    for k, v in updates.items():
        if k not in written:
            result.append(f"{k}={v}")
    WIZARD_ENV.write_text("\n".join(result) + "\n")

app = Flask(__name__)
app.config["SECRET_KEY"] = f"{_PREFIX}-wizard"
# Try gevent first, fallback to threading
try:
    import gevent
    from gevent import pywsgi
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent", manage_session=False)
except ImportError:
    print("⚠️ gevent not found, using threading mode (WebSocket may have issues)")
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", manage_session=False)

_state: dict = {}
_conversation: list[dict] = []
_logs: list[dict] = []

# mapping: ENV key → _state key (auto-generated from ENV_SCHEMA)
# Special cases for backward compat (old code uses these state key names)
_STATE_KEY_ALIASES = {
    "GITHUB_SSH_KEY":    "github_key",
    "OPENROUTER_API_KEY":"openrouter_key",
}
_ENV_TO_STATE = {}
for _e in ENV_SCHEMA:
    _k = _e["key"]
    _ENV_TO_STATE[_k] = _STATE_KEY_ALIASES.get(_k, _k.lower())
_STATE_TO_ENV = {v: k for k, v in _ENV_TO_STATE.items()}

_STATE_FILE = WIZARD_DIR / ".state.json"

# Keys that must NOT be persisted (secrets / per-session only)
_STATE_SKIP_PERSIST = frozenset({
    "_lang", "step",
    "openrouter_key", "anthropic_api_key", "github_token",
    "jira_token", "trello_token", "linear_token",
})


def save_state():
    """Persist non-sensitive _state keys to dockfra/.state.json."""
    try:
        data = {}
        for k, v in _state.items():
            if k in _STATE_SKIP_PERSIST:
                continue
            kl = k.lower()
            if any(s in kl for s in ("password", "secret", "token", "api_key")):
                continue
            env_key = _STATE_TO_ENV.get(k)
            if env_key:
                if any(s in env_key for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
                    continue
                if (env_key.endswith("_KEY") or "_KEY_" in env_key) and "SSH_KEY" not in env_key and env_key != "GITHUB_SSH_KEY":
                    continue
            if kl.endswith("_key") and kl not in ("github_key",):
                continue
            data[k] = v
        _STATE_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def load_state() -> dict:
    """Load persisted state from dockfra/.state.json. Returns {} on error."""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        pass
    return {}


def reset_state():
    global _state
    env = load_env()
    _state = {"step": "welcome"}
    for env_key, state_key in _ENV_TO_STATE.items():
        _state[state_key] = env.get(env_key, "")
    # Overlay persisted non-sensitive state (env values take precedence for secrets)
    for k, v in load_state().items():
        if k not in _STATE_SKIP_PERSIST and not _state.get(k):
            _state[k] = v
    _conversation.clear()
    _logs.clear()

reset_state()

# ── helpers ──────────────────────────────────────────────────────────────────
def detect_config():
    cfg = {}
    try: cfg["git_name"]  = subprocess.check_output(["git","config","--global","user.name"],  text=True).strip()
    except: pass
    try: cfg["git_email"] = subprocess.check_output(["git","config","--global","user.email"], text=True).strip()
    except: pass
    try: cfg["openrouter_key"] = subprocess.check_output(
            ["getv","get","llm","openrouter","OPENROUTER_API_KEY"], text=True, stderr=subprocess.DEVNULL).strip()
    except:
        f = Path.home()/".getv"/"llm"/"openrouter.env"
        if f.exists():
            for l in f.read_text().splitlines():
                if l.startswith("OPENROUTER_API_KEY="):
                    cfg["openrouter_key"] = l.split("=",1)[1].strip(); break
    dev_env = DEVS/".env.local"
    if dev_env.exists():
        for l in dev_env.read_text().splitlines():
            if l.startswith("RPI3_HOST="): cfg["device_ip"]   = l.split("=",1)[1].strip()
            if l.startswith("RPI3_USER="): cfg["device_user"] = l.split("=",1)[1].strip()
    return cfg

def _build_env_var_field(var: str) -> dict:
    """Build a single input field dict for a given env var name."""
    sk = _ENV_TO_STATE.get(var, var.lower())
    _secret = any(k in var for k in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    _placeholder = ""
    _chips = []
    if var.endswith("_URL"):
        _placeholder = "https://..."
    elif var.endswith("_EMAIL"):
        _placeholder = "you@example.com"
    elif "PORT" in var:
        _placeholder = "8080"
    elif var.endswith("_ENABLED") or var.startswith("ENABLE_"):
        _chips = [{"label": "true", "value": "true"}, {"label": "false", "value": "false"}]
    elif var.endswith("_INTERVAL") or var.endswith("_INTERVAL_S"):
        _chips = [{"label": "60", "value": "60"}, {"label": "120", "value": "120"}, {"label": "300", "value": "300"}]
    return {"name": var, "label": var,
            "type": "password" if _secret else "text",
            "placeholder": _placeholder, "chips": _chips,
            "value": _state.get(sk, "")}


def _emit_health_acme_form():
    """Emit ACME_STORAGE inline input + fix buttons."""
    cur = _state.get("acme_storage", "letsencrypt/acme.json")
    _sid_emit("widget", {"type": "input", "name": "ACME_STORAGE",
                         "label": _t_i18n('acme_storage_label'),
                         "placeholder": "letsencrypt/acme.json",
                         "value": cur, "secret": False, "hint":
                         _t_i18n('acme_hint'),
                         "chips": [], "modal_type": ""})
    _sid_emit("widget", {"type": "buttons", "items": [
        {"label": _t_i18n('apply_fix_traefik'), "value": "fix_acme_storage"},
        {"label": _t_i18n('settings'), "value": "settings"},
    ]})


def _emit_health_network_form(network: str):
    """Emit network overlap fix buttons."""
    _sid_emit("widget", {"type": "buttons", "items": [
        {"label": _t_i18n('remove_network', net=network),  "value": f"fix_network_overlap::{network}"},
        {"label": _t_i18n('clean_unused_networks'), "value": "fix_network_overlap::"},
    ]})


def _emit_health_unbound_var_form(line: str, btns: list):
    """Emit inline input + buttons for unbound / missing env var."""
    import re as _re
    _mv = _re.search(r'"([A-Z_]{3,})" variable is not set', line)
    _uv = _re.search(r':\s*([A-Z][A-Z0-9_]{2,})\s*:\s*unbound variable', line)
    var = (_mv.group(1) if _mv else (_uv.group(1) if _uv else ""))
    if not var:
        if btns:
            _sid_emit("widget", {"type": "buttons", "items": btns})
        return
    field = _build_env_var_field(var)
    _sid_emit("widget", {"type": "input", "name": var,
                         "label": var, "placeholder": field["placeholder"] or "",
                         "value": field["value"],
                         "secret": field["type"] == "password",
                         "hint": _t_i18n('set_env_var_hint', var=var),
                         "chips": field["chips"], "modal_type": ""})
    btn_items = [
        {"label": _t_i18n('save_env_var_button', var=var), "value": f"save_env_var::{var}"},
        {"label": _t_i18n('settings'), "value": "settings"},
    ]
    group = next((e.get("group", "") for e in ENV_SCHEMA if e.get("key") == var), "")
    if group:
        btn_items.append({"label": _t_i18n('settings_group_button', group=group), "value": f"settings_group::{group}"})
    if "autopilot-daemon.sh" in line or "[autopilot]" in line or var.startswith("AUTOPILOT_"):
        env = _state.get("environment", "local")
        ap = "dockfra-ssh-autopilot-prod" if env == "production" else cname("ssh-autopilot")
        btn_items.append({"label": _t_i18n('rebuild_management'), "value": "rebuild_stack::management"})
        btn_items.append({"label": _t_i18n('restart_autopilot'), "value": f"restart_container::{ap}"})
        btn_items.append({"label": _t_i18n('check_pilot_status'), "value": "ssh_cmd::autopilot::pilot-status::"})
    _sid_emit("widget", {"type": "buttons", "items": btn_items})


def _match_config_error(line: str, fired: set):
    """Check line against config-error patterns. Returns True if matched."""
    import re as _re
    for pattern, title, desc, fields, settings_group in _CONFIG_ERROR_PATTERNS:
        key = "cfg:" + pattern[:40]
        if key in fired:
            continue
        m = _re.search(pattern, line, _re.IGNORECASE)
        if not m:
            continue
        extra_fields = list(fields)
        if not extra_fields and m.lastindex:
            for gi in range(1, m.lastindex + 1):
                try:
                    var = m.group(gi)
                    if var and _re.match(r'^[A-Z][A-Z0-9_]{2,}$', var):
                        extra_fields = [_build_env_var_field(var)]
                        break
                except Exception:
                    pass
        _title = _t_i18n(title) if title in _STRINGS else title
        _desc = _t_i18n(desc) if desc in _STRINGS else desc
        _resolved_fields = [{**f, "label": (_t_i18n(f["label"]) if f["label"] in _STRINGS else f["label"])} for f in extra_fields]
        _emit_config_form(_title, _t_i18n('detected_in_logs', line=line.strip()[:120], desc=_desc),
                          _resolved_fields, settings_group, key, fired)
        return True
    return False


def _emit_health_inline_form(line: str, btn_values: str, btns: list, network: str):
    """Emit the appropriate inline form/buttons for a matched health pattern."""
    if "fix_acme_storage" in btn_values:
        _emit_health_acme_form()
    elif "fix_network_overlap::" in btn_values and network:
        _emit_health_network_form(network)
    elif "fix_network_overlap::" in btn_values and not network:
        _sid_emit("widget", {"type": "buttons", "items": btns})
    elif ("variable is not set" in line
          or "Defaulting to a blank string" in line
          or "unbound variable" in line):
        _emit_health_unbound_var_form(line, btns)
    else:
        if btns:
            _sid_emit("widget", {"type": "buttons", "items": btns})


def _emit_log_error(line: str, fired: set):
    """Check a single log line against health + config-error patterns; emit alerts/forms."""
    import re as _re
    # ── Config-error patterns (API keys, auth, tool login) ───────────────────
    if _match_config_error(line, fired):
        return True
    # ── Docker health patterns ────────────────────────────────────────────────
    for pattern, sev, message, solutions in _HEALTH_PATTERNS:
        key = pattern[:40]
        if key in fired or sev not in ("err", "warn"):
            continue
        m = _re.search(pattern, line, _re.IGNORECASE)
        if not m:
            continue
        fired.add(key)
        port = ""
        network = ""
        if m.lastindex:
            try:
                g = m.group(1)
                if g and g.isdigit():
                    port = g
            except Exception:
                pass
        _nm = _re.search(r"failed to create network ([\w_-]+)", line)
        if _nm:
            network = _nm.group(1)
        icon = "🔴" if sev == "err" else "🟡"
        btns = []
        for b in solutions:
            val = b["value"].replace("__PORT__", port).replace("__NETWORK__", network)
            if "__NAME__" in val:
                continue
            btns.append({"label": _t_i18n(b["label"]), "value": val})
        _msg = _t_i18n(message, net=PROJECT['network']) if '{net}' in _t_i18n(message) else _t_i18n(message)
        _sid_emit("message", {"role": "bot",
                               "text": f"{icon} **{_msg}**\n`{line.strip()[:160]}`"})
        btn_values = " ".join(b["value"] for b in btns)
        _emit_health_inline_form(line, btn_values, btns, network)
        return True

    return False

def _strip_motd_line(text: str) -> bool:
    """Return True if the line is a MOTD box-drawing line that should be suppressed."""
    import re
    t = text.strip()
    if not t:
        return False
    if re.match(r'^[╔┌╚└]', t):
        return True
    if re.match(r'^[║╠╣│]', t):
        return True
    if t and not re.sub(r'[\s╔╗╚╝╠╣║═─━│┌┐└┘├┤┬┴┼▀▄█▌▐░▒▓]', '', t):
        return True
    return False


def run_cmd(cmd, cwd=None):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=str(cwd or ROOT))
    lines = []
    _fired: set = set()
    _had_fixes = False
    in_box = False
    for line in proc.stdout:
        text = line.rstrip()
        # Filter MOTD box-drawing banners
        t = text.strip()
        if not in_box and t and t[0] in '╔┌':
            in_box = True; continue
        if in_box and t and t[0] in '╚└':
            in_box = False; continue
        if in_box:
            continue
        if _strip_motd_line(text):
            continue
        lines.append(text)
        log_id = f"log-{len(_logs)}"
        _logs.append({"id": log_id, "text": text, "timestamp": time.time()})
        _sid_emit("log_line", {"id": log_id, "text": text})
        try:
            if _emit_log_error(text, _fired):
                _had_fixes = True
        except Exception:
            pass
    proc.wait()
    try:
        _tl.had_auto_fixes = bool(_had_fixes)
    except Exception:
        pass
    return proc.returncode, "\n".join(lines)

def docker_ps():
    try:
        out = subprocess.check_output(
            ["docker","ps","--format","{{.Names}}::{{.Status}}::{{.Ports}}"],
            text=True, stderr=subprocess.DEVNULL)
        rows = []
        for l in out.strip().splitlines():
            p = l.split("::",2)
            rows.append({"name":p[0],"status":p[1] if len(p)>1 else "","ports":p[2] if len(p)>2 else ""})
        return rows
    except Exception:
        # Fallback: Docker Python SDK
        cli = _docker_client()
        if not cli:
            return []
        try:
            rows = []
            for c in cli.containers.list(all=True):
                rows.append({"name": c.name,
                             "status": c.status,
                             "ports": str(c.ports or "")})
            return rows
        except Exception:
            return []

def mask(k): return k[:12]+"..."+k[-4:] if len(k)>=16 else "***"

def msg(text, role="bot"):
    msg_id = f"msg-{len(_conversation)}"
    _conversation.append({"id": msg_id, "role": role, "text": text, "timestamp": time.time()})
    _sid_emit("message", {"id": msg_id, "role": role, "text": text}); time.sleep(0.04)
def widget(w):                      _sid_emit("widget",    w);                          time.sleep(0.04)
def buttons(items, label=""):       widget({"type":"buttons",  "label":label, "items":items})
def text_input(n,l,ph="",v="",sec=False,hint="",chips=None,modal_type="",desc="",autodetect=False,help_url=""): widget({"type":"input","name":n,"label":l,"placeholder":ph,"value":v,"secret":sec,"hint":hint,"chips":chips or [],"modal_type":modal_type,"desc":desc,"autodetect":autodetect,"help_url":help_url})
def select(n,l,opts,v="",desc="",autodetect=False):                                               widget({"type":"select",  "name":n,"label":l,"options":opts,"value":v,"desc":desc,"autodetect":autodetect})
def code_block(t):                  widget({"type":"code",     "text":t})
def status_row(items):              widget({"type":"status_row","items":items})
def progress(label, done=False, error=False): widget({"type":"progress","label":label,"done":done,"error":error})
def action_grid(run_value, commands, label=""): widget({"type":"action_grid","run_value":run_value,"commands":commands,"label":label})
def clear_widgets():                _sid_emit("clear_widgets", {})

# ── steps ────────────────────────────────────────────────────────────────────
def _env_status_summary() -> str:
    """One-line summary: which required vars are missing."""
    missing = []
    for e in ENV_SCHEMA:
        sk = _ENV_TO_STATE.get(e["key"], e["key"].lower())
        if e.get("required_for") and not _state.get(sk):
            missing.append(e["key"])
    if missing:
        vars_str = '`, `'.join(missing[:4]) + ('...' if len(missing) > 4 else '')
        return _t_i18n('env_status_missing', vars=vars_str)
    return _t_i18n('env_status_ok')


def _arp_devices() -> list[dict]:
    """Return [{ip, mac, iface, state}] sorted REACHABLE first."""
    import re
    devices: list[dict] = []
    seen: set[str] = set()
    # ip neigh includes connection state (REACHABLE / STALE / DELAY / FAILED)
    try:
        out = subprocess.check_output(["ip","neigh"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.match(r'^(\d+\.\d+\.\d+\.\d+)\s+dev\s+(\S+)(?:.*lladdr\s+(\S+))?\s+(\S+)$', line.strip())
            if m and m.group(1) not in seen:
                devices.append({"ip": m.group(1), "iface": m.group(2),
                                 "mac": m.group(3) or "", "state": m.group(4) or "UNKNOWN"})
                seen.add(m.group(1))
    except: pass
    if not devices:
        try:
            out = subprocess.check_output(["arp","-a"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                m = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                if m and m.group(1) not in seen and m.group(1) != "0.0.0.0":
                    devices.append({"ip": m.group(1), "iface": "", "mac": "", "state": "UNKNOWN"})
                    seen.add(m.group(1))
        except: pass
    order = {"REACHABLE": 0, "DELAY": 1, "PROBE": 1, "STALE": 2, "UNKNOWN": 3, "FAILED": 4}
    devices.sort(key=lambda d: order.get(d["state"], 3))
    return devices[:16]

def _devices_env_ip() -> str:
    """Read RPI3_HOST from devices/.env.local or devices/.env."""
    for path in [DEVS / ".env.local", DEVS / ".env"]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("RPI3_HOST="):
                    val = line.split("=", 1)[1].strip()
                    if val: return val
    return ""

def _docker_container_env(container: str, var: str) -> str:
    """Extract an env var value from a running Docker container."""
    try:
        out = subprocess.check_output(
            ["docker","inspect","--format",
             "{{range .Config.Env}}{{println .}}{{end}}", container],
            text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if line.startswith(var + "="):
                return line.split("=", 1)[1].strip()
    except: pass
    return ""

def _local_interfaces() -> list[str]:
    """Return host IPs (non-loopback)."""
    import re
    ips = []
    try:
        out = subprocess.check_output(["ip","addr"], text=True, stderr=subprocess.DEVNULL)
        for m in re.finditer(r'inet (\d+\.\d+\.\d+\.\d+)/\d+.*scope global', out):
            ips.append(m.group(1))
    except: pass
    return ips

def _subnet_ping_sweep(max_hosts: int = 254, timeout: float = 0.4) -> list[str]:
    """Ping-sweep the host's first non-loopback /24 subnet. Returns responding IPs."""
    import re, ipaddress
    from concurrent.futures import ThreadPoolExecutor
    # Find a suitable subnet (prefer 192.168.x, 10.x, 172.16-31.x; skip 10.42 CNI)
    subnet_ip = ""
    try:
        out = subprocess.check_output(["ip","addr"], text=True, stderr=subprocess.DEVNULL)
        for m in re.finditer(r'inet (\d+\.\d+\.\d+\.\d+)/(\d+).*scope global', out):
            ip, prefix = m.group(1), int(m.group(2))
            parts = [int(x) for x in ip.split(".")]
            # skip CNI / docker ranges
            if parts[0] == 10 and parts[1] in (42, 96, 244): continue
            if parts[0] == 172 and 16 <= parts[1] <= 31: continue
            if parts[0] == 127: continue
            subnet_ip = ip
            break
    except: pass
    if not subnet_ip: return []
    try:
        net = ipaddress.IPv4Network(f"{subnet_ip}/24", strict=False)
        hosts = [str(h) for h in net.hosts() if str(h) != subnet_ip][:max_hosts]
    except: return []
    def _ping(ip: str) -> str:
        try:
            with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                # Try port 22 (SSH) first — fast
                if s.connect_ex((ip, 22)) == 0: return ip
            # Fallback: ICMP via system ping (1 packet, 0.4s timeout)
            r = subprocess.run(["ping","-c1","-W1",ip], capture_output=True, timeout=2)
            if r.returncode == 0: return ip
        except: pass
        return ""
    responding = []
    with ThreadPoolExecutor(max_workers=32) as ex:
        for result in ex.map(_ping, hosts):
            if result: responding.append(result)
    return responding

def _detect_git_suggestions(s: dict):
    """Detect git repo URL, branch, user name/email."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip()
        if url: s["GIT_REPO_URL"] = {"value": url, "hint": "git remote origin"}
    except: pass
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip()
        all_out = subprocess.check_output(
            ["git", "branch", "-a", "--format=%(refname:short)"],
            text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip()
        branches = list(dict.fromkeys(
            b.strip().replace("origin/", "") for b in all_out.splitlines() if b.strip()))[:8]
        s["GIT_BRANCH"] = {
            "value": branch or (branches[0] if branches else ""),
            "hint": f"aktualna gałąź: {branch}" if branch else "dostępne gałęzie",
            "chips": [{"label": b, "value": b} for b in branches],
        }
    except: pass
    for key, cmd in [("GIT_NAME",  ["git","config","--global","user.name"]),
                     ("GIT_EMAIL", ["git","config","--global","user.email"])]:
        try:
            v = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            if v: s[key] = {"value": v, "hint": f"z ~/.gitconfig"}
        except: pass


def _detect_ssh_keys(s: dict):
    """Detect SSH keys in ~/.ssh."""
    ssh_dir = Path.home() / ".ssh"
    if ssh_dir.exists():
        keys = sorted(f for f in ssh_dir.iterdir()
                      if f.is_file() and not f.suffix and f.stem.startswith("id_"))
        if keys:
            s["GITHUB_SSH_KEY"] = {
                "value": str(keys[0]),
                "hint": f"znaleziono {len(keys)} klucz(e) w ~/.ssh",
                "chips": [{"label": f.name, "value": str(f)} for f in keys[:6]],
            }


def _detect_api_keys(s: dict):
    """Detect API keys from environment variables."""
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        s["OPENROUTER_API_KEY"] = {"value": or_key, "hint": "z zmiennej środowiskowej"}


def _detect_secrets(s: dict):
    """Generate random secret suggestions."""
    for key, n in [("POSTGRES_PASSWORD", 12), ("REDIS_PASSWORD", 12), ("SECRET_KEY", 32)]:
        gens = [_secrets.token_urlsafe(n) for _ in range(3)]
        s[key] = {"value": "", "hint": "kliknij chip aby wstawić",
                  "chips": [{"label": g, "value": g} for g in gens]}


def _is_docker_internal(ip: str) -> bool:
    """Check if IP belongs to Docker internal network ranges."""
    p = ip.split(".")
    if len(p) != 4: return False
    a, b = int(p[0]), int(p[1])
    return (a == 172 and 16 <= b <= 31) or (a == 10 and b in (0, 1, 88, 89))


def _detect_device_ip(s: dict):
    """Detect device IP from env files, Docker containers, and ARP cache."""
    local_ips = set(_local_interfaces())
    env_ip = _devices_env_ip()
    docker_ip = ""
    for cn in [cname("ssh-rpi3"), "ssh-rpi3"]:
        docker_ip = _docker_container_env(cn, "RPI3_HOST")
        if docker_ip: break
    best_ip = env_ip or docker_ip or ""

    arp = _arp_devices()
    state_icon = {"REACHABLE": "🟢", "DELAY": "🟡", "PROBE": "🟡",
                  "STALE": "🟠", "FAILED": "🔴", "UNKNOWN": "⚪"}
    chips: list[dict] = []
    for ip, src in [(env_ip, "devices/.env"), (docker_ip, "docker ssh-rpi3")]:
        if ip and ip not in {c["value"] for c in chips}:
            chips.append({"label": f"📌 {ip}  ({src})", "value": ip})
    for d in arp:
        if d["ip"] in local_ips or _is_docker_internal(d["ip"]): continue
        if d["ip"] in {c["value"] for c in chips}: continue
        icon = state_icon.get(d["state"], "⚪")
        iface = f" — {d['iface']}" if d["iface"] else ""
        chips.append({"label": f"{icon} {d['ip']}{iface}", "value": d["ip"]})
        if len(chips) >= 10: break

    reachable = sum(1 for d in arp
                    if d["state"] == "REACHABLE"
                    and d["ip"] not in local_ips
                    and not _is_docker_internal(d["ip"]))
    hint_parts: list[str] = []
    if env_ip:          hint_parts.append(f"devices/.env: {env_ip}")
    elif docker_ip:     hint_parts.append(f"z kontenera ssh-rpi3: {docker_ip}")
    if reachable:       hint_parts.append(f"{reachable} aktywnych w sieci")
    elif chips and not env_ip and not docker_ip:
                        hint_parts.append("urządzenia z ARP cache")
    s["DEVICE_IP"] = {
        "value": best_ip,
        "hint":  " · ".join(hint_parts) if hint_parts else "wpisz IP urządzenia docelowego",
        "chips": chips,
    }


def _read_devices_env_var(pattern: str) -> str:
    """Read a variable from devices/.env or .env.local matching the given regex pattern."""
    val = ""
    for ef in [ROOT / "devices" / ".env", ROOT / "devices" / ".env.local"]:
        if ef.exists():
            for line in ef.read_text(errors="ignore").splitlines():
                m = _re.match(pattern, line.strip())
                if m: val = m.group(1).strip(); break
        if val: break
    return val


def _detect_device_user(s: dict):
    """Detect device SSH user from env files, Docker, and common defaults."""
    env_user = _read_devices_env_var(r'^(?:RPI3_USER|DEVICE_USER)=(.+)$')
    docker_user = ""
    for cn in [cname("ssh-rpi3"), "ssh-rpi3"]:
        docker_user = _docker_container_env(cn, "RPI3_USER")
        if docker_user: break
    best_user = env_user or docker_user or "pi"
    user_chips = []
    _seen_users = set()
    for u, src in [(env_user, "devices/.env"), (docker_user, "docker ssh-rpi3")]:
        if u and u not in _seen_users:
            user_chips.append({"label": f"📌 {u}  ({src})", "value": u})
            _seen_users.add(u)
    for u, lbl in [("pi","Raspberry Pi"), ("root","Root"), ("ubuntu","Ubuntu"),
                   ("debian","Debian"), ("dietpi","DietPi"), ("alarm","Arch ARM"),
                   ("odroid","ODROID"), ("rock","Rock/Radxa")]:
        if u not in _seen_users:
            user_chips.append({"label": f"👤 {u}  ({lbl})", "value": u})
            _seen_users.add(u)
    user_hint_parts = []
    if env_user:    user_hint_parts.append(f"devices/.env: {env_user}")
    elif docker_user: user_hint_parts.append(f"z kontenera: {docker_user}")
    s["DEVICE_USER"] = {
        "value": best_user,
        "hint": " · ".join(user_hint_parts) if user_hint_parts else "użytkownik SSH na urządzeniu docelowym",
        "chips": user_chips,
    }


def _detect_device_port(s: dict):
    """Detect device SSH port from env files, Docker, and common defaults."""
    env_port = _read_devices_env_var(r'^(?:RPI3_PORT|DEVICE_PORT|SSH_PORT)=(\d+)$')
    docker_port = ""
    for cn in [cname("ssh-rpi3"), "ssh-rpi3"]:
        docker_port = _docker_container_env(cn, "RPI3_PORT")
        if docker_port: break
    best_port = env_port or docker_port or "22"
    port_chips = []
    _seen_ports = set()
    for p, src in [(env_port, "devices/.env"), (docker_port, "docker ssh-rpi3")]:
        if p and p not in _seen_ports:
            port_chips.append({"label": f"📌 {p}  ({src})", "value": p})
            _seen_ports.add(p)
    for p, lbl in [("22","SSH standard"), ("2222","SSH alternatywny"),
                   ("2200","SSH developer"), ("8022","Termux/Android")]:
        if p not in _seen_ports:
            port_chips.append({"label": f"🔌 {p}  ({lbl})", "value": p})
            _seen_ports.add(p)
    port_hint_parts = []
    if env_port:      port_hint_parts.append(f"devices/.env: {env_port}")
    elif docker_port: port_hint_parts.append(f"z kontenera: {docker_port}")
    s["DEVICE_PORT"] = {
        "value": best_port,
        "hint": " · ".join(port_hint_parts) if port_hint_parts else "port SSH na urządzeniu docelowym",
        "chips": port_chips,
    }


def _detect_app_info(s: dict):
    """Detect app name from project path and version from git tag."""
    project_name = ROOT.name.lower().replace("-","_")
    s["APP_NAME"]     = {"value": project_name, "hint": f"z nazwy katalogu: {ROOT.name}"}
    s["POSTGRES_DB"]  = {"value": project_name, "hint": "zwykle = APP_NAME"}
    s["POSTGRES_USER"]= {"value": project_name, "hint": "zwykle = APP_NAME"}
    try:
        tag = subprocess.check_output(
            ["git","describe","--tags","--abbrev=0"],
            text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip().lstrip("v")
        if tag: s["APP_VERSION"] = {"value": tag, "hint": f"ostatni git tag: v{tag}"}
    except: pass


def _detect_free_ports(s: dict):
    """Find free ports for services that need them."""
    def _free(port: int, stop: int = 20) -> int:
        for p in range(port, port + stop):
            try:
                with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
                    sock.bind(('0.0.0.0', p)); return p
            except: pass
        return port
    for key, dflt in [("VNC_RPI3_PORT",6080),("DESKTOP_VNC_PORT",6081),("WIZARD_PORT",5050)]:
        p = _free(dflt)
        if p != dflt:
            s[key] = {"value": str(p), "hint": f"port {dflt} zajęty → wolny: {p}",
                      "chips": [{"label": str(p), "value": str(p)}]}


def _detect_suggestions() -> dict:
    """Auto-detect suggested values for form fields. Returns {key: {value, hint, chips}}."""
    s: dict[str, dict] = {}
    _detect_git_suggestions(s)
    _detect_ssh_keys(s)
    _detect_api_keys(s)
    _detect_secrets(s)
    _detect_device_ip(s)
    _detect_device_user(s)
    _detect_device_port(s)
    _detect_app_info(s)
    _detect_free_ports(s)
    return s

def _emit_missing_fields(missing: list[dict]):
    """Emit input/select widgets for each missing env var, with smart suggestions."""
    suggestions = _detect_suggestions()
    for e in missing:
        sk  = _ENV_TO_STATE.get(e["key"], e["key"].lower())
        cur = _state.get(sk, e.get("default", ""))
        sug = suggestions.get(e["key"], {})
        # Pre-fill with suggestion only when field is still empty
        if not cur and sug.get("value"):
            cur = sug["value"]
        hint      = sug.get("hint", "")
        chips     = sug.get("chips", [])
        modal_type = "ip_picker" if e["key"] == "DEVICE_IP" else ""
        if e["type"] == "select":
            opts = [{"label": lbl, "value": val} for val, lbl in e["options"]]
            select(e["key"], e["label"], opts, cur,
                   desc=e.get("desc", ""), autodetect=e.get("autodetect", False))
        else:
            text_input(e["key"], e["label"],
                       e.get("placeholder", ""), cur,
                       sec=(e["type"] == "password"), hint=hint, chips=chips,
                       modal_type=modal_type,
                       desc=e.get("desc", ""), autodetect=e.get("autodetect", False))


# ── Config-error patterns (tool/service auth & missing API keys) ──────────────
# Each entry: (regex, title_pl, desc_pl, fields, settings_group)
# fields: list of {name, label, type, placeholder, chips}
_CONFIG_ERROR_PATTERNS = [
    # Claude Code CLI — not logged in
    (r"Not logged in[\s·•\-]*(Please run|use)\s+/login|not logged in.*login|claude.*not logged in",
     "Claude Code CLI: wymagane logowanie",
     "Claude Code CLI nie jest zalogowany — uruchom `/login` w terminalu.",
     [],
     "claude_code_login"),

    # Anthropic API key
    (r"ANTHROPIC_API_KEY.*(not set|missing|invalid|undefined)|anthropic.*authentication.*fail|anthropic.*api.?key",
     "Brak klucza Anthropic API",
     "Zmienna `ANTHROPIC_API_KEY` nie jest ustawiona lub jest nieprawidłowa.",
     [{"name": "ANTHROPIC_API_KEY", "label": "Klucz Anthropic API",
       "type": "password", "placeholder": "sk-ant-api03-...",
       "chips": [{"label": "anthropic.com/settings", "value": ""}]}],
     "LLM"),

    # OpenAI API key
    (r"OPENAI_API_KEY.*(not set|missing|invalid)|Incorrect API key provided|invalid_api_key",
     "Brak klucza OpenAI API",
     "Zmienna `OPENAI_API_KEY` nie jest ustawiona lub klucz jest nieprawidłowy.",
     [{"name": "OPENAI_API_KEY", "label": "Klucz OpenAI API",
       "type": "password", "placeholder": "sk-proj-...",
       "chips": [{"label": "platform.openai.com/api-keys", "value": ""}]}],
     "LLM"),

    # OpenRouter API key
    (r"OPENROUTER_API_KEY.*(not set|missing|invalid)|openrouter.*unauthorized|No API key found.*openrouter",
     "Brak klucza OpenRouter API",
     "Zmienna `OPENROUTER_API_KEY` nie jest ustawiona lub jest nieprawidłowa.",
     [{"name": "OPENROUTER_API_KEY", "label": "Klucz OpenRouter API",
       "type": "password", "placeholder": "sk-or-v1-...",
       "chips": [{"label": "openrouter.ai/keys", "value": ""}]}],
     "LLM"),

    # Generic API key / unauthorized
    (r"401 Unauthorized|403 Forbidden.*API|API key.*invalid|Invalid API key|authentication.*required",
     "diag_api_auth",
     "diag_api_auth_desc",
     [],
     "LLM"),

    # GitHub token
    (r"GITHUB_TOKEN.*(not set|missing|invalid)|GitHub.*403|Bad credentials.*GitHub|ghp_.*invalid",
     "diag_no_github_token",
     "diag_no_github_token_desc",
     [{"name": "GITHUB_TOKEN", "label": "GitHub Personal Access Token",
       "type": "password", "placeholder": "ghp_...",
       "chips": [{"label": "github.com/settings/tokens", "value": ""}]},
      {"name": "GITHUB_REPO", "label": "GitHub Repo (owner/repo)",
       "type": "text", "placeholder": "org/repo", "chips": []}],
     "Integrations"),

    # Jira token
    (r"JIRA_TOKEN.*(not set|missing|invalid)|JIRA_URL.*(not set|missing)|Jira.*authentication",
     "diag_no_jira",
     "diag_no_jira_desc",
     [{"name": "JIRA_URL", "label": "Jira URL", "type": "text",
       "placeholder": "https://your-org.atlassian.net", "chips": []},
      {"name": "JIRA_TOKEN", "label": "Jira API Token", "type": "password",
       "placeholder": "atl_...", "chips": [{"label": "id.atlassian.com/token", "value": ""}]}],
     "Integrations"),

    # SSH / Git
    (r"Permission denied \(publickey\)|Host key verification failed|Could not read from remote repository",
     "diag_ssh_error",
     "diag_ssh_error_desc",
     [{"name": "GITHUB_SSH_KEY", "label": "ssh_key_path",
       "type": "text", "placeholder": "~/.ssh/id_ed25519", "chips": []},
      {"name": "GIT_REPO_URL", "label": "Git Repo URL",
       "type": "text", "placeholder": "git@github.com:org/app.git", "chips": []}],
     "Git"),

    # Database connection
    (r"could not connect to server|Connection refused.*5432|ECONNREFUSED.*(5432|3306|27017)|mysql.*connection.*refused|postgres.*connection.*refused",
     "diag_db_error",
     "diag_db_error_desc",
     [{"name": "DB_HOST", "label": "db_host_label", "type": "text",
       "placeholder": "localhost", "chips": []},
      {"name": "DB_PASSWORD", "label": "db_password_label", "type": "password",
       "placeholder": "", "chips": []}],
     "App"),

    # Generic missing env var (catch-all for tool output)
    (r'Please set the ([A-Z][A-Z0-9_]{2,}) environment variable|([A-Z][A-Z0-9_]{2,}) must be set|set ([A-Z][A-Z0-9_]{2,}) to',
     "diag_missing_env",
     "diag_missing_env_desc",
     [],
     ""),
]


def _emit_config_form(title: str, desc: str, fields: list, settings_group: str,
                      fired_key: str, fired: set):
    """Emit a config_prompt widget for interactive in-chat configuration."""
    if fired_key in fired:
        return
    fired.add(fired_key)
    action = f"settings_group::{settings_group}" if settings_group and settings_group != "claude_code_login" else "settings"
    save_action = "save_env_vars"
    # Enrich fields with current values from _state
    enriched = []
    for f in fields:
        sk = _ENV_TO_STATE.get(f["name"], f["name"].lower())
        cur = _state.get(sk, "")
        enriched.append({**f, "value": cur})
    _sid_emit("widget", {
        "type": "config_prompt",
        "title": title,
        "desc": desc,
        "fields": enriched,
        "settings_group": settings_group,
        "action": action,
        "save_action": save_action,
    })
    # Event sourcing: persist config error as domain event
    try:
        from dockfra.event_bus import get_bus, EventType
        get_bus().emit(EventType.CONFIG_ERROR, {
            "title": title, "settings_group": settings_group,
            "fields": [f["name"] for f in fields],
        }, src="health_monitor")
    except Exception:
        pass


_HEALTH_PATTERNS = [
    # (regex, severity, message_i18n_key, [solution_buttons with i18n label keys])
    (r"port is already allocated|bind for 0\.0\.0\.0:(\d+) failed",
     "err", "hp_port_conflict",
     [{"label":"diag_port_btn","value":"diag_port::__PORT__"},
      {"label":"change_port_btn","value":"settings"}]),
    (r"Bind for .+:(\d+) failed",
     "err", "hp_port_busy",
     [{"label":"diag_port_btn","value":"diag_port::__PORT__"}]),
    (r"permission denied",
     "err", "hp_no_perms",
     [{"label":"fix_perms_btn","value":"fix_docker_perms"}]),
    (r"no such file or directory",
     "err", "hp_no_file",
     [{"label":"settings","value":"settings"}]),
    (r"connection refused|connection reset by peer",
     "warn", "hp_conn_refused",
     [{"label":"launch_all_btn","value":"launch_all"}]),
    (r'variable .+? is not set|required.*not set|env.*missing',
     "err", "hp_missing_env",
     [{"label":"config_btn","value":"settings"}]),
    (r"unbound variable",
     "err", "hp_missing_env",
     [{"label":"config_btn","value":"settings"}]),
    (r"network .+? not found|network .+? declared as external",
     "err", "hp_no_network",
     [{"label":"launch_all_btn","value":"launch_all"}]),
    (r"oci runtime|oci error|cannot start container",
     "err", "hp_runtime_error",
     [{"label":"show_logs_btn","value":"pick_logs"}]),
    (r"health_status.*unhealthy|container.*unhealthy",
     "warn", "hp_unhealthy",
     [{"label":"show_logs_btn","value":"pick_logs"}]),
    (r"exec.*not found|executable file not found",
     "err", "hp_exec_not_found",
     [{"label":"rebuild_btn","value":"launch_all"}]),
    (r"Read-only file system",
     "err", "hp_readonly_vol",
     [{"label":"fix_vol_perms_btn","value":"fix_readonly_volume::__NAME__"},
      {"label":"settings","value":"settings"}]),
    (r"unable to initialize certificates resolver.*no storage",
     "err", "hp_traefik_acme",
     [{"label":"fix_acme_btn","value":"fix_acme_storage"},
      {"label":"config_btn","value":"settings"}]),
    (r"letsencrypt.*storage|acme.*storage|certificatesresolvers|ACME_STORAGE.*variable is not set",
     "warn", "hp_acme_storage",
     [{"label":"fix_acme_btn","value":"fix_acme_storage"},
      {"label":"settings","value":"settings"}]),
    (r"ACME_STORAGE.*not set|\"ACME_STORAGE\".*Defaulting",
     "warn", "hp_acme_not_set",
     [{"label":"fix_acme_btn","value":"fix_acme_storage"}]),
    (r"address already in use|listen.*address.*in use",
     "err", "hp_addr_in_use",
     [{"label":"diag_port_btn","value":"diag_port::__PORT__"}]),
    (r"host not found in upstream [\"']?([\w-]+)[\"']?",
     "err", "hp_nginx_upstream",
     [{"label":"launch_all_full_btn","value":"launch_all"}]),
    (r"no route to host|network.*unreachable",
     "err", "hp_no_route",
     [{"label":"launch_all_btn","value":"launch_all"}]),
    (r"Pool overlaps with other one on this address space|invalid pool request",
     "err", "hp_pool_overlap",
     [{"label":"remove_conflicting_network","value":"fix_network_overlap::__NETWORK__"},
      {"label":"clean_unused_networks","value":"fix_network_overlap::"}]),
]

def _docker_logs(name: str, tail: int = 40) -> str:
    """Get container logs — shell first, SDK fallback."""
    try:
        return subprocess.check_output(
            ["docker", "logs", "--tail", str(tail), name],
            text=True, stderr=subprocess.STDOUT)
    except Exception:
        cli = _docker_client()
        if not cli:
            raise RuntimeError("docker CLI and SDK both unavailable")
        try:
            raw = cli.containers.get(name).logs(tail=tail, timestamps=False)
            return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        except _docker_sdk.errors.NotFound:
            raise RuntimeError(f"Kontener `{name}` nie istnieje")


def _analyze_container_log(name: str) -> tuple[str, list]:
    """Read last 40 lines of a container log and return (finding_text, buttons)."""
    try:
        out = _docker_logs(name, tail=40)
    except Exception as e:
        return f"Nie można pobrać logów: {e}", []
    import re
    for pattern, sev, message, solutions in _HEALTH_PATTERNS:
        m = re.search(pattern, out, re.IGNORECASE)
        if m:
            port = m.group(1) if m.lastindex and m.group(1).isdigit() else ""
            fixed_btns = [
                {"label": _t_i18n(b["label"]), "value": b["value"].replace("__PORT__", port).replace("__NAME__", name)}
                for b in solutions
            ]
            # add LLM analysis button
            fixed_btns.append({"label":_t_i18n('analyze_with_ai'),"value":f"ai_analyze::{name}"})
            snippet = "\n".join(out.strip().splitlines()[-6:])
            _msg = _t_i18n(message) if message in _STRINGS else message
            return f"**{_msg}**\n```\n{snippet}\n```", fixed_btns
    # No known pattern — return last lines
    snippet = "\n".join(out.strip().splitlines()[-5:])
    return (_t_i18n('unknown_error_logs', snippet=snippet),
            [{"label":_t_i18n('analyze_with_ai'),"value":f"ai_analyze::{name}"},
             {"label":_t_i18n('show_full_logs'),"value":f"logs::{name}"}])
