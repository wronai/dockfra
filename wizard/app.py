#!/usr/bin/env python3
"""Dockfra Setup Wizard — http://localhost:5050"""
import os, json, subprocess, threading, time
from pathlib import Path
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

ROOT = Path(__file__).parent.parent.resolve()
MGMT = ROOT / "management"
APP  = ROOT / "app"
DEVS = ROOT / "devices"

app = Flask(__name__)
app.config["SECRET_KEY"] = "dockfra-wizard"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", manage_session=False)

_state: dict = {}

def reset_state():
    global _state
    _state = {
        "step": "welcome",
        "environment": "local",
        "device_ip": "", "device_user": "pi", "device_port": "22",
        "github_key": str(Path.home() / ".ssh/id_ed25519"),
        "openrouter_key": "", "llm_model": "google/gemini-3-flash-preview",
        "git_name": "", "git_email": "",
    }

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
        socketio.emit("log_line", {"text": line.rstrip()})
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

def msg(text, role="bot"):          socketio.emit("message",  {"role":role, "text":text}); time.sleep(0.04)
def widget(w):                      socketio.emit("widget",    w);                          time.sleep(0.04)
def buttons(items, label=""):       widget({"type":"buttons",  "label":label, "items":items})
def text_input(n,l,ph="",v="",sec=False): widget({"type":"input","name":n,"label":l,"placeholder":ph,"value":v,"secret":sec})
def select(n,l,opts,v=""):          widget({"type":"select",   "name":n,"label":l,"options":opts,"value":v})
def code_block(t):                  widget({"type":"code",     "text":t})
def status_row(items):              widget({"type":"status_row","items":items})
def progress(label, done=False, error=False): widget({"type":"progress","label":label,"done":done,"error":error})
def clear_widgets():                socketio.emit("clear_widgets")

# ── steps ────────────────────────────────────────────────────────────────────
def step_welcome():
    _state["step"] = "welcome"
    cfg = detect_config()
    _state.update({k:v for k,v in cfg.items() if v})
    msg("# 👋 Dockfra Setup Wizard")
    msg("Jestem Twoim asystentem konfiguracji. Co chcesz zrobić?")
    buttons([
        {"label":"🚀 Uruchom infrastrukturę",  "value":"launch_all"},
        {"label":"📦 Wdróż na urządzenie",      "value":"deploy_device"},
        {"label":"📊 Status kontenerów",         "value":"status"},
        {"label":"🔑 Konfiguruj credentials",   "value":"setup_creds"},
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
    buttons([{"label":"🔄 Odśwież","value":"status"},{"label":"📋 Logi","value":"pick_logs"},{"label":"🏠 Menu","value":"back"}])

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
    buttons([{"label":"🔄 Odśwież","value":f"logs::{container}"},{"label":"← Inne logi","value":"pick_logs"},{"label":"🏠 Menu","value":"back"}])

def step_setup_creds():
    _state["step"] = "setup_creds"
    clear_widgets()
    msg("## 🔑 Credentials")
    text_input("git_name","Git user.name","Tom Sapletta",_state.get("git_name",""))
    text_input("git_email","Git user.email","tom@example.com",_state.get("git_email",""))
    text_input("github_key","Ścieżka klucza SSH","~/.ssh/id_ed25519",_state.get("github_key",""))
    text_input("openrouter_key","OpenRouter API Key","sk-or-v1-...",_state.get("openrouter_key",""),sec=True)
    select("llm_model","Model LLM",[
        {"label":"Gemini Flash Preview","value":"google/gemini-3-flash-preview"},
        {"label":"Claude Sonnet 4",     "value":"anthropic/claude-sonnet-4"},
        {"label":"GPT-4o",              "value":"openai/gpt-4o"},
    ],_state.get("llm_model","google/gemini-3-flash-preview"))
    buttons([{"label":"✅ Zapisz","value":"save_creds"},{"label":"← Wróć","value":"back"}])

def step_save_creds(form):
    clear_widgets()
    for k in ("git_name","git_email","github_key","openrouter_key","llm_model"):
        if form.get(k): _state[k] = form[k].strip()
    msg("✅ Zapisano credentials.")
    key = _state.get("openrouter_key","")
    msg(f"- Git: `{_state.get('git_name','')}` <{_state.get('git_email','')}>")
    msg(f"- SSH: `{_state.get('github_key','')}`")
    msg(f"- API: `{mask(key) if key else '(brak)'}`")
    msg(f"- Model: `{_state.get('llm_model','')}`")
    buttons([{"label":"🚀 Uruchom stacki","value":"launch_all"},{"label":"🏠 Menu","value":"back"}])

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

def step_do_launch(form):
    clear_widgets()
    stacks = form.get("stacks","all")
    env    = form.get("environment","local")
    _state.update({"stacks":stacks,"environment":env})
    cf = "docker-compose.yml" if env == "local" else "docker-compose-production.yml"
    targets = []
    if stacks in ("all","management"): targets.append(("management",MGMT))
    if stacks in ("all","app"):        targets.append(("app",APP))
    if stacks in ("all","devices"):    targets.append(("devices",DEVS))

    def run():
        subprocess.run(["docker","network","create","dockfra-shared"],capture_output=True)
        for name, path in targets:
            msg(f"▶️ **{name}**...")
            progress(f"Uruchamiam {name}...")
            rc, _ = run_cmd(["docker","compose","-f",cf,"up","-d","--build"],cwd=path)
            progress(f"{name}", done=(rc==0), error=(rc!=0))
            msg(f"{'✅' if rc==0 else '❌'} {name} (exit {rc})")
        msg("\n✅ **Gotowe!**")
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
STEPS = {
    "welcome":          lambda f: step_welcome(),
    "back":             lambda f: step_welcome(),
    "status":           lambda f: step_status(),
    "pick_logs":        lambda f: step_pick_logs(),
    "setup_creds":      lambda f: step_setup_creds(),
    "save_creds":       step_save_creds,
    "launch_all":       lambda f: step_launch_all(),
    "do_launch":        step_do_launch,
    "deploy_device":    lambda f: step_deploy_device(),
    "test_device":      step_test_device,
    "do_deploy":        step_do_deploy,
    "launch_devices":   step_launch_devices,
    "post_launch_creds":lambda f: step_post_launch_creds(),
    "run_post_creds":   lambda f: step_run_post_creds(),
}

# ── socket events ─────────────────────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    reset_state()
    step_welcome()

@socketio.on("action")
def on_action(data):
    value = data.get("value","")
    form  = data.get("form", {})
    if value.startswith("logs::"):
        step_show_logs(value.split("::",1)[1]); return
    handler = STEPS.get(value)
    if handler:
        handler(form)
    else:
        msg(f"⚠️ Nieznana akcja: `{value}`")
        buttons([{"label":"🏠 Menu","value":"back"}])

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

if __name__ == "__main__":
    print("🧙 Dockfra Wizard → http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
