"""Dockfra — Docker infrastructure setup wizard and CLI."""
from pathlib import Path

try:
    from importlib.metadata import version as _ver
    __version__ = _ver("dockfra")
except Exception:
    _vf = Path(__file__).parent.parent / "VERSION"
    __version__ = _vf.read_text().strip() if _vf.exists() else "0.0.0"

__all__ = ["__version__"]
