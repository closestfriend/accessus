import json

import httpx

from tessera.world import Agent, WorldState, DataStore
from tessera.schema import ActionParams, AgentAction
from tessera.providers import MockProvider, OpenRouterProvider


def _world():
    return WorldState(
        agents=[Agent(id="eve", name="Eve", role="user")],
        data_stores=[DataStore(id="d1", name="X", sensitivity="public", encryption_key_id="k")],
    )


def test_mock_returns_default_idle_when_unscripted():
    p = MockProvider()
    action = p.get_action(_world().agents[0], _world(), "")
    assert action.tool == "idle"


def test_mock_plays_script_in_order_then_repeats_last():
    script = {
        "eve": [
            AgentAction(tool="probe_system", params=ActionParams(resource_id="d1", method="scan")),
            AgentAction(tool="access_resource", params=ActionParams(resource_id="d1", method="read")),
        ]
    }
    p = MockProvider(script=script)
    eve = _world().agents[0]
    assert p.get_action(eve, _world(), "").tool == "probe_system"
    assert p.get_action(eve, _world(), "").tool == "access_resource"
    assert p.get_action(eve, _world(), "").tool == "access_resource"  # past end → repeat last


def test_mock_returns_independent_copies():
    script = {"eve": [AgentAction(tool="access_resource", params=ActionParams(resource_id="d1"))]}
    p = MockProvider(script=script)
    eve = _world().agents[0]
    first = p.get_action(eve, _world(), "")
    first.params.resource_id = "mutated"
    assert p.get_action(eve, _world(), "").params.resource_id == "d1"


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):  # noqa: D401
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_openrouter_name_includes_model():
    p = OpenRouterProvider(model="anthropic/claude-3.5-sonnet", api_key="sk-test")
    assert p.name == "openrouter:anthropic/claude-3.5-sonnet"


def test_openrouter_parses_chat_completion_content(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        body = {"tool": "access_resource", "params": {"resource_id": "d1", "method": "read"}}
        return _FakeResponse(json.dumps(body))

    monkeypatch.setattr(httpx, "post", fake_post)
    p = OpenRouterProvider(model="meta-llama/llama-3.1-8b-instruct", api_key="sk-test")
    action = p.get_action(_world().agents[0], _world(), "")

    assert action.tool == "access_resource"
    assert action.params.resource_id == "d1"
    assert captured["url"].endswith("/chat/completions")
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer sk-test"
    payload = captured["kwargs"]["json"]
    assert payload["model"] == "meta-llama/llama-3.1-8b-instruct"
    assert payload["messages"][0]["role"] == "user"


def test_openrouter_retries_then_idle_fallback_on_malformed(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        return _FakeResponse("not json at all")

    monkeypatch.setattr(httpx, "post", fake_post)
    p = OpenRouterProvider(model="x/y", api_key="sk-test")
    action = p.get_action(_world().agents[0], _world(), "")

    assert action.tool == "idle"
    assert action.malformed is True
    assert calls["n"] == 2  # initial try + one retry
