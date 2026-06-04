from __future__ import annotations

from typing import Protocol

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
