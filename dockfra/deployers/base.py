"""Base types and abstract interface for deployer plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PlatformOS(str, Enum):
    """Supported target operating systems."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS_WSL = "windows_wsl"
    ANY = "any"


class DeployStatus(str, Enum):
    """Deployment lifecycle status."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeployTarget:
    """Deployment target definition (host/cluster + plugin config)."""

    host: str
    port: int = 22
    user: str = "deployer"
    platform: str = "docker_compose"
    os: PlatformOS = PlatformOS.LINUX
    labels: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeployManifest:
    """Deployment artifact representation."""

    app_name: str
    version: str
    compose_file: Path
    env_vars: dict[str, str] = field(default_factory=dict)
    image_tags: list[str] = field(default_factory=list)
    extra_files: list[Path] = field(default_factory=list)


@dataclass
class DeployResult:
    """Result of deploy/rollback/status operations."""

    status: DeployStatus
    message: str = ""
    logs: str = ""
    rollback_id: str = ""
    health_checks: list[dict[str, Any]] = field(default_factory=list)


class DeployerPlugin(ABC):
    """Base class for all deployment plugins."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique plugin ID, e.g. ``docker_compose``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""

    @property
    @abstractmethod
    def supported_os(self) -> list[PlatformOS]:
        """List of operating systems supported by this plugin."""

    @abstractmethod
    def detect(self, target: DeployTarget) -> bool:
        """Return True if required runtime/tooling exists on target."""

    @abstractmethod
    def validate(self, manifest: DeployManifest, target: DeployTarget) -> list[str]:
        """Validate target + manifest before deploy; empty list means OK."""

    @abstractmethod
    def deploy(self, manifest: DeployManifest, target: DeployTarget) -> DeployResult:
        """Execute deployment on target."""

    @abstractmethod
    def rollback(self, target: DeployTarget, rollback_id: str) -> DeployResult:
        """Rollback target to a previous deploy state."""

    @abstractmethod
    def status(self, target: DeployTarget) -> DeployResult:
        """Query current deploy status from target."""

    @abstractmethod
    def health_check(self, target: DeployTarget) -> list[dict[str, Any]]:
        """Run plugin-specific health checks."""

    def pre_deploy(self, manifest: DeployManifest, target: DeployTarget) -> None:
        """Optional hook executed before ``deploy``."""

    def post_deploy(self, result: DeployResult, target: DeployTarget) -> None:
        """Optional hook executed after ``deploy``."""

    def convert_compose(self, compose_path: Path) -> str:
        """Optional conversion from docker-compose to platform-native format."""
        return ""
