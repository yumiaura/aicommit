"""Tests for terminal UI components."""
from __future__ import annotations

import io
import subprocess

from aicommit.ui import (
    _do_commit,
    colored,
    editor,
    print_proposals,
    prompt_suggestion_choice,
    run_suggestion_interactive,
    use_color,
)


def test_colored_respects_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert colored("hello", "\x1b[32m") == "hello"


def test_colored_returns_color_on_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    result = colored("hello", "\x1b[32m")
    assert result.startswith("\x1b[32m")
    assert result.endswith("\x1b[0m")


def test_use_color_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert use_color() is False


def test_editor_returns_fallback():
    parts = editor()
    assert isinstance(parts, list)
    assert len(parts) >= 1


def test_editor_uses_custom(monkeypatch):
    monkeypatch.setenv("EDITOR", "vim")
    assert editor() == ["vim"]


def test_print_proposals_includes_numbers(capsys):
    proposals = ["first message", "second message"]
    print_proposals(proposals)
    out = capsys.readouterr().out
    assert "1." in out
    assert "2." in out
    assert "first message" in out
    assert "second message" in out


def test_prompt_suggestion_choice_enter(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    assert prompt_suggestion_choice(3) == "enter"


def test_prompt_suggestion_choice_digit(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("2\n"))
    assert prompt_suggestion_choice(3) == "2"


def test_prompt_suggestion_choice_q(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("q\n"))
    assert prompt_suggestion_choice(3) == "q"


def test_prompt_suggestion_choice_r(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("r\n"))
    assert prompt_suggestion_choice(3) == "r"


def test_prompt_suggestion_choice_e(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("e\n"))
    assert prompt_suggestion_choice(3) == "e"


def test_run_suggestion_interactive_quit(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("q\n"))
    rc = run_suggestion_interactive(
        ["msg1", "msg2"],
        regenerate=lambda: ["msg3", "msg4"],
    )
    assert rc == 130


def test_run_suggestion_interactive_select_and_commit(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("2\n"))

    committed: list[str] = []

    def fake_commit(msg: str) -> None:
        committed.append(msg)

    monkeypatch.setattr("aicommit.ui.git.commit_with_message", fake_commit)

    rc = run_suggestion_interactive(
        ["msg one", "msg two"],
        regenerate=lambda: ["msg3", "msg4"],
    )
    assert rc == 0
    assert committed == ["msg two"]


def test_run_suggestion_interactive_regenerate(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("r\n2\n"))

    call_count: int = 0

    def fake_regenerate() -> list[str]:
        nonlocal call_count
        call_count += 1
        return ["new A", "new B"]

    committed: list[str] = []

    def fake_commit(msg: str) -> None:
        committed.append(msg)

    monkeypatch.setattr("aicommit.ui.git.commit_with_message", fake_commit)

    rc = run_suggestion_interactive(
        ["old A", "old B"],
        regenerate=fake_regenerate,
    )
    assert rc == 0
    assert call_count == 1
    assert committed == ["new B"]


def test_do_commit_success(monkeypatch):
    monkeypatch.setattr("aicommit.ui.git.commit_with_message", lambda msg: None)
    assert _do_commit("test message") == 0


def test_do_commit_failure(monkeypatch):
    def fail(_msg: str) -> None:
        raise subprocess.CalledProcessError(1, ["git", "commit"])

    monkeypatch.setattr("aicommit.ui.git.commit_with_message", fail)
    assert _do_commit("test message") != 0
