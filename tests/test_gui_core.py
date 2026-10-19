"""Isolated behavior tests for the aicommit desktop Git service (no Qt required)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aicommit.gui_core import (
    QUICK_QUESTIONS,
    GitWorkspace,
    WorkspaceError,
    analysis_prompt,
    assert_local_ollama,
    commit_prompt,
    format_plan,
    parse_plan,
    plan_prompt,
    quick_prompt,
    safe_diff_for_model,
    sensitive_path,
)


def run(path: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True)
    return p.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    run(tmp_path, "init", "-b", "main")
    run(tmp_path, "config", "user.name", "Tester")
    run(tmp_path, "config", "user.email", "tester@example.invalid")
    (tmp_path / "base.txt").write_text("original\n", encoding="utf-8")
    run(tmp_path, "add", "base.txt")
    run(tmp_path, "commit", "-m", "test: initial file")
    return tmp_path


def test_detect_stage_unstage_and_spaces(repo: Path) -> None:
    (repo / "foo bar.py").write_text("def hello():\n    return 2\n", encoding="utf-8")
    g = GitWorkspace(repo)
    assert g.files()[0].path == "foo bar.py"
    assert g.files()[0].unstaged
    g.stage_one("foo bar.py")
    staged = g.files()[0]
    assert staged.staged and not staged.unstaged
    diff, other = g.file_diff("foo bar.py")
    assert "return 2" in diff and not other
    assert "def hello()" in g.staged_diff()
    (repo / "foo bar.py").write_text("def hello():\n    return 3\n", encoding="utf-8")
    assert g.files()[0].staged and g.files()[0].unstaged
    cached, working = g.file_diff("foo bar.py")
    assert "return 2" in cached and "return 3" in working


def test_messages_are_grounded_to_staged(repo: Path) -> None:
    g = GitWorkspace(repo)
    (repo / "report.py").write_text('print("ok")\n', encoding="utf-8")
    g.stage_one("report.py")
    diff = g.staged_diff()
    msg = commit_prompt(g, diff, "Agregué reporte de clientes")
    assert 'print("ok")' in msg
    assert "NO afirmes cambios ausentes" in msg
    explanation = analysis_prompt(g, diff, path="report.py", intent="", question="¿Qué cambió?")
    assert "HECHOS DEL DIFF" in explanation


def test_commit_is_local_and_explicit(repo: Path) -> None:
    g = GitWorkspace(repo)
    (repo / "new.py").write_text("value = 12\n", encoding="utf-8")
    g.stage_one("new.py")
    output = g.commit("feat: add value")
    assert "feat: add value" in output
    assert "feat: add value" in g.git("log", "-1", "--pretty=%s")
    assert not g.files()


def test_untracked_file_is_not_silently_analyzed(repo: Path) -> None:
    g = GitWorkspace(repo)
    (repo / "new.py").write_text("value = 99", encoding="utf-8")
    staged, working = g.file_diff("new.py")
    assert not staged and not working


def test_sensitive_paths_and_content(repo: Path) -> None:
    assert sensitive_path(".env")
    assert sensitive_path("prod/.env.production")
    assert sensitive_path("ssh/id_rsa")
    assert sensitive_path("something.pem")
    assert not sensitive_path("docs/readme.md")
    g = GitWorkspace(repo)
    (repo / ".env").write_text("SECRET=whatever\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="bloqueó"):
        g.stage_one(".env")
    run(repo, "add", ".env")
    with pytest.raises(WorkspaceError, match="confidenciales"):
        g.staged_diff()
    with pytest.raises(WorkspaceError, match="credencial"):
        safe_diff_for_model("+api_key = abcdefghijklmnopqrstuv")


def test_only_loopback_ollama() -> None:
    assert assert_local_ollama("http://localhost:11434") == "http://127.0.0.1:11434"
    for url in [
        "https://localhost:11434",
        "http://0.0.0.0:11434",
        "http://example.com:11434",
        "http://127.0.0.1:11434/fake",
        "http://127.0.0.1:11435",
    ]:
        with pytest.raises(WorkspaceError):
            assert_local_ollama(url)


def test_reject_long_diff() -> None:
    with pytest.raises(WorkspaceError, match="límite"):
        safe_diff_for_model("diff --git a/x b/x\n" + "a" * 30000)


def test_invalid_repo(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="repositorio"):
        GitWorkspace(tmp_path)


def test_rename_git_status_z(repo: Path) -> None:
    run(repo, "mv", "base.txt", "renamed file.txt")
    g = GitWorkspace(repo)
    changed = g.files()
    assert len(changed) == 1
    assert changed[0].path == "renamed file.txt"
    assert changed[0].staged


def test_remote_credentials_not_rendered(repo: Path) -> None:
    run(
        repo,
        "remote",
        "add",
        "origin",
        "https://secretuser:sensitivepassword@github.com/example/repo.git",
    )
    display = GitWorkspace(repo).remote()
    assert "secretuser" not in display and "sensitivepassword" not in display
    assert "***@github.com/example/repo.git" in display


def test_rename_sensitive_old_path_is_blocked() -> None:
    with pytest.raises(WorkspaceError, match="rutas de archivos sensibles"):
        safe_diff_for_model("diff --git a/.env b/public.txt\n--- a/.env\n+++ b/public.txt\n+text")


def test_quick_buttons_grounded(repo: Path):
    g = GitWorkspace(repo)
    (repo / "caja.py").write_text("def vuelto(total,pago):\n return pago-total\n", encoding="utf-8")
    g.stage_one("caja.py")
    diff = g.staged_diff()
    for action in QUICK_QUESTIONS:
        text = quick_prompt(g, diff, path="caja.py", intent="", action=action)
        assert "pago-total" in text
        assert "NO ejecutes" in text
    with pytest.raises(WorkspaceError):
        quick_prompt(g, diff, path="caja.py", intent="", action="ejecutar-sin-permiso")


def test_oneclick_plan_prompt(repo: Path):
    g = GitWorkspace(repo)
    (repo / "cash.py").write_text("print(123)\n", encoding="utf-8")
    g.stage_one("cash.py")
    text = plan_prompt(g, g.staged_diff(), path="cash.py", intent="", may_suggest_commit=True)
    assert "print(123)" in text
    assert "No ejecutes cambios" in text
    assert "JSON válido" in text


def test_parse_valid_and_cautious_commit():
    raw = """```json
{"hechos":["nuevo módulo"],"propuesta":"Agregar pruebas", "riesgos":["sin validación"],"pruebas":["test pagos"],"siguientes":["revisar"],"commit":"feat(cash): add change calculation"}
```"""
    p = parse_plan(raw, may_suggest_commit=True)
    assert p["commit"] == "feat(cash): add change calculation"
    assert "HECHOS INTERPRETADOS POR IA" in format_plan(p)
    assert "NO EJECUTADAS" in format_plan(p)
    assert parse_plan(raw, may_suggest_commit=False)["commit"] == ""


def test_malformed_or_injected_model_output():
    with pytest.raises(WorkspaceError):
        parse_plan("DROP TABLE users", may_suggest_commit=True)
    with pytest.raises(WorkspaceError):
        parse_plan('{"hechos":123}', may_suggest_commit=True)
    good = '{"hechos":[],"propuesta":"OK","riesgos":[],"pruebas":[],"siguientes":[],"commit":"git push origin main"}'
    assert parse_plan(good, may_suggest_commit=True)["commit"] == ""
