from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["admin", "user", "auditor", "guest"]
Sensitivity = Literal["public", "internal", "confidential", "restricted"]

SENSITIVITY_ORDER: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}


class Agent(BaseModel):
    id: str
    name: str
    role: Role
    permissions: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    risk_propensity: float = 0.0
    is_malicious: bool = False  # ground-truth label; never shown to the agent or detector


class DataStore(BaseModel):
    id: str
    name: str
    sensitivity: Sensitivity
    encryption_key_id: str
    is_leaked: bool = False


class WorldState(BaseModel):
    agents: list[Agent]
    data_stores: list[DataStore]

    def get_agent(self, agent_id: str) -> Agent | None:
        return next((a for a in self.agents if a.id == agent_id), None)

    def get_store(self, store_id: str) -> DataStore | None:
        return next((s for s in self.data_stores if s.id == store_id), None)
