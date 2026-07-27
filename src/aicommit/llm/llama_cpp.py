"""llama-cpp-python backend."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

from aicommit.llm.exceptions import LlamaCppError


class LlamaCppBackend:
    """Backend using llama-cpp-python."""

    def __init__(
        self,
        *,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
        n_ctx: int | None = None,
        n_threads: int | None = None,
    ) -> None:
        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise RuntimeError(
                "llama-cpp-python is not installed. "
                "Install it with: pip install 'aicommit[llama-cpp]'"
            ) from e

        if not model:
            raise ValueError("model path cannot be empty")

        if not os.path.isfile(model):
            raise FileNotFoundError(
                f"Model file not found: {model!r}"
            )

        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        if temperature < 0:
            raise ValueError("temperature must be non-negative")

        if n_ctx is not None and n_ctx <= 0:
            raise ValueError("n_ctx must be positive")

        if n_threads is not None and n_threads <= 0:
            raise ValueError("n_threads must be positive")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        kwargs: dict[str, object] = {
            "model_path": model,
            "verbose": False,
        }

        if n_ctx is not None:
            kwargs["n_ctx"] = n_ctx

        if n_threads is not None:
            kwargs["n_threads"] = n_threads

        try:
            self.llm: Any = Llama(**kwargs)
        except Exception as e:
            raise LlamaCppError(f"Failed to load model: {e}") from e

    def generate(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
    ) -> str:
        if not prompt:
            raise ValueError("prompt cannot be empty")

        try:
            result = self.llm(
                prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature if temperature is None else temperature,
                stream=False,
            )
        except Exception as e:
            raise LlamaCppError(str(e)) from e

        choices = result.get("choices")
        if not choices:
            return ""

        return str(choices[0].get("text", "")).strip()

    def stream(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
    ) -> Iterator[str]:
        if not prompt:
            raise ValueError("prompt cannot be empty")

        try:
            for chunk in self.llm(
                prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature if temperature is None else temperature,
                stream=True,
            ):
                choices = chunk.get("choices")
                if not choices:
                    continue

                text = choices[0].get("text")
                if text:
                    yield str(text)

        except Exception as e:
            raise LlamaCppError(str(e)) from e
