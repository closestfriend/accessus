from tessera.schema import (
    ActionParams, AgentAction, PolicyDecision, Event, ObservableEvent, to_observable,
)


def _event() -> Event:
    return Event(
        tick=3, agent_id="agent-5", tool="access_resource",
        params=ActionParams(resource_id="data-3", method="read"),
        internal_thought="grab the records",
        policy_decision=PolicyDecision(
            permitted=True, reason="granted by ACL", leaked=True,
            decryption_success=True, ground_truth_violation=True,
        ),
    )


def test_agent_action_defaults_are_not_shared():
    a, b = AgentAction(tool="idle"), AgentAction(tool="idle")
    a.params.resource_id = "x"
    assert b.params.resource_id is None  # default_factory, not a shared mutable


def test_to_observable_strips_hidden_fields():
    obs = to_observable(_event())
    dumped = obs.model_dump()
    assert dumped == {
        "tick": 3, "agent_id": "agent-5", "tool": "access_resource",
        "params": {"resource_id": "data-3", "method": "read"}, "permitted": True,
    }
    assert "internal_thought" not in dumped
    assert "ground_truth_violation" not in dumped
    assert "leaked" not in dumped


def test_event_round_trips_through_json():
    ev = _event()
    assert Event.model_validate_json(ev.model_dump_json()) == ev
