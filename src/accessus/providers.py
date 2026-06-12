from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from accessus.agents import build_prompt, parse_action
from accessus.schema import AgentAction
from accessus.world import Agent, WorldState

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Recover a JSON object from a model response that may be fenced or wrapped
    in prose. Raises json.JSONDecodeError if no object can be found (e.g. a plain
    natural-language refusal), so the caller can distinguish refusal from bad JSON."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = _FENCE_RE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])  # may raise → caller handles
    raise json.JSONDecodeError("no JSON object found", text, 0)


class LLMProvider(Protocol):
    name: str

    def get_action(self, agent: Agent, world: WorldState, memory_context: str) -> AgentAction: ...


class MockProvider:
    """Deterministic, no-model provider. Plays a per-agent scripted sequence."""

    name = "mock"

    def __init__(
        self,
        script: dict[str, list[AgentAction]] | None = None,
        default: AgentAction | None = None,
    ) -> None:
        self.script = script or {}
        self.default = default or AgentAction(tool="idle")
        self._idx: dict[str, int] = {}

    def get_action(self, agent: Agent, world: WorldState, memory_context: str) -> AgentAction:
        seq = self.script.get(agent.id)
        if not seq:
            return self.default.model_copy(deep=True)
        i = min(self._idx.get(agent.id, 0), len(seq) - 1)
        self._idx[agent.id] = i + 1
        return seq[i].model_copy(deep=True)


class OllamaProvider:
    """Calls a local Ollama model. One retry on malformed JSON, then idle fallback."""

    def __init__(self, model: str, host: str = "http://localhost:11434", timeout: float = 120.0) -> None:
        self.model = model
        self.name = f"ollama:{model}"
        self._url = f"{host}/api/generate"
        self._timeout = timeout

    def _call(self, prompt: str) -> dict:
        resp = httpx.post(
            self._url,
            json={"model": self.model, "prompt": prompt, "stream": False, "format": "json",
                  "options": {"temperature": 0.7}},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return json.loads(resp.json()["response"])

    def get_action(self, agent: Agent, world: WorldState, memory_context: str) -> AgentAction:
        prompt = build_prompt(agent, world, memory_context)
        for _ in range(2):  # initial try + one retry
            try:
                return parse_action(self._call(prompt))
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                continue
        return AgentAction(tool="idle", internal_thought="<<provider error>>", malformed=True)


class OpenRouterProvider:
    """Calls an OpenRouter (OpenAI-compatible) chat model. One retry on malformed
    JSON, then idle fallback. Lets a scenario be swept across model families."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.name = f"openrouter:{model}"
        self._url = f"{base_url}/chat/completions"
        self._api_key = api_key
        self._timeout = timeout

    def _raw(self, prompt: str) -> str:
        resp = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def get_action(self, agent: Agent, world: WorldState, memory_context: str) -> AgentAction:
        prompt = build_prompt(agent, world, memory_context)
        last_content = ""
        for _ in range(2):  # initial try + one retry
            try:
                last_content = self._raw(prompt)
                return parse_action(_extract_json(last_content))
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                continue
        # A response with no JSON object at all is a prose refusal, not broken JSON.
        if last_content and "{" not in last_content:
            return AgentAction(tool="idle", internal_thought="<<model refusal>>", refused=True)
        return AgentAction(tool="idle", internal_thought="<<provider error>>", malformed=True)
