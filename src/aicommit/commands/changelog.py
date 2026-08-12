"""`aicommit changelog <range>` — turn git log into a CHANGELOG entry."""
from __future__ import annotations

import re
import sys

from aicommit import git
from aicommit.config import Config
from aicommit.llm import LLMError, make_backend

# Keep a Changelog buckets, in the order they should appear.
BUCKETS = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]

# Conventional Commit type → bucket. None means "skip from changelog by default".
CONVENTIONAL_MAP: dict[str, str | None] = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "revert": "Removed",
    "security": "Security",
    "deprecate": "Deprecated",
    "docs": None,
    "style": None,
    "test": None,
    "chore": None,
    "build": None,
    "ci": None,
}

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\([^)]+\))?(?P<bang>!)?:\s+(?P<rest>.+)$"
)

CHANGELOG_PROMPT = """You are writing a CHANGELOG entry in the Keep a Changelog style.

Group the commits below into these buckets (omit empty ones):
  ### Added
  ### Changed
  ### Deprecated
  ### Removed
  ### Fixed
  ### Security

Rules:
- One bullet per commit, past tense, starting with a verb.
- Strip Conventional Commit prefixes from the bullet text.
- feat → Added; fix → Fixed; perf/refactor → Changed; revert → Removed.
- Skip pure chore/docs/test/ci/style unless they are user-facing.
- Output ONLY markdown. No preamble, no closing remarks.
- Do NOT include the `## Unreleased` header — the caller adds it.

Commits:
{commits}
"""


def classify_conventional(subject: str) -> tuple[str | None, str]:
    """Return (bucket, cleaned_subject). bucket=None means skip, '?' means unknown."""
    m = CONVENTIONAL_RE.match(subject.strip())
    if not m:
        return "?", subject.strip()
    t = m.group("type")
    rest = m.group("rest").strip()
    breaking = bool(m.group("bang"))
    if t not in CONVENTIONAL_MAP:
        return "?", subject.strip()
    bucket = CONVENTIONAL_MAP[t]
    if breaking and bucket != "Removed":
        bucket = "Changed"
    return bucket, rest


def format_commits(commits: list[tuple[str, str, str]]) -> str:
    blocks = []
    for h, subject, body in commits:
        chunk = f"- {h} {subject}"
        if body.strip():
            indented = "\n  ".join(body.strip().splitlines())
            chunk += f"\n  {indented}"
        blocks.append(chunk)
    return "\n".join(blocks)


def render_deterministic(groups: dict[str, list[str]]) -> str:
    parts: list[str] = []
    for bucket in BUCKETS:
        bullets = groups.get(bucket) or []
        if not bullets:
            continue
        parts.append(f"### {bucket}")
        for b in bullets:
            parts.append(f"- {b}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def run(rev_range: str, *, cfg: Config, out_path: str | None = None) -> int:
    try:
        commits = git.log_range(rev_range)
    except git.GitError as e:
        sys.stderr.write(f"error: {e}\n")
        return 1
    if not commits:
        sys.stderr.write(f"no commits in range {rev_range}\n")
        return 1

    body = build_body(commits, cfg)
    if body is None:
        return 2

    section = f"## Unreleased\n\n{body.rstrip()}\n"
    if out_path:
        prepend_to_changelog(out_path, section)
        print(f"wrote Unreleased section to {out_path}", file=sys.stderr)
    else:
        print(section)
    return 0


def build_body(
    commits: list[tuple[str, str, str]],
    cfg: Config,
) -> str | None:
    """Return rendered markdown body, or None on backend failure."""
    groups: dict[str, list[str]] = {b: [] for b in BUCKETS}
    unknowns: list[tuple[str, str, str]] = []

    if cfg.changelog_skip_conventional:
        for h, subject, bodytxt in commits:
            bucket, cleaned = classify_conventional(subject)
            if bucket == "?":
                unknowns.append((h, subject, bodytxt))
            elif bucket is None:
                continue  # explicit skip
            else:
                groups[bucket].append(cleaned)
    else:
        unknowns = list(commits)

    if not unknowns:
        return render_deterministic(groups)

    # Some commits resisted classification: ask the LLM to handle just those.
    try:
        backend = make_backend(
            cfg.llm_backend,
            url=cfg.llm_url,
            model=cfg.llm_model,
            temperature=cfg.llm_temperature,
            max_tokens=max(cfg.llm_max_tokens, 1024),
        )
    except Exception as e:
        sys.stderr.write(f"error: {e}\n")
        return None

    prompt = CHANGELOG_PROMPT.format(commits=format_commits(unknowns))
    try:
        llm_body = backend.generate(prompt, temperature=0.1).strip()
    except LLMError as e:
        sys.stderr.write(f"error: {e}\n")
        return None
    if not llm_body:
        sys.stderr.write("error: empty response from LLM\n")
        return None

    deterministic = render_deterministic(groups).rstrip()
    if not deterministic.strip():
        return llm_body
    return f"{deterministic}\n\n{llm_body}"


def prepend_to_changelog(path: str, section: str) -> None:
    try:
        with open(path) as f:
            existing = f.read()
    except FileNotFoundError:
        existing = "# Changelog\n\n"
    with open(path, "w") as f:
        f.write(merge_unreleased(existing, section))


def merge_unreleased(existing: str, section: str) -> str:
    lines = existing.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## unreleased"):
            start = i
            break
    if start is not None:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        return (
            "".join(lines[:start])
            + section
            + ("\n" if not section.endswith("\n\n") else "")
            + "".join(lines[end:])
        )

    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = i + 1
            if insert_at < len(lines) and lines[insert_at].strip() == "":
                insert_at += 1
            break
    return "".join(lines[:insert_at]) + section + "\n" + "".join(lines[insert_at:])
