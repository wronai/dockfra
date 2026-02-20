"""Dockfra — Docker infrastructure setup wizard and CLI."""
from pathlib import Path

try:
    from importlib.metadata import version as _ver
    __version__ = _ver("dockfra")
except Exception:
    for _vf in (Path(__file__).parent / "VERSION", Path(__file__).parent.parent / "VERSION"):
        if _vf.exists():
            __version__ = _vf.read_text().strip()
            break
    else:
        __version__ = "0.0.0"

__all__ = ["__version__"]
