#!/usr/bin/env python3
"""Claude Task Manager — terminal dashboard for monitoring vimwiki task files."""

import argparse
import os
import re
import select
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ANSI colours
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

COMPLETION_WORDS = ("done", "complete", "finished")
BLOCKED_WORDS = ("waiting for", "waiting on", "blocked", "needs review", "paused", "stuck")
HOOK_ATTENTION_STATUSES = ("permissionrequest", "posttoolusefailure", "stop", "sessionend")


@dataclass
class TaskState:
    filepath: str = ""
    name: str = "?"
    status: str = "?"
    tmux_window: Optional[str] = None
    last_updated: Optional[datetime] = None
    progress_done: int = 0
    progress_total: int = 0
    is_stale: bool = False
    is_blocked: bool = False
    is_completed: bool = False
    has_active_process: bool = False
    tmux_window_exists: bool = False
    alert_reasons: list[str] = field(default_factory=list)


def parse_timestamp(raw: str) -> Optional[datetime]:
    """Parse timestamps like 'Saturday 14th February 19:30:55' or 'Saturday 14 February 2026 19:30:55'."""
    raw = raw.strip()
    if not raw or raw.startswith("[") or len(raw) < 10:
        return None
    cleaned = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", raw)
    for fmt in ("%A %d %B %Y %H:%M:%S", "%A %d %B %H:%M:%S"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            break
        except ValueError:
            continue
    else:
        return None
    if "%Y" not in fmt:
        now = datetime.now()
        dt = dt.replace(year=now.year)
        if dt > now:
            dt = dt.replace(year=now.year - 1)
    return dt


def parse_wiki_file(filepath: str) -> TaskState:
    """Parse a .wiki file into a TaskState."""
    task = TaskState(filepath=filepath)
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return task
    lines = text.splitlines()
    for line in lines:
        m = re.match(r"^# Task Name:\s*(.+)", line)
        if m:
            task.name = m.group(1).strip()
            break
    for line in lines:
        m = re.match(r"\*\*Status\*\*:\s*(.+)", line)
        if m:
            task.status = m.group(1).strip()
            break
    for line in lines:
        m = re.match(r"\*\*Tmux Window\*\*:\s*(\d+)", line)
        if m:
            task.tmux_window = m.group(1)
            break
    for line in lines:
        m = re.match(r"\*\*Last Updated Date/Time\*\*:\s*(.+)", line)
        if m:
            task.last_updated = parse_timestamp(m.group(1))
            break
    for line in lines:
        if re.match(r"- \[[xXoO ]\]", line):
            task.progress_total += 1
        if re.match(r"- \[[xX]\]", line):
            task.progress_done += 1
    return task


def get_tmux_windows() -> list[str]:
    """Return list of 'session:index' strings from tmux."""
    try:
        out = subprocess.run(
            ["tmux", "list-windows", "-a", "-F", "#{session_name}:#{window_index}"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip().splitlines() if out.returncode == 0 else []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def get_process_list() -> str:
    """Get the full process list (run once per refresh cycle)."""
    try:
        out = subprocess.run(
            ["ps", "axww", "-o", "pid,command"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout if out.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def check_process_in_list(filepath: str, ps_output: str) -> bool:
    """Check if a Claude process for the given task file appears in ps output."""
    own_pid = str(os.getpid())
    for line in ps_output.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == own_pid:
            continue
        if "claude" in line.lower() and filepath in line:
            return True
    return False


def switch_tmux_window(window: str, windows: list[str]) -> bool:
    """Switch to the tmux window matching the given number."""
    for entry in windows:
        if entry.endswith(f":{window}"):
            try:
                subprocess.run(
                    ["tmux", "select-window", "-t", entry],
                    capture_output=True, timeout=5,
                )
                return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False
    return False


def _escape_applescript(s: str) -> str:
    """Escape a string for embedding in AppleScript double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def send_notification(title: str, subtitle: str, message: str) -> None:
    """Send a macOS desktop notification via osascript."""
    script = (
        f'display notification "{_escape_applescript(message)}" '
        f'with title "{_escape_applescript(title)}" '
        f'subtitle "{_escape_applescript(subtitle)}"'
    )
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def classify_alerts(
    task: TaskState, stale_minutes: int, tmux_windows: list[str],
    ps_output: str,
) -> None:
    """Populate alert_reasons, is_stale, is_blocked, is_completed, etc."""
    task.alert_reasons.clear()
    status_low = task.status.lower()
    task.is_completed = any(w in status_low for w in COMPLETION_WORDS)
    task.is_blocked = (
        any(w in status_low for w in BLOCKED_WORDS)
        or status_low in HOOK_ATTENTION_STATUSES
    )
    # Tmux checks
    if task.tmux_window is not None:
        task.tmux_window_exists = any(
            e.endswith(f":{task.tmux_window}") for e in tmux_windows
        )
    # Process check
    task.has_active_process = check_process_in_list(task.filepath, ps_output)
    # Alerts in priority order
    if task.is_blocked:
        task.alert_reasons.append(f"NEEDS ATTENTION (status: {task.status})")
    if not task.has_active_process and not task.is_completed:
        task.alert_reasons.append("NOT RUNNING")
    if task.last_updated is not None:
        age = (datetime.now() - task.last_updated).total_seconds()
        if age > stale_minutes * 60:
            task.is_stale = True
            mins = int(age // 60)
            task.alert_reasons.append(f"STALE ({mins}m since last update)")
    elif task.last_updated is None and task.status != "?":
        task.is_stale = False  # unknown, don't flag
    if task.is_completed:
        task.alert_reasons.append("COMPLETED")


def format_age(dt: Optional[datetime]) -> str:
    """Format a datetime as a relative age string."""
    if dt is None:
        return "?"
    secs = int((datetime.now() - dt).total_seconds())
    if secs < 0:
        return "future?"
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    return f"{hours}h {mins % 60}m ago"


def alert_colour(reasons: list[str]) -> str:
    """Return the ANSI colour for the highest-priority alert."""
    text = " ".join(reasons).lower()
    if "needs attention" in text or "not running" in text:
        return RED
    if "stale" in text:
        return YELLOW
    if "completed" in text:
        return CYAN
    return GREEN


def render_dashboard(
    tasks: list[TaskState], interval: int, in_tmux: bool
) -> None:
    """Clear screen and render the full dashboard."""
    sys.stdout.write("\033[2J\033[H")  # clear + home
    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"{BOLD}=== Claude Task Manager === {now_str} (every {interval}s){RESET}\n")
    if not tasks:
        print(f"  {DIM}No active tasks in wip/{RESET}\n")
    else:
        hdr = f"  {'#':>3}  {'TASK':<34}  {'STATUS':<16}  {'UPDATED':<12}  AGENT"
        print(f"{BOLD}{hdr}{RESET}")
        print(f"  {'─'*3}  {'─'*34}  {'─'*16}  {'─'*12}  {'─'*18}")
        for i, t in enumerate(tasks, 1):
            prog = f"[{t.progress_done}/{t.progress_total}]" if t.progress_total else ""
            age = format_age(t.last_updated)
            col = alert_colour(t.alert_reasons)
            agent = "RUNNING" if t.has_active_process else "STOPPED"
            win = f" (win {t.tmux_window})" if t.tmux_window else ""
            name = t.name[:31] + "..." if len(t.name) > 34 else t.name
            status = t.status[:13] + "..." if len(t.status) > 16 else t.status
            print(f"  {col}{i:>3}  {name:<34}  {status:<16}  {age:<12}  "
                  f"{agent}{win} {prog}{RESET}")
        # Alerts section
        alerts = [(i, t, r) for i, t in enumerate(tasks, 1)
                  for r in t.alert_reasons if "COMPLETED" not in r]
        if alerts:
            print(f"\n{BOLD}Alerts:{RESET}")
            for idx, t, reason in alerts:
                col = RED if ("ATTENTION" in reason or "NOT RUNNING" in reason) else YELLOW
                print(f"  {col}! #{idx} {t.name} — {reason}{RESET}")
    tmux_hint = "  [1-N] switch to window" if in_tmux else ""
    print(f"\n{DIM}[r]efresh{tmux_hint}  [q]uit{RESET}")
    sys.stdout.write("> ")
    sys.stdout.flush()


def scan_tasks(wiki_path: str, stale_minutes: int) -> list[TaskState]:
    """Scan wip/ directory and return classified TaskStates."""
    wip_dir = os.path.join(os.path.expanduser(wiki_path), "wip")
    tasks: list[TaskState] = []
    if not os.path.isdir(wip_dir):
        return tasks
    tmux_windows = get_tmux_windows()
    ps_output = get_process_list()
    for fname in sorted(os.listdir(wip_dir)):
        if not fname.endswith(".wiki"):
            continue
        fpath = os.path.join(wip_dir, fname)
        if not os.path.isfile(fpath):
            continue
        task = parse_wiki_file(fpath)
        classify_alerts(task, stale_minutes, tmux_windows, ps_output)
        tasks.append(task)
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Task Manager dashboard")
    parser.add_argument("--wiki-path", default="~/vimwiki", help="Path to vimwiki root")
    parser.add_argument("--interval", type=int, default=30, help="Refresh interval (s)")
    parser.add_argument("--stale-minutes", type=int, default=10, help="Stale threshold")
    parser.add_argument("--no-notifications", action="store_true", help="Disable alerts")
    args = parser.parse_args()

    in_tmux = bool(os.environ.get("TMUX"))
    if not in_tmux:
        sys.stderr.write(f"{YELLOW}Warning: not inside tmux — window switching disabled{RESET}\n")

    if not sys.stdin.isatty():
        sys.stderr.write("Error: claude_manager requires an interactive terminal.\n")
        sys.exit(1)

    notified: set[tuple[str, str]] = set()
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            tasks = scan_tasks(args.wiki_path, args.stale_minutes)
            # Desktop notifications
            if not args.no_notifications:
                current_alerts: set[tuple[str, str]] = set()
                for t in tasks:
                    for r in t.alert_reasons:
                        key = (t.filepath, r.split("(")[0].strip())
                        current_alerts.add(key)
                        if key not in notified and ("ATTENTION" in r or "NOT RUNNING" in r):
                            send_notification("Claude Task Manager", t.name, r)
                            notified.add(key)
                notified &= current_alerts  # clear resolved
            render_dashboard(tasks, args.interval, in_tmux)
            ready, _, _ = select.select([sys.stdin], [], [], args.interval)
            if ready:
                ch = sys.stdin.read(1)
                if ch == "q":
                    break
                elif ch == "r":
                    continue
                elif ch.isdigit() and in_tmux:
                    idx = int(ch) - 1
                    if 0 <= idx < len(tasks) and tasks[idx].tmux_window:
                        windows = get_tmux_windows()
                        switch_tmux_window(tasks[idx].tmux_window, windows)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except Exception:
            pass
        print(f"\n{DIM}Goodbye.{RESET}")


if __name__ == "__main__":
    main()
