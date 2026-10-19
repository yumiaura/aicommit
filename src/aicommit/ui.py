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
    """Only emit ANSI if stdout can interpret it, including legacy PowerShell."""
    # AICOMMIT_GUI_WINDOWS_V1
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.GetStdHandle.restype = ctypes.c_void_p
        handle = kernel.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if not handle:
            return False
        mode = ctypes.c_ulong()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        vt = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        if mode.value & vt:
            return True
        return bool(kernel.SetConsoleMode(handle, mode.value | vt))
    except (OSError, AttributeError, ValueError):
        return False


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
            try:
                git.commit_with_message(message)
            except subprocess.CalledProcessError as e:
                sys.stderr.write(f"error: git commit failed (rc={e.returncode})\n")
                return e.returncode or 1
            return 0
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
