import re

import pytest

from aicommit.diff import estimate_tokens, truncate_diff


def test_truncate_diff_passthrough_when_small():
    diff = "diff --git a/x b/x\n@@\n-a\n+b\n"
    out, truncated = truncate_diff(diff, max_tokens=1000)
    assert out == diff
    assert truncated is False


def test_truncate_diff_drops_extra_files():
    f1 = "diff --git a/a b/a\n" + ("+x" * 2000) + "\n"
    f2 = "diff --git a/b b/b\n" + ("+y" * 2000) + "\n"
    diff = f1 + f2
    out, truncated = truncate_diff(diff, max_tokens=600)  # ~2400 chars
    assert truncated is True
    assert "diff --git a/a b/a" in out
    # second file should be either dropped entirely or replaced with truncation marker
    assert "truncated" in out


def test_truncate_diff_handles_single_huge_file():
    diff = "diff --git a/huge b/huge\n" + ("+x" * 20000) + "\n"
    out, truncated = truncate_diff(diff, max_tokens=100)
    assert truncated is True
    assert "truncated" in out
    assert len(out) < len(diff)


def test_estimate_tokens_monotonic():
    assert estimate_tokens("") == 1
    assert estimate_tokens("x" * 4) <= estimate_tokens("x" * 40)


@pytest.mark.parametrize(
    "diff",
    [
        "x" * 401,
        "p" * 401 + "\ndiff --git a/x b/x\n+x\n",
        "diff --git a/x b/x\n" + "x" * 500,
        "diff --git a/x b/x\n" + "x" * 360
        + "\ndiff --git a/y b/y\n" + "y" * 400,
    ],
    ids=["no-header", "oversized-preamble", "partial-file", "whole-file-marker"],
)
def test_truncate_diff_reserves_space_for_marker(diff):
    out, truncated = truncate_diff(diff, max_tokens=100)
    assert truncated is True
    assert "truncated" in out
    assert estimate_tokens(out) <= 100


@pytest.mark.parametrize("max_tokens", range(1, 20))
@pytest.mark.parametrize(
    "diff",
    ["x" * 100, "diff --git a/x b/x\n" + "x" * 100],
    ids=["no-header", "file-header"],
)
def test_truncate_diff_tiny_budgets(diff, max_tokens):
    out, truncated = truncate_diff(diff, max_tokens=max_tokens)
    assert truncated is True
    assert "..." in out
    assert estimate_tokens(out) <= max_tokens


def test_truncate_diff_keeps_whole_files_when_marker_fits():
    first = "diff --git a/x b/x\n+x\n"
    second = "diff --git a/y b/y\n" + "y" * 500
    out, truncated = truncate_diff("preamble\n" + first + second, max_tokens=30)
    assert truncated is True
    assert out.startswith("preamble\n" + first)
    assert "diff --git a/y b/y" not in out
    assert "1 more file(s)" in out
    assert estimate_tokens(out) <= 30


def test_truncate_diff_keeps_multiple_whole_files():
    first = "diff --git a/x b/x\n+x\n"
    second = "diff --git a/y b/y\n+y\n"
    third = "diff --git a/z b/z\n" + "z" * 500
    out, truncated = truncate_diff(first + second + third, max_tokens=30)
    assert truncated is True
    assert out.startswith(first + second)
    assert "diff --git a/z b/z" not in out
    assert f"1 more file(s), ~{len(third)} chars" in out
    assert estimate_tokens(out) <= 30


@pytest.mark.parametrize("diff", ["x" * 401, "diff --git a/x b/x\n" + "x" * 500])
def test_truncate_diff_prefix_marker_reports_actual_removed_count(diff):
    out, truncated = truncate_diff(diff, max_tokens=100)
    marker = re.search(r"\n\[\.\.\. truncated (\d+) chars \.\.\.\]\n$", out)
    assert truncated is True
    assert marker is not None
    assert int(marker.group(1)) == len(diff) - marker.start()
    assert out[:marker.start()] == diff[:marker.start()]


@pytest.mark.parametrize("diff", ["", "x" * 400, "diff --git a/x b/x\n" + "x" * 381])
def test_truncate_diff_preserves_input_at_or_below_budget(diff):
    assert truncate_diff(diff, max_tokens=100) == (diff, False)


@pytest.mark.parametrize("max_tokens", [0, -1, 1_000_001])
def test_truncate_diff_rejects_invalid_budgets(max_tokens):
    with pytest.raises(ValueError):
        truncate_diff("diff", max_tokens=max_tokens)
