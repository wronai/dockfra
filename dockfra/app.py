#!/usr/bin/env python3
"""Dockfra Setup Wizard — http://localhost:5050"""
import os, json, re as _re, subprocess, threading, time, socket as _socket, secrets as _secrets, sys
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

def step_welcome():
    _state["step"] = "welcome"
    cfg = detect_config()
    _state.update({k:v for k,v in cfg.items() if v})
    msg("# 👋 Dockfra Setup Wizard")
    all_missing = [e for e in ENV_SCHEMA
                   if e.get("required_for")
                   and not _state.get(_ENV_TO_STATE.get(e["key"], e["key"].lower()))]
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
                select(e["key"], e["label"], opts, cur)
            else:
                text_input(e["key"], e["label"],
                           e.get("placeholder", ""), cur,
                           sec=(e["type"] == "password"),
                           hint=sug.get("hint", ""),
                           chips=sug.get("chips", []),
                           modal_type="ip_picker" if e["key"] == "DEVICE_IP" else "")
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
    select("LLM_MODEL","Model LLM", opts, _state.get("llm_model","google/gemini-flash-1.5"))
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

    if "pull access denied" in lines or "not found" in lines and "image" in lines:
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

    target_names = ["management","app","devices"] if stacks == "all" else [stacks]
    # Pre-flight: check for missing required vars
    if step_preflight_fill(target_names):
        return  # form shown, wait for user

    cf = "docker-compose.yml" if env == "local" else "docker-compose-production.yml"
    targets = []
    if stacks in ("all","management"): targets.append(("management",MGMT))
    if stacks in ("all","app"):        targets.append(("app",APP))
    if stacks in ("all","devices"):    targets.append(("devices",DEVS))

    _launch_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _launch_sid  # propagate SID so _emit_log_error targets the right client
        subprocess.run(["docker","network","create","dockfra-shared"],capture_output=True)
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
                fix_btns.append({"label": f"🔧 Napraw {c['name'].replace('dockfra-','')}", "value": f"fix_container::{c['name']}"})
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
            if "dockfra-desktop" in running_names:
                sections.append(
                    f"### 🖥️ Desktop (noVNC)  [http://localhost:{vnc_port}](http://localhost:{vnc_port})\n"
                    "Przeglądarkowy pulpit z podglądem dashboardu i logów."
                )
            if sections:
                msg("---\n## 🗺️ Co możesz teraz zrobić?\n\n" + "\n\n".join(sections))
            # Build buttons dynamically from discovered roles
            post_btns = []
            for role, ri in _SSH_ROLES.items():
                p = _state.get(f"SSH_{role.upper()}_PORT", ri["port"])
                post_btns.append({"label": f"{ri['icon']} SSH {role.capitalize()}", "value": f"ssh_info::{role}::{p}"})
            post_btns += [
                {"label": "🔑 Setup GitHub + LLM",  "value": "post_launch_creds"},
                {"label": "📦 Wdróż na urządzenie", "value": "deploy_device"},
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
        container = "dockfra-ssh-developer"
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
        subprocess.run(["docker","network","create","dockfra-shared"],capture_output=True)
        progress("Uruchamiam devices...")
        rc, _ = run_cmd(["docker","compose","up","-d","--build"],cwd=DEVS)
        progress("devices",done=(rc==0),error=(rc!=0))
        if rc==0:
            msg("✅ Devices stack uruchomiony!")
            msg("📺 VNC: http://localhost:6080")
            msg("🔒 SSH-RPi3: `ssh deployer@localhost -p 2224`")
        else:
            msg("❌ Błąd uruchamiania devices stack")
    threading.Thread(target=run,daemon=True).start()

def step_post_launch_creds():
    clear_widgets()
    container = "dockfra-ssh-developer"
    if container not in [c["name"] for c in docker_ps()]:
        msg(f"❌ `{container}` nie działa.")
        buttons([{"label":"🚀 Uruchom stacki","value":"launch_all"},{"label":"← Wróć","value":"back"}]); return
    msg("## 🔑 Setup GitHub + LLM w developer")
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
               "DEVELOPER_CONTAINER":"dockfra-ssh-developer","DEVELOPER_USER":"developer",
               "GITHUB_SSH_KEY":_state.get("github_key",str(Path.home()/".ssh/id_ed25519")),
               "LLM_MODEL":_state.get("llm_model","google/gemini-3-flash-preview"),
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

def step_fix_container(name: str):
    """Interactive fix wizard for a failing container.
    1st attempt: algorithmic diagnosis + fix options.
    2nd+ attempt: auto-trigger LLM analysis.
    """
    clear_widgets()
    attempts = _state.setdefault("fix_attempts", {})
    attempts[name] = attempts.get(name, 0) + 1
    attempt = attempts[name]

    msg(f"## 🔧 Naprawianie: `{name}` (próba #{attempt})")

    # Get current container status
    containers = docker_ps()
    cinfo = next((c for c in containers if c["name"] == name), None)
    status_txt = cinfo["status"] if cinfo else "nieznany"
    msg(f"**Stan:** {status_txt}")

    finding, btns = _analyze_container_log(name)

    if attempt >= 2:
        # Repeat failure → escalate to LLM immediately
        msg(f"⚠️ To już **{attempt}. próba** naprawy tego kontenera. Uruchamiam analizę AI...")
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
            progress("🧠 AI analizuje problem...")
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
    btns.append({"label": "🔄 Restart kontenera",    "value": f"restart_container::{name}"})
    btns.append({"label": "💡 Zaproponuj komendy",   "value": f"suggest_commands::{name}"})
    btns.append({"label": "🧠 Analizuj z AI",        "value": f"ai_analyze::{name}"})
    msg("Co chcesz zrobić?")
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
            msg(f"❌ Nie można pobrać logów: {e}"); return
        progress("🧠 AI analizuje i generuje komendy...")
        result = _llm_suggest_commands(name, logs)
        progress("🧠 AI", done=True)
        diagnosis = result.get("diagnosis", "")
        commands  = result.get("commands", [])
        if diagnosis:
            msg(f"**Diagnoza:** {diagnosis}")
        if not commands:
            msg("⚠️ Brak konkretnych komend — spróbuj pełnej analizy AI.")
            buttons([{"label": "🧠 Pełna analiza AI", "value": f"ai_analyze::{name}"}])
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
            {"label":"🔄 Spróbuj ponownie","value":"retry_launch"},
            {"label":"🏠 Menu","value":"back"},
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
        for e in missing:
            if e["type"] == "select":
                opts = [{"label": lbl, "value": val} for val, lbl in e["options"]]
                select(e["key"], e["label"], opts, e.get("default", ""))
            else:
                text_input(e["key"], e["label"],
                           e.get("placeholder", ""),
                           _state.get(_ENV_TO_STATE.get(e["key"], ""), ""),
                           sec=(e["type"] == "password"))
        buttons([
            {"label": "✅ Zapisz i uruchom",  "value": f"preflight_save_launch::{stack_name}"},
            {"label": "⚙️ Pełne ustawienia",   "value": "settings"},
        ])
    else:
        env_file = (MGMT if stack_name=="management" else APP if stack_name=="app" else DEVS) / ".env"
        if env_file.exists():
            msg("Nie znaleziono brakujących znanych zmiennych. Zawartość pliku `.env`:")
            code_block(env_file.read_text())
        else:
            msg(f"Brak pliku `.env` w `{stack_name}/`")
        buttons([
            {"label": "🔑 Skonfiguruj credentials", "value": "setup_creds"},
            {"label": "🔄 Spróbuj ponownie",         "value": "retry_launch"},
        ])


def _prompt_api_key(return_action: str = ""):
    """Show inline form to enter OPENROUTER_API_KEY when LLM is unavailable."""
    msg("⚠️ **Brakuje klucza API** — skonfiguruj `OPENROUTER_API_KEY` poniżej:")
    text_input("OPENROUTER_API_KEY", "OpenRouter API Key",
               "sk-or-v1-...", _state.get("openrouter_key", ""), sec=True)
    opts = [{"label": lbl, "value": val}
            for val, lbl in next(e["options"] for e in ENV_SCHEMA if e["key"] == "LLM_MODEL")]
    select("LLM_MODEL", "Model LLM", opts, _state.get("llm_model", "google/gemini-flash-1.5"))
    btn_items = [{"label": "✅ Zapisz klucz", "value": "save_creds"}]
    if return_action:
        btn_items.append({"label": "🧠 Powtórz analizę", "value": return_action})
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
                        buttons([{"label": "🔄 Spróbuj ponownie", "value": "retry_launch"}])
                        return
                else:
                    msg(f"❌ {err}")
                    buttons([{"label": "🔄 Spróbuj ponownie", "value": "retry_launch"}])
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

    msg("🔄 Restartuję `dockfra-traefik`...")
    _tl_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _tl_sid
        try:
            subprocess.check_output(["docker", "restart", "dockfra-traefik"],
                                    text=True, stderr=subprocess.STDOUT)
            msg("✅ `dockfra-traefik` zrestartowany.")
        except Exception as shell_err:
            cli = _docker_client()
            if cli:
                try:
                    cli.containers.get("dockfra-traefik").restart()
                    msg("✅ `dockfra-traefik` zrestartowany przez SDK.")
                except Exception as sdk_err:
                    msg(f"⚠️ Restart nie powiódł się: {sdk_err}")
            else:
                msg(f"⚠️ {shell_err}")
        time.sleep(5)
        all_c = docker_ps()
        c = next((c for c in all_c if c["name"] == "dockfra-traefik"), None)
        if c:
            ok = "Up" in c["status"] and "Restarting" not in c["status"]
            icon = "✅" if ok else "🔴"
            msg(f"{icon} `dockfra-traefik`: {c['status']}")
        buttons([{"label": "🔄 Uruchom wszystko", "value": "retry_launch"},
                 {"label": "⚙️ Ustawienia",      "value": "settings"}])
        _tl.sid = None
    threading.Thread(target=run, daemon=True).start()


def fix_readonly_volume(container: str = ""):
    """Find read-only volume mounts for a container and fix host directory permissions."""
    clear_widgets()
    cname = container or "dockfra-ssh-developer"
    msg(f"## 🔧 Naprawiam uprawnienia woluminów — `{cname}`")
    _tl_sid = getattr(_tl, 'sid', None)
    def run():
        _tl.sid = _tl_sid
        # Get mount info via docker inspect
        try:
            raw = subprocess.check_output(
                ["docker", "inspect", "--format",
                 "{{range .Mounts}}{{.Source}}:{{.Destination}}:{{.RW}}\n{{end}}", cname],
                text=True, stderr=subprocess.STDOUT).strip()
        except Exception:
            cli = _docker_client()
            if not cli:
                msg("❌ Nie można pobrać informacji o montowaniach."); return
            try:
                attrs = cli.containers.get(cname).attrs
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
    msg("## 🔧 Naprawa uprawnień Docker")
    msg("Uruchom poniższe komendy na hoście, a następnie wyloguj się i zaloguj ponownie:")
    code_block("sudo usermod -aG docker $USER\nnewgrp docker")
    msg("Lub jeśli jesteś rootem, ustaw socket:")
    code_block("sudo chmod 666 /var/run/docker.sock")
    buttons([{"label":"🔄 Spróbuj ponownie","value":"retry_launch"},{"label":"🏠 Menu","value":"back"}])


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
        if value.startswith("logs::"):
            step_show_logs(value.split("::",1)[1]); return
        if value.startswith("fix_container::"):
            step_fix_container(value.split("::",1)[1]); return
        if value.startswith("fix_network_overlap::"):
            fix_network_overlap(value.split("::",1)[1]); return
        if value.startswith("fix_readonly_volume::"):
            fix_readonly_volume(value.split("::",1)[1]); return
        if value.startswith("ssh_info::"):
            _step_ssh_info(value); return
        if value.startswith("ssh_console::"):
            step_ssh_console(value); return
        if value.startswith("run_ssh_cmd::"):
            run_ssh_cmd(value, form); return
        if value.startswith("suggest_commands::"):
            step_suggest_commands(value.split("::",1)[1]); return
        if value.startswith("run_suggested_cmd::"):
            _run_suggested_cmd(value.split("::",1)[1]); return
        if value.startswith("restart_container::"):
            _do_restart_container(value.split("::",1)[1]); return
        if value.startswith("diag_port::"):
            diag_port(value.split("::",1)[1]); return
        if value.startswith("show_missing_env::"):
            show_missing_env(value.split("::",1)[1]); return
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
        if value.startswith("logs_stack::"):
            step_show_logs(value.split("::",1)[1]); return
        if value.startswith("fix_compose::"):
            msg(f"ℹ️ Plik `{value.split('::',1)[1]}/docker-compose.yml` ma błąd — sprawdź sieć lub usługi.")
            buttons([{"label":"📋 Pokaż logi","value":f"logs_stack::{value.split('::',1)[1]}"},{"label":"← Wróć","value":"back"}]); return
        if value.startswith("settings_group::"):
            step_settings(value.split("::",1)[1]); return
        if value.startswith("save_settings::"):
            step_save_settings(value.split("::",1)[1], form); return
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
            return
        handler = STEPS.get(value)
        if handler:
            handler(form)
        elif value.strip():
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
                                  history=history[:-1])  # last is current msg
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
    COMMON_PORTS = [22, 80, 443, 2200, 2201, 2202, 2203, 2222,
                    3000, 5000, 6080, 8000, 8080, 8081, 8082, 8100, 8202, 9000]

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

def _run_action_sync(value: str, form: dict, timeout: float = 30.0) -> list[dict]:
    """Run a wizard action synchronously (for REST API). Returns collected events."""
    _tl.collector = []
    _tl.sid = None
    try:
        # Inline the same dispatch logic as on_action
        if value.startswith("logs::"):        step_show_logs(value.split("::",1)[1])
        elif value.startswith("diag_port::"): diag_port(value.split("::",1)[1])
        elif value.startswith("settings_group::"): step_settings(value.split("::",1)[1])
        elif value.startswith("save_settings::"): step_save_settings(value.split("::",1)[1], form)
        elif value.startswith("ai_analyze::"):
            name = value.split("::",1)[1]
            try:
                out = subprocess.check_output(["docker","logs","--tail","60",name],
                                              text=True, stderr=subprocess.STDOUT)
            except Exception as e:
                msg(f"❌ {e}"); out = ""
            if out:
                reply = _llm_chat(out[-3000:], system_prompt=_WIZARD_SYSTEM_PROMPT)
                msg(f"### 🧠 AI: `{name}`\n{reply}")
        else:
            handler = STEPS.get(value)
            if handler:
                handler(form)
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
