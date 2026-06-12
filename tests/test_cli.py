import pytest

from accessus.cli import build_provider
from accessus.config import ScenarioConfig
from accessus.providers import MockProvider, OllamaProvider, OpenRouterProvider


def _cfg(model: str = "llama3.1:8b") -> ScenarioConfig:
    return ScenarioConfig(name="t", model=model, agents=[], data_stores=[])


def test_build_provider_mock():
    assert isinstance(build_provider("mock", _cfg()), MockProvider)


def test_build_provider_ollama_uses_cfg_model():
    p = build_provider("ollama", _cfg("qwen2.5:7b"))
    assert isinstance(p, OllamaProvider)
    assert p.model == "qwen2.5:7b"


def test_build_provider_openrouter_reads_env_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    p = build_provider("openrouter", _cfg("anthropic/claude-3.5-sonnet"))
    assert isinstance(p, OpenRouterProvider)
    assert p.model == "anthropic/claude-3.5-sonnet"
    assert p._api_key == "sk-or-test"


def test_build_provider_openrouter_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        build_provider("openrouter", _cfg())


def test_build_provider_model_override_beats_cfg():
    p = build_provider("ollama", _cfg("llama3.1:8b"), model="qwen2.5:7b")
    assert p.model == "qwen2.5:7b"


def test_build_provider_uses_cfg_model_when_no_override():
    p = build_provider("ollama", _cfg("llama3.1:8b"), model=None)
    assert p.model == "llama3.1:8b"


def test_main_seed_override_flows_to_manifest(tmp_path):
    from accessus.cli import main
    from accessus.schema import Manifest

    out = tmp_path / "run"
    rc = main(["run", "--provider", "mock", "--seed", "123", "--ticks", "1", "--out", str(out)])
    assert rc == 0
    manifest = Manifest.model_validate_json((out / "manifest.json").read_text())
    assert manifest.seed == 123
