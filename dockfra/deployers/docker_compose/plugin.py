"""Docker Compose deployer plugin."""

from __future__ import annotations

from pathlib import Path
import shlex

from ..base import (
    DeployerPlugin,
    DeployManifest,
    DeployResult,
    DeployStatus,
    DeployTarget,
    PlatformOS,
)
from ..health import HTTPHealthChecker
from ..ssh_utils import rsync_upload, ssh_run


class Plugin(DeployerPlugin):
    @property
    def id(self) -> str:
        return "docker_compose"

    @property
    def name(self) -> str:
        return "Docker Compose"

    @property
    def supported_os(self) -> list[PlatformOS]:
        return [PlatformOS.LINUX, PlatformOS.MACOS, PlatformOS.WINDOWS_WSL]

    def _compose_cmd(self, target: DeployTarget) -> str:
        return str(target.config.get("compose_cmd", "docker compose")).strip() or "docker compose"

    def _deploy_path(self, target: DeployTarget, manifest: DeployManifest | None = None) -> str:
        custom = str(target.config.get("deploy_path", "")).strip()
        if custom:
            return custom
        app = manifest.app_name if manifest else str(target.config.get("app_name", "app"))
        return f"/home/{target.user}/apps/{app}"

    def _compose_filename(self, target: DeployTarget, manifest: DeployManifest | None = None) -> str:
        custom = str(target.config.get("compose_file", "")).strip()
        if custom:
            return custom
        if manifest:
            return manifest.compose_file.name
        return "docker-compose.yml"

    def test_connection(self, target: DeployTarget) -> tuple[int, str]:
        return ssh_run(target, "uname -a && echo DOCKFRA_OK", timeout=20, connect_timeout=8)

    def detect(self, target: DeployTarget) -> bool:
        cmd = "docker compose version >/dev/null 2>&1 || docker-compose --version >/dev/null 2>&1"
        rc, _out = ssh_run(target, cmd, timeout=15, connect_timeout=8)
        return rc == 0

    def validate(self, manifest: DeployManifest, target: DeployTarget) -> list[str]:
        errs: list[str] = []
        if not target.host:
            errs.append("target.host is required")
        if not target.user:
            errs.append("target.user is required")
        if target.port <= 0:
            errs.append("target.port must be > 0")
        if not manifest.compose_file.exists():
            errs.append(f"compose file not found: {manifest.compose_file}")
        if not manifest.app_name:
            errs.append("manifest.app_name is required")
        return errs

    def deploy(self, manifest: DeployManifest, target: DeployTarget) -> DeployResult:
        errs = self.validate(manifest, target)
        if errs:
            return DeployResult(
                status=DeployStatus.FAILED,
                message="Validation failed",
                logs="\n".join(errs),
            )

        remote_dir = self._deploy_path(target, manifest)
        compose_file = self._compose_filename(target, manifest)
        compose_cmd = self._compose_cmd(target)

        rc_mkdir, out_mkdir = ssh_run(
            target,
            f"mkdir -p {shlex.quote(remote_dir)}",
            timeout=30,
            connect_timeout=8,
        )
        if rc_mkdir != 0:
            return DeployResult(
                status=DeployStatus.FAILED,
                message="Failed to create remote deploy directory",
                logs=out_mkdir,
            )

        rc_sync, out_sync = rsync_upload(
            target,
            manifest.compose_file.parent,
            remote_dir,
            timeout=180,
            connect_timeout=10,
        )
        if rc_sync != 0:
            return DeployResult(
                status=DeployStatus.FAILED,
                message="Failed to upload deployment files",
                logs=out_sync,
            )

        remote_compose = f"{remote_dir}/{compose_file}"
        deploy_cmd = (
            f"{compose_cmd} -f {shlex.quote(remote_compose)} pull && "
            f"{compose_cmd} -f {shlex.quote(remote_compose)} up -d"
        )
        rc_up, out_up = ssh_run(target, deploy_cmd, timeout=300, connect_timeout=10)
        if rc_up != 0:
            return DeployResult(
                status=DeployStatus.FAILED,
                message="docker compose up failed",
                logs=out_up,
            )

        checks = self.health_check(target)
        ok = all(c.get("ok", False) for c in checks) if checks else True
        return DeployResult(
            status=DeployStatus.RUNNING if ok else DeployStatus.DEPLOYING,
            message="Deployment completed",
            logs=out_up,
            health_checks=checks,
        )

    def rollback(self, target: DeployTarget, rollback_id: str) -> DeployResult:
        remote_dir = self._deploy_path(target)
        remote_compose = f"{remote_dir}/{self._compose_filename(target)}"
        compose_cmd = self._compose_cmd(target)

        rollback_cmd = (
            f"{compose_cmd} -f {shlex.quote(remote_compose)} down && "
            f"{compose_cmd} -f {shlex.quote(remote_compose)} up -d"
        )
        rc, out = ssh_run(target, rollback_cmd, timeout=180, connect_timeout=10)
        if rc != 0:
            return DeployResult(
                status=DeployStatus.FAILED,
                message=f"Rollback failed ({rollback_id})",
                logs=out,
                rollback_id=rollback_id,
            )
        return DeployResult(
            status=DeployStatus.ROLLED_BACK,
            message=f"Rollback completed ({rollback_id})",
            logs=out,
            rollback_id=rollback_id,
        )

    def status(self, target: DeployTarget) -> DeployResult:
        remote_dir = self._deploy_path(target)
        remote_compose = f"{remote_dir}/{self._compose_filename(target)}"
        compose_cmd = self._compose_cmd(target)
        cmd = f"{compose_cmd} -f {shlex.quote(remote_compose)} ps"
        rc, out = ssh_run(target, cmd, timeout=60, connect_timeout=10)
        if rc != 0:
            return DeployResult(status=DeployStatus.FAILED, message="Unable to read status", logs=out)
        return DeployResult(status=DeployStatus.RUNNING, message="Status OK", logs=out)

    def health_check(self, target: DeployTarget) -> list[dict]:
        checker = HTTPHealthChecker()
        checks: list[dict] = []

        urls = target.config.get("health_urls", [])
        if isinstance(urls, list):
            for url in urls:
                if isinstance(url, str) and url.strip():
                    checks.append(checker.check_http(url.strip()))

        if checks:
            return checks

        remote_dir = self._deploy_path(target)
        remote_compose = f"{remote_dir}/{self._compose_filename(target)}"
        compose_cmd = self._compose_cmd(target)
        rc, out = ssh_run(
            target,
            f"{compose_cmd} -f {shlex.quote(remote_compose)} ps",
            timeout=40,
            connect_timeout=10,
        )
        checks.append(
            {
                "kind": "command",
                "target": "docker compose ps",
                "ok": rc == 0,
                "status": rc,
                "details": out[:1000],
            }
        )
        return checks
