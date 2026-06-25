#!/usr/bin/env bash
# Platform dispatcher for the pi-agent service manager.
#
# Linux  → scripts/service-systemd.py   (systemd; auto-detects system vs user mode)
# macOS  → scripts/service.py           (launchd; user LaunchAgent)
# other  → error
#
# All justfile `service-*` recipes call this script, so users get the right
# backend for whichever OS they're on without thinking about it.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$(uname -s)" in
    Linux)
        exec python3 "$SCRIPT_DIR/service-systemd.py" "$@"
        ;;
    Darwin)
        exec python3 "$SCRIPT_DIR/service.py" "$@"
        ;;
    *)
        echo "error: service manager not supported on $(uname -s)" >&2
        echo "  supported: Linux (systemd), macOS (launchd)" >&2
        exit 1
        ;;
esac
