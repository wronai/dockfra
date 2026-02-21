#!/usr/bin/env python3
"""
Dockfra CLI — terminal shell for the Setup Wizard.

Usage:
  dockfra cli                       # interactive REPL
  dockfra cli --tui                 # three-panel curses TUI
  dockfra cli status                # container health
  dockfra cli tickets               # list all tickets
  dockfra cli diff <T-XXXX>         # show ticket diff & commits
  dockfra cli pipeline <T-XXXX>     # run full pipeline for ticket
  dockfra cli engines               # LLM engine status
  dockfra cli dev-health            # ssh-developer health check
  dockfra cli dev-logs [N]          # ssh-developer container logs
  dockfra cli test                  # full system self-test
  dockfra cli doctor                # diagnose & suggest fixes
  dockfra cli logs [N]              # last N log lines (default 40)
  dockfra cli launch [stack]        # launch stacks
  dockfra cli ask "..."             # free-text LLM query
  dockfra cli action <val>          # raw wizard action
"""
import sys, os, json, time, threading, textwrap, re, argparse
import urllib.request, urllib.error
from pathlib import Path

BASE_URL = os.environ.get("DOCKFRA_URL", "http://localhost:5050")

# ── ANSI colours ──────────────────────────────────────────────────────────────
_NO_COLOR = not sys.stdout.isatty() or bool(os.environ.get("NO_COLOR"))

def _c(code, s):  return s if _NO_COLOR else f"\033[{code}m{s}\033[0m"
def green(s):     return _c("92", s)
def red(s):       return _c("91", s)
def yellow(s):    return _c("93", s)
def cyan(s):      return _c("96", s)
def purple(s):    return _c("95", s)
def bold(s):      return _c("1",  s)
def dim(s):       return _c("2",  s)
def orange(s):    return _c("33", s)

# ── REST Client ───────────────────────────────────────────────────────────────
class WizardClient:
    def __init__(self, base=BASE_URL):
        self.base = base.rstrip("/")

    def _get(self, path, params=None, timeout=15):
        url = self.base + path
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read()), None
        except urllib.error.URLError as e:
            return None, str(e)

    def _post(self, path, data, timeout=60):
        body = json.dumps(data).encode()
        req  = urllib.request.Request(
            self.base + path, data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read()), None
        except urllib.error.URLError as e:
            return None, str(e)

    def action(self, value, form=None):
        return self._post("/api/action", {"action": value, "form": form or {}})
    def health(self):                   return self._get("/api/health")
    def containers(self):               return self._get("/api/containers")
    def logs(self, n=40):               return self._get("/api/logs/tail", {"n": n})
    def history(self):                  return self._get("/api/history")
    def events_since(self, since_id=0): return self._get(f"/api/events/since/{since_id}")
    def ping(self):
        _, err = self._get("/api/containers", timeout=3)
        return err is None

# ── Log classification ────────────────────────────────────────────────────────
def _classify_log(line):
    if re.match(r'^#\d+', line):
        if 'DONE' in line:                          return 'done'
        if re.search(r'error|failed', line, re.I):  return 'err'
        if re.search(r'Downloading|Pulling|RUN|COPY', line, re.I): return 'build'
        return 'build'
    if re.search(r'Restarting|\U0001f534|Stopped', line):      return 'restart'
    if re.search(r'\b(error|fatal|failed|bind for|permission denied|connection refused)\b', line, re.I): return 'err'
    if re.search(r'\b(warning|warn)\b', line, re.I):           return 'warn'
    if re.search(r'\b(successfully|started|healthy|done|built)\b', line, re.I): return 'ok'
    if re.search(r'whl\.metadata|eta 0:00:00|\[notice\]', line): return 'dim'
    return ''

def _colorize_log(line):
    c = _classify_log(line)
    if c == 'err':     return red(line)
    if c == 'warn':    return yellow(line)
    if c == 'ok':      return green(line)
    if c in ('done',): return bold(green(line))
    if c == 'build':   return cyan(line)
    if c == 'restart': return orange(bold(line))
    if c == 'dim':     return dim(line)
    return line

# ── Markdown → ANSI ──────────────────────────────────────────────────────────
def _render_md(text):
    text = re.sub(r'^#{1,3}\s+(.+)$', lambda m: bold(m.group(1)), text, flags=re.M)
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: bold(m.group(1)), text)
    text = re.sub(r'`([^`]+)`', lambda m: cyan(m.group(1)), text)
    text = re.sub(r'```[^\n]*\n(.*?)```', lambda m: dim(m.group(1)), text, flags=re.S)
    text = re.sub(r'^- ', '  • ', text, flags=re.M)
    return text

def _render_result(items):
    for item in items:
        t = item.get("type", "")
        if t == "message":
            role = item.get("role", "bot")
            text = _render_md(item.get("text", "")).strip()
            prefix = bold("🤖 ") if role == "bot" else bold(purple("👤 "))
            for i, ln in enumerate(text.splitlines()):
                print(("   " if i else prefix) + ln)
        elif t == "buttons":
            print()
            for b in item.get("items", []):
                print(f"  {purple('▶')} {b['label']:<30} {dim(repr(b['value']))}")
        elif t == "status_row":
            for c in item.get("items", []):
                ok   = c.get("ok", False)
                icon = green("🟢") if ok else red("🔴")
                print(f"  {icon} {c['name']:<38} {dim(c.get('detail',''))}")
        elif t == "progress":
            icon = green("✅") if item.get("done") else red("❌") if item.get("error") else yellow("⏳")
            print(f"  {icon} {item.get('label','')}")
        elif t == "code":
            print(dim(item.get("value", "")))

# ── One-shot commands ─────────────────────────────────────────────────────────
def cmd_status(client, args):
    data, err = client.health()
    if err:
        print(red(f"❌ Cannot reach wizard at {client.base}:\n   {err}")); return 1
    run, fail = data["running"], data["failing"]
    print(bold(f"\n📊 System Status — {run+fail} containers"))
    print(f"   {green(str(run))} OK  {red(str(fail))} failing\n")
    for c in data.get("containers", []):
        ok = "Up" in c["status"] and "Restarting" not in c["status"]
        print(f"  {green('🟢') if ok else red('🔴')} {c['name']:<40} {dim(c['status'])}")
    if data.get("findings"):
        print(bold(f"\n🔍 Problems ({len(data['findings'])}):\n"))
        for f in data["findings"]:
            print(f"  {red('▶')} {bold(f['container'])} — {dim(f['status'])}")
            finding = re.sub(r'```[^\n]*', '', f.get("finding", ""))
            for ln in finding.strip().splitlines()[:5]:
                print(f"     {dim(ln)}")
            for s in f.get("solutions", [])[:3]:
                print(f"     {purple('→')} {s['label']}")
            print()
    return 0

def cmd_logs(client, args):
    n = int(args[0]) if args else 40
    data, err = client.logs(n)
    if err: print(red(f"❌ {err}")); return 1
    lines = data.get("lines", [])
    buf_info = dim(f"(total buffer: {data['total']})")
    print(bold(f"\n📋 Last {len(lines)} log lines  ") + buf_info + "\n")
    for l in lines:
        print(_colorize_log(l.get("text", "")))
    return 0

def cmd_launch(client, args):
    stk = args[0] if args else "launch_all"
    if stk not in ("launch_all","management","app","devices"):
        stk = "launch_all"
    print(yellow(f"🚀 Launching {stk}…"))
    data, err = client.action(stk)
    if err: print(red(f"❌ {err}")); return 1
    _render_result(data.get("result", [])); return 0

def cmd_ask(client, args):
    q = " ".join(args)
    if not q: print(red("Usage: ask <question>")); return 1
    print(purple(f"\n🧠 {q}\n"))
    data, err = client.action(q)
    if err: print(red(f"❌ {err}")); return 1
    _render_result(data.get("result", [])); return 0

def cmd_action(client, args):
    if not args: print(red("Usage: action <value>")); return 1
    data, err = client.action(" ".join(args))
    if err: print(red(f"❌ {err}")); return 1
    _render_result(data.get("result", [])); return 0

def cmd_tickets(client, args):
    data, err = client._get("/api/tickets")
    if err: print(red(f"❌ {err}")); return 1
    if not data:
        print(dim("  Brak ticketów.")); return 0
    status_icon = {"open": "○", "in_progress": "◐", "review": "◑", "done": "●", "closed": "●"}
    status_clr  = {"open": cyan, "in_progress": yellow, "review": purple, "done": green, "closed": dim}
    prio_icon   = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "🟢"}
    print(bold(f"\n🎫 Tickety ({len(data)})\n"))
    for tk in data:
        si = status_icon.get(tk["status"], "○")
        sc = status_clr.get(tk["status"], dim)
        pi = prio_icon.get(tk.get("priority", ""), "⚪")
        print(f"  {sc(si + ' ' + tk['id']):<28} {pi} {bold(tk['title'])}")
        print(f"     {dim(tk['status'])} · {dim(tk.get('assigned_to',''))} · {dim(str(len(tk.get('comments',[]))))} komentarzy")
    print()
    return 0

def cmd_diff(client, args):
    if not args: print(red("Usage: diff <ticket_id>")); return 1
    tid = args[0]
    data, err = client._get(f"/api/ticket-diff/{tid}")
    if err: print(red(f"❌ {err}")); return 1
    if not data or not data.get("ok"):
        print(red(f"❌ {data.get('error', 'Unknown error') if data else 'No response'}")); return 1
    commits = data.get("commits", [])
    diff = data.get("diff", "")
    print(bold(f"\n📄 Diff: {tid}") + f" — {data.get('title', '')}\n")
    if not commits:
        print(yellow("  Brak commitów dla tego ticketu."))
        print(dim("  Commity muszą zawierać ID ticketu w wiadomości.\n"))
        return 0
    print(bold(f"  📝 Commity ({len(commits)})"))
    for c in commits:
        print(f"    {cyan(c['hash'])} {c['subject']}  {dim(c.get('repo',''))}")
    if diff:
        print(bold(f"\n  📊 Diff:"))
        for line in diff.splitlines()[:80]:
            if line.startswith('+') and not line.startswith('++'):
                print(f"    {green(line)}")
            elif line.startswith('-') and not line.startswith('--'):
                print(f"    {red(line)}")
            elif line.startswith('@@'):
                print(f"    {cyan(line)}")
            else:
                print(f"    {dim(line)}")
        if len(diff.splitlines()) > 80:
            print(dim(f"    ... ({len(diff.splitlines()) - 80} more lines)"))
    print()
    return 0

def cmd_engines(client, args):
    data, err = client._get("/api/engine-status")
    if err: print(red(f"❌ {err}")); return 1
    pref = data.get("preferred", "")
    engines = data.get("engines", [])
    print(bold(f"\n🤖 Silniki LLM\n"))
    for e in engines:
        ok = e.get("ok", False)
        icon = green("✅") if ok else red("🔴")
        star = yellow(" ★ preferred") if e["id"] == pref else ""
        print(f"  {icon} {bold(e['name']):<25}{star}")
        print(f"     {dim(e.get('message',''))}")
    if not engines:
        print(dim("  Brak silników."))
    print()
    return 0

def cmd_dev_health(client, args):
    data, err = client._get("/api/developer-health")
    if err: print(red(f"❌ {err}")); return 1
    print(bold("\n🔧 SSH Developer Health\n"))
    checks = [
        ("Kontener", data.get("container") == "running", data.get("container", "?")),
        ("Exec (SSH)", data.get("ssh") == "ok", data.get("ssh", "?")),
        ("Git repo", data.get("git", "") not in ("fail", "no repo", ""), data.get("git", "?")),
        ("Skrypty", (data.get("scripts", 0) or 0) > 0, f"{data.get('scripts', 0)} scripts"),
    ]
    for label, ok, detail in checks:
        icon = green("✅") if ok else red("🔴")
        print(f"  {icon} {label:<20} {dim(str(detail))}")
    eng = data.get("engines", {})
    if eng:
        print(bold("\n  Silniki:"))
        for name, avail in eng.items():
            icon = green("✅") if avail else red("🔴")
            print(f"    {icon} {name}")
    overall = data.get("ok", False)
    print(f"\n  {'✅ ' + green('Developer OK') if overall else '🔴 ' + red('Developer ma problemy')}\n")
    return 0 if overall else 1

def cmd_dev_logs(client, args):
    n = int(args[0]) if args else 80
    data, err = client._get("/api/developer-logs", {"n": n})
    if err: print(red(f"❌ {err}")); return 1
    logs = data.get("logs", "")
    print(bold(f"\n📋 Developer logs ({data.get('container','')}) — last {n} lines\n"))
    for line in logs.splitlines():
        print(_colorize_log(line))
    print()
    return 0

def cmd_test(client, args):
    """Full system self-test: containers, developer health, engines, ticket API, diff API."""
    print(bold("\n🧪 Dockfra System Test\n"))
    errors = []
    # 1. Wizard reachable
    if client.ping():
        print(green("  ✅ Wizard reachable"))
    else:
        print(red("  🔴 Wizard offline")); errors.append("wizard offline"); return 1
    # 2. Container health
    data, err = client.health()
    if err:
        print(red(f"  🔴 Health check: {err}")); errors.append("health")
    else:
        r, f_ = data["running"], data["failing"]
        if f_ == 0:
            print(green(f"  ✅ Containers: {r} running, 0 failing"))
        else:
            print(red(f"  🔴 Containers: {r} running, {f_} failing")); errors.append(f"{f_} containers failing")
    # 3. Developer health
    data, err = client._get("/api/developer-health")
    if err:
        print(red(f"  🔴 Developer health: {err}")); errors.append("dev-health")
    elif data and data.get("ok"):
        print(green(f"  ✅ Developer: container={data['container']} ssh={data['ssh']} git={data.get('git','?')}"))
    else:
        print(red(f"  🔴 Developer unhealthy: {data}")); errors.append("developer")
    # 4. Engine status
    data, err = client._get("/api/engine-status")
    if err:
        print(red(f"  🔴 Engine status: {err}")); errors.append("engines")
    else:
        working = [e["name"] for e in data.get("engines", []) if e.get("ok")]
        failed  = [e["name"] for e in data.get("engines", []) if not e.get("ok")]
        if working:
            print(green(f"  ✅ Engines OK: {', '.join(working)}"))
        if failed:
            print(yellow(f"  ⚠️  Engines failed: {', '.join(failed)}"))
        if not working:
            errors.append("no working engines")
    # 5. Tickets API
    data, err = client._get("/api/tickets")
    if err:
        print(red(f"  🔴 Tickets API: {err}")); errors.append("tickets")
    else:
        print(green(f"  ✅ Tickets API: {len(data)} tickets"))
    # 6. Stats API
    data, err = client._get("/api/stats")
    if err:
        print(red(f"  🔴 Stats API: {err}")); errors.append("stats")
    else:
        print(green(f"  ✅ Stats API OK"))
    # 7. Ticket diff (quick test)
    tdata, _ = client._get("/api/tickets")
    if tdata and len(tdata) > 0:
        tid = tdata[0]["id"]
        dd, derr = client._get(f"/api/ticket-diff/{tid}")
        if derr:
            print(red(f"  🔴 Diff API ({tid}): {derr}")); errors.append("diff")
        elif dd and dd.get("ok"):
            print(green(f"  ✅ Diff API ({tid}): {len(dd.get('commits',[]))} commits"))
        else:
            print(red(f"  🔴 Diff API ({tid}): {dd}")); errors.append("diff")
    # Summary
    print()
    if errors:
        print(red(f"  ❌ {len(errors)} problem(s): {', '.join(errors)}"))
    else:
        print(green(bold("  ✅ All tests passed!")))
    print()
    return 1 if errors else 0

def cmd_doctor(client, args):
    """Diagnose common issues and suggest fixes."""
    print(bold("\n🩺 Dockfra Doctor\n"))
    fixes = []
    # 1. Wizard
    if not client.ping():
        print(red("  🔴 Wizard offline"))
        fixes.append("Run: make restart")
        return 1
    print(green("  ✅ Wizard online"))
    # 2. Containers
    data, _ = client.health()
    if data:
        for c in data.get("containers", []):
            if "Restarting" in c.get("status", ""):
                print(red(f"  🔴 {c['name']} is restart-looping"))
                fixes.append(f"docker logs {c['name']} --tail 20")
            elif "Up" not in c.get("status", ""):
                print(red(f"  🔴 {c['name']} is not running: {c['status']}"))
                fixes.append(f"docker start {c['name']}")
    # 3. Developer
    dh, _ = client._get("/api/developer-health")
    if dh:
        if dh.get("container") != "running":
            print(red("  🔴 ssh-developer not running"))
            fixes.append("cd app && docker compose up -d ssh-developer")
        elif dh.get("ssh") != "ok":
            print(red("  🔴 ssh-developer exec failed"))
            fixes.append("docker restart dockfra-ssh-developer")
        else:
            print(green("  ✅ ssh-developer healthy"))
            if not dh.get("engines", {}).get("built_in"):
                print(yellow("  ⚠️  built-in engine not available — check OPENROUTER_API_KEY"))
                fixes.append("dockfra cli action prompt_api_key")
    # 4. Engines
    es, _ = client._get("/api/engine-status")
    if es:
        working = [e for e in es.get("engines", []) if e.get("ok")]
        if not working:
            print(red("  🔴 No working engines"))
            fixes.append("Set OPENROUTER_API_KEY in wizard or .env")
    # Summary
    print()
    if fixes:
        print(bold("  🔧 Suggested fixes:"))
        for f in fixes:
            print(f"    {purple('→')} {f}")
    else:
        print(green(bold("  ✅ System healthy — no issues found!")))
    print()
    return 1 if fixes else 0

def cmd_pipeline(client, args):
    if not args: print(red("Usage: pipeline <ticket_id>")); return 1
    tid = args[0]
    print(yellow(f"🔄 Starting pipeline for {tid}..."))
    data, err = client.action(f"ssh_cmd::developer::ticket-work::{tid}")
    if err: print(red(f"❌ {err}")); return 1
    _render_result(data.get("result", [])); return 0

COMMANDS = {
    "status":     (cmd_status,     "📊 Container health overview"),
    "health":     (cmd_status,     "🔍 Algorithmic analysis (same as status)"),
    "logs":       (cmd_logs,       "📋 logs [N]     — last N log lines (default 40)"),
    "launch":     (cmd_launch,     "🚀 launch [stack] — launch stacks (default: all)"),
    "ask":        (cmd_ask,        "🧠 ask <text>   — free-text LLM query"),
    "action":     (cmd_action,     "▶️  action <val> — raw wizard action value"),
    "tickets":    (cmd_tickets,    "🎫 List all tickets"),
    "diff":       (cmd_diff,       "📄 diff <T-XXXX> — show ticket diff and commits"),
    "pipeline":   (cmd_pipeline,   "🔄 pipeline <T-XXXX> — run full pipeline for ticket"),
    "engines":    (cmd_engines,    "🤖 Show LLM engine status"),
    "dev-health": (cmd_dev_health, "🔧 Developer container health check"),
    "dev-logs":   (cmd_dev_logs,   "📋 dev-logs [N] — ssh-developer container logs"),
    "test":       (cmd_test,       "🧪 Full system self-test"),
    "doctor":     (cmd_doctor,     "🩺 Diagnose issues and suggest fixes"),
}

# ── Interactive REPL ──────────────────────────────────────────────────────────
def run_repl(client):
    try:
        import readline as rl
        hist_path = Path.home() / ".dockfra_history"
        if hist_path.exists(): rl.read_history_file(str(hist_path))
        rl.set_history_length(500)
        import atexit; atexit.register(lambda: rl.write_history_file(str(hist_path)))
        opts = list(COMMANDS) + ["help", "quit"]
        rl.set_completer(lambda t, s: ([o for o in opts if o.startswith(t)] + [None])[s])
        rl.parse_and_bind("tab: complete")
    except ImportError:
        pass

    print(bold(cyan("\n🏗  Dockfra CLI — interactive shell")))
    print(dim(f"   Wizard: {client.base}"))
    print(dim("   Commands: help | test | tickets | engines | dev-health | dev-logs | doctor | quit\n"))
    if not client.ping():
        print(red(f"⚠️  Wizard offline at {client.base}"))
        print(yellow("   Start:  dockfra\n"))

    while True:
        try:
            line = input(bold(purple("dockfra")) + " › ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not line: continue
        if line in ("quit", "exit", "q"): break
        if line == "help":
            print()
            for cmd, (_, desc) in COMMANDS.items():
                print(f"  {purple(cmd):<20} {desc}")
            print(f"  {purple('quit'):<20} Exit\n")
            print(dim("  Any other text is sent as a free-text message to the LLM.\n"))
            continue
        parts = line.split(None, 1)
        cmd   = parts[0].lower()
        rest  = parts[1].split() if len(parts) > 1 else []
        if cmd in COMMANDS:
            try: COMMANDS[cmd][0](client, rest)
            except Exception as e: print(red(f"❌ {e}"))
        else:
            try:
                data, err = client.action(line)
                if err: print(red(f"❌ {err}"))
                else:   _render_result(data.get("result", []))
            except Exception as e:
                print(red(f"❌ {e}"))
        print()

# ── Curses TUI ────────────────────────────────────────────────────────────────
def run_tui(client):
    """Three-panel curses TUI: Chat (left) | Processes (centre) | Logs (right)."""
    import curses

    state = {
        "chat":      [], "processes": [], "logs": [],
        "input":     "", "running":   True,
        "chat_off":  0,  "log_off":   0,
        "lock":      threading.Lock(),
        "event_cursor": 0,
    }

    def _fetch():
        while state["running"]:
            try:
                h, _ = client.health()
                if h:
                    with state["lock"]:
                        state["processes"] = h.get("containers", [])
                # Use events_since for efficient incremental sync from SQLite
                ev, _ = client.events_since(state["event_cursor"])
                if ev:
                    new_chat = []
                    new_logs = []
                    for e in ev.get("events", []):
                        if e["event"] == "message":
                            d = e["data"]
                            # Skip CLI user messages — already added locally in _send
                            if e.get("src") == "cli" and d.get("role") == "user":
                                continue
                            new_chat.append({
                                "role": d.get("role", "bot"),
                                "text": d.get("text", ""),
                                "src":  e.get("src", ""),
                            })
                        elif e["event"] == "log_line":
                            new_logs.append(e["data"].get("text", ""))
                    with state["lock"]:
                        state["event_cursor"] = ev.get("max_id", state["event_cursor"])
                        if new_chat:
                            state["chat"].extend(new_chat)
                            state["chat"] = state["chat"][-400:]
                        if new_logs:
                            state["logs"].extend(new_logs)
                            state["logs"] = state["logs"][-400:]
            except Exception:
                pass
            time.sleep(2)

    def _send(text):
        with state["lock"]:
            state["chat"].append({"role": "user", "text": text, "src": "cli"})
        def _bg():
            client.action(text)  # server records user msg + reply to SQLite; _fetch will sync
        threading.Thread(target=_bg, daemon=True).start()

    fetch_t = threading.Thread(target=_fetch, daemon=True)
    fetch_t.start()

    def _main(scr):
        curses.curs_set(1)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN,   -1)  # ok
        curses.init_pair(2, curses.COLOR_CYAN,    -1)  # user msg
        curses.init_pair(3, curses.COLOR_RED,     -1)  # error
        curses.init_pair(4, curses.COLOR_YELLOW,  -1)  # warn
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # build
        curses.init_pair(6, curses.COLOR_WHITE,   -1)  # dim
        scr.timeout(200)

        while True:
            H, W = scr.getmaxyx()
            chat_w = max(24, W * 38 // 100)
            proc_w = max(16, W * 18 // 100)
            log_w  = max(24, W - chat_w - proc_w)
            inp_h  = 3

            # ── windows ──────────────────────────────────────────────────────
            chat_win = scr.subwin(H - inp_h, chat_w, 0, 0)
            proc_win = scr.subwin(H - inp_h, proc_w, 0, chat_w)
            log_win  = scr.subwin(H - inp_h, log_w,  0, chat_w + proc_w)
            inp_win  = scr.subwin(inp_h, W, H - inp_h, 0)

            # ── Chat ─────────────────────────────────────────────────────────
            chat_win.erase(); chat_win.box()
            chat_win.addstr(0, 2, " 💬 Chat ", curses.A_BOLD)
            rows = H - inp_h - 2
            lines = []
            with state["lock"]:
                for m in state["chat"]:
                    text = re.sub(r'[*`#]', '', m.get("text","")).strip()
                    pre  = "🤖 " if m.get("role") == "bot" else "👤 "
                    for i, ln in enumerate(textwrap.wrap(text, chat_w - 6) or [""]):
                        lines.append((pre if i == 0 else "   ", ln, m.get("role","bot")))
            off = state["chat_off"]
            start = max(0, len(lines) - rows - off)
            for i, (pre, ln, role) in enumerate(lines[start:start+rows]):
                attr = curses.color_pair(2) if role == "user" else 0
                try: chat_win.addstr(i+1, 2, (pre+ln)[:chat_w-4], attr)
                except curses.error: pass
            chat_win.noutrefresh()

            # ── Processes ────────────────────────────────────────────────────
            proc_win.erase(); proc_win.box()
            proc_win.addstr(0, 2, " ⚙ Proc ", curses.A_BOLD)
            with state["lock"]:
                procs = list(state["processes"])
            for i, c in enumerate(procs[:H-inp_h-2]):
                ok   = "Up" in c.get("status","") and "Restarting" not in c.get("status","")
                attr = curses.color_pair(1) if ok else curses.color_pair(3)
                name = c.get("name","")[:proc_w-4]
                try:
                    proc_win.addstr(i+1, 1, "●", attr)
                    proc_win.addstr(i+1, 3, name)
                except curses.error: pass
            proc_win.noutrefresh()

            # ── Logs ─────────────────────────────────────────────────────────
            log_win.erase(); log_win.box()
            log_win.addstr(0, 2, " 📋 Logs ", curses.A_BOLD)
            with state["lock"]:
                ls = list(state["logs"])
            lrows = H - inp_h - 2
            loff  = state["log_off"]
            lstart = max(0, len(ls) - lrows - loff)
            for i, ln in enumerate(ls[lstart:lstart+lrows]):
                cls = _classify_log(ln)
                attr = (curses.color_pair(3) if cls == 'err' else
                        curses.color_pair(4) if cls in ('warn','restart') else
                        curses.color_pair(1) if cls in ('ok','done') else
                        curses.color_pair(5) if cls == 'build' else
                        curses.color_pair(6) | curses.A_DIM if cls == 'dim' else 0)
                try: log_win.addstr(i+1, 1, ln[:log_w-2], attr)
                except curses.error: pass
            log_win.noutrefresh()

            # ── Input ────────────────────────────────────────────────────────
            inp_win.erase(); inp_win.box()
            hint = " [Enter]=send [PgUp/Dn]=scroll chat [PgUp/Dn+Shift]=logs [F10/ESC]=quit "
            try:
                inp_win.addstr(0, 2, hint[:W-4], curses.A_DIM)
                inp_win.addstr(1, 2, ("› " + state["input"])[:W-4])
            except curses.error: pass
            inp_win.noutrefresh()

            curses.doupdate()

            # ── Input handling ────────────────────────────────────────────────
            key = scr.getch()
            if key == -1: continue
            if key in (curses.KEY_F10, 27): break
            elif key in (curses.KEY_ENTER, 10, 13):
                text = state["input"].strip()
                state["input"] = ""
                if text:
                    if text in ("quit","exit","q"): break
                    _send(text)
                    state["chat_off"] = 0
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                state["input"] = state["input"][:-1]
            elif key == curses.KEY_PPAGE:  # PgUp → scroll chat up
                state["chat_off"] = min(state["chat_off"] + 5, max(0, len(lines) - (H-inp_h-2)))
            elif key == curses.KEY_NPAGE:  # PgDn → scroll chat down
                state["chat_off"] = max(0, state["chat_off"] - 5)
            elif key == curses.KEY_SR:     # Shift+Up → scroll logs up
                state["log_off"] = min(state["log_off"] + 5, max(0, len(ls) - lrows))
            elif key == curses.KEY_SF:     # Shift+Down → scroll logs down
                state["log_off"] = max(0, state["log_off"] - 5)
            elif 32 <= key <= 126:
                state["input"] += chr(key)

    try:
        curses.wrapper(_main)
    finally:
        state["running"] = False

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Dockfra CLI shell")
    p.add_argument("command", nargs="?", help="Command: status|health|logs|launch|ask|action")
    p.add_argument("args",    nargs="*", help="Command arguments")
    p.add_argument("--url",   default=BASE_URL,  help="Wizard base URL")
    p.add_argument("--tui",   action="store_true", help="Launch three-panel TUI (curses)")
    ns = p.parse_args()

    client = WizardClient(ns.url)

    if ns.tui or (not ns.command):
        if ns.tui:
            run_tui(client)
        else:
            run_repl(client)
        return

    cmd = ns.command.lower()
    args = ns.args

    if cmd in COMMANDS:
        sys.exit(COMMANDS[cmd][0](client, args) or 0)
    else:
        # Treat unknown command as free text to send
        data, err = client.action(cmd + (" " + " ".join(args) if args else ""))
        if err: print(red(f"❌ {err}")); sys.exit(1)
        _render_result(data.get("result", []))

if __name__ == "__main__":
    main()
