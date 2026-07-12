import subprocess
import sys
from types import SimpleNamespace

import pytest

from aicommit.clipboard import ClipboardError, copy_to_clipboard


def test_copy_to_clipboard_uses_pbcopy_on_macos(monkeypatch):
    calls = []

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}" if name == "pbcopy" else None)

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs["input"]))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    tool = copy_to_clipboard("feat: add copy mode")

    assert tool == "pbcopy"
    assert calls == [(["pbcopy"], "feat: add copy mode")]


def test_copy_to_clipboard_uses_wl_copy_on_linux(monkeypatch):
    calls = []

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}" if name == "wl-copy" else None)

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs["input"]))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    tool = copy_to_clipboard("fix: handle staged diff")

    assert tool == "wl-copy"
    assert calls == [(["wl-copy"], "fix: handle staged diff")]


def test_copy_to_clipboard_raises_when_no_tool_exists(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(ClipboardError, match="no supported clipboard command"):
        copy_to_clipboard("docs: update readme")


def test_copy_to_clipboard_raises_on_command_failure(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}" if name == "xclip" else None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stderr="display not found"),
    )

    with pytest.raises(ClipboardError, match="display not found"):
        copy_to_clipboard("chore: test clipboard failure")
