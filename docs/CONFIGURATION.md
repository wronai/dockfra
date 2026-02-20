# Dockfra Configuration

> How Dockfra discovers, manages, and applies configuration for any Docker project.

## Configuration Layers

Dockfra uses a **layered configuration** system. Each layer overrides the previous:

```
1. Auto-discovered defaults (from docker-compose.yml files)
2. dockfra.yaml (optional project config)
3. dockfra/.env (persisted user values)
4. Environment variables (runtime overrides)
```

## 1. Auto-Discovery

### Stack Discovery

On startup, Dockfra scans `ROOT` for subdirectories containing `docker-compose.yml`:

```python
STACKS = _discover_stacks()
# Result: {"app": Path("/project/app"), "management": Path("/project/management"), ...}
```

Skipped directories: `.git`, `.venv`, `__pycache__`, `node_modules`, `dockfra`, `shared`, `scripts`, `tests`, `keys`, `.github`.

### Environment Variable Discovery

All `docker-compose.yml` files are parsed for `${VAR:-default}` patterns:

```yaml
# docker-compose.yml
services:
  db:
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-myapp}      # → discovered: default "myapp"
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}       # → discovered: no default
```

This produces:
- **Variable name** → auto-labeled (e.g., `POSTGRES_USER` → "Postgres User")
- **Type inference** → names containing `PASSWORD`, `SECRET`, `KEY`, `TOKEN` → password field
- **Stack grouping** → grouped by which stack's compose file contains the variable
- **Default values** → extracted from `:-default` syntax

Currently discovers **55+ variables** from compose files automatically.

### Git Auto-Detection

The wizard auto-detects:

| Field | Source |
|---|---|
| `GIT_REPO_URL` | `git remote get-url origin` |
| `GIT_BRANCH` | `git branch --show-current` + all branches as chips |
| `GIT_NAME` | `git config --global user.name` |
| `GIT_EMAIL` | `git config --global user.email` |
| `APP_VERSION` | `git describe --tags --abbrev=0` |
| `APP_NAME` | Root directory name |
| `GITHUB_SSH_KEY` | `~/.ssh/id_ed25519` existence check |
| `OPENROUTER_API_KEY` | getv profile or `~/.getv/llm/openrouter.env` |

## 2. `dockfra.yaml` — Project Config

Optional file in project root. Overrides auto-discovered metadata.

### Minimal Example

```yaml
# dockfra.yaml
lang: pl
```

### Full Example

```yaml
# dockfra.yaml — project-specific wizard configuration
lang: pl    # UI language (pl, en, de, fr, es, it, pt, cs, ro, nl)

env:
  # Override labels, types, groups for discovered variables
  POSTGRES_PASSWORD:
    label: "Hasło bazy danych"
    type: password
    group: Database
    desc: "Hasło PostgreSQL. Generuj losowe."

  REDIS_PASSWORD:
    label: "Hasło Redis"
    group: Cache

  # Add custom variables not in docker-compose
  MY_CUSTOM_VAR:
    label: "Custom Setting"
    group: Custom
    type: text
    default: "value"
    placeholder: "Enter value..."
```

### Supported Fields per Variable

| Field | Type | Description |
|---|---|---|
| `label` | string | Display name in wizard UI |
| `group` | string | Settings section grouping |
| `type` | `text` / `password` / `select` | Input field type |
| `desc` | string | Help text (shown via ℹ️ button) |
| `placeholder` | string | Input placeholder text |
| `default` | string | Default value |
| `required_for` | list | Stack names that require this var |
| `autodetect` | bool | Show ⚡ auto-detect button |
| `options` | list | For select type: `[["value", "Label"], ...]` |

## 3. `dockfra/.env` — Persisted Values

All wizard settings are saved to `dockfra/.env`:

```bash
# dockfra/.env (auto-managed by wizard)
ENVIRONMENT=local
STACKS=all
GIT_REPO_URL=git@github.com:org/app.git
GIT_BRANCH=main
POSTGRES_USER=myapp
POSTGRES_PASSWORD=s3cr3t
LLM_MODEL=google/gemini-flash-1.5
OPENROUTER_API_KEY=sk-or-v1-...
```

### Load/Save Functions

```python
from dockfra.core import load_env, save_env

env = load_env()           # Returns dict with schema defaults + .env values
save_env({"KEY": "val"})   # Merges into existing .env file
```

## 4. Environment Variables

Runtime overrides (highest priority):

| Variable | Default | Description |
|---|---|---|
| `DOCKFRA_ROOT` | Parent of `dockfra/` package | Project root directory |
| `DOCKFRA_PREFIX` | `dockfra` | Prefix for all container/image/network names |

```bash
DOCKFRA_PREFIX=myapp DOCKFRA_ROOT=/path/to/project python -m dockfra
```

## ENV_SCHEMA Structure

The final schema is built by `_build_env_schema()`:

```python
ENV_SCHEMA = [
    # Core entries (always present)
    {"key": "ENVIRONMENT", "label": "Środowisko", "group": "Infrastructure",
     "type": "select", "options": [("local","Local"), ("production","Production")],
     "default": "local"},

    # Auto-discovered from docker-compose.yml
    {"key": "POSTGRES_USER", "label": "Postgres User", "group": "App",
     "type": "text", "default": "dockfra", "required_for": ["app"]},

    # With dockfra.yaml override
    {"key": "POSTGRES_PASSWORD", "label": "Hasło bazy danych", "group": "Database",
     "type": "password", "desc": "Hasło PostgreSQL. Generuj losowe.",
     "required_for": ["app"]},
]
```

### Core Schema Entries (always present)

| Group | Variables |
|---|---|
| Infrastructure | `ENVIRONMENT`, `STACKS` |
| Git | `GIT_REPO_URL`, `GIT_BRANCH`, `GIT_NAME`, `GIT_EMAIL`, `GITHUB_SSH_KEY` |
| LLM | `OPENROUTER_API_KEY`, `LLM_MODEL` |
| Ports | `WIZARD_PORT` |

All other variables are auto-discovered from compose files.

### `_FIELD_META` — Built-in Descriptions

Dockfra ships with descriptions for ~40 commonly used Docker variables (ports, database, Traefik, SSH, etc.). These are applied automatically to matching discovered variables.

## `_ENV_TO_STATE` — Auto-Generated Mapping

The mapping between ENV keys and internal state keys is auto-generated:

```python
# Auto-generated from ENV_SCHEMA
_ENV_TO_STATE = {e["key"]: e["key"].lower() for e in ENV_SCHEMA}
# With backward-compat aliases:
#   GITHUB_SSH_KEY → github_key
#   OPENROUTER_API_KEY → openrouter_key
```

## COMMON_PORTS — Dynamic Port List

The port scanning list is built dynamically from ENV_SCHEMA:

```python
# Extracted from all ENV_SCHEMA entries in group "Ports" with numeric defaults
# Merged with standard ports: 22, 80, 443, 2222, 3000, 5000, 8000, 8080, 9000
COMMON_PORTS = sorted(_schema_ports | {22, 80, 443, ...})
```

## See Also

- [Architecture](ARCHITECTURE.md) — system overview
- [Getting Started](GETTING-STARTED.md) — quickstart guide
- [SSH Roles](SSH-ROLES.md) — role system configuration
