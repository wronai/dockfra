# Dockfra vs Kamal

> Kamal (by Basecamp/37signals) — zero-downtime Docker deployment tool.

## Overview

| Aspect | **Dockfra** | **Kamal** |
|---|---|---|
| **Primary goal** | Multi-agent Docker infrastructure manager with setup wizard | Zero-downtime Docker deployments to bare metal |
| **Language** | Python (Flask + SocketIO) | Ruby |
| **Config format** | Auto-discovered + `dockfra.yaml` | `config/deploy.yml` |
| **Target** | Any Docker Compose project | Web apps with Traefik proxy |
| **UI** | Web wizard + CLI | CLI only |
| **License** | Apache 2.0 | MIT |

## Feature Comparison

| Feature | Dockfra | Kamal |
|---|:---:|:---:|
| Web setup wizard | ✅ | — |
| Auto-discover env vars from compose | ✅ | — |
| Docker Compose native | ✅ | ✅ (v2+) |
| Zero-downtime deploys | — | ✅ |
| Rolling restarts | — | ✅ |
| Multi-server support | ✅ (SSH) | ✅ (SSH) |
| Traefik integration | ✅ | ✅ |
| SSL/Let's Encrypt | ✅ | ✅ |
| SSH role isolation | ✅ (4 roles) | — |
| LLM integration | ✅ | — |
| Multi-agent orchestration | ✅ | — |
| Ticket system | ✅ | — |
| Health monitoring | ✅ | ✅ (basic) |
| IoT/device deploy | ✅ | — |
| Container log analysis | ✅ (AI) | — |
| Secrets management | ✅ (env-based) | ✅ (kamal secrets) |
| Docker registry push | — | ✅ |
| Accessory services (DB, Redis) | ✅ | ✅ |
| Hooks (pre/post deploy) | — | ✅ |

## When to Choose

### Choose Dockfra when:
- You need a **web-based setup wizard** for team onboarding
- You want **LLM-powered** error analysis and code assistance
- You need **role-based SSH access** with isolation
- You have a **multi-stack** project (app + management + devices)
- You want **auto-discovery** of env vars from docker-compose files
- You need **ticket-driven workflows** with AI assistance

### Choose Kamal when:
- You need **zero-downtime rolling deploys** to production
- You're deploying to **multiple bare-metal servers**
- You need **Docker registry integration** (build → push → deploy)
- You want a mature, **battle-tested** deployment tool (used by HEY, Basecamp)
- You prefer **Ruby** ecosystem and `deploy.yml` configuration
- You need **hook scripts** for pre/post deploy actions

## Complementary Usage

Dockfra and Kamal can be used **together**:
- **Dockfra** for local development, team setup, and management orchestration
- **Kamal** for production deployment pipeline

```
Local dev: Dockfra wizard → configure → docker compose up
Production: Kamal → build → push → deploy → zero-downtime restart
```

## Architecture Differences

**Kamal** follows a traditional deploy pipeline:
```
Developer → git push → Kamal CLI → Docker build → Registry push → SSH deploy → Traefik
```

**Dockfra** is an ongoing infrastructure manager:
```
Wizard → auto-discover → configure → launch → monitor → fix → AI-assist → deploy
         ↑                                                              ↓
         └────────────── ticket system ← autopilot decisions ←──────────┘
```

## Links

- [Kamal](https://kamal-deploy.org/) — official site
- [Kamal GitHub](https://github.com/basecamp/kamal)
- [Back to comparisons](README.md)
