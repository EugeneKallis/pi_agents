# Extension Installation Guide

This repo has three scopes for extensions. Understanding the difference is key to keeping agents cleanly configured.

---

## 1. Pi packages (npm) — global user level

Installed without `-l`. Shared by **every Pi session on your machine**, including all agents in this repo.

```bash
# Outside pi, from anywhere:
pi install npm:@llblab/pi-telegram
pi install npm:pi-subagents

# Inside pi:
/install npm:@llblab/pi-telegram
```

**Where it lands:** `~/.pi/agent/npm/` — in your Pi user config, not in this repo.
**Config file:** `~/.pi/agent/settings.json` — the `packages` list.
**Scope:** Every pi process you start, everywhere.

---

## 2. Pi packages (npm) — per-agent level

Installed with `-l`. Scoped to **one agent's `.pi/` directory**.

```bash
# From the agent's directory with PI_CODING_AGENT_DIR set:
cd agents/coder
PI_CODING_AGENT_DIR=$(pwd)/.pi pi install -l npm:@llblab/pi-telegram
```

**Where it lands:** `agents/coder/.pi/npm/`
**Config file:** `agents/coder/.pi/settings.json` — the `packages` list.
**Scope:** Only that agent. Other agents don't see it.

### What's the difference?

| Command | Config written to | Package stored at | Visible to |
|---------|------------------|-------------------|------------|
| `pi install npm:pkg` | `~/.pi/agent/settings.json` | `~/.pi/agent/npm/` | All agents + all other Pi projects |
| `pi install -l npm:pkg` | `<agent>/.pi/settings.json` | `<agent>/.pi/npm/` | Only that agent |

**Use case for global:** Things like `pi-web-access`, `context-mode`, or `pi-subagents` that you want available in every Pi session.

**Use case for per-agent:** `@llblab/pi-telegram` when different agents connect to different bots, or role-specific packages you don't want cluttering other agents.

---

## 3. Custom extension files (`.ts`) — repo-shared level

Custom `.ts` extension files that live in this repo and are loaded by **every agent**.

### Install a new shared extension

```bash
# 1. Drop the file
cp my-extension.ts extensions/

# 2. Register it in each agent's .pi/settings.json
# Edit agents/coder/.pi/settings.json:
#   "extensions": [
#     "../../../extensions/audit-logger.ts",
#     "../../../extensions/file-guard.ts",
#     "../../../extensions/my-extension.ts"    ← add this
#   ]
#
# Repeat for agents/qa-engineer/.pi/settings.json

# 3. Reload or restart
```

**Where it lives:** `pi_agents/extensions/` (checked into git)
**Config:** Each agent's `.pi/settings.json` under `"extensions"` — relative path from the settings file to `pi_agents/extensions/`
**Path resolution:** From `agents/coder/.pi/settings.json`, `../../../extensions/my-extension.ts` resolves to `pi_agents/extensions/my-extension.ts`.

**Use case:** Audit logging, file guards, notification hooks, metrics — anything every agent should have.

### Uninstall a shared extension

```bash
# Remove from each agent's .pi/settings.json "extensions" list
# Optionally delete the file from extensions/
```

---

## 4. Custom extension files (`.ts`) — per-agent level

Custom `.ts` extension files that live in **one agent's `.pi/extensions/`** directory and are auto-discovered by Pi.

### Install an agent-specific extension

```bash
# Just drop it in the agent's .pi/extensions/ directory
cp my-agent-tool.ts agents/coder/.pi/extensions/

# Pi discovers it automatically — no config changes needed.
# Next session start or /reload picks it up.
```

**Where it lives:** `agents/<name>/.pi/extensions/` (checked into git)
**Config:** None — Pi auto-discovers `.ts` files in this directory.
**Scope:** Only that agent.

**Use case:** Role-specific tools (e.g., `coder-tools.ts` for the coder, `qa-tools.ts` for QA), or a Telegram bot extension unique to one agent.

### Uninstall an agent-specific extension

```bash
rm agents/coder/.pi/extensions/my-agent-tool.ts
```

---

## Quick reference

| Scope | Mechanism | Where files live | Config needed? |
|-------|-----------|-----------------|----------------|
| **Global user** (all Pi) | `pi install npm:pkg` | `~/.pi/agent/npm/` | No (auto) |
| **Per-agent (npm)** | `pi install -l npm:pkg` | `<agent>/.pi/npm/` | No (auto) |
| **Repo-shared (`.ts`)** | `"extensions"` in settings | `pi_agents/extensions/` | Yes — each agent's `.pi/settings.json` |
| **Per-agent (`.ts`)** | Auto-discover from directory | `<agent>/.pi/extensions/` | No |

## `just` shortcuts

See the `justfile` for convenience commands:

```bash
just install-pkg coder npm:@llblab/pi-telegram   # Install npm package for one agent
just install-pkg-global npm:pi-subagents          # Install npm package for all agents
just install-ext shared/my-thing.ts               # Install a .ts extension repo-wide
just install-ext coder agent-tool.ts              # Install a .ts extension for one agent
```
