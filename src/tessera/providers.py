from __future__ import annotations

import json
from typing import Protocol

import httpx

from tessera.agents import build_prompt, parse_action
from tessera.schema import AgentAction
from tessera.world import Agent, WorldState


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
