"""Exceptions raised by the LLM backends."""

from __future__ import annotations


class LLMError(RuntimeError):
    """Base exception for all LLM errors."""


class OllamaError(LLMError):
    """Raised when Ollama fails."""


class LlamaCppError(LLMError):
    """Raised when llama.cpp fails."""
