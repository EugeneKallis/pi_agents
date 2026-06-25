# Pi Multi-Agent Manager

Run multiple Pi agents with shared extensions, isolated configs, and different roles — all sharing your **global API keys**. Each agent can run interactively, in a persistent terminal workspace ([herdr](https://herdr.dev)), or as a **macOS launchd service** that auto-restarts on crash and survives logout.

Everything is driven through `just` recipes. Run `just` with no args to see the full list.

## Structure

```
pi_agents/
├── justfile                     ← All operational commands (this README is a guide to it)
├── .env                         ← Shared env vars for every just recipe (gitignored, optional)
├── EXTENSIONS.md                ← Deep dive on the 4-tier extension system
│
├── scripts/
│   ├── launch-agent.sh          ← pty wrapper invoked by launchd (sources .env, execs pi)
│   └── service.py               ← launchd service manager (install/uninstall/start/stop/status/list)
│
├── extensions/                  ← Shared .ts extensions loaded by ALL agents
│   ├── audit-logger.ts
│   └── file-guard.ts
│
├── templates/base-agent/        ← Copy to add a new agent (via `just new-agent`)
│   ├── agent.yaml
│   ├── SYSTEM.md
│   ├── AGENTS.md                ← Per-agent conventions (stub — fill in)
│   └── .env.example             ← Template for the agent's .env (gitignored when copied to .env)
│
├── agents/
│   ├── coder/                   ← Each agent is one folder (self-contained / "universal")
│   │   ├── agent.yaml           ← id, name, model, permissions
│   │   ├── SYSTEM.md            ← System prompt (role / persona) — loaded via systemPromptFile
│   │   ├── AGENTS.md            ← Per-agent conventions — loaded by pi's walk-up from cwd = this folder
│   │   ├── .env                 ← Per-agent secrets (TELEGRAM_BOT_TOKEN, etc.) — gitignored
│   │   └── .pi/
│   │       ├── auth.json        (symlink → ~/.pi/agent/auth.json)
│   │       ├── settings.json    (model, extensions, packages — just the overrides)
│   │       ├── extensions/      ← Auto-discovered .ts files (agent-specific tools)
│   │       ├── npm/             ← Per-agent npm packages (from `just install-pkg -l`)
│   │       └── sessions/        ← Conversation history (gitignored)
│   ├── qa-engineer/
│   └── jobsearch/
│
└── logs/                        ← launchd service logs (gitignored, created on `just service-install`)
    ├── <agent>.log              ← pty / TUI capture (tail with `just service-logs`)
    └── <agent>.{out,err}.log    ← launchd's own stdout/stderr (tail with `just service-debug`)
```

## How auth works

Pi stores API keys in `~/.pi/agent/auth.json`. Each agent has its own `.pi/` directory via `PI_CODING_AGENT_DIR`, but the `auth.json` is **symlinked** from the global config so all agents share the same credentials.

```
~/.pi/agent/auth.json  ← your real API keys
         ↕ symlink
agents/coder/.pi/auth.json     ← agent sees the same keys
agents/qa-engineer/.pi/auth.json  ← same keys
```

Run `just auth-sync` after adding a new agent to set up the symlink. Run `just auth-status` to verify.

Everything else (`settings.json`, theme, global packages) is merged from `~/.pi/agent/settings.json` automatically — **no extra config needed**.

## Settings merge

Pi merges settings from two levels — the agent only needs to specify what it overrides:

```
~/.pi/agent/settings.json         ← Provider, global packages, theme
         ↓ inherits
<agent>/.pi/settings.json         ← Just: model, per-agent packages, extensions
```

**Global settings** (`~/.pi/agent/settings.json`):
- `defaultProvider` — e.g. `opencode-go`
- Globally installed packages (like `pi-subagents`, `context-mode`)
- Theme, keybindings

**Per-agent settings** (`agents/coder/.pi/settings.json`):
```json
{
  "defaultModel": "deepseek-v4-flash",
  "packages": [],
  "extensions": ["../../../extensions/audit-logger.ts"]
}
```

Just the overrides. Provider, theme, global packages — all inherited. Per-agent `packages` **replaces** (not merges) the global `packages` array, so each agent gets exactly the packages it declares.

## Per-agent `.env` files

Each agent can carry its own secrets without polluting the global shell or the tracked `settings.json`:

| File | Scope | Loaded by | Gitignored? |
|------|-------|-----------|-------------|
| `.env` (repo root) | Shared by every `just` recipe | `set dotenv-load` in the justfile (auto) | Yes |
| `agents/<name>/.env` | Only that agent's `just <name>` / `just run <name>` / service | Inlined in each pi-launching recipe + `scripts/launch-agent.sh` | Yes |
| `templates/base-agent/.env.example` | Template for new agents | Not loaded — reference only | **No** (tracked) |

Per-agent `.env` wins on conflict (loaded after the repo-root `.env`). The service wrapper (`scripts/launch-agent.sh`) also sources `agents/<name>/.env` before exec'ing pi, so a service sees the same secrets as an interactive run.

To seed a new agent's `.env` from the template:
```bash
just new-agent my-agent    # copies .env.example → .env automatically
# then edit agents/my-agent/.env with real values
```

---

# How to do things with `just`

All operational commands are `just` recipes. Run `just` (no args) to see the full list with descriptions.

## Launch an agent interactively

```bash
just coder                 # the coder agent
just qa                    # the QA engineer
just jobsearch "golang roles in NYC"   # jobsearch agent with an initial prompt
just jobsearch-kdb         # auto-search KDB+ jobs using your KDB resume
just jobsearch-go          # auto-search Golang jobs using your Go resume
just run coder             # any agent by folder name
```

Each recipe sources `agents/<name>/.env` (if it exists) on the same shell line as the `pi` invocation, then runs `PI_CODING_AGENT_DIR=$(pwd)/agents/<name>/.pi pi`. Close the terminal and the agent dies — for long-running use, see the service section below.

## Run an agent as a launchd service (long-running, auto-restart)

This is the path for Telegram-bridged always-on agents: the service survives terminal close and logout, auto-restarts on crash, and starts automatically when you log in.

### One-time Telegram setup (interactive)

```bash
just install-pkg coder npm:@llblab/pi-telegram   # 1. install the telegram package for the agent
just coder                                        # 2. run the agent once interactively
# inside pi: /telegram-setup    (paste bot token, get chat ID)
# inside pi: /telegram-connect  (start polling)
# exit pi
```

### Install as a service

```bash
just service-install coder
```

Generates `~/Library/LaunchAgents/agent-coder.plist`, calls `launchctl bootstrap`, and starts the agent. The plist:
- Runs `scripts/launch-agent.sh coder` (which sources `agents/coder/.env` and execs `pi` under a pty)
- `KeepAlive.Crashed=true` → auto-restart on crash
- `KeepAlive.SuccessfulExit=false` → no restart on clean exit (a deliberate `/quit` keeps it down)
- `ThrottleInterval=10` → caps restart loops at one per 10s
- `RunAtLoad=true` → starts on login AND on install
- Captures the pty (TUI) to `logs/coder.log`; launchd's own stdout/stderr to `logs/coder.{out,err}.log`

### Manage the service

```bash
just service-status coder     # PID + plist + log paths
just service-list             # all installed pi-agent services
just service-stop coder       # stop (launchctl bootout)
just service-start coder      # start (re-bootstraps if stopped, then kickstart)
just service-logs coder       # tail -f logs/coder.log  (pty / TUI capture)
just service-debug coder      # tail -f logs/coder.{out,err}.log  (wrapper/launchd errors)
just service-uninstall coder  # stop + remove the plist
```

`service-start` correctly handles the post-`service-stop` state: after `bootout` the service is unloaded, so `service-start` detects that via `launchctl print`, re-`bootstrap`s from the plist, then `kickstart -k`s. The stop→start round-trip works.

If `pi` isn't on the service's `PATH`, the wrapper exits 127 with a clear error in `logs/coder.err.log` (visible via `just service-debug`) instead of silently crash-looping.

## Create a new agent

```bash
just new-agent research-assistant
# → copies templates/base-agent/ to agents/research-assistant/
# → seeds agents/research-assistant/.env from .env.example
just auth-sync                 # link global auth into the new agent
# Then edit:
#   agents/research-assistant/agent.yaml     (id, name, model, permissions)
#   agents/research-assistant/SYSTEM.md      (system prompt: role / persona)
#   agents/research-assistant/AGENTS.md      (per-agent conventions — auto-loaded by pi)
#   agents/research-assistant/.pi/settings.json  (packages, extensions)
#   agents/research-assistant/.env           (secrets — already seeded)
```

## herdr — persistent terminal workspace

[herdr](https://herdr.dev) runs your agents in a **persistent server** — detach and the agents keep running, reattach from any terminal. Use this when you want live TUI access to multiple agents at once. For headless long-running use, prefer the launchd service above.

```bash
just herdr                    # create/attach the pi-agents workspace (idempotent)
just herdr-attach             # reattach to an existing session
just herdr-agents             # list running agents
just herdr-focus coder        # jump to a specific agent's pane
just herdr-attach-agent coder # attach to one agent's terminal
just herdr-stop               # stop all agents and close the workspace
```

Detach (keep running): `Ctrl+B` then `D`. If an agent crashes, herdr restarts it automatically.

## Extensions

There are four tiers — see `EXTENSIONS.md` (`just help-extensions`) for the full guide.

```bash
# Show what each agent loads
just show-ext

# Shared .ts extension (loaded by ALL agents)
just install-ext my-extension.ts          # copies to extensions/ + registers in each settings.json
just uninstall-ext my-extension.ts        # removes from each settings.json (keeps the file)

# Agent-specific .ts extension (auto-discovered, no config needed)
just install-ext-for coder coder-tools.ts # drops into agents/coder/.pi/extensions/
just uninstall-ext-for coder coder-tools.ts
```

## Packages (npm)

```bash
# Per-agent (writes to agents/<name>/.pi/settings.json, stored in agents/<name>/.pi/npm/)
just install-pkg coder npm:@llblab/pi-telegram
just remove-pkg coder npm:@llblab/pi-telegram
just list-pkgs coder

# Global (every pi session on the machine, not just this repo)
just install-pkg-global npm:pi-subagents
just list-pkgs-global
```

## Auth

```bash
just auth-sync              # symlink ~/.pi/agent/auth.json into every agent's .pi/
just auth-status            # check which agents have auth linked
```

## Utilities

```bash
just tree                   # file tree (excludes .git, node_modules, .gitkeep)
just setup                  # one-time repo setup (bun run src/setup.ts)
just help-extensions        # print EXTENSIONS.md
just                        # list all recipes
```

---

# Complete `just` recipe reference

Organized by task. Run `just --list` for the canonical list with descriptions.

### Run agents (interactive)
| Recipe | Description |
|--------|-------------|
| `just coder` | Launch the coder agent |
| `just qa` | Launch the QA engineer |
| `just jobsearch [query]` | Launch jobsearch agent, optionally with an initial prompt |
| `just jobsearch-kdb` | Auto-search KDB+ jobs using your KDB resume |
| `just jobsearch-go` | Auto-search Golang jobs using your Go resume |
| `just run <agent>` | Launch any agent by folder name |
| `just all` | Launch all agents via the orchestrator (`bun run start`) |

### Service (launchd — long-running, auto-restart)
| Recipe | Description |
|--------|-------------|
| `just service-install <agent>` | Generate plist, `launchctl bootstrap`, start |
| `just service-uninstall <agent>` | `launchctl bootout` + remove plist |
| `just service-start <agent>` | Start (re-bootstraps if stopped, then `kickstart -k`) |
| `just service-stop <agent>` | Stop (`launchctl bootout`) |
| `just service-status <agent>` | PID + plist + log paths |
| `just service-logs <agent>` | `tail -f logs/<agent>.log` (pty / TUI capture) |
| `just service-debug <agent>` | `tail -f logs/<agent>.{out,err}.log` (launchd stdout/stderr) |
| `just service-list` | All installed pi-agent services and their status |

### Create / scaffold agents
| Recipe | Description |
|--------|-------------|
| `just new-agent <name>` | Copy template to `agents/<name>/`, seed `.env` from `.env.example` |

### herdr — persistent terminal workspace
| Recipe | Description |
|--------|-------------|
| `just herdr` | Create/attach the pi-agents workspace (idempotent) |
| `just herdr-attach` | Reattach to the session |
| `just herdr-agents` | List running agents |
| `just herdr-focus <agent>` | Jump to a specific agent's pane |
| `just herdr-attach-agent <agent>` | Attach to one agent's terminal |
| `just herdr-stop` | Stop all agents and close the workspace |

### Auth — global API keys
| Recipe | Description |
|--------|-------------|
| `just auth-sync` | Symlink `~/.pi/agent/auth.json` into every agent's `.pi/` |
| `just auth-status` | Check which agents have auth linked |

### Packages (npm)
| Recipe | Description |
|--------|-------------|
| `just install-pkg <agent> <pkg>` | Install an npm package for one agent (`-l`) |
| `just install-pkg-global <pkg>` | Install an npm package globally (all pi sessions) |
| `just remove-pkg <agent> <pkg>` | Remove a package from one agent |
| `just list-pkgs <agent>` | List one agent's packages |
| `just list-pkgs-global` | List global packages |

### Extensions (.ts)
| Recipe | Description |
|--------|-------------|
| `just install-ext <file.ts>` | Shared extension for all agents (copies to `extensions/`, registers in each settings.json) |
| `just install-ext-for <agent> <file.ts>` | Agent-specific extension (drops into `agents/<name>/.pi/extensions/`) |
| `just uninstall-ext <filename>` | Remove shared extension reference from all agents (keeps the file) |
| `just uninstall-ext-for <agent> <filename>` | Remove an agent-specific extension (deletes the file) |
| `just show-ext` | Show which extensions each agent loads |
| `just help-extensions` | Print `EXTENSIONS.md` (the full 4-tier guide) |

### Utilities
| Recipe | Description |
|--------|-------------|
| `just tree` | File tree (excludes `.git`, `node_modules`, `.gitkeep`) |
| `just setup` | One-time repo setup (`bun run src/setup.ts`) |

---

## Troubleshooting services

**`just service-status <agent>` says "not running" right after install.** Check `just service-debug <agent>` — if you see `error: 'pi' not found on PATH`, the plist's hardcoded `PATH` (`/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`) doesn't include your `pi` install. Edit `scripts/service.py`'s `PLIST_PATH_TEMPLATE` to add your `pi` location, `just service-uninstall <agent>`, then `just service-install <agent>`.

**Service crash-loops every 10 seconds.** `ThrottleInterval=10` is doing its job. Check `just service-debug <agent>` for the wrapper's stderr (e.g., `pi` not found, bad `.env` syntax). Fix the root cause, then `just service-start <agent>`.

**`just service-start` after `just service-stop` doesn't work.** It should — the start recipe detects the unloaded state via `launchctl print` and re-`bootstrap`s before `kickstart`. If it still fails, check that `~/Library/LaunchAgents/agent-<agent>.plist` still exists (`service-stop` doesn't remove it; only `service-uninstall` does).

**Logs are filling the disk.** `logs/<agent>.{log,out,err}.log` grow without rotation. There's no built-in rotation yet — periodically truncate or delete them while the service is stopped, then `just service-start <agent>`.

**Service doesn't survive reboot.** `RunAtLoad=true` starts it on **login**, not boot. That's correct for a user LaunchAgent. If you need it running before login, that requires a system LaunchDaemon (root), which is out of scope for this setup.
