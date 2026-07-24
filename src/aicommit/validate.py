"""Conventional Commit message validation + auto-correction prompt builder."""
from __future__ import annotations

import re

from aicommit.diff import truncate_diff

VALID_TYPES: set[str] = {
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert", "security",
    "deprecate",
}

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:\s+(?P<description>.+)$"
)

SUBJECT_MAX_LENGTH = 72
BODY_MAX_LENGTH = 72


class ValidationResult:
    is_valid: bool
    errors: list[str]

    def __init__(self, is_valid: bool = True, errors: list[str] | None = None) -> None:
        self.is_valid = is_valid
        self.errors = errors or []

    def __bool__(self) -> bool:
        return self.is_valid

    def __repr__(self) -> str:
        status = "valid" if self.is_valid else "invalid"
        if self.errors:
            return f"<ValidationResult {status}: {self.errors!r}>"
        return f"<ValidationResult {status}>"


def validate_message(message: str, style: str = "conventional") -> ValidationResult:
    if style == "conventional":
        return validate_conventional(message)
    return validate_plain(message)


def validate_plain(message: str) -> ValidationResult:
    errors: list[str] = []
    if not message.strip():
        errors.append("commit message is empty")
        return ValidationResult(False, errors)
    return ValidationResult()


def validate_conventional(message: str) -> ValidationResult:
    errors: list[str] = []

    text = message.strip()
    if not text:
        errors.append("commit message is empty")
        return ValidationResult(False, errors)

    parts = text.split("\n", 1)
    subject = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""

    if len(subject) > SUBJECT_MAX_LENGTH:
        errors.append(
            f"subject line is {len(subject)} chars, max is {SUBJECT_MAX_LENGTH}"
        )

    m = CONVENTIONAL_RE.match(subject)
    if not m:
        errors.append(
            "subject must match format: type[(scope)][!]: description "
            "(e.g. feat(auth): add login page)"
        )
    else:
        cc_type = m.group("type").lower()
        if cc_type not in VALID_TYPES:
            errors.append(
                f"unknown type {cc_type!r}; valid: {', '.join(sorted(VALID_TYPES))}"
            )
        desc = m.group("description")
        if desc.endswith("."):
            errors.append("subject should not end with a period")

    if body:
        for i, line in enumerate(body.split("\n"), start=2):
            if len(line) > BODY_MAX_LENGTH + 10:
                errors.append(
                    f"line {i} of body is {len(line)} chars, "
                    f"consider wrapping at ~{BODY_MAX_LENGTH} chars"
                )
                break

    return ValidationResult(not errors, errors)


def build_correction_prompt(
    diff: str,
    invalid_message: str,
    errors: list[str],
    style: str = "conventional",
) -> str:
    trimmed, _ = truncate_diff(diff, 2048)
    error_bullets = "\n".join(f"- {e}" for e in errors)

    if style == "conventional":
        return (
            "The commit message below is not a valid Conventional Commit.\n"
            "Fix it so it follows this format:\n"
            "  type[(scope)][!]: description\n\n"
            "Valid types: feat, fix, docs, style, refactor, perf, test, "
            "build, ci, chore, revert, security, deprecate\n\n"
            "Invalid message:\n"
            f"{invalid_message}\n\n"
            "Errors:\n"
            f"{error_bullets}\n\n"
            "Diff:\n---\n"
            f"{trimmed}\n---\n"
            "Output ONLY the corrected commit message. No preamble, no fences."
        )

    return (
        "The commit message below does not look right.\n\n"
        "Invalid message:\n"
        f"{invalid_message}\n\n"
        "Errors:\n"
        f"{error_bullets}\n\n"
        "Diff:\n---\n"
        f"{trimmed}\n---\n"
        "Output ONLY a corrected commit message. No preamble, no fences."
    )
