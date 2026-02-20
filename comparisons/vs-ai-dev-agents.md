# Dockfra vs AI Development Agents

> OpenDevin, Devika, SWE-Agent, Aider — AI agents that write code autonomously.

## Overview

| Aspect | **Dockfra** | **OpenDevin** | **Devika** | **SWE-Agent** | **Aider** |
|---|---|---|---|---|---|
| **Primary goal** | Docker infrastructure + multi-agent system | Autonomous software engineer | AI software engineer | Automated bug fixing | AI pair programming |
| **Agent model** | 4 role-isolated containers | Single sandboxed agent | Single agent | Single agent | Single CLI tool |
| **Scope** | Full DevOps lifecycle | Code writing + execution | Code writing + web research | Issue → PR pipeline | Edit files in git repo |
| **Infrastructure** | ✅ Docker mgmt | ✅ Docker sandbox | — | Docker sandbox | — |
| **License** | Apache 2.0 | MIT | AGPL-3.0 | MIT | Apache 2.0 |

## Fundamental Difference

**AI dev agents** (OpenDevin, Devika, SWE-Agent) are **code-writing machines** — given a task, they produce code:

```
Issue/prompt → AI Agent → code changes → PR/commit
```

**Dockfra** is a **full DevOps system** where AI is one component among many:

```
Setup → Configure → Launch → Monitor → Troubleshoot → Develop → Deploy → Repeat
  ↑        ↑          ↑        ↑           ↑            ↑         ↑
  AI      auto     wizard    daemon      AI fix      AI code    AI deploy
```

**Aider** is the closest comparison — it's a CLI pair programming tool. In Dockfra, Aider runs **inside** the developer container as one of many available tools.

## Feature Comparison

| Feature | Dockfra | OpenDevin | Devika | SWE-Agent | Aider |
|---|:---:|:---:|:---:|:---:|:---:|
| Web UI | ✅ (wizard) | ✅ | ✅ | — | — |
| CLI | ✅ | — | — | ✅ | ✅ |
| Code writing | ✅ (via roles) | ✅ | ✅ | ✅ | ✅ |
| Code review | ✅ | — | — | — | — |
| Git operations | ✅ | ✅ | ✅ | ✅ | ✅ |
| Docker management | ✅ | — | — | — | — |
| Multi-agent | ✅ (4 roles) | — | — | — | — |
| Role isolation | ✅ (containers) | ✅ (sandbox) | — | ✅ (sandbox) | — |
| Ticket system | ✅ | — | — | ✅ (GitHub) | — |
| Autonomous mode | ✅ (autopilot) | ✅ | ✅ | ✅ | — |
| Health monitoring | ✅ | — | — | — | — |
| Deploy to production | ✅ | — | — | — | — |
| IoT/device deploy | ✅ | — | — | — | — |
| Env var management | ✅ | — | — | — | — |
| Docker Compose | ✅ | ✅ (sandbox) | — | — | — |
| Web research | — | ✅ | ✅ | — | — |
| Benchmark scores | N/A | SWE-bench | N/A | SWE-bench | SWE-bench |
| Multi-model | ✅ | ✅ | ✅ | ✅ | ✅ |
| Per-agent LLM config | ✅ | — | — | — | — |

## Architecture Comparison

### OpenDevin / Devika

```
User prompt → Planner Agent → Code Agent → Sandbox (Docker)
                                              │
                                              ├── bash execution
                                              ├── file editing
                                              └── browser (OpenDevin)
```

Single agent in a sandbox. Focus: write code to solve a task.

### SWE-Agent

```
GitHub Issue → SWE-Agent → Edit/Test loop → Pull Request
                  │
                  └── Specialized ACI (Agent-Computer Interface)
```

Single agent, specialized for GitHub issue → PR pipeline.

### Dockfra

```
┌─────────────────────────────────────────────────────────────────┐
│                     Dockfra Infrastructure                       │
│                                                                 │
│  Manager ──ticket──► Developer ──code──► Monitor ──deploy──►    │
│     │                    │                  │                    │
│     │ plan               │ implement        │ health-check      │
│     │ ask                │ review           │ log-analyze        │
│     ▼                    ▼                  ▼                    │
│   LLM                  LLM + Aider        LLM                   │
│                                                                 │
│  Autopilot (daemon) ── observes all ── makes decisions ──►      │
│     │                                                           │
│     ▼                                                           │
│   LLM (autonomous orchestration)                                │
└─────────────────────────────────────────────────────────────────┘
```

Four agents, each in isolated containers, with real filesystem access, SSH, and git.

## When to Choose

### Choose Dockfra when:
- You need a **full DevOps workflow** (setup → develop → deploy → monitor)
- You want **multiple specialized agents** working on different aspects
- You need **infrastructure management** alongside AI coding
- You want **human SSH access** to agent workspaces
- You need **persistent agents** running as services (not one-shot tasks)
- You're managing a **Docker Compose project**

### Choose OpenDevin / Devika when:
- You need an **autonomous software engineer** for complex coding tasks
- You want the agent to **plan and execute** multi-step coding projects
- You need **web research** capabilities integrated with coding
- You're optimizing for **SWE-bench** style tasks

### Choose SWE-Agent when:
- You have a **GitHub Issues → PR** pipeline to automate
- You want state-of-the-art **benchmark performance** on bug fixing
- You need a **specialized agent-computer interface**

### Choose Aider when:
- You want **simple CLI pair programming** (no infrastructure needed)
- You work on a **single repository** with a single developer
- You want the **fastest path** from prompt to code changes
- You prefer **lightweight tools** over full platforms

## Dockfra + Aider Integration

Aider runs **inside** Dockfra's developer container:

```bash
# From the wizard or CLI:
make ssh-developer
aider-start                  # Launches aider with project context
```

Dockfra provides the infrastructure; Aider provides the AI pair programming. This is why they're complementary, not competing.

## Links

- [OpenDevin](https://github.com/OpenDevin/OpenDevin) — autonomous AI software engineer
- [Devika](https://github.com/stitionai/devika) — AI software engineer
- [SWE-Agent](https://github.com/princeton-nlp/SWE-agent) — automated bug fixing
- [Aider](https://github.com/paul-gauthier/aider) — AI pair programming in terminal
- [Back to comparisons](README.md)
