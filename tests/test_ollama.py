import pytest
import socket
from aicommit.llm.ollama import OllamaBackend, OllamaError


def test_generate_replay(cassette):
    cas = cassette("commit_simple")
    backend = OllamaBackend(url="http://test", model="m", temperature=0.0)
    out = backend.generate("anything")
    assert "feat(parser)" in out
    assert cas.idx == 1
    assert cas.requests[0]["stream"] is False
    assert cas.requests[0]["model"] == "m"


def test_stream_yields_chunks(cassette):
    cas = cassette("commit_simple")
    backend = OllamaBackend(url="http://test", model="m", temperature=0.0)
    chunks = list(backend.stream("anything"))
    assert len(chunks) >= 1
    assert "feat(parser)" in "".join(chunks)
    assert cas.requests[0]["stream"] is True


def test_regenerate_uses_different_temperature(cassette):
    cas = cassette("commit_regenerate")
    backend = OllamaBackend(url="http://test", model="m", temperature=0.2)
    backend.generate("p", temperature=0.2)
    backend.generate("p", temperature=0.5)
    assert cas.requests[0]["options"]["temperature"] == 0.2
    assert cas.requests[1]["options"]["temperature"] == 0.5


def test_ollama_socket_timeout(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise socket.timeout("timed out")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = OllamaBackend(url="http://test", model="m")
    with pytest.raises(OllamaError) as exc_info:
        backend.generate("prompt")
    assert "Cannot reach Ollama at http://test" in str(exc_info.value)


def test_ollama_json_decode_error(monkeypatch):
    from tests.conftest import FakeResponse
    def fake_urlopen(req, timeout=None):
        return FakeResponse(b"invalid-json")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = OllamaBackend(url="http://test", model="m")
    with pytest.raises(OllamaError) as exc_info:
        backend.generate("prompt")
    assert "Invalid JSON returned by Ollama" in str(exc_info.value)


def test_ollama_error_in_body(monkeypatch):
    from tests.conftest import FakeResponse
    def fake_urlopen(req, timeout=None):
        return FakeResponse(b'{"error": "some ollama error details"}')
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = OllamaBackend(url="http://test", model="m")
    with pytest.raises(OllamaError) as exc_info:
        backend.generate("prompt")
    assert "some ollama error details" in str(exc_info.value)


def test_ollama_error_in_stream(monkeypatch):
    from tests.conftest import FakeResponse
    def fake_urlopen(req, timeout=None):
        return FakeResponse(b'{"error": "streaming failure"}')
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = OllamaBackend(url="http://test", model="m")
    with pytest.raises(OllamaError) as exc_info:
        list(backend.stream("prompt"))
    assert "streaming failure" in str(exc_info.value)


def test_ollama_empty_prompt():
    backend = OllamaBackend(url="http://test", model="m")
    with pytest.raises(ValueError) as exc_info:
        backend.generate("")
    assert "prompt cannot be empty" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        list(backend.stream(""))
    assert "prompt cannot be empty" in str(exc_info.value)
