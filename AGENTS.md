# Pi Agents — Project Conventions

This file is loaded by pi for every agent launched from this repo (pi walks
up from cwd and finds it). It holds **project-wide** rules shared by all
agents in `agents/`.

## Default Model

All agents use **`deepseek-v4-flash`** via the **`opencode-go`** provider.

- In `agent.yaml`: `model: deepseek-v4-flash`
- In `.pi/settings.json`: both `"defaultProvider": "opencode-go"` and `"defaultModel": "deepseek-v4-flash"`
- **Always set both** `defaultProvider` and `defaultModel` in `.pi/settings.json` — do not rely on inheritance from global settings

## Agent Structure (self-contained / "universal")

Each agent folder is **self-contained** — it carries its own identity, system
prompt, conventions, and config. You can copy `agents/<name>/` into another
project and it will still load its own context.

```
agents/<name>/
├── agent.yaml              # Agent identity, model, permissions
├── SYSTEM.md               # System prompt (role + behavior) — loaded via systemPromptFile
├── AGENTS.md               # Per-agent conventions — loaded by pi's walk-up discovery
├── references/             # Data files (resumes, configs, memory)
└── .pi/
    ├── settings.json       # Model override, packages, extensions
    └── extensions/         # Per-agent .ts extension files
```

### How loading works (important)

Pi launches each agent with cwd = `agents/<name>/` (set by the `justfile`
recipes, `scripts/launch-agent.sh`, and `src/orchestrator.ts`). Pi's
context-file discovery walks **up** from cwd, so the order is:

1. `agents/<name>/AGENTS.md` ← per-agent conventions
2. `agents/AGENTS.md` ← (none, but reserved for agent-shared rules)
3. `AGENTS.md` ← this file (project-wide)
4. parent directories… (`~/.pi/agent/AGENTS.md`, etc.)

Each agent also loads its own `SYSTEM.md` (system prompt, via `systemPromptFile`).
These are **different layers** — `SYSTEM.md` is the prompt, `AGENTS.md` files
are injected context.

### What goes where

- **This file (repo `AGENTS.md`)** — project-wide rules, model defaults,
  shared conventions, file layout. Applies to every agent in this repo.
- **`agents/<name>/AGENTS.md`** — agent-specific conventions, commands,
  toolchain preferences, reference-file list. Travels with the agent.
- **`agents/<name>/SYSTEM.md`** — the agent's identity and behavior. Don't
  put conventions here; put them in the agent's `AGENTS.md`.

## Creating a New Agent

```bash
just new-agent <name>
# Then edit agent.yaml, SYSTEM.md, AGENTS.md, and .pi/settings.json
# Then: just auth-sync
```

The template at `templates/base-agent/` ships with a stub `AGENTS.md` — fill
in agent-specific conventions there.
