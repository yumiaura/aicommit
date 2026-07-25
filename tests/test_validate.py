"""Tests for Conventional Commit validation."""
from __future__ import annotations

import io

from aicommit import validate as validatemod

# ── validate_message ───────────────────────────────────────────────────


def test_valid_conventional_message():
    r = validatemod.validate_message(
        "feat(auth): add login page\n\n- implements OAuth flow\n"
    )
    assert r.is_valid
    assert r.errors == []


def test_valid_conventional_no_scope():
    r = validatemod.validate_message("fix: handle null pointer")
    assert r.is_valid


def test_valid_conventional_breaking():
    r = validatemod.validate_message("feat!: rewrite public API")
    assert r.is_valid


def test_valid_conventional_breaking_with_scope():
    r = validatemod.validate_message("feat(core)!: rewrite public API")
    assert r.is_valid


def test_invalid_empty_message():
    r = validatemod.validate_message("")
    assert not r.is_valid
    assert any("empty" in e for e in r.errors)


def test_invalid_no_type_prefix():
    r = validatemod.validate_message("add login page")
    assert not r.is_valid
    assert any("format" in e for e in r.errors)


def test_invalid_no_colon():
    r = validatemod.validate_message("feat add login page")
    assert not r.is_valid
    assert any("format" in e for e in r.errors)


def test_invalid_unknown_type():
    r = validatemod.validate_message("wtf: add login page")
    assert not r.is_valid
    assert any("unknown type" in e for e in r.errors)


def test_invalid_trailing_period():
    r = validatemod.validate_message("feat(auth): add login page.")
    assert not r.is_valid
    assert any("period" in e for e in r.errors)


def test_invalid_subject_too_long():
    long_subject = "x" * 73
    r = validatemod.validate_message(f"feat: {long_subject}")
    assert not r.is_valid
    assert any("chars" in e and "max is 72" in e for e in r.errors)


def test_plain_style_accepts_anything():
    r = validatemod.validate_message("some random message", style="plain")
    assert r.is_valid


def test_plain_style_rejects_empty():
    r = validatemod.validate_message("", style="plain")
    assert not r.is_valid
    assert any("empty" in e for e in r.errors)


def test_body_line_too_long():
    body = "x" * 90
    r = validatemod.validate_message(f"feat: add stuff\n\n{body}")
    assert not r.is_valid
    assert any("line 2" in e and "90 chars" in e for e in r.errors)


def test_body_within_length_is_fine():
    body = "x" * 72
    r = validatemod.validate_message(f"feat: add stuff\n\n{body}")
    assert r.is_valid


# ── build_correction_prompt ────────────────────────────────────────────


def test_correction_prompt_includes_diff_and_errors():
    prompt = validatemod.build_correction_prompt(
        "diff --git a/x b/x\n+a\n",
        "add login page",
        ["subject must match format"],
        style="conventional",
    )
    assert "add login page" in prompt
    assert "subject must match format" in prompt
    assert "diff --git" in prompt
    assert "type[(scope)][!]" in prompt


def test_correction_prompt_plain_style():
    prompt = validatemod.build_correction_prompt(
        "diff --git a/x b/x\n+a\n",
        "",
        ["commit message is empty"],
        style="plain",
    )
    assert "commit message is empty" in prompt
    assert "type[(scope)]" not in prompt


# ── Integration: CLI with --validate ───────────────────────────────────


def test_validate_flag_corrects_invalid_message(
    isolated_home, cassette, monkeypatch, capsys,
):
    cassette("commit_validate_correction")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    from aicommit import cli

    rc = cli.main(["--no-stream", "--validate"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "feat(auth)" in out


def test_validate_off_by_default(
    isolated_home, cassette, monkeypatch, capsys,
):
    cassette("commit_simple")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    from aicommit import cli

    rc = cli.main(["--no-stream"])
    out = capsys.readouterr().out
    assert rc == 0
    # Should get whatever the LLM returns without validation
    assert "feat(parser)" in out


def test_validate_flag_passthrough_valid_message(
    isolated_home, cassette, monkeypatch, capsys,
):
    cassette("commit_simple")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/x b/x\n+a\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    from aicommit import cli

    rc = cli.main(["--no-stream", "--validate"])
    out = capsys.readouterr().out
    assert rc == 0
    # commit_simple fixture already returns a valid conventional commit
    assert "feat(parser)" in out
