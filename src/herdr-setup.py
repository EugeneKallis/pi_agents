#!/usr/bin/env python3
"""
Herdr workspace setup for Pi agents.

Creates a dedicated herdr workspace with one tab per agent,
each running pi with the correct PI_CODING_AGENT_DIR.

Idempotent — safe to re-run.
"""

import json
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")
WORKSPACE_LABEL = "pi-agents"


def herdr(*args):
    """Run a herdr CLI command and return parsed JSON result."""
    result = subprocess.run(
        ["herdr", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        if result.stderr.strip():
            return {"error": result.stderr.strip()}
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout.strip()}


def get_workspaces():
    """Get list of current workspaces."""
    result = herdr("workspace", "list")
    return result.get("result", {}).get("workspaces", [])


def get_agents():
    """Get list of registered agents."""
    result = herdr("agent", "list")
    return result.get("result", {}).get("agents", [])


def find_workspace_by_label(label):
    """Find workspace by label."""
    for ws in get_workspaces():
        if ws.get("label") == label:
            return ws
    return None


def find_tab_by_label(workspace_id, label):
    """Find tab by label in a workspace."""
    result = herdr("tab", "list", "--workspace", workspace_id)
    tabs = result.get("result", {}).get("tabs", [])
    for tab in tabs:
        if tab.get("label") == label:
            return tab
    return None


def agent_dirs():
    """List agent directories."""
    if not os.path.isdir(AGENTS_DIR):
        return []
    return sorted([
        d for d in os.listdir(AGENTS_DIR)
        if os.path.isdir(os.path.join(AGENTS_DIR, d))
        and not d.startswith(".")
    ])


def main():
    agents = agent_dirs()
    if not agents:
        print("No agent directories found in agents/")
        sys.exit(1)

    print(f"Found agents: {', '.join(agents)}")
    print()

    # Find or create the workspace
    ws = find_workspace_by_label(WORKSPACE_LABEL)
    if ws:
        ws_id = ws["workspace_id"]
        print(f"[workspace] Using existing '{WORKSPACE_LABEL}' (id: {ws_id})")
    else:
        print(f"[workspace] Creating '{WORKSPACE_LABEL}'...")
        result = herdr("workspace", "create", "--label", WORKSPACE_LABEL,
                       "--cwd", REPO_ROOT, "--no-focus")
        created = result.get("result", {})
        ws_id = created.get("workspace", {}).get("workspace_id")
        if not ws_id:
            print(f"  Failed: {result}")
            sys.exit(1)
        print(f"  Created workspace {ws_id}")

    # Existing agent names in herdr (for dedup)
    existing_agents = set()
    for a in get_agents():
        if a.get("name"):
            existing_agents.add(a["name"])

    print()

    # Create a tab per agent and launch pi
    for agent_name in agents:
        agent_path = os.path.join(AGENTS_DIR, agent_name)
        pi_dir = agent_path

        print(f"[{agent_name}] ", end="")

        # Check if tab exists
        existing_tab = find_tab_by_label(ws_id, agent_name)
        if existing_tab:
            print(f"Tab already exists (id: {existing_tab['tab_id']})")

            # Check if pi is already running in this agent
            tab_agents = [
                a for a in get_agents()
                if a.get("name") == agent_name
            ]
            if tab_agents:
                status = tab_agents[0].get("agent_status", "unknown")
                print(f"         Pi already running (status: {status})")
                print()
                continue

            # Tab exists but pi isn't running — launch in it
            print("Tab exists, launching pi...")
            result = herdr("agent", "start", agent_name,
                          "--workspace", ws_id,
                          "--cwd", pi_dir,
                          "--split", "down",
                          "--no-focus",
                          "--",
                          "/bin/bash", "-c",
                          f"PI_CODING_AGENT_DIR={pi_dir} pi")
            if "error" in result:
                print(f"  Launch failed: {result['error']}")
            else:
                print(f"  Started pi (pane: {result.get('result', {}).get('agent', {}).get('pane_id', '?')})")
        else:
            # Create tab and launch
            print("Creating tab...")
            tab_result = herdr("tab", "create",
                              "--workspace", ws_id,
                              "--label", agent_name,
                              "--cwd", pi_dir,
                              "--no-focus")
            if "error" in tab_result:
                print(f"  Tab creation failed: {tab_result['error']}")
                print()
                continue

            tab_id = tab_result.get("result", {}).get("tab", {}).get("tab_id", "?")
            print(f"  Tab created (id: {tab_id})")

            # Brief pause for the tab to settle
            time.sleep(0.5)

            # Launch pi in this tab (use --tab to target the right tab)
            print(f"  Launching pi...")
            result = herdr("agent", "start", agent_name,
                          "--tab", tab_id,
                          "--cwd", pi_dir,
                          "--split", "down",
                          "--no-focus",
                          "--",
                          "/bin/bash", "-c",
                          f"PI_CODING_AGENT_DIR={pi_dir} pi")
            if "error" in result:
                print(f"  Launch failed: {result['error']}")
            else:
                print(f"  Started pi (pane: {result.get('result', {}).get('agent', {}).get('pane_id', '?')})")

        print()

    # Focus the workspace
    herdr("workspace", "focus", ws_id)
    print(f"Focused workspace '{WORKSPACE_LABEL}'")
    print()
    print("Done. All agents are running in herdr tabs.")
    print("Close terminal and reopen → herdr re-attaches, agents keep running.")
    print()
    print("To attach to a specific agent:")
    print("  herdr agent attach <name>")
    print("  herdr agent focus <name>")
    print("Or switch tabs in herdr's UI.")


if __name__ == "__main__":
    main()
