"""LLM backend factory."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from aicommit.llm.exceptions import LlamaCppError, LLMError, OllamaError
from aicommit.llm.ollama import OllamaBackend


class Backend(Protocol):
    def generate(self, prompt: str, *, temperature: float | None = None) -> str: ...
    def stream(self, prompt: str, *, temperature: float | None = None) -> Iterator[str]: ...


def make_backend(
    backend: str,
    *,
    url: str,
    model: str,
    temperature: float,
    max_tokens: int = 512,
) -> Backend:
    backend = backend.strip().lower()

    if backend == "ollama":
        return OllamaBackend(
            url=url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if backend in {"llama-cpp", "llamacpp", "llama_cpp"}:
        try:
            from aicommit.llm.llama_cpp import LlamaCppBackend

            return LlamaCppBackend(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except (RuntimeError, FileNotFoundError, ImportError) as e:
            raise LLMError(
                f"Failed to initialise llama-cpp backend: {e}"
            ) from e

    raise LLMError(
        f"Unknown backend {backend!r}. "
        "Supported backends are: 'ollama', 'llama-cpp'."
    )


__all__ = [
    "Backend",
    "LLMError",
    "LlamaCppError",
    "OllamaBackend",
    "OllamaError",
    "make_backend",
]
