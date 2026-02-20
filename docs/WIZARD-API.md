# Wizard API Reference

> REST and WebSocket API for the Dockfra Setup Wizard.

## Server

Default: `http://localhost:5050` (configurable via `WIZARD_PORT`).

## REST API

### `GET /api/env`

Returns all configured environment variables (secrets masked).

```json
{
  "ENVIRONMENT": "local",
  "POSTGRES_USER": "myapp",
  "POSTGRES_PASSWORD": "****",
  "OPENROUTER_API_KEY": "sk-or-***"
}
```

### `POST /api/env`

Update environment variables. Body: JSON object with key-value pairs.

```bash
curl -X POST http://localhost:5050/api/env \
  -H 'Content-Type: application/json' \
  -d '{"POSTGRES_USER": "newuser", "POSTGRES_PASSWORD": "newpass"}'
```

### `GET /api/containers`

Running Docker containers with status, ports, image info.

```json
[
  {"name": "dockfra-backend", "status": "Up 2 hours", "ports": "8081/tcp"},
  {"name": "dockfra-db", "status": "Up 2 hours (healthy)", "ports": "5432/tcp"}
]
```

### `GET /api/processes`

Wizard-managed processes (compose up/down, builds).

### `GET /api/history`

Conversation history + log entries.

### `GET /api/events`

Decision event log (for dashboard).

### `GET /api/logs/tail?n=100`

Last N log lines from the global log buffer.

### `GET /api/detect/<key>`

Auto-detect a value for an environment variable.

| Key | Detection Method |
|---|---|
| `GIT_REPO_URL` | `git remote get-url origin` |
| `GIT_BRANCH` | `git branch --show-current` + all branches |
| `APP_VERSION` | `git describe --tags --abbrev=0` |
| `APP_NAME` | Root directory name |

Response:
```json
{
  "value": "git@github.com:org/app.git",
  "hint": "git remote origin",
  "options": [{"value": "main", "label": "main"}, {"value": "develop", "label": "develop"}]
}
```

### `GET /api/ssh-options/<kind>/<role>`

Options for SSH role interactions.

| Kind | Returns |
|---|---|
| `tickets` | Available tickets for role |
| `files` | Source files in container workspace |
| `branches` | Git branches in container |

### `POST /api/action`

Execute a wizard action synchronously (for non-WebSocket clients).

```bash
curl -X POST http://localhost:5050/api/action \
  -H 'Content-Type: application/json' \
  -d '{"action": "welcome"}'
```

Response:
```json
{
  "ok": true,
  "result": [
    {"event": "message", "data": {"role": "bot", "text": "# 👋 Dockfra Setup Wizard"}},
    {"event": "widget", "data": {"type": "buttons", "items": [...]}}
  ]
}
```

### `GET /dashboard`

Real-time dashboard with container status and decision log.

## WebSocket API

Connect via Socket.IO to `http://localhost:5050`.

### Client → Server

#### `action`

```javascript
socket.emit('action', {value: 'welcome', form: {}});
socket.emit('action', {value: 'settings_group::Git', form: {}});
socket.emit('action', {value: 'do_launch', form: {stacks: 'all', environment: 'local'}});
socket.emit('action', {value: 'ssh_info::developer::2200', form: {}});
socket.emit('action', {value: 'run_ssh_cmd::developer::ask', form: {Q: 'How to fix?'}});
```

### Server → Client

#### `message`

Chat message (bot or system).

```json
{"role": "bot", "text": "# 👋 Welcome", "id": "msg_abc123"}
```

#### `widget`

UI widget to render.

**Buttons:**
```json
{"type": "buttons", "items": [
  {"label": "🚀 Launch", "value": "do_launch"},
  {"label": "⚙️ Settings", "value": "settings"}
]}
```

**Text input:**
```json
{"type": "input", "name": "GIT_EMAIL", "label": "Git Email",
 "placeholder": "user@example.com", "value": "", "secret": false,
 "hint": "from git config", "chips": [], "desc": "...", "autodetect": false}
```

**Select:**
```json
{"type": "select", "name": "ENVIRONMENT", "label": "Environment",
 "options": [{"value": "local", "label": "Local"}, {"value": "production", "label": "Production"}],
 "value": "local", "desc": "...", "autodetect": false}
```

**Progress:**
```json
{"type": "progress", "label": "Building ssh-base...", "done": false, "error": false}
```

**Code block:**
```json
{"type": "code", "text": "POSTGRES_USER=myapp\nPOSTGRES_PASSWORD=..."}
```

**Status row:**
```json
{"type": "status_row", "items": [
  {"label": "backend", "status": "running", "icon": "✅"},
  {"label": "db", "status": "unhealthy", "icon": "🔴"}
]}
```

**Action grid:**
```json
{"type": "action_grid", "items": [
  {"label": "ask", "value": "run_ssh_cmd::developer::ask", "icon": "🤖", "desc": "LLM query"}
]}
```

#### `log_line`

Docker Compose streaming output.

```json
{"text": "backend-1  | INFO:     Application startup complete."}
```

#### `clear_widgets`

Clear all current widgets from the UI.

## Action Values

### Navigation
| Value | Description |
|---|---|
| `welcome` | Show welcome screen |
| `back` | Return to welcome |
| `settings` | Show settings group selector |
| `settings_group::<group>` | Open specific settings group |
| `save_settings::<group>` | Save settings for group |

### Launch & Deploy
| Value | Description |
|---|---|
| `do_launch` | Launch selected stacks |
| `retry_launch` | Retry failed launch |
| `launch_all` | Launch all stacks |
| `clone_and_launch_app` | Git clone app/ then launch |
| `deploy_device` | Deploy to IoT device |

### SSH Roles
| Value | Description |
|---|---|
| `ssh_info::<role>::<port>` | Show role info + commands |
| `ssh_console::<role>` | Open SSH console |
| `run_ssh_cmd::<role>::<cmd>` | Execute command in container |

### Fixes
| Value | Description |
|---|---|
| `fix_container::<name>` | Restart/rebuild container |
| `fix_network_overlap::<net>` | Remove conflicting network |
| `fix_acme_storage` | Configure ACME/Let's Encrypt |
| `fix_readonly_volume::<name>` | Fix volume permissions |
| `fix_docker_perms` | Fix Docker socket permissions |

### AI
| Value | Description |
|---|---|
| `ai_analyze::<container>` | LLM-powered error analysis |
| `suggest_commands::<container>` | LLM suggests fix commands |
| Free text | Sent to LLM as chat message |

## See Also

- [Architecture](ARCHITECTURE.md) — system internals
- [Getting Started](GETTING-STARTED.md) — quickstart
- [Configuration](CONFIGURATION.md) — env vars and config
