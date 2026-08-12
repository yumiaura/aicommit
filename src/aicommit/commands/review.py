"""Pre-commit review pass: ask the LLM for likely bugs in the staged diff."""
from __future__ import annotations

import sys

from aicommit.config import Config
from aicommit.llm import LLMError, make_backend

REVIEW_PROMPT = """You are a senior engineer reviewing the staged diff for likely defects.

Output rules:
- If the diff has no concerning issues, output exactly:
    NO_ISSUES
- Otherwise, output one finding per line, no bullets, in the format:
    [severity] file:line — one-sentence description
  where severity is one of: critical, warning, nit
- Focus on real defects: off-by-one, null/None handling, resource leaks,
  unhandled exceptions, security issues (injection, path traversal),
  race conditions, broken invariants. NOT style or formatting nits.
- No preamble, no headers, no closing remarks.

Diff:
---
{diff}
---
"""


# 0 → all good, 1 → findings present but user wants to ship, 2 → abort.
def run(diff: str, *, cfg: Config, review_only: bool = False) -> int:
    if not diff.strip():
        if review_only:
            sys.stderr.write("nothing to review (empty diff)\n")
            return 1
        return 0
    try:
        backend = make_backend(
            cfg.llm_backend,
            url=cfg.llm_url,
            model=cfg.llm_model,
            temperature=0.0,
            max_tokens=max(cfg.llm_max_tokens, 1024),
        )
    except Exception as e:
        sys.stderr.write(f"error: {e}\n")
        return 2
    try:
        raw = backend.generate(REVIEW_PROMPT.format(diff=diff), temperature=0.0).strip()
    except LLMError as e:
        sys.stderr.write(f"error: {e}\n")
        return 2

    findings = parse_findings(raw)
    if not findings:
        if review_only:
            print("✓ review: no findings", file=sys.stderr)
        return 0

    print_findings(findings)
    if review_only:
        # exit code reflects whether anything was flagged
        return 1 if findings else 0

    return prompt_continue(findings)


def parse_findings(raw: str) -> list[tuple[str, str]]:
    """Return [(severity, body)] for each finding. Returns [] for NO_ISSUES."""
    if not raw or raw.upper().startswith("NO_ISSUES"):
        return []
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            sev, rest = line[1:].split("]", 1)
            out.append((sev.strip().lower(), rest.strip()))
        else:
            out.append(("warning", line))
    return out


def print_findings(findings: list[tuple[str, str]]) -> None:
    from aicommit.ui import Ansi, colored

    print(colored("─" * 56, Ansi.DIM), file=sys.stderr)
    print(colored(f"review: {len(findings)} finding(s)", Ansi.BOLD), file=sys.stderr)
    print(colored("─" * 56, Ansi.DIM), file=sys.stderr)
    sev_color = {"critical": Ansi.RED, "warning": Ansi.YELLOW, "nit": Ansi.CYAN}
    for sev, body in findings:
        tag = colored(f"[{sev}]", sev_color.get(sev, Ansi.YELLOW))
        print(f"{tag} {body}", file=sys.stderr)
    print(colored("─" * 56, Ansi.DIM), file=sys.stderr)


def prompt_continue(findings: list[tuple[str, str]]) -> int:
    has_critical = any(sev == "critical" for sev, _ in findings)
    label = "continue (commit anyway) [s] / fix first (abort) [f]"
    if has_critical:
        label = "critical findings present — " + label
    print(label, file=sys.stderr)
    try:
        choice = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return 2
    if choice in {"f", "fix", "abort"}:
        print("aborted; fix and re-run", file=sys.stderr)
        return 2
    return 0
