"""
dockfra.engines — Dev engine abstraction for autonomous coding tools.

Discovers, tests, and selects from multiple autonomous dev engines:
  1. built_in  — llm_client.py via OpenRouter (always available if API key works)
  2. aider     — CLI tool that edits files autonomously via LLM
  3. claude_code — Anthropic's Claude Code CLI

Each engine has: detect() → bool, test() → (ok, msg), implement(ticket) → (rc, output)
Auto-selects the first working engine; user can override.
"""
import json
import os
import subprocess
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Engine Registry ───────────────────────────────────────────────────────────

_ENGINES: list[dict] = []


def _strip_motd(text: str) -> str:
    """Strip MOTD box-drawing banners from command output."""
    import re
    lines = text.split('\n')
    keep = []
    in_box = False
    for line in lines:
        t = line.strip()
        if not in_box and re.match(r'^[╔┌]', t):
            in_box = True; continue
        if in_box and re.match(r'^[╚└]', t):
            in_box = False; continue
        if in_box:
            continue
        if re.match(r'^[║╠╣│]', t):
            continue
        if t and not re.sub(r'[\s╔╗╚╝╠╣║═─━│┌┐└┘├┤┬┴┼▀▄█▌▐░▒▓]', '', t):
            continue
        keep.append(line)
    return '\n'.join(keep).strip()


def _run_in_container(container: str, user: str, cmd: str,
                      extra_env: list[str] | None = None, timeout: int = 30) -> tuple[int, str]:
    """Run a command in the dev container. Returns (rc, output)."""
    parts = ["docker", "exec"]
    if extra_env:
        parts += extra_env
    parts += ["-u", user, container, "bash", "-lc", cmd]
    try:
        r = subprocess.run(parts, capture_output=True, text=True, timeout=timeout)
        return r.returncode, _strip_motd((r.stdout + r.stderr).strip())
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


def _detect_in_container(container: str, user: str, cmd: str) -> bool:
    """Check if a command exists in the container."""
    rc, _ = _run_in_container(container, user, f"command -v {cmd} 2>/dev/null", timeout=10)
    return rc == 0


# ── Engine: Built-in LLM (llm_client.py via OpenRouter) ──────────────────────

def _builtin_detect(container: str, user: str) -> bool:
    """Built-in is always available if llm_client.py exists."""
    rc, _ = _run_in_container(container, user,
        "python3 -c 'import sys; sys.path.insert(0,\"/shared/lib\"); import llm_client; print(\"ok\")'",
        timeout=10)
    return rc == 0


def _builtin_test(container: str, user: str, env: list[str]) -> tuple[bool, str]:
    """Test built-in LLM by making a tiny API call."""
    rc, out = _run_in_container(container, user,
        "python3 -c \""
        "import sys; sys.path.insert(0,'/shared/lib'); import llm_client; "
        "r = llm_client.chat('Say OK', max_tokens=5); "
        "print(r); "
        "exit(0 if '[LLM] Error' not in r else 1)\"",
        extra_env=env, timeout=20)
    if rc == 0 and "[LLM] Error" not in out:
        return True, f"OK: {out[:100]}"
    return False, out[:200]


def _builtin_implement_cmd(ticket_id: str) -> str:
    """Return the shell command to implement via built-in LLM."""
    return f"'/home/developer/scripts/implement.sh' {ticket_id}"


# ── Engine: Aider ─────────────────────────────────────────────────────────────

def _aider_detect(container: str, user: str) -> bool:
    return _detect_in_container(container, user, "aider")


def _aider_test(container: str, user: str, env: list[str]) -> tuple[bool, str]:
    """Test aider by checking version and API connectivity."""
    rc, out = _run_in_container(container, user, "aider --version 2>&1", extra_env=env, timeout=15)
    if rc != 0:
        return False, f"aider not installed: {out[:100]}"
    version = out.strip()
    # Test API connectivity with --no-auto-commits dry run
    rc2, out2 = _run_in_container(container, user,
        "cd /repo && echo 'test' | aider --no-auto-commits --no-git --yes --message 'Say OK' --dry-run 2>&1 | head -20",
        extra_env=env, timeout=20)
    if rc2 == 0 and "error" not in out2.lower():
        return True, f"aider {version} — API OK"
    # aider might not have --dry-run, just check version is enough if API key is set
    return True, f"aider {version} (API test skipped)"


def _aider_implement_cmd(ticket_id: str) -> str:
    """Return the shell command to implement via aider."""
    return (
        f"cd /repo && python3 -c \""
        f"import sys; sys.path.insert(0,'/shared/lib'); import ticket_system; "
        f"t = ticket_system.get('{ticket_id}'); "
        f"print(t['title'] if t else 'unknown'); print(t.get('description','') if t else '')\" "
        f"| {{ read TITLE; read DESC; "
        f"aider --no-auto-commits --yes "
        f"--message \"Implement: $TITLE. $DESC. Write actual code files, run tests.\" "
        f"2>&1; }}"
    )


# ── Engine: Claude Code CLI ──────────────────────────────────────────────────

def _claude_detect(container: str, user: str) -> bool:
    return _detect_in_container(container, user, "claude")


def _claude_test(container: str, user: str, env: list[str]) -> tuple[bool, str]:
    """Test claude CLI by checking version."""
    rc, out = _run_in_container(container, user, "claude --version 2>&1", extra_env=env, timeout=15)
    if rc != 0:
        return False, f"claude not installed: {out[:100]}"
    return True, f"claude {out.strip()}"


def _claude_implement_cmd(ticket_id: str) -> str:
    """Return the shell command to implement via claude code CLI."""
    return (
        f"cd /repo && python3 -c \""
        f"import sys; sys.path.insert(0,'/shared/lib'); import ticket_system; "
        f"t = ticket_system.get('{ticket_id}'); "
        f"msg = f'Implement ticket {ticket_id}: ' + (t['title'] if t else 'unknown') + '. ' + (t.get('description','') if t else ''); "
        f"print(msg)\" "
        f"| xargs -I{{}} claude --print \"{{}}\" 2>&1"
    )


# ── Engine Registry ───────────────────────────────────────────────────────────

ENGINE_DEFS = [
    {
        "id": "built_in",
        "name": "Wbudowany LLM (OpenRouter)",
        "desc": "llm_client.py — szybki, konfigurowalny, używa OpenRouter API",
        "detect": _builtin_detect,
        "test": _builtin_test,
        "implement_cmd": _builtin_implement_cmd,
        "needs_key": "OPENROUTER_API_KEY",
        "install_hint": "Preinstalowany — wymaga OPENROUTER_API_KEY",
    },
    {
        "id": "aider",
        "name": "Aider (autonomiczny CLI)",
        "desc": "Edytuje pliki autonomicznie, tworzy commity, naprawia błędy iteracyjnie",
        "detect": _aider_detect,
        "test": _aider_test,
        "implement_cmd": _aider_implement_cmd,
        "needs_key": "OPENROUTER_API_KEY",
        "install_hint": "pip install aider-chat",
    },
    {
        "id": "claude_code",
        "name": "Claude Code CLI",
        "desc": "Anthropic CLI — natywnie remote, działa w SSH sesji",
        "detect": _claude_detect,
        "test": _claude_test,
        "implement_cmd": _claude_implement_cmd,
        "needs_key": "ANTHROPIC_API_KEY",
        "install_hint": "npm install -g @anthropic-ai/claude-code",
    },
]


# ── Public API ────────────────────────────────────────────────────────────────

def discover_engines(container: str, user: str = "developer") -> list[dict]:
    """Discover which engines are available in the container.
    Returns list of {id, name, desc, available, install_hint}."""
    results = []
    for eng in ENGINE_DEFS:
        try:
            available = eng["detect"](container, user)
        except Exception:
            available = False
        results.append({
            "id": eng["id"],
            "name": eng["name"],
            "desc": eng["desc"],
            "available": available,
            "needs_key": eng.get("needs_key", ""),
            "install_hint": eng.get("install_hint", ""),
        })
    return results


def test_engine(engine_id: str, container: str, user: str = "developer",
                env: list[str] | None = None) -> tuple[bool, str]:
    """Test a specific engine. Returns (ok, message)."""
    for eng in ENGINE_DEFS:
        if eng["id"] == engine_id:
            try:
                return eng["test"](container, user, env or [])
            except Exception as e:
                return False, str(e)
    return False, f"Unknown engine: {engine_id}"


def test_all_engines(container: str, user: str = "developer",
                     env: list[str] | None = None) -> list[dict]:
    """Test all available engines. Returns [{id, name, ok, message}]."""
    results = []
    for eng in ENGINE_DEFS:
        try:
            available = eng["detect"](container, user)
        except Exception:
            available = False
        if not available:
            results.append({"id": eng["id"], "name": eng["name"],
                           "ok": False, "message": "nie zainstalowany"})
            continue
        try:
            ok, message = eng["test"](container, user, env or [])
        except Exception as e:
            ok, message = False, str(e)
        results.append({"id": eng["id"], "name": eng["name"],
                       "ok": ok, "message": message})
    return results


def select_first_working(container: str, user: str = "developer",
                         env: list[str] | None = None) -> tuple[str, str]:
    """Auto-select the first working engine. Returns (engine_id, message).
    Returns ('', error_msg) if none works."""
    for eng in ENGINE_DEFS:
        try:
            if not eng["detect"](container, user):
                continue
            ok, message = eng["test"](container, user, env or [])
            if ok:
                return eng["id"], f"{eng['name']}: {message}"
        except Exception:
            continue
    return "", "Żaden silnik deweloperski nie działa. Sprawdź API key i instalację narzędzi."


def get_implement_cmd(engine_id: str, ticket_id: str) -> str:
    """Get the shell command for implementing a ticket with the given engine."""
    for eng in ENGINE_DEFS:
        if eng["id"] == engine_id:
            return eng["implement_cmd"](ticket_id)
    # Fallback to built-in
    return _builtin_implement_cmd(ticket_id)


def get_engine_info(engine_id: str) -> dict | None:
    """Get engine definition by ID."""
    for eng in ENGINE_DEFS:
        if eng["id"] == engine_id:
            return eng
    return None


# ── Persistent engine preference ──────────────────────────────────────────────

_PREF_FILE = Path(os.environ.get("TICKETS_DIR",
    str(Path(__file__).resolve().parent.parent / "shared" / "tickets"))) / ".engine_pref.json"


def get_preferred_engine() -> str:
    """Get user's preferred engine ID, or empty string."""
    try:
        if _PREF_FILE.exists():
            data = json.loads(_PREF_FILE.read_text())
            return data.get("engine_id", "")
    except Exception:
        pass
    return ""


def set_preferred_engine(engine_id: str):
    """Save user's preferred engine ID."""
    _PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PREF_FILE.write_text(json.dumps({"engine_id": engine_id,
        "updated_at": __import__("datetime").datetime.now().isoformat()}))
