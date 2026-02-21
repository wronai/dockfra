# Dockfra — Plan Optymalizacji Wdrożeniowej

## Spis treści

1. [Analiza obecnego stanu](#1-analiza-obecnego-stanu)
2. [Architektura systemu pluginowego](#2-architektura-systemu-pluginowego)
3. [Pluginy platform wdrożeniowych](#3-pluginy-platform-wdrożeniowych)
4. [Zmiany w istniejącym kodzie](#4-zmiany-w-istniejącym-kodzie)
5. [TODO dla lokalnego LLM — krok po kroku](#5-todo-dla-lokalnego-llm--krok-po-kroku)

---

## 1. Analiza obecnego stanu

### Co mamy

Obecnie `ssh-deployer` (rola Monitor w `ssh-monitor`) wdraża wyłącznie przez:

- SSH do kontenerów `devices/` (emulacja RPi3)
- `docker compose up` na hoście docelowym
- Weryfikacja przez HTTP `/health`

Ograniczenia:

- **Brak abstrakcji platformy** — deploy jest sztywno powiązany z Docker Compose
- **Brak obsługi Podman, K8s, Nomad, Swarm** — zero pluginów
- **Brak multi-OS** — skrypty zakładają Linux/Debian (apt, systemd)
- **Monolityczny `steps.py` i `engines.py`** — logika deploy wpleciona w wizard flow
- **Brak registry artefaktów** — deploy kopiuje pliki przez SSH, brak OCI push

### Co trzeba zmienić

| Obszar | Obecny stan | Cel |
|--------|------------|-----|
| Deploy target | Tylko Docker Compose + SSH | Plugin per platforma |
| OS support | Tylko Linux (Debian) | Linux, macOS, Windows (WSL) |
| Runtime | Tylko Docker | Docker, Podman, K8s, Nomad, Swarm |
| Artefakty | Kopia plików przez SSH | OCI registry + deploy manifest |
| Konfiguracja | Sztywne `.env` | Per-target deploy config (YAML) |
| Rollback | Brak | Per-plugin rollback strategy |
| Health check | Tylko HTTP `/health` | Pluginowy health provider |

---

## 2. Architektura systemu pluginowego

### 2.1 Struktura katalogów

```
dockfra/
├── deployers/                      # ══ SYSTEM PLUGINOWY ══
│   ├── __init__.py                 # Registry + discovery
│   ├── base.py                     # DeployerPlugin ABC
│   ├── registry.py                 # PluginRegistry (auto-load)
│   ├── manifest.py                 # DeployManifest dataclass
│   ├── health.py                   # HealthChecker ABC
│   │
│   ├── docker_compose/             # Plugin: Docker Compose (obecny default)
│   │   ├── __init__.py
│   │   ├── plugin.py               # DockerComposeDeployer(DeployerPlugin)
│   │   ├── health.py               # HTTPHealthChecker
│   │   └── plugin.yaml             # Metadata + capabilities
│   │
│   ├── podman/                     # Plugin: Podman / Podman Compose
│   │   ├── __init__.py
│   │   ├── plugin.py               # PodmanDeployer(DeployerPlugin)
│   │   ├── health.py
│   │   ├── quadlet.py              # Generacja Quadlet unit files
│   │   └── plugin.yaml
│   │
│   ├── kubernetes/                 # Plugin: Kubernetes
│   │   ├── __init__.py
│   │   ├── plugin.py               # KubernetesDeployer(DeployerPlugin)
│   │   ├── health.py               # K8s probe-based health
│   │   ├── manifests.py            # Generacja YAML z compose
│   │   └── plugin.yaml
│   │
│   ├── swarm/                      # Plugin: Docker Swarm
│   │   ├── __init__.py
│   │   ├── plugin.py               # SwarmDeployer(DeployerPlugin)
│   │   └── plugin.yaml
│   │
│   ├── nomad/                      # Plugin: HashiCorp Nomad
│   │   ├── __init__.py
│   │   ├── plugin.py               # NomadDeployer(DeployerPlugin)
│   │   ├── jobspec.py              # Generacja HCL z compose
│   │   └── plugin.yaml
│   │
│   └── ssh_raw/                    # Plugin: Raw SSH (skrypty)
│       ├── __init__.py
│       ├── plugin.py               # SSHRawDeployer(DeployerPlugin)
│       └── plugin.yaml
```

### 2.2 Bazowa klasa pluginu (`base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class PlatformOS(Enum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS_WSL = "windows_wsl"
    ANY = "any"


class DeployStatus(Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeployTarget:
    """Cel wdrożenia — jeden host/klaster."""
    host: str                           # IP lub hostname
    port: int = 22                      # SSH port
    user: str = "deployer"              # SSH user
    platform: str = "docker_compose"    # ID pluginu
    os: PlatformOS = PlatformOS.LINUX
    labels: dict = field(default_factory=dict)   # np. {"env": "prod", "region": "eu"}
    config: dict = field(default_factory=dict)   # plugin-specific config


@dataclass
class DeployManifest:
    """Artefakt wdrożenia — co wdrażamy."""
    app_name: str
    version: str
    compose_file: Path
    env_vars: dict = field(default_factory=dict)
    image_tags: list = field(default_factory=list)   # OCI image refs
    extra_files: list = field(default_factory=list)   # dodatkowe pliki do przesłania


@dataclass
class DeployResult:
    """Wynik wdrożenia."""
    status: DeployStatus
    message: str = ""
    logs: str = ""
    rollback_id: str = ""          # ID do rollbacku
    health_checks: list = field(default_factory=list)


class DeployerPlugin(ABC):
    """Bazowa klasa dla wszystkich pluginów wdrożeniowych."""

    # ── Metadata ──
    @property
    @abstractmethod
    def id(self) -> str:
        """Unikalny ID pluginu, np. 'docker_compose'."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nazwa wyświetlana, np. 'Docker Compose'."""

    @property
    @abstractmethod
    def supported_os(self) -> list[PlatformOS]:
        """Lista wspieranych systemów operacyjnych."""

    # ── Lifecycle ──
    @abstractmethod
    def detect(self, target: DeployTarget) -> bool:
        """Czy target ma zainstalowany runtime (np. docker, podman, kubectl)."""

    @abstractmethod
    def validate(self, manifest: DeployManifest, target: DeployTarget) -> list[str]:
        """Walidacja przed deploy. Zwraca listę błędów (pusta = OK)."""

    @abstractmethod
    def deploy(self, manifest: DeployManifest, target: DeployTarget) -> DeployResult:
        """Wykonaj wdrożenie."""

    @abstractmethod
    def rollback(self, target: DeployTarget, rollback_id: str) -> DeployResult:
        """Cofnij do poprzedniej wersji."""

    @abstractmethod
    def status(self, target: DeployTarget) -> DeployResult:
        """Sprawdź aktualny stan wdrożenia."""

    # ── Health ──
    @abstractmethod
    def health_check(self, target: DeployTarget) -> list[dict]:
        """Sprawdź zdrowie usług. Zwraca [{service, status, details}]."""

    # ── Optional hooks ──
    def pre_deploy(self, manifest: DeployManifest, target: DeployTarget) -> None:
        """Hook przed deploy (np. push do registry)."""

    def post_deploy(self, result: DeployResult, target: DeployTarget) -> None:
        """Hook po deploy (np. notyfikacje, cleanup)."""

    def convert_compose(self, compose_path: Path) -> str:
        """Konwertuj docker-compose.yml na natywny format platformy."""
        return ""
```

### 2.3 Plugin Registry (`registry.py`)

```python
import importlib
import pkgutil
from pathlib import Path
from typing import Optional

_PLUGINS: dict[str, DeployerPlugin] = {}


def discover_plugins(extra_dirs: list[Path] = None) -> dict[str, DeployerPlugin]:
    """Auto-discover pluginów z dockfra/deployers/ + opcjonalnych katalogów."""
    base_pkg = "dockfra.deployers"
    pkg_path = Path(__file__).parent

    for finder, name, ispkg in pkgutil.iter_modules([str(pkg_path)]):
        if ispkg and name not in ("__pycache__",):
            try:
                mod = importlib.import_module(f"{base_pkg}.{name}.plugin")
                cls = getattr(mod, "Plugin", None)
                if cls and issubclass(cls, DeployerPlugin):
                    instance = cls()
                    _PLUGINS[instance.id] = instance
            except (ImportError, AttributeError):
                pass

    # Pluginy użytkownika z extra_dirs
    if extra_dirs:
        for d in extra_dirs:
            _load_external_plugin(d)

    return _PLUGINS


def get_plugin(plugin_id: str) -> Optional[DeployerPlugin]:
    """Pobierz plugin po ID."""
    return _PLUGINS.get(plugin_id)


def list_plugins() -> list[dict]:
    """Lista pluginów z metadanymi."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "supported_os": [os.value for os in p.supported_os],
        }
        for p in _PLUGINS.values()
    ]
```

### 2.4 Konfiguracja targetów (`deploy-targets.yaml`)

Nowy plik w katalogu projektu:

```yaml
# deploy-targets.yaml — definicja celów wdrożeniowych
targets:
  # ── Produkcja: Docker Compose na VPS ──
  prod-vps:
    host: 192.168.1.100
    port: 2224
    user: deployer
    platform: docker_compose
    os: linux
    labels:
      env: production
      region: eu-central
    config:
      compose_project: myapp
      pull_policy: always
      restart_policy: unless-stopped

  # ── Staging: Podman na RHEL ──
  staging-rhel:
    host: 10.0.0.50
    user: deploy
    platform: podman
    os: linux
    config:
      use_quadlet: true          # Generuj systemd unit files
      rootless: true             # Podman rootless mode
      pod_name: myapp-pod

  # ── Produkcja: Kubernetes ──
  prod-k8s:
    host: k8s-api.company.com
    platform: kubernetes
    config:
      namespace: myapp-prod
      kubeconfig: /home/deployer/.kube/config
      strategy: rolling          # rolling | recreate | blue-green
      replicas: 3
      resource_limits:
        cpu: "500m"
        memory: "512Mi"

  # ── Edge: RPi3 przez SSH ──
  edge-rpi3:
    host: 192.168.1.200
    port: 22
    user: pi
    platform: ssh_raw
    os: linux
    labels:
      device: rpi3
      env: edge
    config:
      deploy_path: /home/pi/apps
      service_manager: systemd
      pre_script: "sudo systemctl stop myapp"
      post_script: "sudo systemctl start myapp"

  # ── Docker Swarm cluster ──
  swarm-cluster:
    host: swarm-manager.local
    platform: swarm
    config:
      stack_name: myapp
      replicas: 2
      update_parallelism: 1
      update_delay: "10s"

  # ── Nomad cluster ──
  nomad-cluster:
    host: nomad.company.com
    platform: nomad
    config:
      datacenter: dc1
      job_name: myapp
      count: 3
      driver: docker
```

---

## 3. Pluginy platform wdrożeniowych

### 3.1 Docker Compose (refaktor istniejącego)

Wyciągnięcie logiki z `steps.py:step_do_deploy()` i `fixes.py` do pluginu.

```python
class Plugin(DeployerPlugin):
    id = "docker_compose"
    name = "Docker Compose"
    supported_os = [PlatformOS.LINUX, PlatformOS.MACOS, PlatformOS.WINDOWS_WSL]

    def detect(self, target):
        rc, out = ssh_run(target, "docker compose version")
        return rc == 0

    def deploy(self, manifest, target):
        # 1. rsync/scp compose + env files
        # 2. ssh: docker compose pull
        # 3. ssh: docker compose up -d --build
        # 4. health check
        ...

    def rollback(self, target, rollback_id):
        # ssh: docker compose down
        # ssh: docker tag previous → current
        # ssh: docker compose up -d
        ...
```

### 3.2 Podman

```python
class Plugin(DeployerPlugin):
    id = "podman"
    name = "Podman / Podman Compose"
    supported_os = [PlatformOS.LINUX, PlatformOS.MACOS]

    def detect(self, target):
        rc, _ = ssh_run(target, "podman --version")
        return rc == 0

    def deploy(self, manifest, target):
        if self._config(target).get("use_quadlet"):
            # Generuj .container / .pod unit files
            units = self._generate_quadlet(manifest)
            # scp → /etc/containers/systemd/ (rootful) lub ~/.config/... (rootless)
            # systemctl --user daemon-reload && systemctl --user start pod
        else:
            # podman-compose up -d
            ...

    def convert_compose(self, compose_path):
        """Konwertuj docker-compose.yml → Quadlet unit files."""
        ...
```

### 3.3 Kubernetes

```python
class Plugin(DeployerPlugin):
    id = "kubernetes"
    name = "Kubernetes"
    supported_os = [PlatformOS.ANY]

    def detect(self, target):
        rc, _ = ssh_run(target, "kubectl cluster-info")
        return rc == 0

    def deploy(self, manifest, target):
        cfg = target.config
        # 1. Konwertuj compose → K8s manifests (Deployment, Service, ConfigMap)
        k8s_yaml = self._compose_to_k8s(manifest, cfg)
        # 2. kubectl apply -f
        # 3. kubectl rollout status deployment/...
        ...

    def rollback(self, target, rollback_id):
        # kubectl rollout undo deployment/app --to-revision=N
        ...

    def health_check(self, target):
        # kubectl get pods -l app=... -o json → parse readiness
        ...

    def convert_compose(self, compose_path):
        """docker-compose.yml → Deployment + Service + ConfigMap YAML."""
        # Kompose-like konwersja
        ...
```

### 3.4 Docker Swarm

```python
class Plugin(DeployerPlugin):
    id = "swarm"
    name = "Docker Swarm"
    supported_os = [PlatformOS.LINUX]

    def deploy(self, manifest, target):
        # docker stack deploy -c compose.yml stack_name
        ...

    def rollback(self, target, rollback_id):
        # docker service rollback service_name
        ...
```

### 3.5 Nomad

```python
class Plugin(DeployerPlugin):
    id = "nomad"
    name = "HashiCorp Nomad"
    supported_os = [PlatformOS.ANY]

    def deploy(self, manifest, target):
        # 1. Generuj jobspec HCL z compose
        # 2. nomad job run job.hcl
        ...

    def convert_compose(self, compose_path):
        """docker-compose.yml → Nomad job HCL."""
        ...
```

### 3.6 SSH Raw (obecny RPi3 deploy, uogólniony)

```python
class Plugin(DeployerPlugin):
    id = "ssh_raw"
    name = "SSH Deploy (raw)"
    supported_os = [PlatformOS.LINUX, PlatformOS.MACOS]

    def deploy(self, manifest, target):
        cfg = target.config
        # 1. pre_script (jeśli ustawiony)
        # 2. rsync artefakty → deploy_path
        # 3. post_script (jeśli ustawiony)
        # 4. health check
        ...
```

---

## 4. Zmiany w istniejącym kodzie

### 4.1 Moduły do zmodyfikowania

| Moduł | Zmiana | Priorytet |
|-------|--------|-----------|
| `core.py` | Dodać `load_deploy_targets()`, `DEPLOY_TARGETS` dict | 🔴 Wysoki |
| `steps.py` | `step_deploy_device()` → delegacja do plugin registry | 🔴 Wysoki |
| `steps.py` | `step_do_launch()` → oddzielić local launch od remote deploy | 🔴 Wysoki |
| `pipeline.py` | Dodać `deploy_step` korzystający z pluginu | 🔴 Wysoki |
| `fixes.py` | `fix_*` funkcje → per-plugin fix providers | 🟡 Średni |
| `discover.py` | `_discover_ssh_roles()` → dodać discovery deploy targets | 🟡 Średni |
| `app.py` | Nowe API: `/api/deploy-targets`, `/api/deploy/<target>` | 🟡 Średni |
| `cli.py` | Nowe komendy: `deploy`, `targets`, `rollback` | 🟡 Średni |
| `engines.py` | Bez zmian (AI engines niezależne od deploy) | ⚪ Brak |
| `tickets.py` | Dodać pole `deploy_target` w tickecie | 🟢 Niski |
| `wizard.js` | UI do wyboru target + platform | 🟢 Niski |

### 4.2 Nowe moduły

| Moduł | Opis |
|-------|------|
| `dockfra/deployers/__init__.py` | Eksport registry |
| `dockfra/deployers/base.py` | ABC + dataclasses |
| `dockfra/deployers/registry.py` | Auto-discovery + cache |
| `dockfra/deployers/manifest.py` | Build manifest z compose |
| `dockfra/deployers/health.py` | Bazowy health checker |
| `dockfra/deployers/ssh_utils.py` | Wspólne SSH helpers (rsync, scp, ssh_run) |
| `dockfra/deployers/*/plugin.py` | 6 pluginów (compose, podman, k8s, swarm, nomad, ssh_raw) |

### 4.3 Nowe API routes

```
GET  /api/deploy-targets          → lista targetów z deploy-targets.yaml
GET  /api/deploy-targets/<id>     → szczegóły targetu + status
POST /api/deploy/<target_id>      → wdróż na target
POST /api/rollback/<target_id>    → rollback
GET  /api/deploy-plugins          → lista dostępnych pluginów
POST /api/deploy-test/<target_id> → test connectivity + detect runtime
```

### 4.4 Nowe CLI komendy

```
dockfra cli targets               → lista targetów (tabela)
dockfra cli deploy <target>       → wdróż na target
dockfra cli rollback <target>     → rollback
dockfra cli deploy-test <target>  → test connectivity
dockfra cli deploy-status         → status wszystkich targetów
```

---

## 5. TODO dla lokalnego LLM — krok po kroku

Każdy krok jest atomowy — LLM implementuje go, uruchamia testy, commituje, przechodzi do kolejnego.

### FAZA 1: Fundament pluginowy (zmiany w core)

```
T-0100  [IMPLEMENT] Stwórz dockfra/deployers/__init__.py
        ├─ Plik: dockfra/deployers/__init__.py
        ├─ Co: Eksportuj discover_plugins, get_plugin, list_plugins
        ├─ Test: import dockfra.deployers działa
        └─ Commit: "feat(deployers): init plugin package"

T-0101  [IMPLEMENT] Stwórz dockfra/deployers/base.py
        ├─ Plik: dockfra/deployers/base.py
        ├─ Co: Dataclasses (PlatformOS, DeployStatus, DeployTarget,
        │       DeployManifest, DeployResult) + ABC DeployerPlugin
        ├─ Wymagania:
        │   - DeployerPlugin musi mieć: id, name, supported_os (property)
        │   - Metody abstract: detect, validate, deploy, rollback, status, health_check
        │   - Metody opcjonalne: pre_deploy, post_deploy, convert_compose
        ├─ Test: isinstance check, ABC nie da się instantiate
        └─ Commit: "feat(deployers): base plugin ABC and dataclasses"

T-0102  [IMPLEMENT] Stwórz dockfra/deployers/registry.py
        ├─ Plik: dockfra/deployers/registry.py
        ├─ Co: discover_plugins() — pkgutil.iter_modules auto-load
        │       get_plugin(id), list_plugins()
        ├─ Wymagania:
        │   - Skanuj dockfra/deployers/**/plugin.py
        │   - Każdy plugin.py musi eksportować klasę Plugin(DeployerPlugin)
        │   - Cache w _PLUGINS dict
        │   - Obsługa extra_dirs dla pluginów użytkownika
        ├─ Test: discover z pustym katalogiem → 0 pluginów
        └─ Commit: "feat(deployers): plugin registry with auto-discovery"

T-0103  [IMPLEMENT] Stwórz dockfra/deployers/ssh_utils.py
        ├─ Plik: dockfra/deployers/ssh_utils.py
        ├─ Co: ssh_run(target, cmd), scp_upload(target, src, dst),
        │       rsync_upload(target, src, dst), test_connection(target)
        ├─ Wymagania:
        │   - Używaj subprocess z timeout
        │   - Obsłuż klucze SSH (identity file z konfiguracji)
        │   - Zwracaj (returncode, stdout+stderr)
        ├─ Test: mock subprocess, test_connection z nieistniejącym hostem
        └─ Commit: "feat(deployers): SSH utility helpers"

T-0104  [IMPLEMENT] Stwórz dockfra/deployers/manifest.py
        ├─ Plik: dockfra/deployers/manifest.py
        ├─ Co: build_manifest(compose_path, env) → DeployManifest
        │       Parsuj docker-compose.yml, wyciągnij image tagi, env vars
        ├─ Test: parsowanie przykładowego compose → poprawny manifest
        └─ Commit: "feat(deployers): manifest builder from compose files"

T-0105  [IMPLEMENT] Stwórz dockfra/deployers/health.py
        ├─ Plik: dockfra/deployers/health.py
        ├─ Co: HealthChecker ABC z check_http(), check_tcp(), check_command()
        │       HTTPHealthChecker(HealthChecker) — domyślny
        ├─ Test: HTTPHealthChecker z mock requests
        └─ Commit: "feat(deployers): health check base + HTTP checker"
```

### FAZA 2: Plugin Docker Compose (refaktor istniejącego kodu)

```
T-0110  [REFACTOR] Wyciągnij logikę deploy z steps.py do pluginu
        ├─ Plik: dockfra/deployers/docker_compose/plugin.py
        ├─ Co: Klasa Plugin(DeployerPlugin)
        │   - detect(): ssh docker compose version
        │   - validate(): sprawdź compose file, wymagane env vars
        │   - deploy(): rsync files → docker compose pull → up -d
        │   - rollback(): docker compose down → tag previous → up
        │   - status(): docker compose ps
        │   - health_check(): HTTP /health na usługach
        ├─ Wymagania:
        │   - Przenieś logikę z step_do_deploy() i step_test_device()
        │   - NIE usuwaj jeszcze starych funkcji (backward compat)
        ├─ Test: Plugin().detect() z mock ssh
        └─ Commit: "feat(deployers): docker-compose plugin (extracted from steps)"

T-0111  [IMPLEMENT] Stwórz plugin.yaml dla docker_compose
        ├─ Plik: dockfra/deployers/docker_compose/plugin.yaml
        ├─ Co: Metadata — name, version, author, capabilities, required_tools
        └─ Commit: "feat(deployers): docker-compose plugin metadata"

T-0112  [IMPLEMENT] Testy jednostkowe dla docker_compose plugin
        ├─ Plik: tests/test_deployers.py
        ├─ Co: TestDockerComposePlugin class
        │   - test_detect_with_docker, test_detect_without_docker
        │   - test_validate_missing_compose, test_validate_ok
        │   - test_deploy_mock, test_rollback_mock
        │   - test_health_check_mock
        ├─ Wymagania: Wszystkie testy muszą przejść
        └─ Commit: "test(deployers): docker-compose plugin unit tests"
```

### FAZA 3: Nowe pluginy

```
T-0120  [IMPLEMENT] Plugin: Podman
        ├─ Plik: dockfra/deployers/podman/plugin.py
        ├─ Co: PodmanDeployer
        │   - detect(): podman --version
        │   - deploy(): podman-compose up LUB quadlet (config.use_quadlet)
        │   - convert_compose(): → Quadlet .container/.pod files
        │   - Obsługa rootless mode
        ├─ Test: test_podman_detect, test_quadlet_generation
        └─ Commit: "feat(deployers): podman plugin with Quadlet support"

T-0121  [IMPLEMENT] Plugin: Kubernetes
        ├─ Plik: dockfra/deployers/kubernetes/plugin.py
        ├─ Co: KubernetesDeployer
        │   - detect(): kubectl cluster-info
        │   - deploy(): kubectl apply -f (generated manifests)
        │   - rollback(): kubectl rollout undo
        │   - health_check(): kubectl get pods readiness
        │   - convert_compose(): compose → Deployment + Service + ConfigMap
        ├─ Plik: dockfra/deployers/kubernetes/manifests.py
        │   - compose_to_deployment(), compose_to_service(),
        │     compose_to_configmap()
        ├─ Test: test_k8s_manifest_generation, test_k8s_deploy_mock
        └─ Commit: "feat(deployers): kubernetes plugin with compose conversion"

T-0122  [IMPLEMENT] Plugin: Docker Swarm
        ├─ Plik: dockfra/deployers/swarm/plugin.py
        ├─ Co: SwarmDeployer
        │   - detect(): docker info → Swarm: active
        │   - deploy(): docker stack deploy -c compose.yml
        │   - rollback(): docker service rollback
        │   - health_check(): docker service ls
        ├─ Test: test_swarm_detect, test_swarm_deploy_mock
        └─ Commit: "feat(deployers): docker-swarm plugin"

T-0123  [IMPLEMENT] Plugin: Nomad
        ├─ Plik: dockfra/deployers/nomad/plugin.py
        ├─ Co: NomadDeployer
        │   - detect(): nomad version
        │   - deploy(): nomad job run
        │   - convert_compose(): → HCL jobspec
        ├─ Plik: dockfra/deployers/nomad/jobspec.py
        │   - compose_to_hcl()
        ├─ Test: test_nomad_hcl_generation
        └─ Commit: "feat(deployers): nomad plugin with HCL generation"

T-0124  [IMPLEMENT] Plugin: SSH Raw (uogólnienie devices/)
        ├─ Plik: dockfra/deployers/ssh_raw/plugin.py
        ├─ Co: SSHRawDeployer
        │   - detect(): test SSH connection
        │   - deploy(): pre_script → rsync → post_script
        │   - rollback(): symlink swap (/current → /releases/prev)
        │   - health_check(): SSH command lub HTTP check
        ├─ Wymagania:
        │   - Capistrano-style release dirs: /releases/20260221/, /current → symlink
        │   - Konfigurowalny service_manager: systemd, supervisord, pm2
        ├─ Test: test_ssh_raw_deploy_mock
        └─ Commit: "feat(deployers): ssh-raw plugin (generalized devices deploy)"
```

### FAZA 4: Integracja z istniejącym kodem

```
T-0130  [MODIFY] core.py — dodaj load_deploy_targets()
        ├─ Plik: dockfra/core.py
        ├─ Co:
        │   - Nowa funkcja load_deploy_targets() → dict[str, DeployTarget]
        │   - Parsuj deploy-targets.yaml z ROOT
        │   - Dodaj DEPLOY_TARGETS do globalnego stanu
        │   - Fallback: jeśli brak pliku, stwórz domyślny target z devices/
        ├─ Test: test_load_deploy_targets z przykładowym yaml
        └─ Commit: "feat(core): deploy-targets.yaml loader"

T-0131  [MODIFY] steps.py — zrefaktoruj step_deploy_device()
        ├─ Plik: dockfra/steps.py
        ├─ Co:
        │   - step_deploy_device() → pokaż listę targetów z DEPLOY_TARGETS
        │   - Użytkownik wybiera target → get_plugin(target.platform)
        │   - plugin.validate() → plugin.deploy() → plugin.health_check()
        │   - Zachowaj starą ścieżkę jako fallback
        ├─ Test: test_step_deploy_with_plugin (mock plugin)
        └─ Commit: "refactor(steps): deploy via plugin registry"

T-0132  [MODIFY] pipeline.py — dodaj deploy step w pipeline
        ├─ Plik: dockfra/pipeline.py
        ├─ Co:
        │   - Nowy krok w pipeline: "deploy" po "review"
        │   - Pipeline: create → implement → test → review → DEPLOY → verify → close
        │   - Deploy step pobiera target z ticketu (ticket.deploy_target)
        │   - Używa plugin.deploy()
        ├─ Test: test_pipeline_with_deploy_step
        └─ Commit: "feat(pipeline): add deploy step using deployer plugins"

T-0133  [MODIFY] app.py — nowe API routes
        ├─ Plik: dockfra/app.py
        ├─ Co:
        │   - GET  /api/deploy-targets → list_deploy_targets()
        │   - GET  /api/deploy-targets/<id> → target details + status
        │   - POST /api/deploy/<target_id> → trigger deploy
        │   - POST /api/rollback/<target_id> → trigger rollback
        │   - GET  /api/deploy-plugins → list available plugins
        │   - POST /api/deploy-test/<target_id> → test connectivity
        ├─ Test: test_api_deploy_targets, test_api_deploy_trigger
        └─ Commit: "feat(api): deploy targets and plugin management endpoints"

T-0134  [MODIFY] cli.py — nowe komendy deploy
        ├─ Plik: dockfra/cli.py
        ├─ Co:
        │   - cmd_targets(client, args) → tabela targetów
        │   - cmd_deploy(client, args) → POST /api/deploy/<target>
        │   - cmd_rollback(client, args) → POST /api/rollback/<target>
        │   - cmd_deploy_test(client, args) → test connectivity
        │   - Dodaj do COMMANDS dict i helpów
        ├─ Test: test_cli_targets, test_cli_deploy
        └─ Commit: "feat(cli): deploy, targets, rollback commands"

T-0135  [MODIFY] discover.py — discover deploy targets
        ├─ Plik: dockfra/discover.py
        ├─ Co: Dodaj discovery deploy-targets.yaml w _discover_ssh_roles()
        │       Pokaż targets obok SSH roles w wizard UI
        └─ Commit: "feat(discover): include deploy targets in discovery"
```

### FAZA 5: Multi-OS support

```
T-0140  [IMPLEMENT] OS detection w ssh_utils.py
        ├─ Plik: dockfra/deployers/ssh_utils.py
        ├─ Co: detect_os(target) → PlatformOS
        │   - SSH: uname -s → Linux/Darwin
        │   - SSH: wsl.exe --version → Windows WSL
        │   - Ustaw target.os automatycznie
        ├─ Test: test_detect_os_linux, test_detect_os_macos
        └─ Commit: "feat(deployers): OS auto-detection"

T-0141  [IMPLEMENT] Package manager abstraction
        ├─ Plik: dockfra/deployers/os_utils.py
        ├─ Co: install_package(target, pkg), service_control(target, svc, action)
        │   - Linux/Debian: apt install, systemctl
        │   - Linux/RHEL: dnf install, systemctl
        │   - macOS: brew install, launchctl
        │   - Alpine: apk add, rc-service
        ├─ Test: test_install_package_debian, test_service_control_systemd
        └─ Commit: "feat(deployers): cross-OS package and service management"

T-0142  [MODIFY] Podman plugin — dodaj macOS support
        ├─ Plik: dockfra/deployers/podman/plugin.py
        ├─ Co: Obsłuż podman machine (macOS) vs natywny podman (Linux)
        │   - macOS: podman machine init → podman machine start → deploy
        └─ Commit: "feat(deployers): podman macOS support via podman machine"
```

### FAZA 6: UI + dokumentacja

```
T-0150  [MODIFY] wizard.js — deploy target selector
        ├─ Plik: dockfra/static/wizard.js
        ├─ Co:
        │   - Nowy widget: deploy target picker (dropdown + test button)
        │   - Pokaż status każdego targetu (green/red dot)
        │   - Deploy button per target
        │   - Rollback button jeśli jest rollback_id
        └─ Commit: "feat(ui): deploy target selector widget"

T-0151  [IMPLEMENT] Dokumentacja pluginów
        ├─ Plik: docs/DEPLOYERS.md
        ├─ Co: Jak pisać własne pluginy, API reference, przykłady
        └─ Commit: "docs: deployer plugin development guide"

T-0152  [MODIFY] README.md — aktualizacja
        ├─ Co: Dodaj sekcje o pluginach, nowych CLI komendach, targetach
        └─ Commit: "docs: update README with deployer plugin system"

T-0153  [IMPLEMENT] Testy E2E
        ├─ Plik: tests/test_deployers_e2e.py
        ├─ Co:
        │   - Test: discover_plugins() → 6 pluginów
        │   - Test: get_plugin("docker_compose") → valid
        │   - Test: full deploy pipeline z mock target
        │   - Test: API endpoints (targets, deploy, rollback)
        └─ Commit: "test: deployer e2e tests"
```

### FAZA 7: Zaawansowane funkcje

```
T-0160  [IMPLEMENT] Blue-green deploy dla K8s
        ├─ Strategia: dwa Deploymenty (blue/green), Service switch
        └─ Commit: "feat(deployers): kubernetes blue-green strategy"

T-0161  [IMPLEMENT] Canary deploy
        ├─ Stopniowe przesuwanie traffic (10% → 50% → 100%)
        │   - K8s: Ingress weight annotations
        │   - Compose: Traefik weighted routing
        └─ Commit: "feat(deployers): canary deployment strategy"

T-0162  [IMPLEMENT] OCI Registry push w pre_deploy
        ├─ Przed deploy: docker build → docker push → target pulls
        ├─ Obsługa: Docker Hub, GHCR, self-hosted registry
        └─ Commit: "feat(deployers): OCI registry push in pre-deploy hook"

T-0163  [IMPLEMENT] Deploy notifications
        ├─ Webhook po deploy (Slack, Discord, email)
        ├─ Konfiguracja w deploy-targets.yaml: notifications: [...]
        └─ Commit: "feat(deployers): deploy notifications via webhooks"

T-0164  [IMPLEMENT] Deploy history + audit log
        ├─ Zapisuj każdy deploy do SQLite (event_bus)
        ├─ event_type: "deploy", data: {target, version, status, duration}
        └─ Commit: "feat(deployers): deploy history via event bus"
```

---

## Podsumowanie priorytetów

| Faza | Tickety | Szacowany czas | Priorytet |
|------|---------|---------------|-----------|
| **1. Fundament** | T-0100..T-0105 | 2-3 dni | 🔴 Krytyczny |
| **2. Docker Compose** | T-0110..T-0112 | 1-2 dni | 🔴 Krytyczny |
| **3. Nowe pluginy** | T-0120..T-0124 | 3-5 dni | 🟡 Ważny |
| **4. Integracja** | T-0130..T-0135 | 2-3 dni | 🔴 Krytyczny |
| **5. Multi-OS** | T-0140..T-0142 | 1-2 dni | 🟡 Ważny |
| **6. UI + docs** | T-0150..T-0153 | 2-3 dni | 🟡 Ważny |
| **7. Zaawansowane** | T-0160..T-0164 | 3-5 dni | 🟢 Nice-to-have |

**Razem: ~30 ticketów, ~14-23 dni pracy LLM**

### Kolejność wykonania przez LLM

```
SPRINT 1 (Faza 1+2):  T-0100 → T-0101 → T-0102 → T-0103 → T-0104 → T-0105
                       → T-0110 → T-0111 → T-0112
                       ✅ Plugin system działa z Docker Compose

SPRINT 2 (Faza 4):    T-0130 → T-0131 → T-0132 → T-0133 → T-0134 → T-0135
                       ✅ Integracja z wizard, CLI, pipeline

SPRINT 3 (Faza 3):    T-0120 → T-0121 → T-0122 → T-0123 → T-0124
                       ✅ 6 pluginów platform

SPRINT 4 (Faza 5+6):  T-0140 → T-0141 → T-0142 → T-0150 → T-0151 → T-0152 → T-0153
                       ✅ Multi-OS + UI + dokumentacja

SPRINT 5 (Faza 7):    T-0160 → T-0161 → T-0162 → T-0163 → T-0164
                       ✅ Zaawansowane strategie deploy
```