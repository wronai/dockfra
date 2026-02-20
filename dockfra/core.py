"""Dockfra core — shared state, Flask app, UI helpers, env, docker utils."""
import os, json, re as _re, subprocess, threading, time, socket as _socket, secrets as _secrets, sys

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
    # Paths
    'ROOT', 'MGMT', 'APP', 'DEVS', 'WIZARD_DIR', 'WIZARD_ENV', '_PKG_DIR',
    # ENV
    'ENV_SCHEMA', '_schema_defaults', 'load_env', 'save_env',
    # Helpers
    'detect_config', '_emit_log_error', 'run_cmd', 'docker_ps',
    'mask', 'msg', 'widget', 'buttons', 'text_input', 'select',
    'code_block', 'status_row', 'progress', 'action_grid', 'clear_widgets',
    '_env_status_summary',
    '_arp_devices', '_devices_env_ip', '_docker_container_env',
    '_local_interfaces', '_subnet_ping_sweep',
    '_detect_suggestions', '_emit_missing_fields',
    # Health
    '_HEALTH_PATTERNS', '_docker_logs', '_analyze_container_log',
]
from collections import deque
from pathlib import Path
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

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

_WIZARD_SYSTEM_PROMPT = """
You are the Dockfra Setup Wizard assistant. Dockfra is a multi-stack Docker infrastructure
(management, app, devices) managed through this chat UI.
Help the user configure environment variables, troubleshoot Docker errors, understand
service roles, and launch stacks. Be concise and practical. Use Markdown.
Available stacks: management (ssh-manager, ssh-autopilot, ssh-monitor),
app (frontend, backend, db, redis, mobile-backend, desktop-app),
devices (ssh-rpi3, vnc-rpi3).
If asked about a Docker error, suggest the most likely fix.
"""

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

# Thread-local: when set, emit helpers target this SID instead of broadcasting
_tl = threading.local()

# Global log buffer (circular, last 2000 lines) for /api/logs/tail
_log_buffer: deque = deque(maxlen=2000)

def _sid_emit(event, data):
    """Emit to SID, or to collector (REST mode), or broadcast."""
    # REST API collector mode: capture all emitted events
    collector = getattr(_tl, 'collector', None)
    if collector is not None:
        collector.append({"event": event, "data": data})
    # Capture log lines to global buffer
    if event == "log_line":
        _log_buffer.append({"text": data.get("text",""), "ts": time.time()})
    # Emit via SocketIO unless in pure REST mode (no sid AND collector set)
    sid = getattr(_tl, 'sid', None)
    if sid:
        socketio.emit(event, data, room=sid)
    elif collector is None:
        socketio.emit(event, data)

_PKG_DIR   = Path(__file__).parent.resolve()
ROOT       = Path(os.environ.get("DOCKFRA_ROOT", str(_PKG_DIR.parent))).resolve()
MGMT       = ROOT / "management"
APP        = ROOT / "app"
DEVS       = ROOT / "devices"
WIZARD_DIR = _PKG_DIR
WIZARD_ENV = WIZARD_DIR / ".env"

# ── ENV schema ───────────────────────────────────────────────────────────────
# Each entry: key, label, group, type(text|password|select), placeholder,
#             required_for(list of stacks), options(for select), default
ENV_SCHEMA = [
    # Infrastructure
    {"key":"ENVIRONMENT",       "label":"Środowisko",           "group":"Infrastructure",
     "type":"select", "options":[("local","Local"),("production","Production")], "default":"local"},
    {"key":"STACKS",            "label":"Stacki do uruchomienia", "group":"Infrastructure",
     "type":"select", "options":[("all","Wszystkie"),("management","Management"),("app","App"),("devices","Devices")], "default":"all"},
    # Device SSH
    {"key":"DEVICE_IP",         "label":"IP urządzenia",         "group":"Device",
     "type":"text",  "placeholder":"192.168.1.100",              "default":"",
     "required_for":["deploy"]},
    {"key":"DEVICE_USER",       "label":"Użytkownik SSH",         "group":"Device",
     "type":"text",  "placeholder":"pi",                         "default":"pi"},
    {"key":"DEVICE_PORT",       "label":"Port SSH",               "group":"Device",
     "type":"text",  "placeholder":"22",                         "default":"22"},
    # Git
    {"key":"GIT_NAME",          "label":"Git user.name",          "group":"Git",
     "type":"text",  "placeholder":"Jan Kowalski",               "default":""},
    {"key":"GIT_EMAIL",         "label":"Git user.email",         "group":"Git",
     "type":"text",  "placeholder":"jan@example.com",            "default":""},
    {"key":"GITHUB_SSH_KEY",    "label":"Ścieżka klucza SSH",     "group":"Git",
     "type":"text",  "placeholder":"~/.ssh/id_ed25519",          "default":str(Path.home()/".ssh/id_ed25519")},
    # LLM
    {"key":"OPENROUTER_API_KEY","label":"OpenRouter API Key",     "group":"LLM",
     "type":"password","placeholder":"sk-or-v1-...",             "default":"",
     "required_for":["management"]},
    {"key":"LLM_MODEL",         "label":"Model LLM",              "group":"LLM",
     "type":"select", "options":[
         ("google/gemini-flash-1.5",   "Gemini Flash 1.5"),
         ("google/gemini-2.0-flash-001","Gemini 2.0 Flash"),
         ("anthropic/claude-3-5-haiku","Claude 3.5 Haiku"),
         ("openai/gpt-4o-mini",        "GPT-4o Mini"),
         ("openai/gpt-4o",             "GPT-4o"),
     ], "default":"google/gemini-flash-1.5"},
    # App stack
    {"key":"POSTGRES_USER",     "label":"PostgreSQL user",        "group":"App",
     "type":"text",  "placeholder":"dockfra",                    "default":"dockfra",
     "required_for":["app"]},
    {"key":"POSTGRES_PASSWORD", "label":"PostgreSQL password",    "group":"App",
     "type":"password","placeholder":"hasło",                   "default":"",
     "required_for":["app"]},
    {"key":"POSTGRES_DB",       "label":"PostgreSQL database",    "group":"App",
     "type":"text",  "placeholder":"dockfra",                    "default":"dockfra",
     "required_for":["app"]},
    {"key":"REDIS_PASSWORD",    "label":"Redis password",          "group":"App",
     "type":"password","placeholder":"hasło",                   "default":""},
    {"key":"SECRET_KEY",        "label":"App SECRET_KEY",          "group":"App",
     "type":"password","placeholder":"losowy klucz",            "default":"",
     "required_for":["app"]},
    {"key":"APP_NAME",          "label":"Nazwa aplikacji",         "group":"App",
     "type":"text",  "placeholder":"dockfra",                    "default":"dockfra"},
    {"key":"APP_VERSION",       "label":"Wersja aplikacji",        "group":"App",
     "type":"text",  "placeholder":"0.1.0",                      "default":"0.1.0"},
    {"key":"DEPLOY_MODE",       "label":"Deploy mode",            "group":"App",
     "type":"select", "options":[("local","Local"),("production","Production")], "default":"local"},
    # Ports
    {"key":"VNC_RPI3_PORT",     "label":"Port VNC RPi3",           "group":"Ports",
     "type":"text",  "placeholder":"6080",                       "default":"6080"},
    {"key":"DESKTOP_VNC_PORT",  "label":"Port Desktop VNC",        "group":"Ports",
     "type":"text",  "placeholder":"6081",                       "default":"6081"},
    {"key":"WIZARD_PORT",       "label":"Port Wizarda",            "group":"Ports",
     "type":"text",  "placeholder":"5050",                       "default":"5050"},
]

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
app.config["SECRET_KEY"] = "dockfra-wizard"
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

# mapping: ENV key → _state key (lowercase)
_ENV_TO_STATE = {
    "ENVIRONMENT":       "environment",
    "STACKS":            "stacks",
    "DEVICE_IP":         "device_ip",
    "DEVICE_USER":       "device_user",
    "DEVICE_PORT":       "device_port",
    "GIT_NAME":          "git_name",
    "GIT_EMAIL":         "git_email",
    "GITHUB_SSH_KEY":    "github_key",
    "OPENROUTER_API_KEY":"openrouter_key",
    "LLM_MODEL":         "llm_model",
    "POSTGRES_USER":     "postgres_user",
    "POSTGRES_PASSWORD": "postgres_password",
    "POSTGRES_DB":       "postgres_db",
    "REDIS_PASSWORD":    "redis_password",
    "SECRET_KEY":        "secret_key",
    "APP_NAME":          "app_name",
    "APP_VERSION":       "app_version",
    "DEPLOY_MODE":       "deploy_mode",
    "VNC_RPI3_PORT":     "vnc_rpi3_port",
    "DESKTOP_VNC_PORT":  "desktop_vnc_port",
    "WIZARD_PORT":       "wizard_port",
}
_STATE_TO_ENV = {v: k for k, v in _ENV_TO_STATE.items()}

def reset_state():
    global _state, _conversation, _logs
    env = load_env()
    _state = {"step": "welcome"}
    for env_key, state_key in _ENV_TO_STATE.items():
        _state[state_key] = env.get(env_key, "")
    _conversation = []
    _logs = []

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

def _emit_log_error(line: str, fired: set):
    """Check a single log line against _HEALTH_PATTERNS; emit chat alert if matched (debounced)."""
    import re as _re
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
        # extract network name for pool-overlap errors
        _nm = _re.search(r"failed to create network ([\w_-]+)", line)
        if _nm:
            network = _nm.group(1)
        icon = "🔴" if sev == "err" else "🟡"
        btns = []
        for b in solutions:
            val = b["value"].replace("__PORT__", port).replace("__NETWORK__", network)
            if "__NAME__" in val:
                continue  # skip container-specific buttons during build stream
            btns.append({**b, "value": val})
        _sid_emit("message", {"role": "bot",
                               "text": f"{icon} **{message}**\n`{line.strip()[:160]}`"})

        # ── Inline forms for known fixable patterns ─────────────────────────
        btn_values = " ".join(b["value"] for b in btns)

        if "fix_acme_storage" in btn_values:
            # Propose ACME_STORAGE path with smart default
            cur = _state.get("acme_storage", "letsencrypt/acme.json")
            _sid_emit("widget", {"type": "input", "name": "ACME_STORAGE",
                                 "label": "Ścieżka ACME storage (traefik)",
                                 "placeholder": "letsencrypt/acme.json",
                                 "value": cur, "secret": False, "hint":
                                 "Plik acme.json zostanie utworzony automatycznie.",
                                 "chips": [], "modal_type": ""})
            _sid_emit("widget", {"type": "buttons", "items": [
                {"label": "✅ Zastosuj i napraw traefik", "value": "fix_acme_storage"},
                {"label": "⚙️ Ustawienia", "value": "settings"},
            ]})

        elif "fix_network_overlap::" in btn_values and network:
            # Show network removal with specific name pre-filled
            _sid_emit("widget", {"type": "buttons", "items": [
                {"label": f"🔧 Usuń sieć `{network}`",  "value": f"fix_network_overlap::{network}"},
                {"label": "🧹 Wyczyść wszystkie sieci", "value": "fix_network_overlap::"},
            ]})

        elif "fix_network_overlap::" in btn_values and not network:
            _sid_emit("widget", {"type": "buttons", "items": btns})

        elif "variable is not set" in line or "Defaulting to a blank string" in line:
            # Extract var name and propose inline input
            _mv = _re.search(r'"([A-Z_]{3,})" variable is not set', line)
            if _mv:
                var = _mv.group(1)
                _sid_emit("widget", {"type": "input", "name": var,
                                     "label": var, "placeholder": "",
                                     "value": _state.get(var.lower(), ""),
                                     "secret": "KEY" in var or "PASSWORD" in var or "SECRET" in var,
                                     "hint": f"Ustaw wartość zmiennej `{var}`",
                                     "chips": [], "modal_type": ""})
                _sid_emit("widget", {"type": "buttons", "items": [
                    {"label": f"💾 Zapisz {var}", "value": f"save_settings::General"},
                ]})
            else:
                if btns:
                    _sid_emit("widget", {"type": "buttons", "items": btns})

        else:
            if btns:
                _sid_emit("widget", {"type": "buttons", "items": btns})

        break  # one alert per line

def run_cmd(cmd, cwd=None):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=str(cwd or ROOT))
    lines = []
    _fired: set = set()
    for line in proc.stdout:
        text = line.rstrip()
        lines.append(text)
        log_id = f"log-{len(_logs)}"
        _logs.append({"id": log_id, "text": text, "timestamp": time.time()})
        _sid_emit("log_line", {"id": log_id, "text": text})
        _emit_log_error(text, _fired)
    proc.wait()
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
def text_input(n,l,ph="",v="",sec=False,hint="",chips=None,modal_type=""): widget({"type":"input","name":n,"label":l,"placeholder":ph,"value":v,"secret":sec,"hint":hint,"chips":chips or [],"modal_type":modal_type})
def select(n,l,opts,v=""):          widget({"type":"select",   "name":n,"label":l,"options":opts,"value":v})
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
        return f"⚠️ Brakuje: `{'`, `'.join(missing[:4])}{'...' if len(missing)>4 else ''}`"
    return "✅ Konfiguracja kompletna"


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

def _detect_suggestions() -> dict:
    """Auto-detect suggested values for form fields. Returns {key: {value, hint, chips}}."""
    s: dict[str, dict] = {}

    # ── Git config ────────────────────────────────────────────────────────────
    for key, cmd in [("GIT_NAME",  ["git","config","--global","user.name"]),
                     ("GIT_EMAIL", ["git","config","--global","user.email"])]:
        try:
            v = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            if v: s[key] = {"value": v, "hint": f"z ~/.gitconfig"}
        except: pass

    # ── SSH keys ──────────────────────────────────────────────────────────────
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

    # ── OpenRouter key ────────────────────────────────────────────────────────
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        s["OPENROUTER_API_KEY"] = {"value": or_key, "hint": "z zmiennej środowiskowej"}

    # ── Random secrets ────────────────────────────────────────────────────────
    for key, n in [("POSTGRES_PASSWORD", 12), ("REDIS_PASSWORD", 12), ("SECRET_KEY", 32)]:
        gens = [_secrets.token_urlsafe(n) for _ in range(3)]
        s[key] = {"value": "", "hint": "kliknij chip aby wstawić",
                  "chips": [{"label": g, "value": g} for g in gens]}

    # ── Device IP (priority chain) ────────────────────────────────────────────
    local_ips = set(_local_interfaces())
    def _is_docker_internal(ip: str) -> bool:
        p = ip.split(".")
        if len(p) != 4: return False
        a, b = int(p[0]), int(p[1])
        return (a == 172 and 16 <= b <= 31) or (a == 10 and b in (0, 1, 88, 89))

    # L1: devices stack env files
    env_ip = _devices_env_ip()
    # L2: running devices-stack container
    docker_ip = ""
    for cname in ["dockfra-ssh-rpi3", "ssh-rpi3"]:
        docker_ip = _docker_container_env(cname, "RPI3_HOST")
        if docker_ip: break
    best_ip = env_ip or docker_ip or ""

    # L3: ARP cache — REACHABLE first, icons by state
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

    # ── App name from project path ────────────────────────────────────────────
    project_name = ROOT.name.lower().replace("-","_")
    s["APP_NAME"]     = {"value": project_name, "hint": f"z nazwy katalogu: {ROOT.name}"}
    s["POSTGRES_DB"]  = {"value": project_name, "hint": "zwykle = APP_NAME"}
    s["POSTGRES_USER"]= {"value": project_name, "hint": "zwykle = APP_NAME"}

    # ── App version from git tag ──────────────────────────────────────────────
    try:
        tag = subprocess.check_output(
            ["git","describe","--tags","--abbrev=0"],
            text=True, stderr=subprocess.DEVNULL, cwd=str(ROOT)).strip().lstrip("v")
        if tag: s["APP_VERSION"] = {"value": tag, "hint": f"ostatni git tag: v{tag}"}
    except: pass

    # ── Free port suggestions ─────────────────────────────────────────────────
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
            select(e["key"], e["label"], opts, cur)
        else:
            text_input(e["key"], e["label"],
                       e.get("placeholder", ""), cur,
                       sec=(e["type"] == "password"), hint=hint, chips=chips,
                       modal_type=modal_type)


_HEALTH_PATTERNS = [
    # (regex, severity, message_pl, [solution_buttons])
    (r"port is already allocated|bind for 0\.0\.0\.0:(\d+) failed",
     "err", "Konflikt portu — inny proces zajmuje port",
     [{"label":"🔍 Diagnozuj port","value":"diag_port::__PORT__"},
      {"label":"⚙️ Zmień port","value":"settings"}]),
    (r"Bind for .+:(\d+) failed",
     "err", "Port zajęty",
     [{"label":"🔍 Diagnozuj port","value":"diag_port::__PORT__"}]),
    (r"permission denied",
     "err", "Brak uprawnień — Docker może wymagać sudo lub grupy docker",
     [{"label":"🔧 Napraw uprawnienia","value":"fix_docker_perms"}]),
    (r"no such file or directory",
     "err", "Brak pliku lub katalogu — sprawdź ścieżki woluminów",
     [{"label":"⚙️ Ustawienia","value":"settings"}]),
    (r"connection refused|connection reset by peer",
     "warn", "Odmowa połączenia — zależna usługa może nie być gotowa",
     [{"label":"🔄 Uruchom ponownie","value":"launch_all"}]),
    (r'variable .+? is not set|required.*not set|env.*missing',
     "err", "Brakuje zmiennej środowiskowej",
     [{"label":"⚙️ Konfiguracja","value":"settings"}]),
    (r"network .+? not found|network .+? declared as external",
     "err", "Brak sieci Docker — uruchom `docker network create dockfra-shared`",
     [{"label":"🚀 Uruchom ponownie","value":"launch_all"}]),
    (r"oci runtime|oci error|cannot start container",
     "err", "Błąd Docker runtime",
     [{"label":"🐋 Pokaż logi","value":"pick_logs"}]),
    (r"health_status.*unhealthy|container.*unhealthy",
     "warn", "Kontener niezdrowy (healthcheck nie przechodzi)",
     [{"label":"📋 Pokaż logi","value":"pick_logs"}]),
    (r"exec.*not found|executable file not found",
     "err", "Nie znaleziono wykonywalnego pliku w obrazie",
     [{"label":"🔧 Przebuduj","value":"launch_all"}]),
    (r"Read-only file system",
     "err", "Wolumin zamontowany jako read-only — napraw uprawnienia lub sprawdź `volumes:`",
     [{"label":"🔧 Napraw uprawnienia woluminu","value":"fix_readonly_volume::__NAME__"},
      {"label":"⚙️ Ustawienia","value":"settings"}]),
    (r"unable to initialize certificates resolver.*no storage",
     "err", "Traefik: brak ścieżki certyfikatów ACME — napraw automatycznie lub ustaw ręcznie",
     [{"label":"🔧 Napraw ACME storage","value":"fix_acme_storage"},
      {"label":"⚙️ Konfiguracja","value":"settings"}]),
    (r"letsencrypt.*storage|acme.*storage|certificatesresolvers|ACME_STORAGE.*variable is not set",
     "warn", "Traefik ACME/Let's Encrypt: brakuje konfiguracji storage",
     [{"label":"🔧 Napraw ACME storage","value":"fix_acme_storage"},
      {"label":"⚙️ Ustawienia","value":"settings"}]),
    (r"ACME_STORAGE.*not set|\"ACME_STORAGE\".*Defaulting",
     "warn", "Traefik: `ACME_STORAGE` nie ustawiony — certyfikaty nie będą działać",
     [{"label":"🔧 Napraw ACME storage","value":"fix_acme_storage"}]),
    (r"address already in use|listen.*address.*in use",
     "err", "Port zajęty przez inny proces",
     [{"label":"🔍 Diagnozuj port","value":"diag_port::__PORT__"}]),
    (r"host not found in upstream [\"']?([\w-]+)[\"']?",
     "err", "nginx: nie można znaleźć upstream — zależna usługa nie działa lub jest w innej sieci",
     [{"label":"🚀 Uruchom wszystko","value":"launch_all"}]),
    (r"no route to host|network.*unreachable",
     "err", "Brak trasy do hosta — sprawdź sieci Docker",
     [{"label":"🚀 Uruchom ponownie","value":"launch_all"}]),
    (r"Pool overlaps with other one on this address space|invalid pool request",
     "err", "Konflikt przestrzeni adresowej sieci Docker — stara sieć blokuje tworzenie nowej",
     [{"label":"🔧 Usuń konfikującą sieć","value":"fix_network_overlap::__NETWORK__"},
      {"label":"🧹 Wyczyść wszystkie sieci","value":"fix_network_overlap::"}]),
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
                {**b, "value": b["value"].replace("__PORT__", port).replace("__NAME__", name)}
                for b in solutions
            ]
            # add LLM analysis button
            fixed_btns.append({"label":"🧠 Analizuj z AI","value":f"ai_analyze::{name}"})
            snippet = "\n".join(out.strip().splitlines()[-6:])
            return f"**{message}**\n```\n{snippet}\n```", fixed_btns
    # No known pattern — return last lines
    snippet = "\n".join(out.strip().splitlines()[-5:])
    return (f"Nieznany błąd — ostatnie logi:\n```\n{snippet}\n```",
            [{"label":"🧠 Analizuj z AI","value":f"ai_analyze::{name}"},
             {"label":"📋 Pokaż pełne logi","value":f"logs::{name}"}])
