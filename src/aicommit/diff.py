"""Token-budget aware diff trimming.

The Ollama API will happily accept a 200kB diff and burn 30s of GPU on it
before timing out. Capping the prompt at a sensible size keeps latency
predictable and keeps small models from drifting off into noise.
"""

from __future__ import annotations

import re

CHARS_PER_TOKEN = 4

FILE_HEADER: re.Pattern[str] = re.compile(r"(?=^diff --git )", re.MULTILINE)


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _truncate_prefix(diff: str, budget_chars: int) -> str:
    """Reserve a marker before retaining a prefix, including for tiny budgets."""
    # The largest possible skipped count reserves enough room even when the
    # final count has fewer digits. Tiny budgets still retain an explicit mark.
    marker = f"\n[... truncated {len(diff)} chars ...]\n"
    if len(marker) > budget_chars:
        marker = "..."
        return diff[: budget_chars - len(marker)] + marker

    kept = budget_chars - len(marker)
    skipped = len(diff) - kept
    return diff[:kept] + f"\n[... truncated {skipped} chars ...]\n"


def truncate_diff(diff: str, max_tokens: int) -> tuple[str, bool]:
    """Trim a diff so its estimated token count fits within `max_tokens`.

    Strategy:
    - Keep the preamble when it fits.
    - Add as many whole file diffs as fit, including the truncation marker.
    - If none fit, partially include the input's prefix.
    - Always mark removed content; use `...` when the detailed marker cannot fit.

    Returns:
        (trimmed_diff, was_truncated)
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")

    if max_tokens > 1_000_000:
        raise ValueError("max_tokens is unreasonably large")

    budget_chars = max_tokens * CHARS_PER_TOKEN

    if len(diff) <= budget_chars:
        return diff, False

    files = FILE_HEADER.split(diff)
    preamble = files[0]
    file_chunks = files[1:]
    out = [preamble]
    used = len(preamble)
    kept = 0

    for chunk in file_chunks:
        next_used = used + len(chunk)
        skipped_files = len(file_chunks) - kept - 1
        skipped_chars = len(diff) - next_used
        marker = (
            f"\n[... truncated {skipped_files} more file(s), ~{skipped_chars} chars ...]\n"
        )
        if next_used + len(marker) > budget_chars:
            break
        out.append(chunk)
        used = next_used
        kept += 1

    if kept:
        skipped_files = len(file_chunks) - kept
        skipped_chars = len(diff) - used
        out.append(
            f"\n[... truncated {skipped_files} more file(s), ~{skipped_chars} chars ...]\n"
        )
        return "".join(out), True

    return _truncate_prefix(diff, budget_chars), True
