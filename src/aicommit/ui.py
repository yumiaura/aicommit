"""Terminal UI: proposal rendering + the [Enter/e/r/q] interactive loop."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable

from aicommit import git


class Ansi:
    RESET = "\x1b[0m"
    DIM = "\x1b[2m"
    BOLD = "\x1b[1m"
    GREEN = "\x1b[32m"
    RED = "\x1b[31m"
    YELLOW = "\x1b[33m"
    CYAN = "\x1b[36m"


def use_color() -> bool:
    """Honour NO_COLOR (https://no-color.org) and only colorize on a TTY."""
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def colored(s: str, color: str) -> str:
    if not use_color():
        return s
    return f"{color}{s}{Ansi.RESET}"


STAT_NUMS = re.compile(r"^(?P<head>.+?\|\s*\d+\s*)(?P<marks>[+\-]+)\s*$")


def color_diff_stat(stat: str) -> str:
    """Recolour the `+`/`-` markers in `git diff --stat` output."""
    if not use_color() or not stat:
        return stat
    out = []
    for line in stat.splitlines():
        m = STAT_NUMS.match(line)
        if m:
            plus = colored("+" * m.group("marks").count("+"), Ansi.GREEN)
            minus = colored("-" * m.group("marks").count("-"), Ansi.RED)
            out.append(f"{m.group('head')}{plus}{minus}")
        else:
            out.append(line)
    return "\n".join(out)


def print_diff_stat(stat: str) -> None:
    if not stat.strip():
        return
    bar = "─" * 56
    print(colored(bar, Ansi.DIM))
    print(colored("staged changes:", Ansi.BOLD))
    print(colored(bar, Ansi.DIM))
    print(color_diff_stat(stat.rstrip()))


def editor() -> list[str]:
    """Return the editor invocation (split on whitespace; fallback to `nano`)."""
    name = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    return name.split()


def edit_message(initial: str) -> str:
    """Open `initial` in $EDITOR and return the resulting (stripped) text."""
    fd, path = tempfile.mkstemp(suffix=".COMMIT_EDITMSG", prefix="aicommit-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(initial)
            if not initial.endswith("\n"):
                f.write("\n")
        subprocess.run([*editor(), path], check=False)
        with open(path) as f:
            return f.read().strip()
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def print_proposal(message: str) -> None:
    bar = "─" * 56
    print(colored(bar, Ansi.DIM))
    print(colored("proposed commit message:", Ansi.BOLD))
    print(colored(bar, Ansi.DIM))
    print(message)
    print(colored(bar, Ansi.DIM))


def prompt_choice() -> str:
    """Read a single keystroke-y choice. Empty input == Enter == commit."""
    print()
    print("[ Enter = commit · e = edit · r = regenerate · q = quit ]")
    while True:
        try:
            raw = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"
        if raw == "":
            return "enter"
        if raw in {"e", "r", "q"}:
            return raw
        print(f"unknown choice {raw!r}; expected Enter / e / r / q")


def run_interactive(initial: str, *, regenerate: Callable[[], str]) -> int:
    """Drive the approve/edit/regen/quit loop. Returns a process exit code."""
    message = initial
    while True:
        print_proposal(message)
        choice = prompt_choice()
        if choice == "enter":
            return _do_commit(message)
        if choice == "e":
            new = edit_message(message)
            if not new.strip():
                sys.stderr.write("aborted: empty message\n")
                return 1
            message = new
            continue
        if choice == "r":
            try:
                message = regenerate()
            except Exception as e:  # surfaced from backend
                sys.stderr.write(f"error: {e}\n")
                return 2
            continue
        if choice == "q":
            sys.stderr.write("aborted by user\n")
            return 130


def _do_commit(message: str) -> int:
    try:
        git.commit_with_message(message)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"error: git commit failed (rc={e.returncode})\n")
        return e.returncode or 1
    return 0


# ── Multiple suggestions mode ──────────────────────────────────────────────


def print_proposals(proposals: list[str]) -> None:
    bar = "─" * 56
    print(colored(bar, Ansi.DIM))
    print(colored("proposed commit messages:", Ansi.BOLD))
    print(colored(bar, Ansi.DIM))
    for idx, msg in enumerate(proposals, start=1):
        print(colored(f"{idx}.", Ansi.CYAN))
        print(msg)
        if idx < len(proposals):
            print()
    print(colored(bar, Ansi.DIM))


def prompt_suggestion_choice(count: int) -> str:
    nums = " · ".join(str(i) for i in range(1, count + 1))
    print()
    print(f"[ {nums} = select & commit · e = edit · r = regenerate · q = quit ]")
    while True:
        try:
            raw = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"
        if raw == "":
            return "enter"
        if raw in {str(i) for i in range(1, count + 1)}:
            return raw
        if raw in {"e", "r", "q"}:
            return raw
        print(f"unknown choice {raw!r}")


def prompt_edit_which(count: int) -> int | None:
    try:
        raw = input(f"edit which? [1-{count}] > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if raw in {str(i) for i in range(1, count + 1)}:
        return int(raw) - 1
    return None


def run_suggestion_interactive(
    proposals: list[str],
    *,
    regenerate: Callable[[], list[str]],
) -> int:
    while True:
        print_proposals(proposals)
        choice = prompt_suggestion_choice(len(proposals))
        if choice == "enter":
            return _do_commit(proposals[0])
        if choice in {str(i) for i in range(1, len(proposals) + 1)}:
            return _do_commit(proposals[int(choice) - 1])
        if choice == "e":
            idx = prompt_edit_which(len(proposals))
            if idx is None:
                continue
            new = edit_message(proposals[idx])
            if not new.strip():
                sys.stderr.write("aborted: empty message\n")
                return 1
            proposals[idx] = new
            continue
        if choice == "r":
            try:
                proposals = regenerate()
            except Exception as e:
                sys.stderr.write(f"error: {e}\n")
                return 2
            continue
        if choice == "q":
            sys.stderr.write("aborted by user\n")
            return 130
