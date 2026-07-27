"""Ollama HTTP backend — stdlib only."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Iterator

from aicommit.llm.exceptions import OllamaError


class OllamaBackend:
    def __init__(
        self,
        *,
        url: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 512,
        timeout: float = 120.0,
    ) -> None:
        if not url:
            raise ValueError("url cannot be empty")

        if not model:
            raise ValueError("model cannot be empty")

        if timeout <= 0:
            raise ValueError("timeout must be positive")

        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        self.url = url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def build_payload(
        self,
        prompt: str,
        *,
        temperature: float | None,
        stream: bool,
    ) -> dict[str, object]:
        if not prompt:
            raise ValueError("prompt cannot be empty")

        return {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": (
                    self.temperature if temperature is None else temperature
                ),
                "num_predict": self.max_tokens,
            },
        }

    def build_request(self, payload: dict[str, object]) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

    def generate(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
    ) -> str:
        req = self.build_request(
            self.build_payload(prompt, temperature=temperature, stream=False)
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.load(resp)

        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise OllamaError(f"Ollama HTTP {e.code}: {detail}") from e

        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise OllamaError(f"Cannot reach Ollama at {self.url}: {e}") from e

        except json.JSONDecodeError as e:
            raise OllamaError("Invalid JSON returned by Ollama") from e

        if "error" in body:
            raise OllamaError(body["error"])

        return str(body.get("response", "")).strip()

    def stream(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
    ) -> Iterator[str]:
        req = self.build_request(
            self.build_payload(prompt, temperature=temperature, stream=True)
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw in resp:
                    if not raw.strip():
                        continue

                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if "error" in chunk:
                        raise OllamaError(chunk["error"])

                    text = chunk.get("response")
                    if text:
                        yield str(text)

                    if chunk.get("done", False):
                        break

        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise OllamaError(f"Ollama HTTP {e.code}: {detail}") from e

        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise OllamaError(f"Cannot reach Ollama at {self.url}: {e}") from e
