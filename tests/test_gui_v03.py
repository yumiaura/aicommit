"""V0.3 safety checks — all tests use isolated temporary local Git repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aicommit.gui_core import GitWorkspace, WorkspaceError
from aicommit.gui_v03_core import (
    apply_proposal,
    localized_analysis_prompt,
    parse_proposal,
    proposal_prompt,
    read_python_target,
    remote_readonly,
)


def git(root: Path, *args: str) -> str:
    cmd = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return cmd.stdout.strip()


@pytest.fixture
def ws(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "QA")
    git(tmp_path, "config", "user.email", "qa@example.invalid")
    (tmp_path / "cash.py").write_text(
        "def change(total, paid):\n    return paid - total\n", encoding="utf-8"
    )
    git(tmp_path, "add", "cash.py")
    git(tmp_path, "commit", "-m", "base")
    (tmp_path / "cash.py").write_text(
        'def change(total, paid):\n    if paid < total:\n        raise ValueError("insufficient")\n    return paid - total\n',
        encoding="utf-8",
    )
    git(tmp_path, "add", "cash.py")
    return GitWorkspace(tmp_path)


def model_code(proposed: str) -> str:
    return "Proposed improvement.\n===BEGIN_CODE===\n" + proposed + "\n===END_CODE==="


def test_default_local_readonly_no_git_mutation(ws):
    before = ws.git("rev-parse", "HEAD")
    status = ws.git("status", "--porcelain=v1")
    info = remote_readonly(ws)
    assert info["remote_head"] == "not checked"
    assert info["head"] == before
    assert ws.git("status", "--porcelain=v1") == status


def test_plan_language_and_truth_rules(ws):
    diff = ws.staged_diff()
    en = localized_analysis_prompt(
        ws, diff, path="cash.py", intent="", language="en", action="plan"
    )
    es = localized_analysis_prompt(
        ws, diff, path="cash.py", intent="", language="es", action="risks"
    )
    assert "Respond in English" in en
    assert "Respond in Spanish" in es
    assert "never repeat an implemented feature" in en.lower()
    assert "tests as passed" in en
    assert "return paid - total" in en


def test_prompt_file_and_explicit_code_markers(ws):
    before, digest = read_python_target(ws, "cash.py")
    prompt = proposal_prompt(ws, "cash.py", before, intent="make safer", language="en")
    assert "COMPLETE proposed Python file" in prompt
    assert "===BEGIN_CODE===" in prompt
    assert len(digest) == 64


def test_proposal_requires_single_markers(ws):
    before, digest = read_python_target(ws, "cash.py")
    with pytest.raises(WorkspaceError):
        parse_proposal("replace whole file", "cash.py", before, digest)
    with pytest.raises(WorkspaceError):
        parse_proposal(model_code("def bad(: pass"), "cash.py", before, digest)
    with pytest.raises(WorkspaceError):
        parse_proposal(model_code(before), "cash.py", before, digest)
    with pytest.raises(WorkspaceError):
        parse_proposal(model_code("```python\nx = 1\n```"), "cash.py", before, digest)


def test_proposal_preview_is_unified_diff(ws):
    before, digest = read_python_target(ws, "cash.py")
    after = before + "\ndef help_customer():\n    return True\n"
    p = parse_proposal(model_code(after), "cash.py", before, digest)
    assert "--- CURRENT/cash.py" in p.preview
    assert "+++ PROPOSED/cash.py" in p.preview
    assert "+def help_customer" in p.preview
    assert "help_customer" not in (ws.root / "cash.py").read_text()


def test_requires_approval(ws):
    before, digest = read_python_target(ws, "cash.py")
    p = parse_proposal(model_code(before + "\nnew = 1\n"), "cash.py", before, digest)
    with pytest.raises(WorkspaceError, match="approval"):
        apply_proposal(ws, p, approved=False)
    assert "new = 1" not in (ws.root / "cash.py").read_text()


def test_approval_writes_local_only_and_preserves_stage(ws):
    before, digest = read_python_target(ws, "cash.py")
    original_bytes = (ws.root / "cash.py").read_bytes()
    p = parse_proposal(model_code(before + "\nnew = 1\n"), "cash.py", before, digest)
    old_staged = ws.staged_diff()
    old_head = ws.git("rev-parse", "HEAD")
    backup = apply_proposal(ws, p, approved=True)
    assert backup.exists() and backup.read_bytes() == original_bytes
    assert "new = 1" in (ws.root / "cash.py").read_text()
    assert ws.staged_diff() == old_staged
    assert ws.git("rev-parse", "HEAD") == old_head
    assert ws.git("remote", "-v", allow_failure=True) == ""
    assert ws.file_diff("cash.py")[1]  # worktree changed; no stage or commit


def test_windows_crlf_backup_preserves_exact_bytes(ws):
    """A CRLF file must be restored byte-for-byte, not compared via read_text()."""
    source = ws.root / "cash.py"
    crlf = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    source.write_bytes(crlf)
    git(ws.root, "add", "cash.py")
    before, digest = read_python_target(ws, "cash.py")
    proposal = parse_proposal(model_code(before + "\nverified = True\n"), "cash.py", before, digest)
    backup = apply_proposal(ws, proposal, approved=True)
    assert backup.read_bytes() == crlf
    assert b"verified = True" in source.read_bytes()


def test_changed_file_rejects_stale_proposal(ws):
    before, digest = read_python_target(ws, "cash.py")
    p = parse_proposal(model_code(before + "\nnew = 1\n"), "cash.py", before, digest)
    (ws.root / "cash.py").write_text(before + "\nexternal = 1\n")
    with pytest.raises(WorkspaceError, match="changed"):
        apply_proposal(ws, p, approved=True)
    assert "new = 1" not in (ws.root / "cash.py").read_text()


def test_pre_existing_unstaged_changes_rejected(ws):
    before, digest = read_python_target(ws, "cash.py")
    p = parse_proposal(model_code(before + "\nnew = 1\n"), "cash.py", before, digest)
    (ws.root / "cash.py").write_text(before + "\nmanual = 1\n")
    with pytest.raises(WorkspaceError):
        apply_proposal(ws, p, approved=True)


def test_oversize_python_refused(ws):
    (ws.root / "cash.py").write_text("x=1\n" * 4000)
    with pytest.raises(WorkspaceError, match="too large"):
        read_python_target(ws, "cash.py")


def test_secret_content_never_enters_prompt(ws):
    (ws.root / "cash.py").write_text('password = "dangerously_secret_value"\n')
    with pytest.raises(WorkspaceError, match="credencial"):
        read_python_target(ws, "cash.py")


def test_symlinks_rejected(ws, tmp_path):
    dest = tmp_path / "outside.py"
    dest.write_text("print(42)")
    alias = ws.root / "linked.py"
    try:
        alias.symlink_to(dest)
    except OSError:
        pytest.skip("Symlinks require privileges on Windows")
    git(ws.root, "add", "linked.py")
    with pytest.raises(WorkspaceError):
        read_python_target(ws, "linked.py")


def test_origin_rejects_unsupported_remote_url_before_network(ws):
    git(ws.root, "remote", "add", "origin", "https://evil.example.com/owner/repo")
    with pytest.raises(WorkspaceError, match="GitHub"):
        remote_readonly(ws, online=True)
    assert ws.git("rev-parse", "HEAD")


def test_python_only(ws):
    (ws.root / "notes.txt").write_text("text")
    git(ws.root, "add", "notes.txt")
    with pytest.raises(WorkspaceError, match="Python"):
        read_python_target(ws, "notes.txt")


def test_commit_is_not_done_by_proposal(ws):
    before, digest = read_python_target(ws, "cash.py")
    original_count = ws.git("rev-list", "--count", "HEAD")
    _ = parse_proposal(model_code(before + "\nnew = 1\n"), "cash.py", before, digest)
    assert ws.git("rev-list", "--count", "HEAD") == original_count


def test_removing_api_is_blocked(ws):
    before, digest = read_python_target(ws, "cash.py")
    with pytest.raises(WorkspaceError, match="top-level API"):
        parse_proposal(model_code("new = 123"), "cash.py", before, digest)


def test_changing_existing_function_arity_is_blocked(ws):
    before, digest = read_python_target(ws, "cash.py")
    with pytest.raises(WorkspaceError, match="top-level API"):
        parse_proposal(
            model_code("def change(total, paid, currency):\n    return paid - total"),
            "cash.py",
            before,
            digest,
        )
