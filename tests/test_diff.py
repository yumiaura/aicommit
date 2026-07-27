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
