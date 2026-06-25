#!/usr/bin/env python3
"""
Manage a pi agent as a Linux systemd service.

Subcommands:
    install <agent>     Generate the systemd unit, install it, enable + start.
    uninstall <agent>   Stop, disable, and remove the unit.
    start <agent>       Start (or restart) the service.
    stop <agent>        Stop the service.
    status <agent>      Print whether the service is active, plus unit/log paths.
    list                Print all installed pi-agent services and their status.

Modes:
    --system            System-wide unit at /etc/systemd/system/. The unit's
                        `User=` is set to the sudo invoker (NOT literal root),
                        so the service runs with normal user privileges. Requires
                        `sudo` to install.
    --user              Per-user unit at ~/.config/systemd/user/. Runs as the
                        calling user. No sudo needed. Auto-enables linger via
                        `loginctl enable-linger` so the service survives logout
                        and starts on boot.

    If neither is passed, mode is auto-detected:
        - EUID=0 with $SUDO_USER set → system mode (target = $SUDO_USER)
        - else → user mode (target = $USER / $LOGNAME / `id -un`)

    Override with --system / --user when auto-detect is wrong.

Run from the repo root so $(pwd) is the repo path embedded in the unit.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

UNIT_PREFIX = "pi-agent-"
WRAPPER_REL = "scripts/launch-agent-systemd.sh"
REPO_NAME = "pi_agents"  # used for fallback repo path resolution under target user's home

# Unit file templates. Paths are quoted to handle spaces in repo locations.
UNIT_TEMPLATE_SYSTEM = """\
[Unit]
Description=Pi agent: {agent}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User="{user}"
Group="{group}"
WorkingDirectory="{repo}/agents/{agent}"
ExecStart={wrapper} {agent}
Restart=always
RestartSec=10
StandardOutput=append:"{repo}/logs/{agent}.out.log"
StandardError=append:"{repo}/logs/{agent}.err.log"

[Install]
WantedBy=multi-user.target
"""

UNIT_TEMPLATE_USER = """\
[Unit]
Description=Pi agent: {agent}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory="{repo}/agents/{agent}"
ExecStart={wrapper} {agent}
Restart=always
RestartSec=10
StandardOutput=append:"{repo}/logs/{agent}.out.log"
StandardError=append:"{repo}/logs/{agent}.err.log"

[Install]
WantedBy=default.target
"""


# ── arg parsing ────────────────────────────────────────────────────────────

def parse_args(argv):
    """Return (action, mode_flag, agent). mode_flag is 'system'|'user'|None."""
    if len(argv) < 2:
        return None, None, None
    action = argv[1]
    if action in ("-h", "--help", "help"):
        return action, None, None

    mode = None
    agent = None
    for a in argv[2:]:
        if a == "--system":
            mode = "system"
        elif a == "--user":
            mode = "user"
        elif a.startswith("-"):
            print(f"error: unknown flag {a!r}", file=sys.stderr)
            sys.exit(2)
        else:
            agent = a
            break
    return action, mode, agent


# ── mode + user detection ─────────────────────────────────────────────────

def detect_mode_and_user():
    """Return (mode, target_user). mode is 'system' or 'user'."""
    euid = os.geteuid()
    sudo_user = os.environ.get("SUDO_USER", "")
    if euid == 0 and sudo_user:
        return "system", sudo_user
    # Fall back to $USER / $LOGNAME / `id -un`
    user = os.environ.get("USER") or os.environ.get("LOGNAME")
    if not user:
        try:
            user = subprocess.check_output(["id", "-un"], text=True).strip()
        except subprocess.CalledProcessError:
            user = "nobody"
    return "user", user


def get_user_identity(user):
    """Return (home_dir, group) for `user`, or (None, None) if not found."""
    try:
        out = subprocess.check_output(["getent", "passwd", user], text=True)
        parts = out.strip().split(":")
        home = parts[5] if len(parts) >= 6 else None
    except (subprocess.CalledProcessError, IndexError, FileNotFoundError):
        home = None
    try:
        group = subprocess.check_output(["id", "-gn", user], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        group = user  # best-effort fallback
    return home, group


# ── paths ─────────────────────────────────────────────────────────────────

def unit_dir_for(mode, user):
    if mode == "system":
        return Path("/etc/systemd/system")
    home, _ = get_user_identity(user)
    return (Path(home) if home else Path.home()) / ".config" / "systemd" / "user"


def systemctl_cmd(mode):
    return ["systemctl"] if mode == "system" else ["systemctl", "--user"]


def label_for(agent):
    return f"{UNIT_PREFIX}{agent}"


def unit_path_for(mode, user, agent):
    return unit_dir_for(mode, user) / f"{label_for(agent)}.service"


# ── systemctl wrappers ─────────────────────────────────────────────────────

def systemctl(*args, mode, check=True):
    return subprocess.run(
        [*systemctl_cmd(mode), *args],
        capture_output=True, text=True, check=check,
    )


def get_active_state(mode, agent):
    label = label_for(agent)
    result = subprocess.run(
        [*systemctl_cmd(mode), "is-active", label],
        capture_output=True, text=True, check=False,
    )
    state = result.stdout.strip()
    return state if state else None


# ── subcommands ────────────────────────────────────────────────────────────

def cmd_install(agent, mode, target_user):
    repo = Path.cwd().resolve()

    if not re.fullmatch(r"[A-Za-z0-9._-]+", agent):
        print(f"error: invalid agent name {agent!r} — allowed: letters, digits, ., _, -", file=sys.stderr)
        sys.exit(1)
    agent_dir = repo / "agents" / agent
    if not agent_dir.is_dir():
        print(f"error: agent directory not found: {agent_dir}", file=sys.stderr)
        print(f"  create it first with: just new-agent {agent}", file=sys.stderr)
        sys.exit(1)

    wrapper = repo / WRAPPER_REL
    if not wrapper.exists():
        print(f"error: wrapper not found at {wrapper}", file=sys.stderr)
        sys.exit(1)
    if not os.access(wrapper, os.X_OK):
        print(f"error: wrapper not executable: {wrapper}", file=sys.stderr)
        sys.exit(1)

    # Mode-specific preconditions
    if mode == "system":
        if os.geteuid() != 0:
            print("error: --system mode requires root (run with sudo)", file=sys.stderr)
            sys.exit(1)
        if not os.environ.get("SUDO_USER"):
            print("error: --system mode requires sudo (no SUDO_USER set)", file=sys.stderr)
            print("  refusing to run as literal root — invoke via `sudo -E <cmd> install <agent>`", file=sys.stderr)
            sys.exit(1)

    target_home, target_group = get_user_identity(target_user)
    if not target_home:
        print(f"error: cannot determine home dir for user {target_user!r}", file=sys.stderr)
        sys.exit(1)

    label = label_for(agent)
    unit_path = unit_path_for(mode, target_user, agent)
    if unit_path.exists():
        print(f"→ {label} already installed at {unit_path}", file=sys.stderr)
        print(f"  to re-install: just service-uninstall {agent} && just service-install {agent}", file=sys.stderr)
        sys.exit(1)

    # Ensure logs dir exists and is writable by the target user.
    logs_dir = repo / "logs"
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True)
        if mode == "system":
            subprocess.run(
                ["chown", f"{target_user}:{target_group}", str(logs_dir)],
                check=True,
            )

    # Generate unit content
    template = UNIT_TEMPLATE_SYSTEM if mode == "system" else UNIT_TEMPLATE_USER
    unit_dir = unit_path.parent
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(template.format(
        agent=agent,
        user=target_user,
        group=target_group,
        repo=str(repo),
        wrapper=str(wrapper),
    ))

    # In system mode, ensure the unit file is owned by root (it is by default,
    # since we are root), and the wrapper + logs are owned by the target user
    # (so the running service can write).
    if mode == "system":
        subprocess.run(["chown", "-R", f"{target_user}:{target_group}", str(logs_dir)], check=False)

    # Enable linger in user mode so the service survives logout / starts on boot.
    if mode == "user":
        try:
            subprocess.run(
                ["loginctl", "enable-linger", target_user],
                check=False, capture_output=True,
            )
        except FileNotFoundError:
            pass  # loginctl not available (e.g., containerized)

    # daemon-reload, enable, start
    try:
        systemctl("daemon-reload", mode=mode, check=True)
    except subprocess.CalledProcessError as e:
        unit_path.unlink()
        msg = e.stderr.strip() if e.stderr else str(e)
        print(f"error: systemctl daemon-reload failed: {msg}", file=sys.stderr)
        sys.exit(1)

    try:
        systemctl("enable", label, mode=mode, check=True)
    except subprocess.CalledProcessError as e:
        unit_path.unlink()
        msg = e.stderr.strip() if e.stderr else str(e)
        print(f"error: systemctl enable failed: {msg}", file=sys.stderr)
        sys.exit(1)

    # Start may fail if pi is missing on PATH; we leave the unit in place so the
    # user can investigate via `journalctl` / `service-status` rather than silently
    # loop. daemon-reload + enable already succeeded.
    start_result = systemctl("start", label, mode=mode, check=False)
    if start_result.returncode != 0:
        msg = (start_result.stderr or start_result.stdout).strip()
        print(f"warning: systemctl start returned non-zero: {msg}", file=sys.stderr)
        print(f"  unit left installed — inspect with: just service-status {agent}", file=sys.stderr)

    print(f"→ installed and started {label} ({mode} mode, as user {target_user})")
    print(f"  unit:   {unit_path}")
    print(f"  repo:   {repo}")
    print(f"  out:    {repo}/logs/{agent}.out.log")
    print(f"  err:    {repo}/logs/{agent}.err.log")
    print(f"  status: just service-status {agent}")
    print(f"  stop:   just service-stop {agent}    uninstall: just service-uninstall {agent}")


def cmd_uninstall(agent, mode, target_user):
    label = label_for(agent)
    unit_path = unit_path_for(mode, target_user, agent)
    if not unit_path.exists():
        print(f"{label} not installed ({mode} mode)")
        return
    systemctl("stop", label, mode=mode, check=False)
    systemctl("disable", label, mode=mode, check=False)
    unit_path.unlink()
    systemctl("daemon-reload", mode=mode, check=False)
    print(f"→ uninstalled {label} ({mode} mode)")


def cmd_start(agent, mode, target_user):
    label = label_for(agent)
    unit_path = unit_path_for(mode, target_user, agent)
    if not unit_path.exists():
        print(f"error: {label} not installed ({mode} mode) — run: just service-install {agent}", file=sys.stderr)
        sys.exit(1)
    result = systemctl("start", label, mode=mode, check=False)
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip()
        print(f"error: systemctl start failed: {msg}", file=sys.stderr)
        sys.exit(1)
    print(f"→ started {label}")


def cmd_stop(agent, mode, target_user):
    label = label_for(agent)
    result = systemctl("stop", label, mode=mode, check=False)
    if result.returncode == 0:
        print(f"stopped {label}")
    else:
        print(f"{label} not running (or already stopped)")


def cmd_status(agent, mode, target_user):
    label = label_for(agent)
    unit_path = unit_path_for(mode, target_user, agent)
    state = get_active_state(mode, agent) or "unknown"
    print(f"{label}: {state} ({mode} mode, as {target_user})")
    print(f"  unit: {unit_path}")
    if unit_path.exists():
        repo = Path.cwd()
        print(f"  out:  {repo}/logs/{agent}.out.log")
        print(f"  err:  {repo}/logs/{agent}.err.log")
    else:
        print(f"  (not installed — run: just service-install {agent})")


def cmd_list(mode, target_user):
    print(f"=== Installed pi-agent services ({mode} mode) ===")
    unit_dir = unit_dir_for(mode, target_user)
    found = False
    if unit_dir.is_dir():
        for unit in sorted(unit_dir.glob(f"{UNIT_PREFIX}*.service")):
            if not unit.exists():
                continue
            found = True
            label = unit.stem
            agent = label[len(UNIT_PREFIX):]
            state = get_active_state(mode, agent) or "unknown"
            print(f"  {agent}: {state}")
    if not found:
        print("  (none — install one with: just service-install <agent>)")


# ── main ───────────────────────────────────────────────────────────────────

def main():
    action, mode_flag, agent = parse_args(sys.argv)
    if action in (None, "-h", "--help", "help"):
        print(__doc__, file=sys.stderr)
        sys.exit(0 if action else 2)

    # Resolve mode + target user. `--system` / `--user` override auto-detect.
    if mode_flag == "system":
        if not os.environ.get("SUDO_USER"):
            print("error: --system requires sudo (SUDO_USER not set)", file=sys.stderr)
            sys.exit(1)
        mode, target_user = "system", os.environ["SUDO_USER"]
    elif mode_flag == "user":
        mode, target_user = "user", os.environ.get("USER") or os.environ.get("LOGNAME")
    else:
        mode, target_user = detect_mode_and_user()

    if action == "list":
        return cmd_list(mode, target_user)

    if agent is None:
        print(f"usage: service-systemd.py {action} [opts] <agent>", file=sys.stderr)
        sys.exit(2)

    {
        "install":   cmd_install,
        "uninstall": cmd_uninstall,
        "start":     cmd_start,
        "stop":      cmd_stop,
        "status":    cmd_status,
    }[action](agent, mode, target_user)


if __name__ == "__main__":
    main()
