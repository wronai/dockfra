#!/usr/bin/env python3
"""Dockfra Setup Wizard — http://localhost:5050"""
import os, json, subprocess, threading, time, socket as _socket, secrets as _secrets
from pathlib import Path
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

# Thread-local: when set, emit helpers target this SID instead of broadcasting
_tl = threading.local()

def _sid_emit(event, data):
    """Emit to current SID if inside a handler, broadcast otherwise."""
    sid = getattr(_tl, 'sid', None)
    if sid:
        socketio.emit(event, data, room=sid)
    else:
        socketio.emit(event, data)

ROOT = Path(__file__).parent.parent.resolve()
MGMT = ROOT / "management"
APP  = ROOT / "app"
DEVS = ROOT / "devices"
WIZARD_DIR = Path(__file__).parent
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
    """Load wizard/.env, create from .env.example if missing."""
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
    """Write updates to wizard/.env preserving comments and unknown keys."""
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

def run_cmd(cmd, cwd=None):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=str(cwd or ROOT))
    lines = []
    for line in proc.stdout:
        lines.append(line.rstrip())
        log_id = f"log-{len(_logs)}"
        _logs.append({"id": log_id, "text": line.rstrip(), "timestamp": time.time()})
        socketio.emit("log_line", {"id": log_id, "text": line.rstrip()})
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
    except: return []

def mask(k): return k[:12]+"..."+k[-4:] if len(k)>=16 else "***"

def msg(text, role="bot"):
    msg_id = f"msg-{len(_conversation)}"
    _conversation.append({"id": msg_id, "role": role, "text": text, "timestamp": time.time()})
    _sid_emit("message", {"id": msg_id, "role": role, "text": text}); time.sleep(0.04)
def widget(w):                      _sid_emit("widget",    w);                          time.sleep(0.04)
def buttons(items, label=""):       widget({"type":"buttons",  "label":label, "items":items})
def text_input(n,l,ph="",v="",sec=False,hint="",chips=None): widget({"type":"input","name":n,"label":l,"placeholder":ph,"value":v,"secret":sec,"hint":hint,"chips":chips or []})
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
    """Return [{ip, mac, iface}] from ARP cache / ip-neigh."""
    import re
    devices = []
    seen: set[str] = set()
    # ip neigh (Linux)
    try:
        out = subprocess.check_output(["ip","neigh"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.match(r'^(\d+\.\d+\.\d+\.\d+)\s+dev\s+(\S+).*lladdr\s+(\S+)', line)
            if m and m.group(1) not in seen:
                devices.append({"ip": m.group(1), "iface": m.group(2), "mac": m.group(3)})
                seen.add(m.group(1))
    except: pass
    # arp -a fallback
    if not devices:
        try:
            out = subprocess.check_output(["arp","-a"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                m = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                if m and m.group(1) not in seen and m.group(1) != "0.0.0.0":
                    devices.append({"ip": m.group(1), "iface": "", "mac": ""})
                    seen.add(m.group(1))
        except: pass
    return devices[:12]

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

    # ── Device IP ─────────────────────────────────────────────────────────────
    devices = _arp_devices()
    local_ips = set(_local_interfaces())
    # exclude own IPs and docker bridge 172.17.x.x from chips
    dev_chips = [{"label": f"{d['ip']}  {('— '+d['iface']) if d['iface'] else ''}".strip(),
                  "value": d["ip"]}
                 for d in devices if d["ip"] not in local_ips and not d["ip"].startswith("172.17.")]
    # Docker network subnets as hint
    docker_subnets: list[str] = []
    try:
        nets = subprocess.check_output(
            ["docker","network","ls","--format","{{.Name}}"],
            text=True, stderr=subprocess.DEVNULL).strip().splitlines()
        for net in nets:
            if net in ("bridge","host","none"): continue
            try:
                sub = subprocess.check_output(
                    ["docker","network","inspect", net,
                     "--format","{{range .IPAM.Config}}{{.Subnet}} {{end}}"],
                    text=True, stderr=subprocess.DEVNULL).strip()
                if sub: docker_subnets.extend(sub.split())
            except: pass
    except: pass
    hint_parts = []
    if dev_chips:    hint_parts.append(f"znaleziono {len(dev_chips)} urządzeń w ARP")
    if docker_subnets: hint_parts.append("Docker: " + ", ".join(docker_subnets[:3]))
    s["DEVICE_IP"] = {
        "value": "",
        "hint": " · ".join(hint_parts) if hint_parts else "wpisz IP urządzenia docelowego",
        "chips": dev_chips[:8],
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
        hint  = sug.get("hint", "")
        chips = sug.get("chips", [])
        if e["type"] == "select":
            opts = [{"label": lbl, "value": val} for val, lbl in e["options"]]
            select(e["key"], e["label"], opts, cur)
        else:
            text_input(e["key"], e["label"],
                       e.get("placeholder", ""), cur,
                       sec=(e["type"] == "password"), hint=hint, chips=chips)

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
            {"label": "📊 Status",               "value": "status"},
        ])
    else:
        msg("✅ Konfiguracja kompletna. Co chcesz zrobić?")
        buttons([
            {"label": "🚀 Uruchom infrastrukturę", "value": "launch_all"},
            {"label": "📦 Wdróż na urządzenie",     "value": "deploy_device"},
            {"label": "⚙️ Ustawienia (.env)",        "value": "settings"},
            {"label": "📊 Status",                   "value": "status"},
        ])

def step_status():
    _state["step"] = "status"
    clear_widgets()
    containers = docker_ps()
    if not containers:
        msg("⚠️ Brak uruchomionych kontenerów.")
        buttons([{"label":"🚀 Uruchom teraz","value":"launch_all"},{"label":"🏠 Menu","value":"back"}])
        return
    msg(f"**Uruchomione kontenery ({len(containers)}):**")
    status_row([{"name":c["name"],"ok":"Up" in c["status"],"detail":c["status"]} for c in containers])
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
        msg("Kliknij sekcję aby edytować jej zmienne. Wszystko zapisywane do `wizard/.env`.")
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
        for e in entries:
            sk = _ENV_TO_STATE.get(e["key"], e["key"].lower())
            cur = _state.get(sk, e.get("default", ""))
            if e["type"] == "select":
                opts = [{"label": lbl, "value": val} for val, lbl in e["options"]]
                select(e["key"], e["label"], opts, cur)
            else:
                text_input(e["key"], e["label"],
                           e.get("placeholder", ""), cur,
                           sec=(e["type"] == "password"))
        buttons([
            {"label": "💾 Zapisz",    "value": f"save_settings::{group}"},
            {"label": "← Sekcje",    "value": "settings"},
        ])


def step_save_settings(group: str, form: dict):
    """Save edited group back to _state and wizard/.env."""
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
    msg(f"✅ **{group}** — zapisano do `wizard/.env`")
    for e in entries:
        sk = _ENV_TO_STATE.get(e["key"], e["key"].lower())
        val = _state.get(sk, "")
        display = mask(val) if e["type"] == "password" and val else (val or "(puste)")
        msg(f"- `{e['key']}` = `{display}`")
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
    msg("✅ Zapisano i zaktualizowano `wizard/.env`.")
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
    select("stacks","Stacki do uruchomienia",[
        {"label":"Wszystkie (management + app + devices)","value":"all"},
        {"label":"Management","value":"management"},
        {"label":"App","value":"app"},
        {"label":"Devices","value":"devices"},
    ],"all")
    select("environment","Środowisko",[
        {"label":"Local","value":"local"},
        {"label":"Production","value":"production"},
    ],_state.get("environment","local"))
    buttons([{"label":"▶️ Uruchom","value":"do_launch"},{"label":"← Wróć","value":"back"}])

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
        analysis.append(f"❌ **Stack `{name}` nie uruchomił się** (exit code ≠ 0).")
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

    def run():
        subprocess.run(["docker","network","create","dockfra-shared"],capture_output=True)
        env_file_args = ["--env-file", str(WIZARD_ENV)] if WIZARD_ENV.exists() else []
        failed = []
        for name, path in targets:
            msg(f"▶️ **{name}**...")
            progress(f"Uruchamiam {name}...")
            rc, out = run_cmd(["docker","compose","-f",cf]+env_file_args+["up","-d","--build"],cwd=path)
            progress(f"{name}", done=(rc==0), error=(rc!=0))
            if rc == 0:
                msg(f"✅ **{name}** uruchomiony")
            else:
                failed.append((name, out))
                msg(f"❌ **{name}** — błąd (exit {rc})")

        if failed:
            msg("---")
            msg("## 🔍 Analiza błędów")
            for name, out in failed:
                analysis, solutions = _analyze_launch_error(name, out)
                msg(f"### Stack: `{name}`\n{analysis}")
                msg("Co chcesz zrobić?")
                buttons(solutions)
                time.sleep(0.1)
        else:
            msg("## ✅ Wszystkie stacki uruchomione!")
            containers = docker_ps()
            dockfra = [c for c in containers if "dockfra" in c["name"]]
            if dockfra:
                status_row([{"name":c["name"],"ok":"Up" in c["status"],"detail":c["status"]} for c in dockfra])
            socketio.emit("widget",{"type":"buttons","items":[
                {"label":"🔑 Setup GitHub + LLM","value":"post_launch_creds"},
                {"label":"📦 Wdróż na urządzenie","value":"deploy_device"},
                {"label":"📊 Status","value":"status"},
                {"label":"🏠 Menu","value":"back"},
            ]})
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
            {"label":"▶️ Uruchom devices stack","value":"launch_devices"},
            {"label":"📊 Status","value":"status"},{"label":"🏠 Menu","value":"back"}]})
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
        socketio.emit("widget",{"type":"buttons","items":[
            {"label":"📊 Status","value":"status"},{"label":"🏠 Menu","value":"back"}]})
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
        socketio.emit("widget",{"type":"buttons","items":[
            {"label":"📊 Status","value":"status"},{"label":"🏠 Menu","value":"back"}]})
    threading.Thread(target=run,daemon=True).start()

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
    clear_widgets()
    env_file = (MGMT if stack_name=="management" else APP if stack_name=="app" else DEVS) / ".env"
    msg(f"## 📄 Brakujące zmienne — `{stack_name}`")
    if env_file.exists():
        code_block(env_file.read_text())
    else:
        msg(f"Brak pliku `.env` w `{stack_name}/`")
        msg("Skopiuj plik `.env.example` lub użyj `make init` żeby go wygenerować.")
    buttons([
        {"label":"🔑 Skonfiguruj credentials","value":"setup_creds"},
        {"label":"🔄 Spróbuj ponownie","value":"retry_launch"},
        {"label":"🏠 Menu","value":"back"},
    ])


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


def fix_docker_perms():
    clear_widgets()
    msg("## 🔧 Naprawa uprawnień Docker")
    msg("Uruchom poniższe komendy na hoście, a następnie wyloguj się i zaloguj ponownie:")
    code_block("sudo usermod -aG docker $USER\nnewgrp docker")
    msg("Lub jeśli jesteś rootem, ustaw socket:")
    code_block("sudo chmod 666 /var/run/docker.sock")
    buttons([{"label":"🔄 Spróbuj ponownie","value":"retry_launch"},{"label":"🏠 Menu","value":"back"}])


STEPS = {
    "welcome":          lambda f: step_welcome(),
    "back":             lambda f: step_welcome(),
    "status":           lambda f: step_status(),
    "pick_logs":        lambda f: step_pick_logs(),
    "settings":         lambda f: step_settings(),
    "setup_creds":      lambda f: step_setup_creds(),
    "save_creds":       step_save_creds,
    "launch_all":       lambda f: step_launch_all(),
    "do_launch":        step_do_launch,
    "retry_launch":     lambda f: retry_launch(f),
    "deploy_device":    lambda f: step_deploy_device(),
    "test_device":      step_test_device,
    "do_deploy":        step_do_deploy,
    "launch_devices":   step_launch_devices,
    "post_launch_creds":lambda f: step_post_launch_creds(),
    "run_post_creds":   lambda f: step_run_post_creds(),
    "fix_docker_perms": lambda f: fix_docker_perms(),
    "fix_vnc_port":     lambda f: fix_vnc_port(),
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
        if value.startswith("diag_port::"):
            diag_port(value.split("::",1)[1]); return
        if value.startswith("show_missing_env::"):
            show_missing_env(value.split("::",1)[1]); return
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
        else:
            msg(f"⚠️ Nieznana akcja: `{value}`")
            buttons([{"label":"← Wróć","value":"back"}])
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

if __name__ == "__main__":
    print("🧙 Dockfra Wizard → http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
