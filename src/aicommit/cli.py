"""aicommit CLI entry point."""
from __future__ import annotations

import argparse
import sys
from typing import Any

from aicommit import __version__, git, ui
from aicommit import config as cfgmod
from aicommit import diff as diffmod
from aicommit import validate as validatemod
from aicommit.commands import changelog as changelog_cmd
from aicommit.commands import config as config_cmd
from aicommit.commands import review as review_cmd
from aicommit.git import GitError
from aicommit.llm import LLMError, OllamaError, make_backend
from aicommit.prompts import build_commit_prompt


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aicommit",
        description="AI commit messages from your local LLM (Ollama or llama-cpp).",
    )
    p.add_argument("--version", action="version", version=f"aicommit {__version__}")

    # Global LLM overrides — apply to every subcommand.
    p.add_argument("--backend", choices=["ollama", "llama-cpp"])
    p.add_argument("--model")
    p.add_argument("--url", help="Ollama base URL (e.g. http://10.0.0.5:11434)")
    p.add_argument("--temperature", type=float)
    p.add_argument("--max-tokens", type=int, dest="max_tokens")
    p.add_argument("--style", choices=["conventional", "plain"])
    p.add_argument("--no-body", action="store_true")
    p.add_argument("--print", action="store_true", dest="print_only")
    p.add_argument(
        "--validate",
        action="store_true",
        help="validate generated message against Conventional Commits and auto-correct",
    )
    p.add_argument(
        "--suggestions",
        action="store_true",
        help="show multiple commit message suggestions to choose from",
    )
    p.add_argument(
        "--num-suggestions",
        type=int,
        dest="suggestions_count",
        help="number of suggestions to generate (default 3)",
    )
    p.add_argument("-y", "--yes", action="store_true")
    p.add_argument(
        "--review",
        action="store_true",
        help="run a pre-commit review pass before generating the message",
    )
    p.add_argument(
        "--review-only",
        action="store_true",
        dest="review_only",
        help="run the review pass and exit (useful in CI; exits 1 if findings)",
    )
    p.add_argument("--debug", action="store_true")
    p.add_argument(
        "--no-stream",
        action="store_true",
        dest="no_stream",
        help="disable token-by-token streaming in --print mode",
    )

    sub = p.add_subparsers(dest="cmd", metavar="[changelog|config]")
    chg = sub.add_parser("changelog", help="generate a CHANGELOG.md entry from a git range")
    chg.add_argument("range", help="git revision range, e.g. v0.3.0..HEAD")
    chg.add_argument("--out", help="prepend to this file under ## Unreleased")
    sub.add_parser(
        "config",
        help="create + open the user config in $EDITOR (falls back to nano)",
    )
    return p


def cli_overrides(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    llm: dict[str, Any] = {}
    if args.backend:
        llm["backend"] = args.backend
    if args.model:
        llm["model"] = args.model
    if args.url:
        llm["url"] = args.url
    if args.temperature is not None:
        llm["temperature"] = args.temperature
    if args.max_tokens is not None:
        llm["max_tokens"] = args.max_tokens
    if llm:
        overrides["llm"] = llm

    commit: dict[str, Any] = {}
    if args.style:
        commit["style"] = args.style
    if args.no_body:
        commit["include_body"] = False
    if args.validate:
        commit["validate"] = True
    if args.suggestions:
        commit["suggestions"] = True
    if args.suggestions_count is not None:
        commit["suggestions_count"] = args.suggestions_count
    if commit:
        overrides["commit"] = commit
    return overrides


def read_diff() -> tuple[str, bool]:
    if not sys.stdin.isatty():
        return sys.stdin.read(), True
    try:
        return git.staged_diff(), False
    except GitError as e:
        sys.stderr.write(f"error: {e}\n")
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = cfgmod.load(cli_overrides(args))
    if args.debug:
        sys.stderr.write(f"[debug] config sources: {' < '.join(cfg.sources)}\n")
        sys.stderr.write(
            f"[debug] backend={cfg.llm_backend} url={cfg.llm_url} model={cfg.llm_model}\n"
        )

    if args.cmd == "changelog":
        return changelog_cmd.run(args.range, cfg=cfg, out_path=args.out)
    if args.cmd == "config":
        return config_cmd.run()

    return commit_flow(args, cfg)


def commit_flow(args: argparse.Namespace, cfg: cfgmod.Config) -> int:
    diff, from_stdin = read_diff()
    if not diff.strip():
        sys.stderr.write("no staged changes (and nothing on stdin)\n")
        return 1

    if args.review_only:
        return review_cmd.run(diff, cfg=cfg, review_only=True)

    if args.review or cfg.review_enabled:
        rc = review_cmd.run(diff, cfg=cfg, review_only=False)
        if rc != 0:
            return rc

    try:
        backend = make_backend(
            cfg.llm_backend,
            url=cfg.llm_url,
            model=cfg.llm_model,
            temperature=cfg.llm_temperature,
            max_tokens=cfg.llm_max_tokens,
        )
    except LLMError as e:
        sys.stderr.write(f"error: {e}\n")
        return 2

    _, truncated = diffmod.truncate_diff(diff, max_tokens=2048)
    if truncated and args.debug:
        sys.stderr.write("[debug] diff truncated to fit prompt budget\n")
    prompt = build_commit_prompt(
        diff,
        style=cfg.commit_style,
        include_body=cfg.commit_include_body,
    )

    def ask(temperature: float | None = None, *, correction_prompt: str | None = None) -> str:
        p = correction_prompt if correction_prompt is not None else prompt
        try:
            return backend.generate(p, temperature=temperature)
        except OllamaError as e:
            raise SystemExit(emit_ollama_error(e)) from e

    def ask_stream() -> str:
        chunks: list[str] = []
        try:
            for piece in backend.stream(prompt):
                chunks.append(piece)
                sys.stdout.write(piece)
                sys.stdout.flush()
        except OllamaError as e:
            raise SystemExit(emit_ollama_error(e)) from e
        sys.stdout.write("\n")
        return "".join(chunks).strip()

    def validate_and_correct(msg: str, *, attempt_offset: int = 0) -> str:
        if not cfg.commit_validate:
            return msg
        for attempt in range(cfg.commit_validate_max_retries + 1):
            result = validatemod.validate_message(msg, cfg.commit_style)
            if result.is_valid:
                if attempt > 0 and args.debug:
                    sys.stderr.write("[debug] message validated after correction\n")
                break
            if attempt < cfg.commit_validate_max_retries:
                if args.debug:
                    sys.stderr.write(
                        f"[debug] message invalid, attempting correction "
                        f"({attempt + 1}/{cfg.commit_validate_max_retries})\n"
                    )
                corr_prompt = validatemod.build_correction_prompt(
                    diff, msg, result.errors, style=cfg.commit_style
                )
                temp = min(
                    1.0,
                    cfg.llm_temperature + 0.15 * (attempt + 1 + attempt_offset),
                )
                msg = ask(temperature=temp, correction_prompt=corr_prompt)
                if not msg:
                    sys.stderr.write("error: empty response from LLM\n")
                    return ""
        else:
            for err in result.errors:
                sys.stderr.write(f"warning: {err}\n")
            sys.stderr.write(
                "warning: using message as-is despite validation errors\n"
            )
        return msg

    use_suggestions = cfg.commit_suggestions and not from_stdin and not args.print_only
    suggestions_count = cfg.commit_suggestions_count

    def generate_one(temp: float) -> str:
        msg = ask(temperature=temp)
        if not msg:
            return ""
        if cfg.commit_validate:
            msg = validate_and_correct(msg)
        return msg

    def generate_suggestions(count: int, *, temp_offset: float = 0.0) -> list[str]:
        messages: list[str] = []
        for i in range(count):
            temp = min(1.0, cfg.llm_temperature + 0.2 * i + temp_offset)
            if args.debug:
                sys.stderr.write(
                    f"[debug] generating suggestion {i + 1}/{count} "
                    f"(temperature={temp:.2f})\n"
                )
            msg = ask(temperature=temp)
            if not msg:
                sys.stderr.write("error: empty response from LLM\n")
                return []
            if cfg.commit_validate:
                msg = validate_and_correct(msg, attempt_offset=i)
                if not msg:
                    return []
            messages.append(msg)
        return messages

    # In print/pipe mode, stream by default — gives interactive feel even
    # though we're just dumping to stdout. Interactive mode buffers so the
    # boxed proposal renders cleanly.
    if from_stdin or args.print_only:
        if args.no_stream or not hasattr(backend, "stream"):
            message = ask()
            if not message:
                sys.stderr.write("error: empty response from LLM\n")
                return 2
            message = validate_and_correct(message)
            if not message:
                return 2
            print(message)
        else:
            message = ask_stream()
            if not message:
                sys.stderr.write("error: empty response from LLM\n")
                return 2
        return 0

    if use_suggestions:
        proposals = generate_suggestions(suggestions_count)
        if not proposals:
            return 2
    else:
        message = ask()
        if not message:
            sys.stderr.write("error: empty response from LLM\n")
            return 2
        message = validate_and_correct(message)
        if not message:
            return 2

    if args.yes:
        msg_to_commit = proposals[0] if use_suggestions else message
        try:
            git.commit_with_message(msg_to_commit)
        except Exception as e:
            sys.stderr.write(f"error: git commit failed: {e}\n")
            return 1
        return 0

    try:
        ui.print_diff_stat(git.staged_stat())
    except GitError:
        pass

    if use_suggestions:
        sug_state: dict[str, float] = {"temp_offset": 0.0}

        def regenerate_suggestions() -> list[str]:
            sug_state["temp_offset"] = min(1.0, sug_state["temp_offset"] + 0.15)
            return generate_suggestions(suggestions_count, temp_offset=sug_state["temp_offset"])

        return ui.run_suggestion_interactive(proposals, regenerate=regenerate_suggestions)

    regen_state: dict[str, float] = {"temperature": cfg.llm_temperature}

    def regenerate() -> str:
        regen_state["temperature"] = min(1.0, regen_state["temperature"] + 0.15)
        msg = ask(temperature=regen_state["temperature"])
        if not msg:
            return ""
        if cfg.commit_validate:
            msg = validate_and_correct(msg, attempt_offset=3)
        return msg

    return ui.run_interactive(message, regenerate=regenerate)


def emit_ollama_error(e: OllamaError) -> int:
    sys.stderr.write(f"error: {e}\n")
    if "cannot reach" in str(e):
        sys.stderr.write("hint: is `ollama serve` running and reachable?\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
