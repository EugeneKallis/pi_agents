# ─── Pi Multi-Agent Manager ──────────────────────────────────────────────────
# justfile — run agents, install extensions

PY := "python3 src/ext.py"
H_SETUP := "python3 src/herdr-setup.py"

# ─── Settings ────────────────────────────────────────────────────────────────

# Auto-load the repo-root `.env` before every recipe (shared env vars).
# Per-agent `.env` files at `agents/<name>/.env` are loaded inline by each
# `pi`-launching recipe below — the load and the `pi` invocation must share
# a single shell line, because just runs each recipe line in its own shell.
set dotenv-load

# ─── Run agents ──────────────────────────────────────────────────────────────

# Launch the coder agent. `cd agents/coder` so pi's walk-up discovers this
# agent's own AGENTS.md (and then the repo-root AGENTS.md on the way up).
coder:
    cd agents/coder && { [ -f ".env" ] && { set -a; . ".env"; set +a; } || true; } && PI_CODING_AGENT_DIR=$(pwd)/.pi pi

# Launch the QA engineer
qa:
    cd agents/qa-engineer && { [ -f ".env" ] && { set -a; . ".env"; set +a; } || true; } && PI_CODING_AGENT_DIR=$(pwd)/.pi pi

# Launch the job search agent interactively.
# Pass a query to auto-start the search, e.g.: just jobsearch "find me senior golang roles"
jobsearch query="":
    cd agents/jobsearch && { [ -f ".env" ] && { set -a; . ".env"; set +a; } || true; } && PI_CODING_AGENT_DIR=$(pwd)/.pi pi "{{query}}"

# Auto-search jobs for a given role. The full job-search workflow (resume,
# boards, location filter, output format, HTML/open, verify-still-open) lives
# in agents/jobsearch/SYSTEM.md and AGENTS.md — this recipe only supplies
# the role. Examples: just jobsearch-role kdb, just jobsearch-role "Golang"
jobsearch-role role:
    cd agents/jobsearch && { [ -f ".env" ] && { set -a; . ".env"; set +a; } || true; } && \
    PI_CODING_AGENT_DIR=$(pwd)/.pi pi \
      "Search for {{role}} developer jobs and follow the standard job-search workflow."

# Convenience aliases for the two resumes on file
jobsearch-kdb: (jobsearch-role "KDB+")
jobsearch-go: (jobsearch-role "Golang")

# Launch all agents via the orchestrator
all:
    bun run start

# Launch any agent by folder name (e.g., just run coder, just run qa-engineer)
run agent:
    cd agents/{{agent}} && { [ -f ".env" ] && { set -a; . ".env"; set +a; } || true; } && PI_CODING_AGENT_DIR=$(pwd)/.pi pi

# ─── Service — long-running, auto-restart, runs on login ──────────────────
#
# Platform dispatch:
#   Linux → systemd (scripts/service-systemd.py)
#     Two modes, auto-detected by EUID + $SUDO_USER:
#       - system mode: unit at /etc/systemd/system/pi-agent-<name>.service,
#         runs as the sudo invoker (NOT literal root). Requires `sudo`.
#       - user mode:   unit at ~/.config/systemd/user/pi-agent-<name>.service,
#         runs as the calling user, no sudo. Auto-enables linger so the
#         service survives logout and starts on boot.
#     Override with `just service-install <agent> -- system` or `-- user`.
#     Logs: <repo>/logs/<name>.{out,err}.log
#
#   macOS → launchd (scripts/service.py, user LaunchAgent)
#     Plist at ~/Library/LaunchAgents/agent-<name>.plist, runs as the calling
#     user. Logs: <repo>/logs/<name>.log (pty/TUI capture) + .out.log/.err.log.
#
# First-time Telegram setup is interactive (you must run the agent once to
# approve the bot, then `/telegram-connect`). After that, these recipes are
# all you need to bring the agent up as a long-running service.
service-install agent mode="":
    bash scripts/service.sh install {{mode}} {{agent}}

# Uninstall the service for the current platform
service-uninstall agent mode="":
    bash scripts/service.sh uninstall {{mode}} {{agent}}

# Start (or restart) the service
service-start agent mode="":
    bash scripts/service.sh start {{mode}} {{agent}}

# Stop the service
service-stop agent mode="":
    bash scripts/service.sh stop {{mode}} {{agent}}

# Check service status (active state, unit path, log paths)
service-status agent mode="":
    bash scripts/service.sh status {{mode}} {{agent}}

# Tail the service log (Linux: stdout; macOS: pty-captured TUI log)
service-logs agent:
    @if [ "$(uname -s)" = "Linux" ]; then tail -f logs/{{agent}}.out.log; else tail -f logs/{{agent}}.log; fi

# Tail the service's stderr + stdout (useful for wrapper/script errors and restart events on both platforms)
service-debug agent:
    @tail -f logs/{{agent}}.err.log logs/{{agent}}.out.log

# List all installed pi-agent services and their status (auto-detects mode)
service-list:
    bash scripts/service.sh list

# Create a new agent from the base template
new-agent name:
    cp -r templates/base-agent agents/{{name}}
    # Seed a .env from the template example (only if it doesn't already exist)
    @if [ -f "agents/{{name}}/.env.example" ] && [ ! -f "agents/{{name}}/.env" ]; then \
        cp "agents/{{name}}/.env.example" "agents/{{name}}/.env"; \
        echo "Seeded agents/{{name}}/.env from .env.example"; \
    fi
    @echo "Created agents/{{name}}/"
    @echo "Next: edit agent.yaml, SYSTEM.md, AGENTS.md, and .pi/settings.json"
    @echo "Then run: just auth-sync"

# ─── herdr — persistent terminal workspace ─────────────────────────────────

# Create/attach herdr workspace with all agents (idempotent)
herdr:
    {{H_SETUP}}

# Reattach to the herdr session
herdr-attach:
    herdr

# List running agents in herdr
herdr-agents:
    herdr agent list

# Focus a specific agent pane (e.g., just herdr-focus coder)
herdr-focus agent:
    herdr agent focus {{agent}}

# Attach to a specific agent's terminal
herdr-attach-agent agent:
    herdr agent attach {{agent}}

# Stop all agents and close the workspace
herdr-stop:
    herdr workspace close pi-agents

# ─── Auth — global API keys ─────────────────────────────────────────────────

# Link the global auth.json into every agent's .pi/ directory
# This makes each agent inherit your global API keys (opencode-go, openrouter, etc.)
auth-sync:
    @echo "Linking global auth.json into each agent..."
    @for agent_dir in agents/*/; do \
        agent=$(basename $agent_dir); \
        target="$agent_dir.pi/auth.json"; \
        mkdir -p "$agent_dir.pi"; \
        ln -snf ~/.pi/agent/auth.json "$target"; \
        echo "  $agent ✓"; \
    done
    @echo "Done. Agents now share your global API keys."

# Check which agents have auth linked
auth-status:
    @echo "=== Agent auth status ==="
    @for agent_dir in agents/*/; do \
        agent=$(basename $agent_dir); \
        auth="$agent_dir.pi/auth.json"; \
        if [ -L "$auth" ] && [ -e "$auth" ]; then \
            echo "  $agent ✅ linked -> $(readlink $auth)"; \
        elif [ -f "$auth" ]; then \
            echo "  $agent ⚠️  local copy (not a symlink)"; \
        else \
            echo "  $agent ❌ missing — run  just auth-sync"; \
        fi; \
    done

# ─── Pi npm packages ────────────────────────────────────────────────────────

# Install a Pi npm package for ONE agent (writes to agent's .pi/settings.json)
install-pkg agent pkg:
    PI_CODING_AGENT_DIR=$(pwd)/agents/{{agent}}/.pi pi install -l {{pkg}}

# Install a Pi npm package globally (all agents inherit it)
install-pkg-global pkg:
    pi install {{pkg}}

# List per-agent packages
list-pkgs agent:
    @{{PY}} list-pkgs agents/{{agent}}/.pi/settings.json | awk '{print "  " $0}'

# List global user packages
list-pkgs-global:
    @{{PY}} list-pkgs ~/.pi/agent/settings.json | awk '{print "  " $0}'

# Remove a package from one agent
remove-pkg agent pkg:
    PI_CODING_AGENT_DIR=$(pwd)/agents/{{agent}}/.pi pi remove {{pkg}}

# ─── Custom .ts extensions ──────────────────────────────────────────────────

# Install a .ts extension for ALL agents (repo-shared level)
# Copies to extensions/ and registers in each agent's settings.json
install-ext src:
    @echo "Installing shared extension: {{src}}..."
    cp "{{src}}" extensions/
    @basename="$(basename {{src}})"; \
    relpath="../../../extensions/$basename"; \
    for agent_dir in agents/*/; do \
        agent=$(basename $agent_dir); \
        settings="$agent_dir.pi/settings.json"; \
        if [ -f "$settings" ]; then \
            result="$({{PY}} add-shared "$settings" "$relpath")"; \
            echo "  [$result] $agent"; \
        fi; \
    done
    @echo "Done — restart or /reload each agent"

# Install a .ts extension for ONE agent only (auto-discovered)
install-ext-for agent src:
    cp "{{src}}" agents/{{agent}}/.pi/extensions/
    @echo "Installed for {{agent}} — auto-discovered on next launch or /reload"

# Remove a shared extension reference from all agents (keeps the file)
uninstall-ext filename:
    @relpath="../../../extensions/{{filename}}"; \
    for agent_dir in agents/*/; do \
        agent=$(basename $agent_dir); \
        settings="$agent_dir.pi/settings.json"; \
        if [ -f "$settings" ]; then \
            result="$({{PY}} remove-shared "$settings" "$relpath")"; \
            echo "  [$result] $agent"; \
        fi; \
    done
    @echo "Done — file still at extensions/{{filename}}"

# Remove an agent-specific extension (deletes the file)
uninstall-ext-for agent filename:
    rm -f agents/{{agent}}/.pi/extensions/{{filename}}
    @echo "Removed agents/{{agent}}/.pi/extensions/{{filename}}"

# ─── Utilities ──────────────────────────────────────────────────────────────

# Show which extensions each agent loads
show-ext:
    @echo "=== Shared (repo-level) extensions ==="
    @ls extensions/*.ts 2>/dev/null | sed 's|.*/|  |' || echo "  (none)"
    @echo ""
    @for agent_dir in agents/*/; do \
        agent=$(basename $agent_dir); \
        echo "=== $agent agent extensions ==="; \
        echo "  From settings.json (shared):"; \
        {{PY}} list-extensions "$agent_dir.pi/settings.json" 2>/dev/null | sed 's|.*/|    |' || echo "    (none)"; \
        echo "  From .pi/extensions/ (agent-specific):"; \
        ls "$agent_dir.pi/extensions/"*.ts 2>/dev/null | sed 's|.*/|    |' || echo "    (none)"; \
        echo ""; \
    done

show-extensions: show-ext

# Open the extension install guide
help-extensions:
    cat EXTENSIONS.md

# File tree
tree:
    find . -not -path "*/.git/*" -not -path "*/node_modules/*" -not -name ".gitkeep" -type f | sort | head -60

# One-time setup
setup:
    bun run src/setup.ts

# Default help
_default:
    @just --list
