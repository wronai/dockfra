"""Unit tests for deployer foundation (Phase 1: T-0100..T-0105)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from dockfra.deployers import discover_plugins, get_plugin, list_plugins
from dockfra.deployers.base import (
    DeployerPlugin,
    DeployManifest,
    DeployResult,
    DeployStatus,
    DeployTarget,
    PlatformOS,
)
from dockfra.deployers.health import HTTPHealthChecker
from dockfra.deployers.manifest import build_manifest
from dockfra.deployers.ssh_utils import ssh_run, test_connection


def test_deployers_package_import_exports():
    import dockfra.deployers as deployers

    assert callable(deployers.discover_plugins)
    assert callable(deployers.get_plugin)
    assert callable(deployers.list_plugins)


def test_deployer_plugin_is_abstract():
    with pytest.raises(TypeError):
        DeployerPlugin()


def test_registry_empty_external_dir(tmp_path):
    plugins = discover_plugins(extra_dirs=[tmp_path], force_reload=True)
    assert isinstance(plugins, dict)
    assert plugins == {}


def test_registry_can_load_external_plugin(tmp_path):
    plugin_dir = tmp_path / "example"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin_file = plugin_dir / "plugin.py"
    plugin_file.write_text(
        "\n".join(
            [
                "from dockfra.deployers.base import DeployerPlugin, DeployResult, DeployStatus, PlatformOS",
                "",
                "class Plugin(DeployerPlugin):",
                "    @property",
                "    def id(self): return 'dummy'",
                "    @property",
                "    def name(self): return 'Dummy'",
                "    @property",
                "    def supported_os(self): return [PlatformOS.ANY]",
                "    def detect(self, target): return True",
                "    def validate(self, manifest, target): return []",
                "    def deploy(self, manifest, target): return DeployResult(status=DeployStatus.RUNNING, message='ok')",
                "    def rollback(self, target, rollback_id): return DeployResult(status=DeployStatus.ROLLED_BACK, message='rb')",
                "    def status(self, target): return DeployResult(status=DeployStatus.RUNNING, message='st')",
                "    def health_check(self, target): return []",
            ]
        )
    )

    plugins = discover_plugins(extra_dirs=[tmp_path], force_reload=True)
    assert "dummy" in plugins
    assert get_plugin("dummy") is not None
    assert any(p["id"] == "dummy" for p in list_plugins())


def test_build_manifest_from_compose(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        """
services:
  web:
    image: nginx:1.27
    environment:
      APP_ENV: production
      PORT: "8080"
  db:
    image: postgres:16
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=myapp
""".strip()
    )

    m = build_manifest(compose, env={"APP_VERSION": "1.2.3", "EXTRA": "ok"})

    assert isinstance(m, DeployManifest)
    assert m.app_name == tmp_path.name
    assert m.version == "1.2.3"
    assert m.compose_file == compose.resolve()
    assert "nginx:1.27" in m.image_tags
    assert "postgres:16" in m.image_tags
    assert m.env_vars["APP_ENV"] == "production"
    assert m.env_vars["POSTGRES_DB"] == "myapp"
    assert m.env_vars["EXTRA"] == "ok"


def test_http_health_checker_with_mock(monkeypatch):
    checker = HTTPHealthChecker()

    class DummyResp:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    import urllib.request as _url

    monkeypatch.setattr(_url, "urlopen", lambda *_a, **_kw: DummyResp())
    result = checker.check_http("http://example.test")

    assert result["ok"] is True
    assert result["status"] == 204


def test_ssh_run_builds_command(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", fake_run)

    target = DeployTarget(host="10.0.0.2", port=2222, user="deployer", config={"identity_file": "~/.ssh/id_ed25519"})
    rc, out = ssh_run(target, "echo hi", timeout=12, connect_timeout=3)

    assert rc == 0
    assert out == "ok"
    assert calls
    cmd = calls[0]
    assert cmd[0] == "ssh"
    assert "-p" in cmd and "2222" in cmd
    assert "deployer@10.0.0.2" in cmd
    assert "echo hi" in cmd


def test_test_connection_surfaces_failure(monkeypatch):
    def fake_run(_cmd, capture_output, text, timeout):
        return SimpleNamespace(returncode=255, stdout="", stderr="No route to host")

    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", fake_run)

    target = DeployTarget(host="203.0.113.1", port=22, user="deployer")
    rc, out = test_connection(target, timeout=2)

    assert rc == 255
    assert "No route" in out


def test_deploy_result_dataclass_fields():
    result = DeployResult(status=DeployStatus.RUNNING, message="ok", health_checks=[{"service": "api", "ok": True}])
    assert result.status == DeployStatus.RUNNING
    assert result.message == "ok"
    assert result.health_checks[0]["service"] == "api"


def test_platform_os_enum_values():
    assert PlatformOS.LINUX.value == "linux"
    assert PlatformOS.ANY.value == "any"
