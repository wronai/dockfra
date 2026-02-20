# Dockfra vs Coolify

> Coolify — open-source, self-hosted Heroku/Netlify/Vercel alternative.

## Overview

| Aspect | **Dockfra** | **Coolify** |
|---|---|---|
| **Primary goal** | Multi-agent Docker infrastructure + setup wizard | Self-hosted PaaS for deploying apps |
| **Language** | Python | PHP (Laravel) + Svelte |
| **Architecture** | Docker Compose orchestrator + SSH agents | Full PaaS with build system |
| **Target users** | DevOps teams, AI-augmented dev teams | Solo devs, small teams wanting Heroku-like UX |
| **License** | Apache 2.0 | Apache 2.0 |

## Feature Comparison

| Feature | Dockfra | Coolify |
|---|:---:|:---:|
| Web UI | ✅ (chat wizard) | ✅ (full dashboard) |
| One-click deploy | — | ✅ |
| Git push deploy | — | ✅ |
| Docker Compose support | ✅ (native) | ✅ |
| Dockerfile support | ✅ | ✅ |
| Nixpacks / Buildpacks | — | ✅ |
| Database provisioning | ✅ (via compose) | ✅ (managed) |
| SSL/Let's Encrypt | ✅ | ✅ |
| Multi-server | ✅ (SSH) | ✅ |
| Team management | ✅ (SSH roles) | ✅ (users/teams) |
| SSH role isolation | ✅ (4 roles) | — |
| LLM integration | ✅ | — |
| AI error analysis | ✅ | — |
| Multi-agent orchestration | ✅ | — |
| Ticket system | ✅ | — |
| Auto-discover env vars | ✅ | — |
| Auto-discover stacks | ✅ | — |
| S3 backup | — | ✅ |
| Monitoring (Grafana) | — | ✅ (built-in) |
| Webhook integrations | — | ✅ |
| API | ✅ (REST + WebSocket) | ✅ (REST) |

## Philosophy Differences

**Coolify** is a **PaaS replacement** — it abstracts away Docker entirely:
- You push code, Coolify builds and deploys
- Managed databases, S3, monitoring out of the box
- No need to write `docker-compose.yml`

**Dockfra** is a **Docker Compose power tool** — it enhances your existing Docker setup:
- You write `docker-compose.yml`, Dockfra auto-discovers and manages it
- LLM-powered troubleshooting and development assistance
- Role-based SSH access for team collaboration
- Works with ANY existing Docker Compose project

## When to Choose

### Choose Dockfra when:
- You already have `docker-compose.yml` files and want to keep them
- You need **AI-powered** development workflows (tickets, code review, pair programming)
- You want **role-based SSH isolation** for team security
- You need a **multi-agent system** with autonomous orchestration
- You want **zero-config discovery** of your existing Docker project

### Choose Coolify when:
- You want a **Heroku-like experience** without vendor lock-in
- You need **git push → auto deploy** workflow
- You want **managed databases** with backups
- You need **monitoring dashboards** (Grafana) out of the box
- You prefer a **polished web dashboard** over a chat-based wizard
- You don't need LLM/AI integration

## Complementary Usage

These tools serve different layers:
- **Coolify** for production hosting and continuous deployment
- **Dockfra** for local development environment, team onboarding, and AI-assisted workflows

## Links

- [Coolify](https://coolify.io/) — official site
- [Coolify GitHub](https://github.com/coollabsio/coolify)
- [Back to comparisons](README.md)
