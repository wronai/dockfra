# Dockfra vs Other Systems

> How Dockfra compares to other multi-agent, Docker-based, and infrastructure management systems.

## Quick Comparison Matrix

| Feature | **Dockfra** | Kamal | Coolify | Portainer | Docker Swarm | Kubernetes | CrewAI | AutoGen | OpenDevin |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Web setup wizard** | ✅ | — | ✅ | ✅ | — | — | — | — | ✅ |
| **CLI (14 commands + TUI)** | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Auto-discover stacks** | ✅ | — | — | ✅ | — | — | — | — | — |
| **Auto-discover env vars** | ✅ | — | — | — | — | — | — | — | — |
| **SSH role isolation** | ✅ (4 roles) | — | — | — | — | — | — | — | — |
| **Dev engines (Aider, Claude Code...)** | ✅ (5) | — | — | — | — | — | — | — | ✅ (1) |
| **LLM integration** | ✅ OpenRouter | — | — | — | — | — | ✅ | ✅ | ✅ |
| **Multi-agent orchestration** | ✅ | — | — | — | — | — | ✅ | ✅ | — |
| **Ticket-driven pipeline** | ✅ | — | — | — | — | — | ✅ | — | — |
| **Docker Compose native** | ✅ | ✅ | ✅ | ✅ | — | — | — | — | ✅ |
| **Device emulation (RPi3)** | ✅ | — | — | — | — | — | — | — | — |
| **IoT/device deploy via SSH** | ✅ | ✅ | — | — | — | — | — | — | — |
| **Zero-config for any project** | ✅ | — | — | — | — | — | — | — | — |
| **Self-hosted** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Production-ready scaling** | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — |
| **GUI dashboard** | ✅ | — | ✅ | ✅ | — | ✅* | — | ✅* | ✅ |
| **System self-test (`dockfra cli test`)** | ✅ | — | — | — | — | — | — | — | — |
| **Auto-diagnose (`dockfra cli doctor`)** | ✅ | — | — | — | — | — | — | — | — |

\* via third-party dashboards

## Detailed Comparisons

- [vs Kamal (Basecamp)](vs-kamal.md) — deployment tool
- [vs Coolify](vs-coolify.md) — self-hosted PaaS
- [vs Portainer](vs-portainer.md) — Docker management UI
- [vs CrewAI / AutoGen](vs-multi-agent-frameworks.md) — multi-agent AI frameworks
- [vs OpenDevin / Aider](vs-ai-dev-agents.md) — AI development agents

## Category Positioning

Dockfra sits at the intersection of three categories:

```
         Docker Management          Multi-Agent AI           Dev Tooling
         ┌──────────────┐          ┌──────────────┐        ┌──────────────┐
         │ Portainer    │          │ CrewAI       │        │ OpenDevin    │
         │ Coolify      │          │ AutoGen      │        │ Aider        │
         │ Kamal        │          │ LangGraph    │        │ Claude Code  │
         └──────┬───────┘          └──────┬───────┘        └──────┬───────┘
                │                         │                       │
                └─────────────┬───────────┘───────────────────────┘
                              │
                       ┌──────┴───────┐
                       │   DOCKFRA    │
                       │  v1.0.41     │
                       │ Docker mgmt  │
                       │ + 5 engines  │
                       │ + 4 SSH roles│
                       │ + 14 CLI cmd │
                       └──────────────┘
```

**Dockfra is unique** because it combines:
1. **Infrastructure management** (Docker Compose orchestration, env config, health monitoring, device emulation)
2. **Multi-agent system** (4 SSH-isolated roles with independent LLM configs, autopilot orchestration)
3. **Developer tooling** (5 AI engines — Aider, Claude Code, OpenCode, Built-in LLM, MCP SSH Manager)
4. **Full lifecycle CLI** (14 commands: test, doctor, tickets, pipeline, engines, dev-health, dev-logs...)

No other system in any single category provides all four.
