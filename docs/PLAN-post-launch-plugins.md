# Plan: Post-Launch Plugin System (F)

## Problem
Post-launch UI in `steps.py` hardcodes project-specific actions:
- Desktop/noVNC check (`cname("desktop")`)
- "📦 Wdróż na urządzenie" (deploy to RPi3)
- "🔑 Setup GitHub + LLM" credentials flow
- `fix_acme_storage()`, `fix_vnc_port()` in `fixes.py`

These only make sense for the current dockfra project, not a generic Docker manager.

## Proposed Solution: `dockfra.yaml` post_launch hooks

### 1. Config-driven post-launch buttons

```yaml
# dockfra.yaml
post_launch:
  - label: "🔑 Setup GitHub + LLM"
    action: post_launch_creds          # maps to existing step function
    condition: stack_running("app")     # show only when app stack is up

  - label: "📦 Wdróż na urządzenie"
    action: deploy_device
    condition: stack_exists("devices")

  - label: "🖥️ Desktop noVNC"
    url: "http://localhost:${DESKTOP_VNC_PORT:-6081}"
    condition: container_running("desktop-app")

  - label: "📊 Traefik Dashboard"
    url: "http://localhost:${TRAEFIK_DASHBOARD_PORT:-8080}"
    condition: container_running("traefik")
```

### 2. Condition evaluators (add to `core.py`)

```python
_POST_LAUNCH_CONDITIONS = {
    "stack_exists":       lambda name: name in STACKS,
    "stack_running":      lambda name: any(
        c["name"].startswith(cname("")) and name in c["name"]
        for c in docker_ps() if "Up" in c["status"]),
    "container_running":  lambda name: cname(name) in {
        c["name"] for c in docker_ps() if "Up" in c["status"]},
    "ssh_roles_exist":    lambda _: bool(_SSH_ROLES),
}
```

### 3. Generic post-launch renderer (replace hardcoded block in `steps.py`)

```python
def _render_post_launch(running_names: set):
    """Build post-launch buttons from dockfra.yaml config + SSH roles."""
    btns = []
    # Always: SSH role buttons (auto-discovered)
    for role, ri in _SSH_ROLES.items():
        if ri["container"] in running_names:
            p = _state.get(f"SSH_{role.upper()}_PORT", ri["port"])
            btns.append({"label": f"{ri['icon']} SSH {role.capitalize()}",
                         "value": f"ssh_info::{role}::{p}"})
    # Config-driven buttons
    for hook in _PROJECT_CONFIG.get("post_launch", []):
        cond = hook.get("condition", "")
        if cond:
            func_name, _, arg = cond.partition("(")
            arg = arg.rstrip(")")
            evaluator = _POST_LAUNCH_CONDITIONS.get(func_name)
            if evaluator and not evaluator(arg.strip('"').strip("'")):
                continue
        if "url" in hook:
            # Expand ${VAR:-default} in URL
            url = _expand_env_vars(hook["url"])
            btns.append({"label": hook["label"], "value": f"open_url::{url}"})
        elif "action" in hook:
            btns.append({"label": hook["label"], "value": hook["action"]})
    buttons(btns)
```

### 4. Fix system as plugins

Move project-specific fixes to `dockfra.yaml`:

```yaml
fixes:
  acme_storage:
    pattern: "acme.*storage|letsencrypt"
    label: "🔧 Napraw ACME storage"
    action: fix_acme_storage
    condition: container_running("traefik")

  vnc_port:
    pattern: "port.*6080|6080.*bind"
    label: "🔧 Zmień port VNC"
    action: fix_vnc_port
    condition: stack_exists("devices")
```

## Implementation Order

1. **Parse `post_launch` from `dockfra.yaml`** — already loaded by `_load_project_config()`
2. **Add condition evaluators** to `core.py`
3. **Refactor `step_do_launch` post-launch block** to use `_render_post_launch()`
4. **Move project-specific fixes** to config, keep generic ones in code
5. **Add `open_url::` action handler** for URL buttons

## Effort Estimate
- Steps 1-3: ~2h (main refactor)
- Steps 4-5: ~1h (cleanup)
- Testing: ~30min

## Files Affected
- `core.py` — condition evaluators, `_expand_env_vars()`
- `steps.py` — replace hardcoded post-launch block
- `fixes.py` — make project-specific fixes conditional
- `dockfra.yaml` — new config sections
