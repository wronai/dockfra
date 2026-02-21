"""Plugin registry and discovery for deployers."""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from pathlib import Path
from types import ModuleType

from .base import DeployerPlugin

_PLUGINS: dict[str, DeployerPlugin] = {}


def _register_plugin_instance(instance: DeployerPlugin) -> None:
    """Register plugin instance in the global registry."""
    if not instance.id:
        return
    _PLUGINS[instance.id] = instance


def _register_plugin_from_module(mod: ModuleType) -> bool:
    """Register Plugin class from module. Returns True when successful."""
    cls = getattr(mod, "Plugin", None)
    if not cls:
        return False
    try:
        instance = cls()
    except Exception:
        return False
    if not isinstance(instance, DeployerPlugin):
        return False
    _register_plugin_instance(instance)
    return True


def _discover_internal_plugins() -> None:
    """Discover plugins from ``dockfra/deployers/*/plugin.py``."""
    pkg_path = Path(__file__).parent
    base_pkg = __package__ or "dockfra.deployers"
    for _finder, name, ispkg in pkgutil.iter_modules([str(pkg_path)]):
        if not ispkg or name.startswith("_") or name == "__pycache__":
            continue
        mod_name = f"{base_pkg}.{name}.plugin"
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        _register_plugin_from_module(mod)


def _iter_external_plugin_files(extra_dir: Path):
    """Yield plugin.py files from external plugin dirs."""
    # direct: /path/to/plugin.py
    direct = extra_dir / "plugin.py"
    if direct.is_file():
        yield direct
    # package dirs: /path/<name>/plugin.py
    for child in extra_dir.iterdir() if extra_dir.exists() else []:
        if not child.is_dir() or child.name.startswith("."):
            continue
        plugin_file = child / "plugin.py"
        if plugin_file.is_file():
            yield plugin_file


def _discover_external_plugins(extra_dirs: list[Path]) -> None:
    """Discover plugins from user-provided directories."""
    for root in extra_dirs:
        d = Path(root).expanduser().resolve()
        if not d.exists() or not d.is_dir():
            continue
        for plugin_file in _iter_external_plugin_files(d):
            mod_name = f"dockfra_ext_deployer_{plugin_file.parent.name}_{abs(hash(str(plugin_file)))}"
            try:
                spec = importlib.util.spec_from_file_location(mod_name, str(plugin_file))
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            except Exception:
                continue
            _register_plugin_from_module(mod)


def discover_plugins(extra_dirs: list[Path] | None = None, force_reload: bool = False) -> dict[str, DeployerPlugin]:
    """Auto-discover plugins from package and optional external directories."""
    if force_reload:
        _PLUGINS.clear()
    elif _PLUGINS and not extra_dirs:
        return dict(_PLUGINS)

    _discover_internal_plugins()
    if extra_dirs:
        _discover_external_plugins(extra_dirs)
    return dict(_PLUGINS)


def get_plugin(plugin_id: str) -> DeployerPlugin | None:
    """Return plugin by ID."""
    if plugin_id in _PLUGINS:
        return _PLUGINS[plugin_id]
    discover_plugins()
    return _PLUGINS.get(plugin_id)


def list_plugins() -> list[dict]:
    """List discovered plugin metadata."""
    if not _PLUGINS:
        discover_plugins()
    out = []
    for p in _PLUGINS.values():
        out.append({
            "id": p.id,
            "name": p.name,
            "supported_os": [os_.value for os_ in p.supported_os],
        })
    return sorted(out, key=lambda x: x["id"])
