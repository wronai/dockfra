"""Shared SSH helpers for deployer plugins."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .base import DeployTarget


def _identity_file(target: DeployTarget) -> str:
    """Resolve identity file path from target config."""
    for key in ("identity_file", "ssh_key", "key_file", "private_key"):
        val = target.config.get(key)
        if val:
            return str(Path(str(val)).expanduser())
    return ""


def _run(cmd: list[str], timeout: int) -> tuple[int, str]:
    """Run command with timeout. Returns (returncode, stdout+stderr)."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = ((res.stdout or "") + (res.stderr or "")).strip()
        return res.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 1, str(e)


def _ssh_base(target: DeployTarget, connect_timeout: int) -> list[str]:
    """Build shared SSH command prefix."""
    cmd = [
        "ssh",
        "-p", str(target.port),
        "-o", f"ConnectTimeout={connect_timeout}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
    ]
    identity = _identity_file(target)
    if identity:
        cmd += ["-i", identity]
    cmd.append(f"{target.user}@{target.host}")
    return cmd


def ssh_run(target: DeployTarget, cmd: str, timeout: int = 30, connect_timeout: int = 10) -> tuple[int, str]:
    """Run SSH command on target."""
    full = _ssh_base(target, connect_timeout) + [cmd]
    return _run(full, timeout=timeout)


def scp_upload(target: DeployTarget, src: str | Path, dst: str, timeout: int = 30, connect_timeout: int = 10) -> tuple[int, str]:
    """Upload file/dir to target over SCP."""
    src_path = Path(src).expanduser()
    if not src_path.exists():
        return 1, f"source not found: {src_path}"

    cmd = [
        "scp",
        "-P", str(target.port),
        "-o", f"ConnectTimeout={connect_timeout}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
    ]
    identity = _identity_file(target)
    if identity:
        cmd += ["-i", identity]
    cmd += [str(src_path), f"{target.user}@{target.host}:{dst}"]
    return _run(cmd, timeout=timeout)


def rsync_upload(target: DeployTarget, src: str | Path, dst: str, timeout: int = 60, connect_timeout: int = 10) -> tuple[int, str]:
    """Upload files to target over rsync + SSH."""
    src_path = Path(src).expanduser()
    if not src_path.exists():
        return 1, f"source not found: {src_path}"

    ssh_cmd = [
        "ssh",
        "-p", str(target.port),
        "-o", f"ConnectTimeout={connect_timeout}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
    ]
    identity = _identity_file(target)
    if identity:
        ssh_cmd += ["-i", identity]

    rsync_src = str(src_path)
    if src_path.is_dir() and not rsync_src.endswith("/"):
        rsync_src += "/"

    cmd = [
        "rsync",
        "-az",
        "-e", " ".join(shlex.quote(p) for p in ssh_cmd),
        rsync_src,
        f"{target.user}@{target.host}:{dst}",
    ]
    return _run(cmd, timeout=timeout)


def test_connection(target: DeployTarget, timeout: int = 10) -> tuple[int, str]:
    """Verify SSH connectivity to target."""
    return ssh_run(target, "echo DOCKFRA_SSH_OK", timeout=timeout, connect_timeout=timeout)


# Prevent pytest from collecting this helper as a test function.
test_connection.__test__ = False
