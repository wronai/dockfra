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
from dockfra.deployers.docker_compose.plugin import Plugin as DockerComposePlugin


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
    assert "docker_compose" in plugins


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


def test_docker_compose_detect_with_docker(monkeypatch):
    plugin = DockerComposePlugin()
    target = DeployTarget(host="10.0.0.2", port=22, user="deployer")

    import dockfra.deployers.docker_compose.plugin as mod

    monkeypatch.setattr(mod, "ssh_run", lambda *_a, **_kw: (0, "ok"))
    assert plugin.detect(target) is True


def test_docker_compose_detect_without_docker(monkeypatch):
    plugin = DockerComposePlugin()
    target = DeployTarget(host="10.0.0.2", port=22, user="deployer")

    import dockfra.deployers.docker_compose.plugin as mod

    monkeypatch.setattr(mod, "ssh_run", lambda *_a, **_kw: (1, "docker: command not found"))
    assert plugin.detect(target) is False


def test_docker_compose_validate_missing_compose(tmp_path):
    plugin = DockerComposePlugin()
    manifest = DeployManifest(
        app_name="app",
        version="1.0.0",
        compose_file=tmp_path / "missing.yml",
    )
    target = DeployTarget(host="10.0.0.2", port=22, user="deployer")
    errs = plugin.validate(manifest, target)
    assert any("compose file not found" in e for e in errs)


def test_docker_compose_validate_ok(tmp_path):
    plugin = DockerComposePlugin()
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services:\n  web:\n    image: nginx:latest\n")
    manifest = DeployManifest(app_name="app", version="1.0.0", compose_file=compose)
    target = DeployTarget(host="10.0.0.2", port=22, user="deployer")
    assert plugin.validate(manifest, target) == []


def test_docker_compose_deploy_mock(tmp_path, monkeypatch):
    plugin = DockerComposePlugin()
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services:\n  web:\n    image: nginx:latest\n")
    manifest = DeployManifest(app_name="app", version="1.0.0", compose_file=compose)
    target = DeployTarget(host="10.0.0.2", port=22, user="deployer")

    import dockfra.deployers.docker_compose.plugin as mod

    def fake_ssh_run(_target, cmd, timeout=0, connect_timeout=0):
        if "mkdir -p" in cmd:
            return 0, "mkdir ok"
        if "pull" in cmd and "up -d" in cmd:
            return 0, "deploy ok"
        if " ps" in cmd:
            return 0, "web  running"
        return 0, "ok"

    monkeypatch.setattr(mod, "ssh_run", fake_ssh_run)
    monkeypatch.setattr(mod, "rsync_upload", lambda *_a, **_kw: (0, "sync ok"))

    result = plugin.deploy(manifest, target)
    assert result.status == DeployStatus.RUNNING
    assert "Deployment completed" in result.message


def test_docker_compose_rollback_mock(monkeypatch):
    plugin = DockerComposePlugin()
    target = DeployTarget(host="10.0.0.2", port=22, user="deployer")

    import dockfra.deployers.docker_compose.plugin as mod

    monkeypatch.setattr(mod, "ssh_run", lambda *_a, **_kw: (0, "rollback ok"))
    result = plugin.rollback(target, rollback_id="rb-1")
    assert result.status == DeployStatus.ROLLED_BACK
    assert result.rollback_id == "rb-1"


def test_docker_compose_health_check_mock(monkeypatch):
    plugin = DockerComposePlugin()
    target = DeployTarget(
        host="10.0.0.2",
        port=22,
        user="deployer",
        config={"health_urls": ["http://service.local/health"]},
    )

    import dockfra.deployers.docker_compose.plugin as mod

    class _DummyChecker:
        def check_http(self, url: str, timeout: int = 5):
            return {"kind": "http", "target": url, "ok": True, "status": 200, "details": "OK"}

    monkeypatch.setattr(mod, "HTTPHealthChecker", _DummyChecker)
    checks = plugin.health_check(target)
    assert checks and checks[0]["ok"] is True


def test_cli_targets(monkeypatch, capsys):
    from dockfra import cli as _cli

    class _Client:
        def deploy_targets(self):
            return {
                "targets": [
                    {
                        "id": "edge-rpi3",
                        "platform": "docker_compose",
                        "user": "pi",
                        "host": "192.168.1.100",
                        "port": 22,
                        "os": "linux",
                        "labels": {"env": "edge"},
                    }
                ]
            }, None

    rc = _cli.cmd_targets(_Client(), [])
    out = capsys.readouterr().out

    assert rc == 0
    assert "edge-rpi3" in out
    assert "docker_compose" in out


def test_cli_deploy(monkeypatch, capsys):
    from dockfra import cli as _cli

    class _Client:
        def deploy(self, target_id, data=None):
            assert target_id == "edge-rpi3"
            assert isinstance(data, dict)
            return {"ok": True, "result": {"status": "running", "message": "Deployment completed"}}, None

    rc = _cli.cmd_deploy(_Client(), ["edge-rpi3"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Deploy finished" in out


def test_step_deploy_with_plugin(monkeypatch, tmp_path):
    pytest.importorskip("flask_socketio")
    from dockfra import steps as steps_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services:\n  web:\n    image: nginx:latest\n")

    emitted: list[tuple[str, dict]] = []
    deployed = {"ok": False}

    class _Plugin:
        id = "docker_compose"

        def detect(self, _target):
            return True

        def deploy(self, _manifest, _target):
            deployed["ok"] = True
            return DeployResult(status=DeployStatus.RUNNING, message="ok")

    class _SyncThread:
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(steps_mod.threading, "Thread", _SyncThread)
    monkeypatch.setattr(steps_mod, "_get_deployer_plugin", lambda _platform: _Plugin())
    monkeypatch.setattr(
        steps_mod,
        "_operation_target_from_state",
        lambda *_a, **_kw: (
            "edge-rpi3",
            DeployTarget(host="10.0.0.2", port=22, user="pi", platform="docker_compose"),
        ),
    )
    monkeypatch.setattr(steps_mod, "_resolve_target_compose_file", lambda _target: compose)
    monkeypatch.setattr(steps_mod, "_update_device_env", lambda *_a, **_kw: None)
    monkeypatch.setattr(steps_mod, "load_env", lambda: {})
    monkeypatch.setattr(steps_mod, "clear_widgets", lambda: None)
    monkeypatch.setattr(steps_mod, "msg", lambda *_a, **_kw: None)
    monkeypatch.setattr(steps_mod, "progress", lambda *_a, **_kw: None)
    monkeypatch.setattr(steps_mod, "code_block", lambda *_a, **_kw: None)

    class _Socket:
        @staticmethod
        def emit(event, data):
            emitted.append((event, data))

    monkeypatch.setattr(steps_mod, "socketio", _Socket)

    form = {
        "deploy_target_id": "edge-rpi3",
        "device_ip": "10.0.0.2",
        "device_user": "pi",
        "device_port": "22",
    }
    steps_mod.step_do_deploy(form)

    assert deployed["ok"] is True
    assert any(
        ev == "widget" and any(i.get("value") == "launch_devices" for i in data.get("items", []))
        for ev, data in emitted
    )


def test_pipeline_with_deploy_step(monkeypatch, tmp_path):
    pytest.importorskip("flask_socketio")
    from dockfra import app as app_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services:\n  web:\n    image: nginx:latest\n")

    class _Plugin:
        id = "docker_compose"

        def validate(self, _manifest, _target):
            return []

        def deploy(self, _manifest, _target):
            return DeployResult(
                status=DeployStatus.RUNNING,
                message="deploy ok",
                logs="ok",
                health_checks=[{"kind": "http", "ok": True}],
            )

        def health_check(self, _target):
            return [{"kind": "http", "ok": True}]

    class _PState:
        def __init__(self):
            self.steps = []
            self.decisions = []

        def record_step(self, result):
            self.steps.append(result)

        def record_decision(self, decision, reason):
            self.decisions.append((decision, reason))

    target = DeployTarget(
        host="10.0.0.2",
        port=22,
        user="pi",
        platform="docker_compose",
        config={"compose_path_local": str(compose)},
    )

    monkeypatch.setattr(app_mod, "load_deploy_targets", lambda: {"edge-rpi3": target})
    monkeypatch.setattr(app_mod, "_discover_deployers", lambda: None)
    monkeypatch.setattr(app_mod, "_get_deployer", lambda _platform: _Plugin())
    monkeypatch.setattr(app_mod, "load_env", lambda: {})
    monkeypatch.setattr(app_mod, "msg", lambda *_a, **_kw: None)
    monkeypatch.setattr(app_mod, "buttons", lambda *_a, **_kw: None)

    ps = _PState()
    ok = app_mod._pipeline_deploy_and_verify(ps, "developer", "T-0001", "edge-rpi3")

    assert ok is True
    assert any(getattr(s, "step", "") == "deploy" for s in ps.steps)
    assert any(getattr(s, "step", "") == "verify-deploy" for s in ps.steps)
