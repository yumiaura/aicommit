"""Small cross-platform clipboard helper for generated commit messages."""
from __future__ import annotations

import shutil
import subprocess
import sys


class ClipboardError(RuntimeError):
    """Raised when no supported clipboard command is available or copy fails."""


def _clipboard_command() -> list[str] | None:
    if sys.platform == "darwin":
        return ["pbcopy"] if shutil.which("pbcopy") else None
    if sys.platform.startswith("win"):
        return ["clip"] if shutil.which("clip") else None

    candidates = [
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            return cmd
    return None


def copy_to_clipboard(text: str) -> str:
    """Copy text to the system clipboard and return the command used."""
    cmd = _clipboard_command()
    if cmd is None:
        raise ClipboardError(
            "no supported clipboard command found "
            "(install pbcopy, clip, wl-copy, xclip, or xsel)"
        )

    try:
        proc = subprocess.run(
            cmd,
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as e:
        raise ClipboardError(f"failed to run {cmd[0]}: {e}") from e

    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"{cmd[0]} exited with {proc.returncode}"
        raise ClipboardError(detail)
    return cmd[0]
