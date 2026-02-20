# Dockfra vs Other Systems

> How Dockfra compares to other multi-agent, Docker-based, and infrastructure management systems.

## Quick Comparison Matrix

| Feature | **Dockfra** | Kamal | Coolify | Portainer | Docker Swarm | Kubernetes | CrewAI | AutoGen | OpenDevin |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Web setup wizard** | ✅ | — | ✅ | ✅ | — | — | — | — | ✅ |
| **Auto-discover stacks** | ✅ | — | — | ✅ | — | — | — | — | — |
| **Auto-discover env vars** | ✅ | — | — | — | — | — | — | — | — |
| **SSH role isolation** | ✅ | — | — | — | — | — | — | — | — |
| **LLM integration** | ✅ | — | — | — | — | — | ✅ | ✅ | ✅ |
| **Multi-agent orchestration** | ✅ | — | — | — | — | — | ✅ | ✅ | — |
| **Ticket-driven workflow** | ✅ | — | — | — | — | — | ✅ | — | — |
| **Docker Compose native** | ✅ | ✅ | ✅ | ✅ | — | — | — | — | ✅ |
| **Zero-config for any project** | ✅ | — | — | — | — | — | — | — | — |
| **Self-hosted** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Production-ready scaling** | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — |
| **GUI dashboard** | ✅ | — | ✅ | ✅ | — | ✅* | — | ✅* | ✅ |
| **CLI** | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **IoT/device deploy** | ✅ | ✅ | — | — | — | — | — | — | — |

\* via third-party dashboards

## Detailed Comparisons

- [vs Kamal (Basecamp)](vs-kamal.md) — deployment tool
- [vs Coolify](vs-coolify.md) — self-hosted PaaS
- [vs Portainer](vs-portainer.md) — Docker management UI
- [vs CrewAI / AutoGen](vs-multi-agent-frameworks.md) — multi-agent AI frameworks
- [vs OpenDevin / Devika](vs-ai-dev-agents.md) — AI development agents

## Category Positioning

Dockfra sits at the intersection of three categories:

```
         Docker Management          Multi-Agent AI           Dev Tooling
         ┌──────────────┐          ┌──────────────┐        ┌──────────────┐
         │ Portainer    │          │ CrewAI       │        │ OpenDevin    │
         │ Coolify      │          │ AutoGen      │        │ Devika       │
         │ Kamal        │          │ LangGraph    │        │ Aider        │
         └──────┬───────┘          └──────┬───────┘        └──────┬───────┘
                │                         │                       │
                └─────────────┬───────────┘───────────────────────┘
                              │
                       ┌──────┴───────┐
                       │   DOCKFRA    │
                       │              │
                       │ Docker mgmt  │
                       │ + AI agents  │
                       │ + Dev tools  │
                       └──────────────┘
```

**Dockfra is unique** because it combines:
1. **Infrastructure management** (Docker Compose orchestration, env config, health monitoring)
2. **Multi-agent system** (4 SSH-isolated roles with independent LLM configs)
3. **Developer tooling** (AI pair programming, ticket workflows, automated deploys)

No other system in any single category provides all three.
