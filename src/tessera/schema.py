from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tool = Literal["access_resource", "probe_system", "request_escalation", "idle"]


class ActionParams(BaseModel):
    resource_id: str | None = None
    method: str | None = None


class AgentAction(BaseModel):
    tool: Tool
    params: ActionParams = Field(default_factory=ActionParams)
    internal_thought: str = ""
    malformed: bool = False


class PolicyDecision(BaseModel):
    permitted: bool
    reason: str
    leaked: bool
    decryption_success: bool
    ground_truth_violation: bool


class Event(BaseModel):
    tick: int
    agent_id: str
    tool: Tool
    params: ActionParams
    internal_thought: str
    policy_decision: PolicyDecision
    malformed: bool = False


class ObservableEvent(BaseModel):
    """What an offline detector / blue-team sees. No thoughts, no ground truth."""

    tick: int
    agent_id: str
    tool: Tool
    params: ActionParams
    permitted: bool


def to_observable(event: Event) -> ObservableEvent:
    return ObservableEvent(
        tick=event.tick,
        agent_id=event.agent_id,
        tool=event.tool,
        params=event.params,
        permitted=event.policy_decision.permitted,
    )


class LabelRow(BaseModel):
    tick: int
    agent_id: str
    is_malicious_agent: bool
    ground_truth_violation: bool
    leaked: bool


class Manifest(BaseModel):
    scenario_name: str
    seed: int
    provider: str
    model: str
    n_ticks: int
    agent_ids: list[str]
    policy_version: str
