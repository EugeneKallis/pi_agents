#!/usr/bin/env python3
"""
Manage a pi agent as a macOS launchd user service.

Subcommands:
    install <agent>     Generate the LaunchAgent plist, write it to
                        ~/Library/LaunchAgents/, and `launchctl bootstrap` it.
    uninstall <agent>   `launchctl bootout` and remove the plist.
    start <agent>       `launchctl kickstart -k` the service.
    stop <agent>        `launchctl bootout` the service.
    status <agent>      Print whether the service is running, plus plist/log paths.
    list                Print all installed pi-agent services and their status.

The plist references scripts/launch-agent.sh <agent> in this repo. Run from
the repo root so $(pwd) is the repo path embedded in the plist.
"""
import os
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
LABEL_PREFIX = "agent-"
WRAPPER_REL = "scripts/launch-agent.sh"
PLIST_PATH_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{wrapper}</string>
        <string>{agent}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{repo}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>StandardOutPath</key>
    <string>{repo}/logs/{agent}.out.log</string>
    <key>StandardErrorPath</key>
    <string>{repo}/logs/{agent}.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
"""


def label_for(agent):
    return f"{LABEL_PREFIX}{agent}"


def plist_path_for(agent):
    return LAUNCH_AGENTS / f"{label_for(agent)}.plist"


def launchctl(*args, check=True):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=check)


def get_pid(label):
    """Return PID string from `launchctl list`, or None."""
    result = subprocess.run(
        ["launchctl", "list"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2] == label:
            return parts[0] if parts[0] != "-" else None
    return None


def cmd_install(agent):
    repo = Path.cwd()
    wrapper = repo / WRAPPER_REL
    if not wrapper.exists():
        print(f"error: wrapper not found at {wrapper}", file=sys.stderr)
        sys.exit(1)
    if not os.access(wrapper, os.X_OK):
        print(f"error: wrapper not executable: {wrapper}", file=sys.stderr)
        sys.exit(1)

    if not re.fullmatch(r"[A-Za-z0-9._-]+", agent):
        print(f"error: invalid agent name {agent!r} — allowed: letters, digits, ., _, -", file=sys.stderr)
        sys.exit(1)
    agent_dir = repo / "agents" / agent
    if not agent_dir.is_dir():
        print(f"error: agent directory not found: {agent_dir}", file=sys.stderr)
        print(f"  create it first with: just new-agent {agent}", file=sys.stderr)
        sys.exit(1)

    label = label_for(agent)
    plist_path = plist_path_for(agent)

    if plist_path.exists():
        print(f"→ {label} already installed at {plist_path}")
        print(f"  to re-install: just service-uninstall {agent} && just service-install {agent}")
        sys.exit(1)

    LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    (repo / "logs").mkdir(exist_ok=True)

    plist_path.write_text(PLIST_PATH_TEMPLATE.format(
        label=escape(label),
        wrapper=escape(str(wrapper)),
        agent=escape(agent),
        repo=escape(str(repo)),
    ))
    uid = os.getuid()
    try:
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        plist_path.unlink()
        msg = e.stderr.strip() if e.stderr else str(e)
        print(f"error: launchctl bootstrap failed: {msg}", file=sys.stderr)
        print(f"  (plist removed — fix the issue and re-run: just service-install {agent})", file=sys.stderr)
        sys.exit(1)
    print(f"→ installed and started {label}")
    print(f"  plist:   {plist_path}")
    print(f"  wrapper: {wrapper}")
    print(f"  log:     {repo}/logs/{agent}.log  (pty / TUI capture)")
    print(f"  out/err: {repo}/logs/{agent}.out.log, {repo}/logs/{agent}.err.log  (launchd stdout/stderr)")
    print(f"  status:  just service-status {agent}")
    print(f"  stop:    just service-stop {agent}    uninstall: just service-uninstall {agent}")


def cmd_uninstall(agent):
    label = label_for(agent)
    plist_path = plist_path_for(agent)
    if not plist_path.exists():
        print(f"{label} not installed")
        return
    # Try modern bootout first, fall back to legacy unload.
    result = subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        launchctl("unload", str(plist_path), check=False)
    plist_path.unlink()
    print(f"→ uninstalled {label}")


def cmd_start(agent):
    label = label_for(agent)
    plist_path = plist_path_for(agent)
    if not plist_path.exists():
        print(f"error: {label} not installed — run: just service-install {agent}", file=sys.stderr)
        sys.exit(1)
    uid = os.getuid()
    domain_target = f"gui/{uid}/{label}"
    # After service-stop (bootout), the service is unloaded and kickstart alone
    # fails. Re-bootstrap from the plist if needed, then kickstart.
    result = subprocess.run(["launchctl", "print", domain_target], capture_output=True, check=False)
    if result.returncode != 0:
        try:
            subprocess.run(
                ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            msg = e.stderr.strip() if e.stderr else str(e)
            print(f"error: launchctl bootstrap failed: {msg}", file=sys.stderr)
            sys.exit(1)
    launchctl("kickstart", "-k", domain_target)
    print(f"→ started {label}")


def cmd_stop(agent):
    label = label_for(agent)
    result = subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
        capture_output=True, check=False,
    )
    if result.returncode == 0:
        print(f"stopped {label}")
    else:
        print(f"{label} not running (or already stopped)")


def cmd_status(agent):
    label = label_for(agent)
    plist_path = plist_path_for(agent)
    pid = get_pid(label)
    if pid:
        print(f"{label} running (pid={pid})")
    else:
        print(f"{label} not running")
    print(f"  plist: {plist_path}")
    if plist_path.exists():
        print(f"  log:   {Path.cwd()}/logs/{agent}.log")
    else:
        print(f"  (not installed — run: just service-install {agent})")


def cmd_list():
    print("=== Installed pi-agent services ===")
    found = False
    for plist in sorted(LAUNCH_AGENTS.glob(f"{LABEL_PREFIX}*.plist")):
        if not plist.exists():
            continue
        found = True
        label = plist.stem
        agent = label[len(LABEL_PREFIX):]
        pid = get_pid(label)
        if pid:
            print(f"  {agent}: running (pid={pid})")
        else:
            print(f"  {agent}: installed (not running)")
    if not found:
        print("  (none — install one with: just service-install <agent>)")


def main():
    if len(sys.argv) < 2:
        print("usage: service.py {install|uninstall|start|stop|status|list} [agent]", file=sys.stderr)
        sys.exit(2)
    action = sys.argv[1]
    if action == "list":
        return cmd_list()
    if len(sys.argv) < 3:
        print(f"usage: service.py {action} <agent>", file=sys.stderr)
        sys.exit(2)
    agent = sys.argv[2]
    {
        "install":   cmd_install,
        "uninstall": cmd_uninstall,
        "start":     cmd_start,
        "stop":      cmd_stop,
        "status":    cmd_status,
    }[action](agent)


if __name__ == "__main__":
    main()
