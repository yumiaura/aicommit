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


def test_cli_handles_generation_errors(isolated_home, monkeypatch, capsys):
    import io

    from aicommit.llm import OllamaError

    # Mock stdin
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    # Mock backend to raise OllamaError during generate
    class FakeErrorBackend:
        def generate(self, *args, **kwargs):
            raise OllamaError("simulated runtime error")

    monkeypatch.setattr("aicommit.cli.make_backend", lambda *a, **k: FakeErrorBackend())

    with pytest.raises(SystemExit) as ei:
        cli.main(["--no-stream"])
    assert ei.value.code == 2
    err = capsys.readouterr().err
    assert "error: simulated runtime error" in err
