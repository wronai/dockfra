"""Health checker abstractions for deployer plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import socket
import subprocess
import urllib.request


class HealthChecker(ABC):
    """Abstract health checker interface."""

    @abstractmethod
    def check_http(self, url: str, timeout: int = 5) -> dict:
        """Check HTTP endpoint health."""

    @abstractmethod
    def check_tcp(self, host: str, port: int, timeout: int = 5) -> dict:
        """Check TCP connectivity health."""

    @abstractmethod
    def check_command(self, cmd: str, timeout: int = 10, cwd: str | Path | None = None) -> dict:
        """Check command execution health."""


class HTTPHealthChecker(HealthChecker):
    """Default health checker implementation using stdlib tools."""

    def check_http(self, url: str, timeout: int = 5) -> dict:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                code = int(getattr(resp, "status", 0) or 0)
                ok = 200 <= code < 400
                return {
                    "kind": "http",
                    "target": url,
                    "ok": ok,
                    "status": code,
                    "details": f"HTTP {code}",
                }
        except Exception as e:
            return {
                "kind": "http",
                "target": url,
                "ok": False,
                "status": 0,
                "details": str(e),
            }

    def check_tcp(self, host: str, port: int, timeout: int = 5) -> dict:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return {
                    "kind": "tcp",
                    "target": f"{host}:{port}",
                    "ok": True,
                    "status": 0,
                    "details": "connected",
                }
        except Exception as e:
            return {
                "kind": "tcp",
                "target": f"{host}:{port}",
                "ok": False,
                "status": 0,
                "details": str(e),
            }

    def check_command(self, cmd: str, timeout: int = 10, cwd: str | Path | None = None) -> dict:
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
            )
            out = ((res.stdout or "") + (res.stderr or "")).strip()
            return {
                "kind": "command",
                "target": cmd,
                "ok": res.returncode == 0,
                "status": int(res.returncode),
                "details": out[:1000],
            }
        except subprocess.TimeoutExpired:
            return {
                "kind": "command",
                "target": cmd,
                "ok": False,
                "status": 124,
                "details": "timeout",
            }
        except Exception as e:
            return {
                "kind": "command",
                "target": cmd,
                "ok": False,
                "status": 1,
                "details": str(e),
            }
