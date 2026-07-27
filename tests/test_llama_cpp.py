import pytest
import sys
from unittest.mock import MagicMock


@pytest.fixture
def mock_llama_cpp(monkeypatch):
    """Mock the llama_cpp module so we can test the backend without it installed."""
    mock_module = MagicMock()
    monkeypatch.setitem(sys.modules, "llama_cpp", mock_module)
    return mock_module


def test_llama_cpp_empty_prompt(mock_llama_cpp, tmp_path):
    from aicommit.llm.llama_cpp import LlamaCppBackend

    # Create a dummy model file
    model_file = tmp_path / "dummy.gguf"
    model_file.write_text("dummy")

    backend = LlamaCppBackend(model=str(model_file))
    with pytest.raises(ValueError) as exc_info:
        backend.generate("")
    assert "prompt cannot be empty" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        list(backend.stream(""))
    assert "prompt cannot be empty" in str(exc_info.value)


def test_llama_cpp_threads_passed(mock_llama_cpp, tmp_path):
    from aicommit.llm.llama_cpp import LlamaCppBackend

    model_file = tmp_path / "dummy.gguf"
    model_file.write_text("dummy")

    # When n_threads is passed, it should be in kwargs
    LlamaCppBackend(model=str(model_file), n_threads=4)
    called_kwargs = mock_llama_cpp.Llama.call_args[1]
    assert called_kwargs["n_threads"] == 4


def test_llama_cpp_threads_default(mock_llama_cpp, tmp_path):
    from aicommit.llm.llama_cpp import LlamaCppBackend

    model_file = tmp_path / "dummy.gguf"
    model_file.write_text("dummy")

    # When n_threads is None, it should NOT be in kwargs to let llama-cpp choose
    LlamaCppBackend(model=str(model_file))
    called_kwargs = mock_llama_cpp.Llama.call_args[1]
    assert "n_threads" not in called_kwargs


def test_llama_cpp_import_error(monkeypatch):
    """Test that missing llama-cpp-python raises the proper RuntimeError."""
    if "llama_cpp" in sys.modules:
        monkeypatch.delitem(sys.modules, "llama_cpp")

    # Force ImportError on import llama_cpp
    import builtins
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "llama_cpp":
            raise ImportError("no module named llama_cpp")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from aicommit.llm.llama_cpp import LlamaCppBackend
    with pytest.raises(RuntimeError) as exc_info:
        LlamaCppBackend(model="dummy")
    assert "llama-cpp-python is not installed" in str(exc_info.value)


def test_make_backend_name_normalization(monkeypatch, tmp_path):
    from aicommit.llm import make_backend
    # Using 'ollama' normalization
    backend = make_backend("  OLLAMA  ", url="http://test", model="m", temperature=0.1)
    from aicommit.llm.ollama import OllamaBackend
    assert isinstance(backend, OllamaBackend)

    # Using 'llama-cpp' normalization
    # Create a dummy gguf file to avoid FileNotFoundError
    model_file = tmp_path / "dummy.gguf"
    model_file.write_text("dummy")

    # Mock the llama_cpp module
    mock_module = MagicMock()
    monkeypatch.setitem(sys.modules, "llama_cpp", mock_module)

    for name in ["llama-cpp", "LLAMACPP", "  llama_cpp  "]:
        backend = make_backend(name, url="http://test", model=str(model_file), temperature=0.1)
        from aicommit.llm.llama_cpp import LlamaCppBackend
        assert isinstance(backend, LlamaCppBackend)


def test_make_backend_llama_cpp_import_error(monkeypatch):
    from aicommit.llm import make_backend, LLMError

    # Force ImportError when importing aicommit.llm.llama_cpp
    import builtins
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "aicommit.llm.llama_cpp":
            raise ImportError("simulated module import error")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(LLMError) as exc_info:
        make_backend("llama-cpp", url="http://test", model="dummy", temperature=0.1)
    assert "Failed to initialise llama-cpp backend" in str(exc_info.value)
