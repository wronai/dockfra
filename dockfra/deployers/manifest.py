"""Build deployment manifest objects from compose files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import DeployManifest


def _load_compose_yaml(compose_path: Path) -> dict[str, Any]:
    """Load docker-compose YAML as dict.

    If PyYAML is unavailable or parsing fails, returns an empty structure.
    """
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(compose_path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _collect_image_tags(services: dict[str, Any]) -> list[str]:
    """Collect unique image tags from compose services."""
    seen: set[str] = set()
    out: list[str] = []
    for svc in services.values() if isinstance(services, dict) else []:
        if not isinstance(svc, dict):
            continue
        img = str(svc.get("image", "")).strip()
        if not img or img in seen:
            continue
        seen.add(img)
        out.append(img)
    return out


def _collect_env_vars(services: dict[str, Any]) -> dict[str, str]:
    """Collect env vars from compose services.

    Supports both list and dict compose environment notation.
    """
    envs: dict[str, str] = {}
    for svc in services.values() if isinstance(services, dict) else []:
        if not isinstance(svc, dict):
            continue
        env = svc.get("environment", {})
        if isinstance(env, dict):
            for k, v in env.items():
                if k:
                    envs[str(k)] = "" if v is None else str(v)
        elif isinstance(env, list):
            for item in env:
                if not isinstance(item, str):
                    continue
                if "=" in item:
                    k, v = item.split("=", 1)
                    if k:
                        envs[k] = v
                elif item:
                    envs[item] = ""
    return envs


def build_manifest(compose_path: str | Path, env: dict[str, str] | None = None) -> DeployManifest:
    """Build DeployManifest from docker-compose file and optional runtime env."""
    compose_file = Path(compose_path).expanduser().resolve()
    if not compose_file.exists():
        raise FileNotFoundError(f"compose file not found: {compose_file}")

    data = _load_compose_yaml(compose_file)
    services = data.get("services", {}) if isinstance(data, dict) else {}

    env_vars = _collect_env_vars(services)
    if env:
        for k, v in env.items():
            env_vars[str(k)] = "" if v is None else str(v)

    app_name = compose_file.parent.name
    version = (env or {}).get("APP_VERSION", "") if env else ""
    if not version:
        version = "latest"

    extra_files = [compose_file]
    env_file = compose_file.parent / ".env"
    if env_file.exists():
        extra_files.append(env_file)

    return DeployManifest(
        app_name=app_name,
        version=version,
        compose_file=compose_file,
        env_vars=env_vars,
        image_tags=_collect_image_tags(services),
        extra_files=extra_files,
    )
