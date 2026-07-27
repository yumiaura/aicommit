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


def truncate_diff(diff: str, max_tokens: int) -> tuple[str, bool]:
    """Trim a diff so its estimated token count fits within `max_tokens`.

    Strategy:
    - Keep the preamble (if any).
    - Add as many whole file diffs as fit.
    - If none fit, partially include the first file.
    - Always append a truncation marker when content was removed.

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

    preamble = files[0] if files else ""
    file_chunks = files[1:] if len(files) > 1 else []

    if not file_chunks:
        trimmed = diff[:budget_chars]
        skipped = len(diff) - budget_chars
        return (
            f"{trimmed}\n[... truncated {skipped} chars ...]\n",
            True,
        )

    if len(preamble) >= budget_chars:
        skipped = len(diff) - budget_chars
        return (
            preamble[:budget_chars]
            + f"\n[... truncated {skipped} chars ...]\n",
            True,
        )

    lengths = [len(chunk) for chunk in file_chunks]

    out: list[str] = []
    used = 0

    if preamble:
        out.append(preamble)
        used = len(preamble)

    kept = 0

    for chunk, length in zip(file_chunks, lengths):
        if used + length > budget_chars:
            break

        out.append(chunk)
        used += length
        kept += 1

    if kept > 0:
        skipped_files = len(file_chunks) - kept
        skipped_chars = sum(lengths[kept:])

        out.append(
            f"\n[... truncated {skipped_files} more file(s), ~{skipped_chars} chars ...]\n"
        )
        return "".join(out), True

    first = file_chunks[0]
    keep_chars = max(0, budget_chars - used)

    out.append(first[:keep_chars])

    skipped_in_file = len(first) - keep_chars
    extra_files = len(file_chunks) - 1
    extra_chars = sum(lengths[1:])

    msg = (
        f"\n[... truncated {skipped_in_file} chars within this file"
    )

    if extra_files:
        msg += f" + {extra_files} more file(s), ~{extra_chars} chars"

    msg += " ...]\n"

    out.append(msg)

    return "".join(out), True
