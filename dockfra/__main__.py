"""Entry point for `python -m dockfra` and the `dockfra` CLI command."""
import argparse
import os
import sys
from pathlib import Path


def _serve(host: str, port: int, root: str | None) -> None:
    if root:
        os.environ["DOCKFRA_ROOT"] = str(Path(root).resolve())
    # Ensure llm_client is importable (bundled alongside app.py)
    _pkg = Path(__file__).parent
    if str(_pkg) not in sys.path:
        sys.path.insert(0, str(_pkg))
    from dockfra import app as _app_module  # noqa: F401 – triggers module load
    from dockfra.app import app, socketio
    print(f"🧙 Dockfra Wizard  →  http://{host}:{port}")
    print(f"   Project root     :  {os.environ.get('DOCKFRA_ROOT', Path(__file__).parent.parent)}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


def _cli(args: list[str]) -> None:
    from dockfra import cli as _cli_module  # noqa: F401
    sys.argv = ["dockfra-cli"] + args
    _cli_module.main()


def _cli_entry() -> None:
    """Entry point for the `dockfra-cli` console script."""
    _cli(sys.argv[1:])


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dockfra",
        description="Dockfra — Docker infrastructure wizard & CLI",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--port",    type=int, default=5050, help="Wizard HTTP port (default 5050)")
    parser.add_argument("--host",    default="0.0.0.0",      help="Bind address (default 0.0.0.0)")
    parser.add_argument("--root",    default=None,           help="Project root directory (default: cwd)")
    parser.add_argument(
        "command", nargs="?",
        choices=["serve", "cli", "version"],
        default="serve",
        help="serve (default) | cli — start TUI shell | version",
    )
    # Pass remaining args to CLI sub-command
    parsed, rest = parser.parse_known_args()

    if parsed.version or parsed.command == "version":
        from dockfra import __version__
        print(f"dockfra {__version__}")
        return

    if parsed.command == "cli":
        _cli(rest)
        return

    _serve(parsed.host, parsed.port, parsed.root or os.getcwd())


if __name__ == "__main__":
    main()
