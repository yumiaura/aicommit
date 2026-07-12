import io

import pytest

from aicommit import cli


def test_print_mode_emits_message(isolated_home, cassette, monkeypatch, capsys):
    cassette("commit_simple")
    # Simulate piped stdin with a diff
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    rc = cli.main(["--no-stream"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "feat(parser)" in out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as ei:
        cli.main(["--version"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "aicommit" in out


def test_no_diff_returns_1(isolated_home, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    rc = cli.main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "no staged changes" in err


def test_review_only_clean(isolated_home, cassette, monkeypatch, capsys):
    cassette("review_clean")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    rc = cli.main(["--review-only"])
    assert rc == 0


def test_review_only_with_findings_exits_1(isolated_home, cassette, monkeypatch, capsys):
    cassette("review_findings")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    rc = cli.main(["--review-only"])
    assert rc == 1


def test_copy_mode_emits_and_copies_message(isolated_home, cassette, monkeypatch, capsys):
    cassette("commit_simple")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    copied: dict[str, str] = {}

    def fake_copy(text: str) -> str:
        copied["text"] = text
        return "test-clipboard"

    monkeypatch.setattr("aicommit.clipboard.copy_to_clipboard", fake_copy)

    rc = cli.main(["--copy", "--no-stream"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "feat(parser)" in captured.out
    assert "feat(parser)" in copied["text"]
    assert "copied commit message to clipboard via test-clipboard" in captured.err


def test_copy_mode_reports_clipboard_failure(isolated_home, cassette, monkeypatch, capsys):
    cassette("commit_simple")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    def fail_copy(_: str) -> str:
        from aicommit.clipboard import ClipboardError

        raise ClipboardError("no clipboard command found")

    monkeypatch.setattr("aicommit.clipboard.copy_to_clipboard", fail_copy)

    rc = cli.main(["--copy", "--no-stream"])
    err = capsys.readouterr().err

    assert rc == 3
    assert "could not copy to clipboard" in err
