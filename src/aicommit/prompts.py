"""Prompt templates used by aicommit subcommands."""
from __future__ import annotations

from aicommit.diff import truncate_diff

VALIDATE_CORRECTION_PROMPT = """The commit message below is not a valid Conventional Commit.
Fix it so it follows this format:
  type[(scope)][!]: description

Valid types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert, security, deprecate

Invalid message:
{message}

Errors:
{errors}

Diff:
---
{diff}
---
Output ONLY the corrected commit message. No preamble, no fences."""

# Default budget for the diff portion of a commit prompt (in tokens).
# Leaves room for the system + rules + the LLM's response inside a typical
# 4k–8k context window.
DEFAULT_DIFF_TOKEN_BUDGET = 2048


COMMIT_SYSTEM = (
    "You are a senior engineer writing ONE Conventional Commit message for the staged diff below."
)

ANTI_HALLUCINATION = """- Describe ONLY what the diff literally changes. Do not invent
  motivations, follow-ups, integrations, or relationships that are
  not visible in the diff itself.
- If you cannot reasonably infer the *why* from the diff alone,
  OMIT the body — a one-line subject is better than a guessed reason.
- Do not claim that removed content "moved" or "was integrated"
  elsewhere unless the diff actually shows it being added there."""


COMMIT_RULES_CONVENTIONAL = f"""Rules:
- Subject line: imperative mood, <=72 chars, lowercase type
  (feat/fix/chore/docs/refactor/test/build/ci/perf/style/revert),
  optional (scope), no trailing period.
- Blank line, then an optional body explaining the *why*, wrapped at ~72 cols.
{ANTI_HALLUCINATION}
- Output ONLY the commit message. No markdown fences, no preamble, no commentary."""

COMMIT_RULES_PLAIN = f"""Rules:
- Subject line: imperative mood, <=72 chars, no type prefix, no trailing period.
- Blank line, then an optional body explaining the *why*, wrapped at ~72 cols.
{ANTI_HALLUCINATION}
- Output ONLY the commit message. No markdown fences, no preamble, no commentary."""


def build_commit_prompt(
    diff: str,
    *,
    style: str = "conventional",
    include_body: bool = True,
    diff_token_budget: int = DEFAULT_DIFF_TOKEN_BUDGET,
) -> str:
    rules = COMMIT_RULES_CONVENTIONAL if style == "conventional" else COMMIT_RULES_PLAIN
    if not include_body:
        rules = rules.replace(
            "- Blank line, then an optional body explaining the *why*, wrapped at ~72 cols.\n",
            "- Subject line only — DO NOT write a body.\n",
        )
    trimmed, _ = truncate_diff(diff, diff_token_budget)
    return f"{COMMIT_SYSTEM}\n\n{rules}\n\nDiff:\n---\n{trimmed}\n---\n"
