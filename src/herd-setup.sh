#!/bin/bash
# Herdr workspace setup — launches coder + QA engineer in split panes
#
# Layout:
#   ┌─────────────────────┐
#   │      coder          │
#   ├─────────────────────┤
#   │    qa-engineer      │
#   └─────────────────────┘
#
# Usage: bash src/herd-setup.sh
# Or:    just herd

set -e

AGENTS_DIR="$(cd "$(dirname "$0")/../agents" && pwd)"
WORKSPACE_LABEL="pi-agents"

# Make sure auth is linked for all agents
echo "🔗 Syncing auth..."
for agent_dir in "$AGENTS_DIR"/*/; do
    agent=$(basename "$agent_dir")
    mkdir -p "$agent_dir/.pi"
    ln -snf "$HOME/.pi/agent/auth.json" "$agent_dir/.pi/auth.json"
    echo "   $agent ✓"
done

# Ensure herdr server is running
echo -e "\n🚀 Ensuring herdr server is running..."
herdr server reload-config 2>/dev/null || true

# Close any existing pi-agents workspace to start clean
EXISTING_WS=$(herdr workspace list 2>/dev/null | grep "$WORKSPACE_LABEL" | grep -oE '^w[a-f0-9:]+' | head -1)
if [ -n "$EXISTING_WS" ]; then
    echo "   Closing existing $WORKSPACE_LABEL workspace ($EXISTING_WS)..."
    herdr workspace close "$EXISTING_WS" 2>/dev/null || true
    sleep 1
fi

# Create fresh workspace
echo -e "\n📁 Creating $WORKSPACE_LABEL workspace..."
WS_ID=$(herdr workspace create --label "$WORKSPACE_LABEL" --cwd "$AGENTS_DIR/.." 2>/dev/null | grep -oE '^w[a-f0-9:]+')

if [ -z "$WS_ID" ]; then
    echo "   ❌ Could not create workspace. Is herdr running?"
    exit 1
fi
echo "   Workspace ID: $WS_ID"

# Step 1: Start coder agent in a new tab with a split pane below
# herdr agent start creates a tab, runs the command in the first pane,
# and --split down creates a second pane below it.
echo -e "\n👨‍💻 Launching coder agent..."
herdr agent start "coder" \
    --workspace "$WS_ID" \
    --cwd "$AGENTS_DIR/coder" \
    --split down \
    --focus \
    -- bash -c "cd '$AGENTS_DIR/coder' && PI_CODING_AGENT_DIR=\$(pwd)/.pi exec pi"

sleep 2

# Step 2: Find the coder tab and its bottom pane (the empty shell from --split down)
echo -e "\n🧪 Setting up QA engineer in the bottom pane..."

# Get coder tab ID
CODER_TAB_ID=$(herdr tab list --workspace "$WS_ID" 2>/dev/null | grep '"coder"' | grep -oE '"tab_id":"[^"]+"' | cut -d'"' -f4 | head -1)

if [ -z "$CODER_TAB_ID" ]; then
    echo "   ⚠️  Could not find coder tab. Agents may be in separate tabs."
    echo "   Run 'herdr workspace focus $WORKSPACE_LABEL' to see."
    exit 1
fi

echo "   Coder tab: $CODER_TAB_ID"

# Find the bottom pane in coder tab (the one NOT running the agent)
CODER_PANES=$(herdr pane list --workspace "$WS_ID" 2>/dev/null)
# The coder tab's panes are the ones whose tab_id matches CODER_TAB_ID
# The panes are listed; the one without an agent entry is the empty shell
for PANE_ID in $(echo "$CODER_PANES" | grep -oE '"pane_id":"w[^"]+' | cut -d'"' -f4); do
    PANE_TAB_ID=$(echo "$CODER_PANES" | grep -A5 "\"pane_id\":\"$PANE_ID\"" | grep -oE '"tab_id":"[^"]+"' | cut -d'"' -f4)
    if [ "$PANE_TAB_ID" = "$CODER_TAB_ID" ]; then
        HAS_AGENT=$(echo "$CODER_PANES" | grep -A10 "\"pane_id\":\"$PANE_ID\"" | grep -oE '"agent":"' | head -1)
        if [ -z "$HAS_AGENT" ]; then
            EMPTY_PANE="$PANE_ID"
            break
        fi
    fi
done

if [ -n "$EMPTY_PANE" ]; then
    echo "   Found empty pane: $EMPTY_PANE — launching QA agent..."
    # Run pi in the empty pane via keystroke simulation
    herdr pane focus "$EMPTY_PANE" 2>/dev/null
    herdr pane send-text "$EMPTY_PANE" "cd '$AGENTS_DIR/qa-engineer' && PI_CODING_AGENT_DIR=\$(pwd)/.pi exec pi" 2>/dev/null
    sleep 0.5
    herdr pane send-keys "$EMPTY_PANE" "enter" 2>/dev/null
    # Rename the pane so herdr shows "qa-engineer"
    herdr pane rename "$EMPTY_PANE" "qa-engineer" 2>/dev/null || true
    echo "   ✅ QA engineer started in bottom pane"
else
    echo "   ⚠️  Could not find empty pane. Starting QA in a new tab..."
    herdr agent start "qa-engineer" \
        --workspace "$WS_ID" \
        --cwd "$AGENTS_DIR/qa-engineer" \
        --split down \
        --no-focus \
        -- bash -c "cd '$AGENTS_DIR/qa-engineer' && PI_CODING_AGENT_DIR=\$(pwd)/.pi exec pi" 2>/dev/null || true
fi

echo -e "\n✅ Agents launched in workspace '$WORKSPACE_LABEL'"
echo ""
echo "Commands:"
echo "   herdr workspace focus $WORKSPACE_LABEL    Reattach"
echo "   herdr agent list                          Show agents"
echo "   herdr agent focus coder                   Jump to coder"
echo "   herdr agent focus qa-engineer             Jump to QA"
