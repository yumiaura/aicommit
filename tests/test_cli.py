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


# ── Suggestions mode ────────────────────────────────────────────────────


def test_suggestions_pipe_mode_falls_back_to_single(
    isolated_home, cassette, monkeypatch, capsys,
):
    """In pipe mode, --suggestions should produce a single message."""
    cassette("commit_simple")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    rc = cli.main(["--no-stream", "--suggestions"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "feat(parser)" in out


def test_suggestions_yes_commits_first(
    isolated_home, cassette, monkeypatch,
):
    """--suggestions --yes should auto-commit the first suggestion."""
    cassette("commit_suggestions")
    monkeypatch.setattr("aicommit.git.staged_diff", lambda: "diff --git a/x b/x\n+a\n")

    committed: list[str] = []
    monkeypatch.setattr("aicommit.git.commit_with_message", lambda msg: committed.append(msg))

    fake_stdin = io.StringIO("")
    fake_stdin.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_stdin)

    rc = cli.main(["--yes", "--suggestions"])
    assert rc == 0
    assert len(committed) == 1
    assert "authentication middleware" in committed[0]


def test_suggestions_interactive_select_first(
    isolated_home, cassette, monkeypatch,
):
    """Select first suggestion in interactive mode."""
    cassette("commit_suggestions")
    monkeypatch.setattr("aicommit.git.staged_diff", lambda: "diff --git a/x b/x\n+a\n")

    committed: list[str] = []
    monkeypatch.setattr("aicommit.git.commit_with_message", lambda msg: committed.append(msg))

    fake_stdin = io.StringIO("1\n")
    fake_stdin.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_stdin)

    rc = cli.main(["--suggestions"])
    assert rc == 0
    assert len(committed) == 1
    assert "authentication middleware" in committed[0]
