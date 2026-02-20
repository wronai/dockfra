# Dockfra vs Multi-Agent AI Frameworks

> CrewAI, AutoGen, LangGraph — frameworks for building multi-agent AI systems.

## Overview

| Aspect | **Dockfra** | **CrewAI** | **AutoGen** | **LangGraph** |
|---|---|---|---|---|
| **Primary goal** | Docker infrastructure + AI agents | General multi-agent orchestration | Multi-agent conversation | Stateful agent workflows |
| **Language** | Python | Python | Python | Python |
| **Agent runtime** | Docker containers (SSH) | Python processes | Python processes | Python processes |
| **Agent isolation** | ✅ OS-level (containers) | — (same process) | — (same process) | — (same process) |
| **Infrastructure mgmt** | ✅ | — | — | — |
| **License** | Apache 2.0 | MIT | MIT | MIT |
| **Maturity** | Early | Growing | Mature | Growing |

## Fundamental Difference

**CrewAI / AutoGen / LangGraph** are **LLM orchestration frameworks** — they coordinate AI model calls in Python:

```python
# CrewAI example
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential
)
result = crew.kickoff()
```

**Dockfra** is an **infrastructure system** where agents are **real OS processes** in isolated containers:

```
┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│ ssh-manager      │  │ ssh-developer    │  │ ssh-autopilot   │
│ (container)      │  │ (container)      │  │ (container)     │
│                  │  │                  │  │                 │
│ • bash scripts   │  │ • git, code      │  │ • daemon loop   │
│ • ticket-create  │  │ • aider          │  │ • LLM decisions │
│ • LLM planning   │  │ • LLM review     │  │ • SSH commands  │
│ • SSH to others  │  │ • tests          │  │ • auto-tickets  │
└────────┬─────────┘  └────────┬─────────┘  └────────┬────────┘
         │   SSH + shared volumes + tickets   │               │
         └────────────────┬───────────────────┘───────────────┘
                          │
                    Docker network
```

## Feature Comparison

| Feature | Dockfra | CrewAI | AutoGen | LangGraph |
|---|:---:|:---:|:---:|:---:|
| Agent isolation (OS-level) | ✅ | — | — | — |
| Filesystem per agent | ✅ | — | — | — |
| Network isolation | ✅ | — | — | — |
| Persistent agents (daemon) | ✅ | — | — | — |
| SSH access to agents | ✅ | — | — | — |
| Human-in-the-loop | ✅ (SSH) | ✅ | ✅ | ✅ |
| Agent communication | SSH + tickets | Python API | Messages | Graph edges |
| Tool use | Bash scripts | Python tools | Python tools | Python tools |
| Real git operations | ✅ | — | — | — |
| Real Docker operations | ✅ | — | — | — |
| Real deployments | ✅ | — | — | — |
| Web UI | ✅ | — | ✅ (Studio) | ✅ (Studio) |
| Docker Compose mgmt | ✅ | — | — | — |
| Multiple LLM providers | ✅ (OpenRouter) | ✅ | ✅ | ✅ |
| Per-agent LLM config | ✅ | ✅ | ✅ | ✅ |
| Memory/state | ✅ (filesystem) | ✅ (in-memory) | ✅ (in-memory) | ✅ (checkpoints) |
| Task queue | ✅ (tickets) | ✅ (tasks) | ✅ (messages) | ✅ (graph) |
| Autonomous mode | ✅ (autopilot) | ✅ | ✅ | ✅ |

## Key Differentiators

### Dockfra agents are REAL environments

In CrewAI/AutoGen, an "agent" is a Python object with a system prompt. It can only call Python functions.

In Dockfra, an agent is a **full Linux container** that can:
- Run any CLI tool (git, docker, ssh, make, npm, pip)
- Edit real files on a real filesystem
- SSH to other containers or remote servers
- Deploy to production servers
- Run tests, build artifacts, serve APIs

### Security through isolation

| Security | Dockfra | CrewAI/AutoGen |
|---|---|---|
| Agent can access other agent's data | ❌ (separate containers) | ✅ (same process) |
| Agent can execute arbitrary code | Contained in Docker | Unrestricted Python |
| Network isolation between agents | ✅ (Docker networks) | ❌ |
| Resource limits per agent | ✅ (Docker limits) | ❌ |
| Audit trail | ✅ (SSH logs, ticket system) | Varies |

### Infrastructure awareness

Dockfra agents don't just *talk about* infrastructure — they **operate** it:
- Manager creates tickets → stored in shared volume → Developer picks up
- Autopilot daemon checks health → decides to redeploy → Monitor executes
- Developer edits code → runs tests → commits → Monitor deploys to production

## When to Choose

### Choose Dockfra when:
- You need agents that **operate real infrastructure** (Docker, SSH, git, deploy)
- You need **OS-level isolation** between agents
- You want agents as **persistent services** (not one-shot scripts)
- You need **human SSH access** to agent environments
- You're managing a **Docker Compose project** with AI assistance

### Choose CrewAI / AutoGen / LangGraph when:
- You need **rapid prototyping** of multi-agent workflows
- Your agents primarily **process text** (research, writing, analysis)
- You need **complex reasoning chains** with tool use
- You want a **Python-native** agent framework
- You don't need infrastructure isolation or Docker management

## Hybrid Architecture

Dockfra can **host** CrewAI/AutoGen agents inside its containers:

```
ssh-autopilot container:
├── autopilot-daemon.sh              ← Bash daemon
├── scripts/
│   └── pilot-run.sh                 ← Triggers LLM decision
└── /workspace/
    └── crewai_orchestrator.py       ← Optional: CrewAI inside container
```

This gives you the best of both worlds:
- **Dockfra** for infrastructure, isolation, and human access
- **CrewAI/AutoGen** for sophisticated LLM reasoning chains inside agents

## Links

- [CrewAI](https://github.com/crewAIInc/crewAI) — multi-agent orchestration
- [AutoGen](https://github.com/microsoft/autogen) — Microsoft multi-agent framework
- [LangGraph](https://github.com/langchain-ai/langgraph) — stateful agent workflows
- [Back to comparisons](README.md)
