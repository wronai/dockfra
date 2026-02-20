# Dockfra vs Portainer

> Portainer — Docker/Kubernetes management GUI.

## Overview

| Aspect | **Dockfra** | **Portainer** |
|---|---|---|
| **Primary goal** | Multi-agent Docker infrastructure + AI wizard | Universal container management GUI |
| **Language** | Python | Go + Angular |
| **Architecture** | Python package + Docker Compose | Docker container (agent + server) |
| **Pricing** | Free (Apache 2.0) | Free (CE) / Paid (Business Edition) |
| **Target** | Dev teams with Docker Compose projects | Ops teams managing Docker/Swarm/K8s |

## Feature Comparison

| Feature | Dockfra | Portainer CE | Portainer BE |
|---|:---:|:---:|:---:|
| Web UI | ✅ (chat wizard) | ✅ (dashboard) | ✅ (dashboard) |
| Container management | ✅ | ✅ | ✅ |
| Docker Compose | ✅ (native) | ✅ (stacks) | ✅ (stacks) |
| Kubernetes | — | ✅ | ✅ |
| Docker Swarm | — | ✅ | ✅ |
| Image management | — | ✅ | ✅ |
| Volume management | — | ✅ | ✅ |
| Network management | ✅ (auto) | ✅ | ✅ |
| User/team RBAC | ✅ (SSH roles) | — | ✅ |
| Auto-discover env vars | ✅ | — | — |
| Auto-discover stacks | ✅ | — | — |
| LLM integration | ✅ | — | — |
| AI error analysis | ✅ | — | — |
| Multi-agent orchestration | ✅ | — | — |
| Ticket system | ✅ | — | — |
| SSH role containers | ✅ | — | — |
| Git integration | ✅ (clone, branch) | ✅ (GitOps) | ✅ (GitOps) |
| Registry management | — | ✅ | ✅ |
| API | ✅ (REST+WS) | ✅ (REST) | ✅ (REST) |
| Edge computing | — | — | ✅ |
| IoT deploy | ✅ | — | ✅ |
| Log streaming | ✅ | ✅ | ✅ |
| Health monitoring | ✅ | ✅ | ✅ |

## Philosophy Differences

**Portainer** is a **general-purpose container management platform**:
- Manages any Docker/Swarm/K8s environment
- Focus on ops: images, volumes, networks, registries
- GUI for everything Docker CLI can do
- Enterprise features in paid edition

**Dockfra** is a **project-specific Docker workflow tool**:
- Manages one project's Docker Compose stacks
- Focus on dev workflow: setup, configure, troubleshoot, develop
- AI-powered: LLM error analysis, code assistance, autonomous orchestration
- Role-based SSH access with per-role LLM config

## When to Choose

### Choose Dockfra when:
- You manage a **specific project** with Docker Compose
- You need **AI-powered** development and troubleshooting
- You want **auto-discovery** of env vars and stacks
- You need **role-based SSH containers** with independent LLM configs
- You want a **chat-based wizard** for team onboarding
- You need **ticket-driven development** workflows

### Choose Portainer when:
- You manage **multiple projects** across different hosts
- You need to manage **Docker images, volumes, networks** via GUI
- You need **Kubernetes or Swarm** support
- You want a **visual Docker dashboard** for ops
- You need **enterprise RBAC** and audit logging
- You manage **registries** and **edge devices** at scale

## Complementary Usage

Dockfra and Portainer serve different layers:
- **Portainer** for infrastructure-wide Docker management (all hosts, all projects)
- **Dockfra** for project-specific dev workflow (one project, AI-powered, role-based)

Both can run simultaneously — Portainer manages the Docker engine while Dockfra manages the project workflow.

## Links

- [Portainer](https://www.portainer.io/) — official site
- [Portainer GitHub](https://github.com/portainer/portainer)
- [Back to comparisons](README.md)
